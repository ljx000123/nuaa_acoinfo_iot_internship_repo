#!/usr/bin/env python3
"""
VSOA 层 LoRa 相机图像接收测试脚本。

连接 bridge 的 VSOA Server（默认 vsoa://127.0.0.1:3001），
订阅 /device/update 和 /bridge/event，实时展示 camera 拼图结果。

用法:
    cd bridge-merged
    python iot_test_platform/vsoa_camera_test.py [vsoa_url]

示例:
    python iot_test_platform/vsoa_camera_test.py
    python iot_test_platform/vsoa_camera_test.py vsoa://192.168.200.204:3001

依赖: pip install vsoa
"""

from __future__ import annotations

import base64
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import vsoa
except ImportError:
    print("请先安装 VSOA SDK: pip install vsoa")
    sys.exit(1)


# ==================================================
# 配置
# ==================================================

VSOA_URL = sys.argv[1] if len(sys.argv) > 1 else "vsoa://127.0.0.1:3001"

IMAGE_DIR = Path(__file__).resolve().parent / "vsoa_images"
os.makedirs(IMAGE_DIR, exist_ok=True)
LATEST_IMAGE = IMAGE_DIR / "vsoa_latest.jpg"

IMAGE_KEYS = ("image_b64", "image_base64", "image_url", "image", "photo")

# 仅关注这个 camera 设备（可改为 None 显示所有）
TARGET_DEVICE = "dc56b7d6a7dd94a1"

# 调试：设为 True 打印 dc56b7d6a7dd94a1 的完整 VSOA payload
DEBUG_PAYLOAD = True
_debug_printed = 0

# ==================================================
# 计数器
# ==================================================

stats = {
    "device_update": 0,
    "bridge_event": 0,
    "camera_complete": 0,
    "camera_progress": 0,
    "camera_duplicate": 0,
    "image_saved": 0,
    "other_devices": 0,
}
stats_lock = threading.Lock()
_seen_devices: dict[str, int] = {}  # device_id → count


# ==================================================
# 时间格式化
# ==================================================

def ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


# ==================================================
# 递归查找 image_b64
# ==================================================

def find_image(payload: dict[str, Any]) -> tuple[str | None, str, int]:
    """在嵌套 dict 中查找图片字段，返回 (base64_str, key_name, bytes_len)。"""
    queue: list[dict[str, Any]] = [payload]
    seen = {id(payload)}
    while queue:
        current = queue.pop(0)
        for key in IMAGE_KEYS:
            value = current.get(key)
            if isinstance(value, str) and value:
                if key in ("image_b64", "image_base64"):
                    try:
                        raw = base64.b64decode(value)
                    except Exception:
                        continue
                    return value, key, len(raw)
                return value, key, 0
        for child in current.values():
            if isinstance(child, dict) and id(child) not in seen:
                seen.add(id(child))
                queue.append(child)
    return None, "", 0


# ==================================================
# 保存图片
# ==================================================

def save_image(device_id: str, image_seq: int, b64: str) -> Path:
    """保存 JPEG 到本地，更新 latest 软链。"""
    ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{device_id}_{ts_str}_seq{image_seq}.jpg"
    path = IMAGE_DIR / filename

    try:
        data = base64.b64decode(b64)
        path.write_bytes(data)
    except Exception as exc:
        print(f"  [ERROR] 保存失败: {exc}")
        return path

    # 更新 latest
    try:
        if LATEST_IMAGE.exists() or LATEST_IMAGE.is_symlink():
            LATEST_IMAGE.unlink()
        LATEST_IMAGE.write_bytes(data)
    except Exception:
        pass

    return path


# ==================================================
# /device/update 回调 — 设备数据更新
# ==================================================

def on_device_update(payload: dict[str, Any]) -> None:
    with stats_lock:
        stats["device_update"] += 1

    device_id = payload.get("device_id", "?")
    dev_type = payload.get("type", "?")

    # 跟踪目标设备的每一次 /device/update
    is_target = (TARGET_DEVICE and device_id == TARGET_DEVICE)

    # 提取嵌套 raw 中的 image_b64（raw 在 if/else 外定义）
    raw = payload.get("raw", {})
    search_in = payload if isinstance(payload, dict) else {}
    b64_str, key, img_bytes = find_image(search_in)

    with stats_lock:
        _seen_devices[device_id] = _seen_devices.get(device_id, 0) + 1

    if not b64_str:
        if is_target:
            raw_keys = list(raw.keys()) if isinstance(raw, dict) else []
            has_image_keys = [k for k in raw_keys if "image" in k.lower() or "b64" in k.lower() or "jpeg" in k.lower() or "camera" in k.lower()]
            print(f"  [{ts()}] /device/update  device={device_id}  type={dev_type}  source={payload.get('source','?')}  raw_keys={raw_keys[:20]}  camera_keys={has_image_keys}  (无图片)")
        return

    image_seq = raw.get("image_seq", raw.get("imageSeq", "?"))
    chunk_count = raw.get("chunk_count", "?")
    img_bytes_kb = img_bytes / 1024

    with stats_lock:
        stats["camera_complete"] += 1

    # 仅关注目标设备时跳过其他
    if TARGET_DEVICE and device_id != TARGET_DEVICE:
        with stats_lock:
            stats["other_devices"] += 1
        return

    print(f"\n{'=' * 60}")
    print(f"  [{ts()}]  CAMERA 图像到达 (VSOA) !!!")
    print(f"  {'=' * 60}")
    print(f"  设备:     {device_id}")
    print(f"  类型:     {dev_type}")
    print(f"  seq:      {image_seq}")
    print(f"  chunks:   {chunk_count}")
    print(f"  大小:     {img_bytes} B ({img_bytes_kb:.1f} KB)")
    print(f"  字段:     raw.{key}")
    print(f"  {'=' * 60}")

    # 保存
    saved_path = save_image(device_id, image_seq if isinstance(image_seq, int) else 0, b64_str)
    print(f"  已保存:   {saved_path}")
    print(f"  latest:   {LATEST_IMAGE}")
    print()

    with stats_lock:
        stats["image_saved"] += 1


