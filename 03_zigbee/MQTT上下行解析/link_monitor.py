#!/usr/bin/env python3
"""Real-time Zigbee link quality monitor (read-only).

订阅上行 MQTT 数据，计算每台设备的链路质量指标：
- 丢包率（基于 ZCL sequence 序号跳变）
- RSSI 信号强度（当前/最小/平均）
- 吞吐量（消息/秒）与 RF 带宽（字节/秒）
- 上报间隔与抖动（jitter）
- 在线/离线可用性

实时打印控制台面板，并可选把指标快照追加到 CSV 供离线分析。
不修改、不干扰现有的上行/下行脚本。
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import threading
import time
import unicodedata
from collections import deque
from datetime import datetime

import paho.mqtt.client as mqtt

# ── 配置 ──────────────────────────────────────────────
DEFAULT_BROKER = "192.168.200.169"
DEFAULT_PORT = 1883
UPLINK_TOPIC = "bridge/uplink/zigbee/+/data"
STATUS_TOPIC_TEMPLATE = "bridge/uplink/zigbee/{device_id}/status"
STATUS_SUMMARY_TOPIC  = "bridge/uplink/zigbee/all/status_summary"  # 汇总所有设备

RATE_WINDOW_S = 60.0       # 吞吐/带宽滑动窗口
OFFLINE_AFTER_S = 30.0     # 超过这个时间没消息 → 判离线
SEQ_RESTART_GAP = 100      # 序号跳变大于此值视为设备重启（非丢包）
# ─────────────────────────────────────────────────────

_lock = threading.Lock()
_devices: dict[str, "DeviceStats"] = {}


def now() -> float:
    return time.time()


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class DeviceStats:
    """单台设备的链路质量统计。"""

    def __init__(self, device_id: str) -> None:
        self.device_id = device_id
        self.total_received = 0
        self.total_lost = 0
        self.restarts = 0
        self.last_seq: int | None = None
        self.last_seen = now()
        self.first_seen = now()

        self.rssi_last: int | None = None
        self.rssi_values: deque[int] = deque(maxlen=200)

        # 滑动窗口：(时间戳, 帧字节数)
        self.window: deque[tuple[float, int]] = deque()
        # 相邻上报间隔（秒），用于抖动
        self.intervals: deque[float] = deque(maxlen=100)
        self._last_arrival: float | None = None

    def update(self, seq: int | None, rssi: int | None, frame_len: int) -> None:
        t = now()
        self.total_received += 1
        self.last_seen = t

        # 丢包检测（基于序号跳变）
        if seq is not None:
            if self.last_seq is not None:
                gap = (seq - self.last_seq) & 0xFF  # 处理 0-255 回绕
                if gap == 0:
                    pass  # 重复帧
                elif gap > SEQ_RESTART_GAP:
                    self.restarts += 1  # 视为设备重启，不计丢包
                else:
                    self.total_lost += gap - 1  # 中间丢了 gap-1 帧
            self.last_seq = seq

        # RSSI
        if rssi is not None:
            self.rssi_last = rssi
            self.rssi_values.append(rssi)

        # 吞吐/带宽滑动窗口
        self.window.append((t, frame_len))
        cutoff = t - RATE_WINDOW_S
        while self.window and self.window[0][0] < cutoff:
            self.window.popleft()

        # 上报间隔与抖动
        if self._last_arrival is not None:
            self.intervals.append(t - self._last_arrival)
        self._last_arrival = t

    def snapshot(self) -> dict:
        t = now()
        expected = self.total_received + self.total_lost
        loss_rate = (self.total_lost / expected * 100.0) if expected else 0.0

        win_count = len(self.window)
        win_bytes = sum(b for _, b in self.window)
        span = RATE_WINDOW_S
        msg_rate = win_count / span
        byte_rate = win_bytes / span

        rssi_avg = statistics.mean(self.rssi_values) if self.rssi_values else None
        rssi_min = min(self.rssi_values) if self.rssi_values else None

        avg_interval = statistics.mean(self.intervals) if self.intervals else None
        jitter = statistics.pstdev(self.intervals) if len(self.intervals) > 1 else 0.0

        age = t - self.last_seen
        online = age < OFFLINE_AFTER_S

        return {
            "device_id": self.device_id,
            "online": online,
            "age_s": round(age, 1),
            "received": self.total_received,
            "lost": self.total_lost,
            "loss_rate_pct": round(loss_rate, 2),
            "restarts": self.restarts,
            "rssi_last": self.rssi_last,
            "rssi_avg": round(rssi_avg, 1) if rssi_avg is not None else None,
            "rssi_min": rssi_min,
            "msg_rate_per_s": round(msg_rate, 3),
            "byte_rate_per_s": round(byte_rate, 1),
            "avg_interval_s": round(avg_interval, 2) if avg_interval else None,
            "jitter_s": round(jitter, 3),
        }


def on_connect(client, _userdata, _flags, rc):
    if rc == 0:
        client.subscribe(UPLINK_TOPIC, qos=1)
        print(f"[{now_iso()}] connected, subscribed to {UPLINK_TOPIC}")
    else:
        print(f"[{now_iso()}] connect failed, rc={rc}")


def on_message(_client, _userdata, msg):
    try:
        event = json.loads(msg.payload.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return

    device_id = (event.get("source") or {}).get("short_address")
    if not device_id:
        return

    seq = event.get("sequence")
    if seq is None:
        seq = (event.get("zcl") or {}).get("sequence")
    rssi = (event.get("radio") or {}).get("rssi_dbm")
    frame_len = event.get("length", 0)

    with _lock:
        stats = _devices.get(device_id)
        if stats is None:
            stats = DeviceStats(device_id)
            _devices[device_id] = stats
        stats.update(seq, rssi, frame_len)


def publish_statuses(client: mqtt.Client) -> None:
    """将每台设备的链路质量状态发布到 Broker。"""
    with _lock:
        snapshots = [stats.snapshot() for stats in _devices.values()]

    timestamp_ms = int(time.time() * 1000)

    # 1. 按设备单独发布（保持兼容）
    for snapshot in snapshots:
        device_id = snapshot["device_id"]
        payload = {
            "device_id": device_id,
            "timestamp": timestamp_ms,
            "type": "status",
            "status": "online" if snapshot["online"] else "offline",
            "rssi_dbm": snapshot["rssi_last"],
            "link_quality": snapshot,
        }
        topic = STATUS_TOPIC_TEMPLATE.format(device_id=device_id)
        result = client.publish(
            topic,
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            qos=1,
            retain=False,
        )
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            print(f"[{now_iso()}] status publish failed topic={topic} rc={result.rc}")

    # 2. 汇总所有设备发布到统一主题（新增）
    summary_payload = {
        "timestamp": timestamp_ms,
        "type": "status_summary",
        "device_count": len(snapshots),
        "devices": []
    }

    for snapshot in snapshots:
        summary_payload["devices"].append({
            "device_id": snapshot["device_id"],
            "status": "online" if snapshot["online"] else "offline",
            "rssi_last": snapshot["rssi_last"],
            "rssi_avg": snapshot["rssi_avg"],
            "rssi_min": snapshot["rssi_min"],
            "received": snapshot["received"],
            "lost": snapshot["lost"],
            "loss_rate_pct": snapshot["loss_rate_pct"],
            "msg_rate": snapshot["msg_rate_per_s"],
            "byte_rate": snapshot["byte_rate_per_s"],
            "interval_s": snapshot["avg_interval_s"],
            "jitter_s": snapshot["jitter_s"],
            "age_s": snapshot["age_s"],
        })

    # 发布汇总
    result = client.publish(
        STATUS_SUMMARY_TOPIC,
        json.dumps(summary_payload, ensure_ascii=False, separators=(",", ":")),
        qos=1,
        retain=False,
    )
    if result.rc != mqtt.MQTT_ERR_SUCCESS:
        print(f"[{now_iso()}] summary publish failed rc={result.rc}")


def _disp_width(text: str) -> int:
    """计算显示宽度：中文/全角字符算 2，其余算 1。"""
    width = 0
    for ch in text:
        width += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return width


def _pad(text: str, width: int) -> str:
    """按显示宽度左对齐补空格。"""
    text = str(text)
    pad = width - _disp_width(text)
    return text + " " * max(0, pad)


# 各列显示宽度
_COLS = [
    ("设备", 10), ("状态", 6), ("收", 7), ("丢", 6), ("丢包率", 9),
    ("RSSI", 7), ("均值", 8), ("最差", 7), ("msg/s", 8), ("B/s", 8),
    ("间隔s", 8), ("抖动s", 8),
]


def render_panel() -> None:
    with _lock:
        snaps = [s.snapshot() for s in _devices.values()]
    snaps.sort(key=lambda s: s["device_id"])

    os.system("cls" if os.name == "nt" else "clear")
    print(f"Zigbee 链路质量监测  {now_iso()}   (窗口 {int(RATE_WINDOW_S)}s)")
    print("=" * 90)

    header = "".join(_pad(name, w) for name, w in _COLS)
    print(header)
    print("-" * 90)

    for s in snaps:
        row = [
            s["device_id"],
            "在线" if s["online"] else "离线",
            s["received"], s["lost"], s["loss_rate_pct"],
            s["rssi_last"], s["rssi_avg"], s["rssi_min"],
            s["msg_rate_per_s"], s["byte_rate_per_s"],
            s["avg_interval_s"], s["jitter_s"],
        ]
        print("".join(_pad(val, w) for val, (_, w) in zip(row, _COLS)))

    if not snaps:
        print("  (等待数据...)")
    print("=" * 90)
    print("Ctrl+C 退出")


def csv_logger(path: str) -> None:
    write_header = not os.path.exists(path)
    with open(path, "a", encoding="utf-8") as f:
        if write_header:
            f.write("timestamp,device_id,online,received,lost,loss_rate_pct,"
                    "rssi_last,rssi_avg,rssi_min,msg_rate_per_s,byte_rate_per_s,"
                    "avg_interval_s,jitter_s\n")
        while True:
            time.sleep(10)
            with _lock:
                snaps = [s.snapshot() for s in _devices.values()]
            ts = now_iso()
            for s in snaps:
                f.write(f"{ts},{s['device_id']},{s['online']},{s['received']},"
                        f"{s['lost']},{s['loss_rate_pct']},{s['rssi_last']},"
                        f"{s['rssi_avg']},{s['rssi_min']},{s['msg_rate_per_s']},"
                        f"{s['byte_rate_per_s']},{s['avg_interval_s']},{s['jitter_s']}\n")
            f.flush()


def main() -> None:
    parser = argparse.ArgumentParser(description="Zigbee 链路质量实时监测")
    parser.add_argument("--broker", default=DEFAULT_BROKER)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--refresh", type=float, default=2.0, help="面板刷新间隔秒")
    parser.add_argument("--csv", default=None, help="可选：CSV 日志路径")
    args = parser.parse_args()

    client = mqtt.Client(client_id="zigbee-link-monitor", clean_session=True)
    client.on_connect = on_connect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=30)
    client.connect_async(args.broker, args.port, keepalive=60)
    client.loop_start()

    if args.csv:
        threading.Thread(target=csv_logger, args=(args.csv,), daemon=True).start()

    try:
        while True:
            render_panel()
            publish_statuses(client)
            time.sleep(args.refresh)
    except KeyboardInterrupt:
        print("\n停止监测")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
