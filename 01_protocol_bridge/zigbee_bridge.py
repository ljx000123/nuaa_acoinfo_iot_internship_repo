#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Zigbee 双向桥接器（合并版）
  上行：订阅网关 Ebyte 二进制帧 → 解析 → 发布 JSON
  下行：订阅应用层 JSON 命令 → 构造 Ebyte 二进制帧 → 发给网关

帧格式 (Ebyte V1.7):
  上行接收帧: 55 | LEN | 82 | 0F | 模式 | ADDR_L ADDR_H | EP | SEQ | 方向 |
              CLU_L CLU_H | MANUF_L MANUF_H | RSSI | CMD | [payload] | CHECKSUM
  下行发送帧: 55 | LEN | 02 | 0F | 模式 | ADDR_L ADDR_H | EP | SEQ | 方向 |
              CLU_L CLU_H | MANUF_L MANUF_H | RSP | CMD | [params] | CHECKSUM
  CHECKSUM = XOR(从TYPE字节到最后一个数据字节)

兼容: Python 3.8.10+
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Dict, List, Optional

import paho.mqtt.client as mqtt


# ==================== 配置参数 ====================
MQTT_BROKER    = "192.168.200.169"
MQTT_PORT      = 1883
MQTT_KEEPALIVE = 60

# 上行
GATEWAY_UPLINK_TOPIC = "zigbee/gw/uplink"
APP_UPLINK_PREFIX    = "bridge/uplink/zigbee"

# 下行
GATEWAY_DOWNLINK_TOPIC = "zigbee/gw/downlink"
APP_DOWNLINK_TOPICS = [
    ("bridge/downlink/#",                   1),
    ("application/+/device/+/command/down", 1),
]

DEVICE_ALIASES = {
    "relay":       "0xB25B",
    "relay_board": "0xB25B",
    "led":         "0xC38F",
    "led_board":   "0xC38F",
}


# ==================== 帧常量 ====================
FRAME_HEAD        = 0x55
TYPE_ZCL_RECEIVE  = 0x82
TYPE_ZCL_SEND     = 0x02
CMD_ZCL           = 0x0F


# ==================== 工具函数 ====================
def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def log(event: str, **kwargs) -> None:
    print(json.dumps({"event": event, "timestamp": now_iso(), **kwargs},
                     ensure_ascii=False, separators=(",", ":")), flush=True)


def u16_le(data: bytes, offset: int) -> int:
    return data[offset] | (data[offset + 1] << 8)


def signed_u8(value: int) -> int:
    return value - 256 if value >= 128 else value


def xor_checksum(data: bytes) -> int:
    result = 0
    for b in data:
        result ^= b
    return result


# ==================== 上行：帧解析 ====================
def decode_sensor_payload(payload: bytes, valid_checksum: bool) -> Optional[Dict]:
    """根据 payload[0] 版本号和 payload[2] 类型码识别并解析传感器数据"""

    # P00 ADC电压传感器: version=0x01, type=0x01
    if len(payload) >= 10 and payload[0] == 0x01 and payload[2] == 0x01:
        voltage_mv = u16_le(payload, 5)
        return {
            "event": "p00_sensor_report",
            "protocol_version": payload[0],
            "sequence": payload[1],
            "sensor_type": "p00_adc",
            "p00": {
                "adc_raw": u16_le(payload, 3),
                "voltage_mv": voltage_mv,
                "voltage_v": round(voltage_mv / 1000.0, 3),
            },
            "status": {"flags": payload[9], "ok": valid_checksum and payload[9] == 0},
        }

    # Terminal1 MQ2+PIR: version=0x02, type=0x01
    if len(payload) >= 11 and payload[0] == 0x02 and payload[2] == 0x01:
        voltage_mv = u16_le(payload, 5)
        smoke_x10 = u16_le(payload, 7)
        pir_detected = payload[9] != 0
        return {
            "event": "terminal1_sensor_report",
            "protocol_version": payload[0],
            "sequence": payload[1],
            "sensor_type": "mq2_and_pir",
            "mq2": {
                "port": "P0.0",
                "adc_raw": u16_le(payload, 3),
                "voltage_mv": voltage_mv,
                "voltage_v": round(voltage_mv / 1000.0, 3),
                "smoke_relative_percent": round(smoke_x10 / 10.0, 1),
            },
            "pir": {
                "port": "P0.2",
                "digital_value": payload[9],
                "motion_detected": pir_detected,
                "state": "motion" if pir_detected else "clear",
            },
            "status": {"flags": payload[10], "ok": valid_checksum and payload[10] == 0},
        }

    # 环境传感器 DHT11+光敏+气压: version=0x03, type=0x02
    if len(payload) >= 15 and payload[0] == 0x03 and payload[2] == 0x02:
        pressure_mv = u16_le(payload, 5)
        light_mv = u16_le(payload, 9)
        dht_ok = payload[13] != 0
        return {
            "event": "environment_sensor_report",
            "protocol_version": payload[0],
            "sequence": payload[1],
            "sensor_type": "dht11_light_pressure",
            "water_pressure_input": {
                "port": "P0.0",
                "adc_raw": u16_le(payload, 3),
                "voltage_mv": pressure_mv,
                "voltage_v": round(pressure_mv / 1000.0, 3),
            },
            "light": {
                "port": "P0.7",
                "adc_raw": u16_le(payload, 7),
                "voltage_mv": light_mv,
                "voltage_v": round(light_mv / 1000.0, 3),
                "unit_note": "raw ADC; lux conversion requires calibration",
            },
            "dht11": {
                "port": "P0.6",
                "temperature_c": payload[11] if dht_ok else None,
                "humidity_percent": payload[12] if dht_ok else None,
                "valid": dht_ok,
            },
            "status": {"flags": payload[14], "ok": valid_checksum and payload[14] == 0},
        }

    return None