# ==================================================
# /bridge/event 回调 — bridge 事件流
# ==================================================

def on_bridge_event(payload: dict[str, Any]) -> None:
    with stats_lock:
        stats["bridge_event"] += 1

    event_type = payload.get("event", "?")
    state = payload.get("state", "?")
    device_id = payload.get("device_id", "?")

    if TARGET_DEVICE and device_id != TARGET_DEVICE:
        return

    if event_type == "camera_reassembly":
        if state == "complete":
            # 拼图成功事件（无 image_b64，图片在 /device/update 里）
            seq = payload.get("image_seq", "?")
            received = payload.get("received_count", "?")
            chunk_count = payload.get("chunk_count", "?")
            print(f"  [{ts()}] /bridge/event  camera_reassembly  state=complete  "
                  f"device={device_id}  seq={seq}  received={received}/{chunk_count}")
        elif state == "progress":
            with stats_lock:
                stats["camera_progress"] += 1
        elif state == "duplicate" or state == "duplicate_complete":
            with stats_lock:
                stats["camera_duplicate"] += 1
    elif event_type == "data_received":
        pass  # 太频繁，不打印
    else:
        print(f"  [{ts()}] /bridge/event  {event_type}  device={device_id}  state={state}")


# ==================================================
# VSOA 客户端的 on_message
# ==================================================

def on_message(cli, url, payload, quick):
    """VSOA 订阅回调。"""
    del cli, quick
    data = dict(payload.param) if payload and getattr(payload, "param", None) else {}
    if not data:
        return

    url_text = url.url if hasattr(url, "url") else str(url)

    if url_text == "/device/update":
        on_device_update(data)
    elif url_text == "/bridge/event":
        on_bridge_event(data)
    elif url_text == "/ctrl/ack":
        pass  # 下行 ACK，不关注
    else:
        print(f"  [{ts()}] {url_text}: {str(data)[:120]}")


def on_connect(cli, connected, server_info):
    del server_info
    status = "CONNECTED" if connected else "DISCONNECTED"
    print(f"\n  [{ts()}] VSOA {status}")
    if not connected:
        print("  [WARN] VSOA 连接断开，等待重连...")


# ==================================================
# 状态报告线程
# ==================================================

def status_reporter(stop: threading.Event) -> None:
    """每 5 秒打印一次统计摘要。"""
    while not stop.wait(5.0):
        with stats_lock:
            s = dict(stats)
            devices = dict(_seen_devices)
        top_devices = sorted(devices.items(), key=lambda x: -x[1])[:5]
        dev_str = "  ".join(f"{did}={cnt}" for did, cnt in top_devices)
        print(
            f"\n  [{ts()}] --- STATS --- "
            f"/device/update={s['device_update']}  "
            f"/bridge/event={s['bridge_event']}  "
            f"complete={s['camera_complete']}  "
            f"progress={s['camera_progress']}  "
            f"dup={s['camera_duplicate']}  "
            f"saved={s['image_saved']}  "
            f"other={s['other_devices']}"
        )
        print(f"  [{ts()}] 设备: {dev_str}")


# ==================================================
# 主函数
# ==================================================

def main() -> None:
    print(f"\n  VSOA Camera Test")
    print(f"  {'=' * 50}")
    print(f"  VSOA URL:     {VSOA_URL}")
    print(f"  订阅:         /device/update, /bridge/event")
    print(f"  目标设备:     {TARGET_DEVICE or '全部'}")
    print(f"  图片目录:     {IMAGE_DIR}")
    print(f"  {'=' * 50}\n")

    # VSOA Client
    client = vsoa.Client()

    # 设置回调
    client.onmessage = on_message
    client.onconnect = on_connect

    # 连接
    print(f"  [{ts()}] 正在连接 {VSOA_URL} ...")
    result = client.connect(VSOA_URL)
    if result != 0:
        print(f"  [ERROR] VSOA 连接失败: code={result}")
        print(f"  请确认 bridge 已启动且监听对应端口")
        sys.exit(1)

    print(f"  [{ts()}] VSOA 连接成功")

    # 订阅
    client.subscribe("/device/update")
    client.subscribe("/bridge/event")
    print(f"  [{ts()}] 已订阅 /device/update, /bridge/event")
    print(f"  [{ts()}] 等待 camera 数据...\n")

    # 启动状态报告
    stop = threading.Event()
    reporter = threading.Thread(target=status_reporter, args=(stop,), daemon=True)
    reporter.start()

    try:
        client.run()
    except KeyboardInterrupt:
        print(f"\n  [{ts()}] 用户中断")
    except Exception as exc:
        print(f"\n  [{ts()}] VSOA run 异常: {exc}")
    finally:
        stop.set()
        reporter.join(timeout=1)
        try:
            client.close()
        except Exception:
            pass

    # 最终统计
    print(f"\n  {'=' * 50}")
    print(f"  运行结束，最终统计:")
    with stats_lock:
        for key, value in stats.items():
            print(f"    {key}: {value}")
    print(f"  图片目录: {IMAGE_DIR}")
    saved = sorted(IMAGE_DIR.glob("*.jpg"))
    print(f"  已保存 {len(saved)} 张图片")
    for path in saved[-5:]:
        size_kb = path.stat().st_size / 1024
        print(f"    {path.name}  ({size_kb:.1f} KB)")
    print(f"  {'=' * 50}\n")


if __name__ == "__main__":
    main()
