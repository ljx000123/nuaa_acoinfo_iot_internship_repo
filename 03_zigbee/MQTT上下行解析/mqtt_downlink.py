#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MQTT版本下行控制程序
订阅应用层控制命令，转换为二进制Ebyte帧后通过MQTT发送给网关

帧格式 (Ebyte V1.7 TYPE_ZCL_SEND):
  55 | LEN(1B) | 0x02 | 0x0F | SEND_MODE | ADDR_L | ADDR_H | EP |
  SEQ | DIR | CLU_L | CLU_H | MANUF_L | MANUF_H | RSP | CMD_ID |
  [cmd_params...] | CHECKSUM
  LEN = 从0x02到最后一个数据字节的字节数
  CHECKSUM = XOR(0x02 到最后一个数据字节)
"""

from __future__ import annotations

import json
import time
from datetime import datetime

import paho.mqtt.client as mqtt


# ==================== 配置参数 ====================
MQTT_BROKER = "192.168.200.169"
MQTT_PORT = 1883
MQTT_KEEPALIVE = 60

GATEWAY_DOWNLINK_TOPIC = "zigbee/gw/downlink"   # 发给网关的二进制帧
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


# ==================== 工具函数 ====================
def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def log(event: str, **kwargs) -> None:
    print(json.dumps({"event": event, "timestamp": now_iso(), **kwargs},
                     ensure_ascii=False, separators=(",", ":")), flush=True)


def xor_checksum(data: bytes) -> int:
    result = 0
    for b in data:
        result ^= b
    return result


# ==================== 帧构建 ====================
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
        0x02,                        # TYPE_ZCL_SEND
        0x0F,                        # ZCL_CMD
        src_ep_index & 0x0F,         # SEND_MODE
        addr_bytes[0],               # TARGET_ADDR low
        addr_bytes[1],               # TARGET_ADDR high
        endpoint & 0xFF,             # TARGET_EP
        seq,                         # SEQ_NUM
        direction & 0xFF,            # CMD_DIR
        cluster_id & 0xFF,           # CLUSTER_ID low
        (cluster_id >> 8) & 0xFF,    # CLUSTER_ID high
        manuf_code & 0xFF,           # MANUF_CODE low
        (manuf_code >> 8) & 0xFF,    # MANUF_CODE high
        rsp_mode & 0xFF,             # RSP_MODE
        cmd_id & 0xFF,               # CMD_ID
    ]) + cmd_params

    checksum = xor_checksum(payload_data)
    length = len(payload_data) + 1   # +1 for checksum
    return bytes([0x55, length]) + payload_data + bytes([checksum])


# ==================== 命令处理 ====================
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


def _handle_command(mqtt_client, device_id: str, action: str,
                    params: dict, raw_cmd: dict) -> None:
    """根据命令构造Ebyte帧并通过MQTT发布给网关"""
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

    # ── 透传发送（Ebyte cluster 0xFC08）──────────────────────────────
    raw_data = params.get("data") or params.get("raw")
    if raw_data is not None:
        if isinstance(raw_data, str):
            payload_bytes = bytes.fromhex(raw_data.replace(" ", ""))
        elif isinstance(raw_data, list):
            payload_bytes = bytes(raw_data)
        else:
            payload_bytes = str(raw_data).encode()
        frame = build_zcl_cmd_frame(
            short_addr=device_id,
            endpoint=endpoint,
            cluster_id=0xFC08,
            cmd_id=0x00,
            cmd_params=payload_bytes,
            manuf_code=0x2000,
        )
        _publish_frame(mqtt_client, frame, device_id)
        return

    # ── ON/OFF 开关控制 (cluster 0x0006) ─────────────────────────────
    relay_val = params.get("relay") or params.get("led") or params.get("switch")
    if relay_val is not None:
        cmd_map = {"on": 0x01, "off": 0x00, "toggle": 0x02, "1": 0x01, "0": 0x00}
        cmd_id = cmd_map.get(str(relay_val).lower())
        if cmd_id is not None:
            frame = build_zcl_cmd_frame(
                short_addr=device_id,
                endpoint=endpoint,
                cluster_id=0x0006,
                cmd_id=cmd_id,
            )
            _publish_frame(mqtt_client, frame, device_id)
            return

    # ── 亮度控制 (cluster 0x0008) ─────────────────────────────────────
    level_val = params.get("level") or params.get("brightness")
    if level_val is not None:
        level = max(0, min(255, int(level_val)))
        frame = build_zcl_cmd_frame(
            short_addr=device_id,
            endpoint=endpoint,
            cluster_id=0x0008,
            cmd_id=0x00,
            cmd_params=bytes([level, 0x00, 0x00]),
        )
        _publish_frame(mqtt_client, frame, device_id)
        return

    log("command_unhandled", device_id=device_id, action=action, params=params)


def _publish_frame(mqtt_client, frame: bytes, device_id: str) -> None:
    """把二进制帧发布到网关下行主题（透传，不做HEX编码）"""
    mqtt_client.publish(GATEWAY_DOWNLINK_TOPIC, frame, qos=1)
    log("zigbee_frame_published",
        device_id=device_id,
        topic=GATEWAY_DOWNLINK_TOPIC,
        frame_hex=frame.hex(" ").upper(),
        length=len(frame))


# ==================== MQTT客户端 ====================
def on_connect(client, _userdata, _flags, rc):
    if rc == 0:
        log("mqtt_connected", broker=MQTT_BROKER, port=MQTT_PORT)
        for topic, qos in APP_DOWNLINK_TOPICS:
            client.subscribe(topic, qos)
            log("subscribed", topic=topic, qos=qos)
    else:
        log("mqtt_connect_failed", reason_code=rc)


def on_disconnect(client, _userdata, rc):
    if rc != 0:
        log("mqtt_disconnected", reason_code=rc, note="will_reconnect")


def on_message(client, _userdata, msg):
    raw = msg.payload.decode("utf-8", errors="replace")
    try:
        cmd = json.loads(raw)
    except json.JSONDecodeError:
        log("downlink_parse_error", topic=msg.topic, raw=raw)
        return

    log("downlink_received", topic=msg.topic, qos=msg.qos, command=cmd)

    action  = cmd.get("action") or cmd.get("cmd") or cmd.get("command")
    params  = cmd.get("params") or cmd.get("data") or {}
    if isinstance(params, str):
        params = {"data": params}

    # 多设备列表
    device_list = cmd.get("devices")
    if device_list and isinstance(device_list, list):
        for dev_id in device_list:
            _handle_command(client, dev_id, action, params, cmd)
        return

    device_id = (cmd.get("device_id") or cmd.get("devEUI")
                 or _extract_device_from_topic(msg.topic))
    _handle_command(client, device_id, action, params, cmd)


def main() -> None:
    print("=" * 60)
    print("MQTT版本 Zigbee下行控制处理器")
    print("=" * 60)
    print(f"Broker:       {MQTT_BROKER}:{MQTT_PORT}")
    print(f"订阅(应用):   {[t for t, _ in APP_DOWNLINK_TOPICS]}")
    print(f"发布(网关):   {GATEWAY_DOWNLINK_TOPIC}")
    print(f"设备别名:     {DEVICE_ALIASES}")
    print("=" * 60)

    client = mqtt.Client(client_id="zigbee-downlink-handler", clean_session=True)
    client.on_connect    = on_connect
    client.on_disconnect = on_disconnect
    client.on_message    = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=30)
    client.connect_async(MQTT_BROKER, MQTT_PORT, keepalive=MQTT_KEEPALIVE)
    client.loop_start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log("stopping")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