def decode_frame(frame: bytes) -> Optional[Dict]:
    """
    解析一个完整的 Ebyte 帧，返回结构化 dict，失败返回 None。
    frame 格式: 55 LEN TYPE CMD ...payload... CHECKSUM
    """
    if len(frame) < 5:
        return None
    if frame[0] != FRAME_HEAD:
        return None

    valid_checksum = xor_checksum(frame[2:-1]) == frame[-1]

    if len(frame) < 17:
        return None
    if frame[2] != TYPE_ZCL_RECEIVE or frame[3] != CMD_ZCL:
        return None

    short_addr = f"0x{u16_le(frame, 5):04X}"
    endpoint   = frame[7]
    sequence   = frame[8]
    cluster_id = f"0x{u16_le(frame, 10):04X}"
    manuf_code = f"0x{u16_le(frame, 12):04X}"
    rssi_dbm   = signed_u8(frame[14])
    cmd_id     = frame[15]
    payload    = frame[16:-1]

    base = {
        "timestamp": now_iso(),
        "frame_hex": frame.hex(" ").upper(),
        "checksum_valid": valid_checksum,
        "source": {"short_address": short_addr, "endpoint": endpoint},
        "zcl": {
            "sequence": sequence,
            "cluster_id": cluster_id,
            "manufacturer_code": manuf_code,
            "command_id": f"0x{cmd_id:02X}",
        },
        "radio": {"rssi_dbm": rssi_dbm},
        "payload_hex": payload.hex(" ").upper(),
    }

    sensor = decode_sensor_payload(payload, valid_checksum)
    if sensor:
        base.update(sensor)

    return base


# ==================== 下行：帧构建 ====================
_seq_num: int = 0


def _next_seq() -> int:
    global _seq_num
    _seq_num = (_seq_num + 1) & 0xFF
    return _seq_num


def _parse_short_addr(addr_str: str) -> bytes:
    """'0xB25B' → b'\\x5B\\xB2' (小端)"""
    addr = int(addr_str, 16) if isinstance(addr_str, str) else int(addr_str)
    return bytes([addr & 0xFF, (addr >> 8) & 0xFF])


def build_zcl_cmd_frame(
    short_addr: str,
    endpoint: int = 1,
    cluster_id: int = 0xFC08,
    cmd_id: int = 0x00,
    cmd_params: bytes = b"",
    manuf_code: int = 0x2000,
    direction: int = 0,
    src_ep_index: int = 0,
    rsp_mode: int = 1,
) -> bytes:
    """构造 TYPE_ZCL_SEND(0x02) + ZCL_CMD(0x0F) 帧"""
    addr_bytes = _parse_short_addr(short_addr)
    seq = _next_seq()

    payload_data = bytes([
        TYPE_ZCL_SEND,
        CMD_ZCL,
        src_ep_index & 0x0F,
        addr_bytes[0],
        addr_bytes[1],
        endpoint & 0xFF,
        seq,
        direction & 0xFF,
        cluster_id & 0xFF,
        (cluster_id >> 8) & 0xFF,
        manuf_code & 0xFF,
        (manuf_code >> 8) & 0xFF,
        rsp_mode & 0xFF,
        cmd_id & 0xFF,
    ]) + cmd_params

    checksum = xor_checksum(payload_data)
    length = len(payload_data) + 1   # +1 for checksum
    return bytes([FRAME_HEAD, length]) + payload_data + bytes([checksum])


# ==================== Zigbee 双向桥接器 ====================
class ZigbeeBridge:
    """一个 MQTT 连接，同时处理上行解析和下行控制"""

    def __init__(self, broker: str, port: int) -> None:
        self.broker = broker
        self.port = port
        self._buffer = bytearray()

        self.client = mqtt.Client(client_id="zigbee_bridge", clean_session=True)
        self.client.on_connect    = self._on_connect
        self.client.on_message    = self._on_message
        self.client.on_disconnect = self._on_disconnect
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)

    # ── MQTT 回调 ──────────────────────────────────────────
    def _on_connect(self, client, _userdata, _flags, rc) -> None:
        if rc == 0:
            log("mqtt_connected", broker=self.broker, port=self.port)
            # 订阅上行（网关原始帧）
            client.subscribe(GATEWAY_UPLINK_TOPIC, qos=1)
            log("subscribed", topic=GATEWAY_UPLINK_TOPIC, direction="uplink")
            # 订阅下行（应用层控制命令）
            for topic, qos in APP_DOWNLINK_TOPICS:
                client.subscribe(topic, qos)
                log("subscribed", topic=topic, qos=qos, direction="downlink")
        else:
            log("mqtt_connect_failed", reason_code=rc)

    def _on_disconnect(self, _client, _userdata, rc) -> None:
        if rc != 0:
            log("mqtt_disconnected", reason_code=rc, note="will_reconnect")

    def _on_message(self, client, _userdata, msg) -> None:
        topic = msg.topic
        try:
            if topic == GATEWAY_UPLINK_TOPIC:
                self._handle_uplink(client, msg.payload)
            else:
                self._handle_downlink(client, topic, msg.payload)
        except Exception as exc:
            log("message_error", topic=topic, error=str(exc))
            import traceback
            traceback.print_exc()

    # ── 上行处理 ───────────────────────────────────────────
    def _handle_uplink(self, client, raw: bytes) -> None:
        """处理网关发布的原始二进制帧 → 解析后发布 JSON"""
        self._buffer.extend(raw)
        frames = self._extract_frames()

        for frame in frames:
            print(f"\n[上行] {frame.hex(' ').upper()}")

            result = decode_frame(frame)
            if not result:
                print("[跳过] 非ZCL接收帧或校验失败")
                continue

            short_addr = result.get("source", {}).get("short_address", "unknown")
            event      = result.get("event", "zigbee_zcl_receive")
            rssi       = result.get("radio", {}).get("rssi_dbm", 0)
            print(f"[解析] 设备:{short_addr}  事件:{event}  RSSI:{rssi}dBm")

            sensor_events = {
                "p00_sensor_report",
                "terminal1_sensor_report",
                "environment_sensor_report",
            }
            if event in sensor_events:
                topic   = f"{APP_UPLINK_PREFIX}/{short_addr}/data"
                payload = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
                client.publish(topic, payload, qos=1, retain=False)
                print(f"[发布] {topic}")

    def _extract_frames(self) -> List[bytes]:
        """从 buffer 中提取完整 Ebyte 帧，容忍噪声"""
        frames: List[bytes] = []
        while True:
            try:
                head = self._buffer.index(FRAME_HEAD)
            except ValueError:
                self._buffer.clear()
                break

            if head:
                del self._buffer[:head]

            if len(self._buffer) < 2:
                break

            total = self._buffer[1] + 2   # LEN + 2（55 和 CHECKSUM）
            if total < 5:
                del self._buffer[0]
                continue
            if len(self._buffer) < total:
                break

            frames.append(bytes(self._buffer[:total]))
            del self._buffer[:total]

        return frames

    # ── 下行处理 ───────────────────────────────────────────
    def _handle_downlink(self, client, topic: str, raw: bytes) -> None:
        """处理应用层 JSON 命令 → 构造 Ebyte 帧 → 发给网关"""
        raw_str = raw.decode("utf-8", errors="replace")
        try:
            cmd = json.loads(raw_str)
        except json.JSONDecodeError:
            log("downlink_parse_error", topic=topic, raw=raw_str)
            return

        log("downlink_received", topic=topic, qos=1, command=cmd)

        action = cmd.get("action") or cmd.get("cmd") or cmd.get("command")
        params = cmd.get("params") or cmd.get("data") or {}
        if isinstance(params, str):
            params = {"data": params}

        # 多设备列表
        device_list = cmd.get("devices")
        if device_list and isinstance(device_list, list):
            for dev_id in device_list:
                self._route_command(client, dev_id, action, params, cmd)
            return

        device_id = (cmd.get("device_id") or cmd.get("devEUI")
                     or _extract_device_from_topic(topic))
        self._route_command(client, device_id, action, params, cmd)

    def _route_command(self, client, device_id: str, action: str,
                       params: Dict, raw_cmd: Dict) -> None:
        """根据命令构造 Ebyte 帧并通过 MQTT 发布给网关"""
        endpoint = int(raw_cmd.get("endpoint", 1))

        # 别名解析
        if device_id and device_id.lower() in DEVICE_ALIASES:
            resolved = DEVICE_ALIASES[device_id.lower()]
            log("alias_resolved", alias=device_id, short_address=resolved)
            device_id = resolved

        # 广播
        if device_id.lower() in ("broadcast", "all", "0xffff"):
            device_id = "0xFFFF"
            endpoint = 0xFF

        # ── 透传发送（Ebyte cluster 0xFC08）──────────────────
        raw_data = params.get("data") or params.get("raw")
        if raw_data is not None:
            if isinstance(raw_data, str):
                payload_bytes = bytes.fromhex(raw_data.replace(" ", ""))
            elif isinstance(raw_data, list):
                payload_bytes = bytes(raw_data)
            else:
                payload_bytes = str(raw_data).encode()
            frame = build_zcl_cmd_frame(
                short_addr=device_id, endpoint=endpoint,
                cluster_id=0xFC08, cmd_id=0x00,
                cmd_params=payload_bytes, manuf_code=0x2000,
            )
            self._publish_frame(client, frame, device_id)
            return

        # ── ON/OFF 开关控制 (cluster 0x0006) ──────────────────
        switch_val = params.get("relay") or params.get("led") or params.get("switch")
        if switch_val is not None:
            cmd_map = {"on": 0x01, "off": 0x00, "toggle": 0x02, "1": 0x01, "0": 0x00}
            cmd_id = cmd_map.get(str(switch_val).lower())
            if cmd_id is not None:
                frame = build_zcl_cmd_frame(
                    short_addr=device_id, endpoint=endpoint,
                    cluster_id=0x0006, cmd_id=cmd_id,
                )
                self._publish_frame(client, frame, device_id)
                return

        # ── 亮度控制 (cluster 0x0008) ─────────────────────────
        level_val = params.get("level") or params.get("brightness")
        if level_val is not None:
            level = max(0, min(255, int(level_val)))
            frame = build_zcl_cmd_frame(
                short_addr=device_id, endpoint=endpoint,
                cluster_id=0x0008, cmd_id=0x00,
                cmd_params=bytes([level, 0x00, 0x00]),
            )
            self._publish_frame(client, frame, device_id)
            return

        log("command_unhandled", device_id=device_id, action=action, params=params)

    def _publish_frame(self, client, frame: bytes, device_id: str) -> None:
        """把二进制帧发布到网关下行主题"""
        client.publish(GATEWAY_DOWNLINK_TOPIC, frame, qos=1)
        log("zigbee_frame_published",
            device_id=device_id,
            topic=GATEWAY_DOWNLINK_TOPIC,
            frame_hex=frame.hex(" ").upper(),
            length=len(frame))

    # ── 启动 ────────────────────────────────────────────────
    def run(self) -> None:
        print("=" * 60)
        print("Zigbee 双向桥接器（上行解析 + 下行控制）")
        print("=" * 60)
        print(f"Broker:       {self.broker}:{self.port}")
        print(f"上行 订阅:     {GATEWAY_UPLINK_TOPIC}")
        print(f"上行 发布:     {APP_UPLINK_PREFIX}/{{device}}/data")
        print(f"下行 订阅:     {[t for t, _ in APP_DOWNLINK_TOPICS]}")
        print(f"下行 发布:     {GATEWAY_DOWNLINK_TOPIC}")
        print(f"设备别名:      {DEVICE_ALIASES}")
        print("=" * 60)

        self.client.connect_async(self.broker, self.port, MQTT_KEEPALIVE)
        self.client.loop_forever()


# ==================== 辅助函数 ====================
def _extract_device_from_topic(topic: str) -> str:
    parts = topic.split("/")
    try:
        idx = parts.index("device")
        return parts[idx + 1]
    except (ValueError, IndexError):
        pass
    try:
        idx = parts.index("downlink")
        return parts[idx + 2] if len(parts) > idx + 2 else "unknown"
    except (ValueError, IndexError):
        return "unknown"


# ==================== 入口 ====================
if __name__ == "__main__":
    ZigbeeBridge(MQTT_BROKER, MQTT_PORT).run()
