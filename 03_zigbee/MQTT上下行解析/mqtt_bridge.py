#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MQTT版本网关桥接程序
订阅网关发布的二进制帧，解析后重新发布为JSON格式

帧格式 (Ebyte V1.7):
  55 | LEN(1B) | TYPE(1B) | CMD(1B) | ...payload... | CHECKSUM(1B)
  LEN = 从TYPE到最后一个数据字节的字节数（不含55和CHECKSUM）
  CHECKSUM = XOR(TYPE 到最后一个数据字节)
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Optional

import paho.mqtt.client as mqtt


# ==================== 配置参数 ====================
MQTT_BROKER = "192.168.200.169"
MQTT_PORT = 1883
MQTT_KEEPALIVE = 60

GATEWAY_UPLINK_TOPIC = "zigbee/gw/uplink"      # 网关发布的原始二进制帧
APP_UPLINK_PREFIX    = "bridge/uplink/zigbee"   # 解析后JSON发布前缀


# ==================== 帧常量 ====================
FRAME_HEAD        = 0x55
TYPE_ZCL_RECEIVE  = 0x82   # 网关上行ZCL接收帧
CMD_ZCL_RECEIVE   = 0x0F


# ==================== 工具函数 ====================
def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def u16_le(data: bytes, offset: int) -> int:
    return data[offset] | (data[offset + 1] << 8)


def signed_u8(value: int) -> int:
    return value - 256 if value >= 128 else value


def xor_checksum(data: bytes) -> int:
    result = 0
    for b in data:
        result ^= b
    return result


# ==================== 传感器解析 ====================
def decode_sensor_payload(payload: bytes, valid_checksum: bool) -> Optional[dict]:
    """根据payload[0]版本号和payload[2]类型码识别并解析传感器数据"""

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
            "status": {
                "flags": payload[9],
                "ok": valid_checksum and payload[9] == 0,
            },
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
            "status": {
                "flags": payload[10],
                "ok": valid_checksum and payload[10] == 0,
            },
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
            "status": {
                "flags": payload[14],
                "ok": valid_checksum and payload[14] == 0,
            },
        }

    return None


# ==================== 帧解析 ====================
def decode_frame(frame: bytes) -> Optional[dict]:
    """
    解析一个完整的Ebyte帧，返回结构化dict，失败返回None。
    frame格式: 55 LEN TYPE CMD ...payload... CHECKSUM
    """
    if len(frame) < 5:
        return None
    if frame[0] != FRAME_HEAD:
        return None

    valid_checksum = xor_checksum(frame[2:-1]) == frame[-1]

    # 仅处理ZCL接收帧
    if len(frame) < 17:
        return None
    if frame[2] != TYPE_ZCL_RECEIVE or frame[3] != CMD_ZCL_RECEIVE:
        return None

    # 解析统一接收帧头（§4.2.1）
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
        "source": {
            "short_address": short_addr,
            "endpoint": endpoint,
        },
        "zcl": {
            "sequence": sequence,
            "cluster_id": cluster_id,
            "manufacturer_code": manuf_code,
            "command_id": f"0x{cmd_id:02X}",
        },
        "radio": {
            "rssi_dbm": rssi_dbm,
        },
        "payload_hex": payload.hex(" ").upper(),
    }

    # 尝试识别传感器数据
    sensor = decode_sensor_payload(payload, valid_checksum)
    if sensor:
        base.update(sensor)

    return base


# ==================== MQTT桥接器 ====================
class MqttBridge:
    """订阅网关原始二进制帧，解析后重新发布为JSON"""

    def __init__(self, broker: str, port: int) -> None:
        self.broker = broker
        self.port = port
        self._buffer = bytearray()
        self.client = mqtt.Client(client_id="mqtt_bridge", clean_session=True)
        self.client.on_connect    = self._on_connect
        self.client.on_message    = self._on_message
        self.client.on_disconnect = self._on_disconnect
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print(f"[MQTT] 已连接到broker {self.broker}:{self.port}")
            client.subscribe(GATEWAY_UPLINK_TOPIC, qos=1)
            print(f"[MQTT] 订阅网关上行主题: {GATEWAY_UPLINK_TOPIC}")
        else:
            print(f"[MQTT] 连接失败，错误码: {rc}")

    def _on_disconnect(self, client, userdata, rc):
        if rc != 0:
            print(f"[MQTT] 意外断开，错误码: {rc}，将自动重连")

    def _on_message(self, client, userdata, msg):
        """处理网关发布的原始二进制帧"""
        try:
            raw = msg.payload

            # 在buffer中查找完整帧（兼容粘包/分包）
            self._buffer.extend(raw)
            frames = self._extract_frames()

            for frame in frames:
                print(f"\n[收到] {frame.hex(' ').upper()}")

                result = decode_frame(frame)
                if not result:
                    print("[跳过] 非ZCL接收帧或校验失败")
                    continue

                short_addr = result.get("source", {}).get("short_address", "unknown")
                event      = result.get("event", "zigbee_zcl_receive")
                rssi       = result.get("radio", {}).get("rssi_dbm", 0)
                print(f"[解析] 设备:{short_addr}  事件:{event}  RSSI:{rssi}dBm")

                # 只发布传感器事件到应用层主题
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

        except Exception as exc:
            print(f"[错误] 处理消息失败: {exc}")
            import traceback
            traceback.print_exc()

    def _extract_frames(self) -> list[bytes]:
        """从buffer中提取完整Ebyte帧，容忍噪声"""
        frames: list[bytes] = []
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

            total = self._buffer[1] + 2   # LEN + 2（55和CHECKSUM）
            if total < 5:
                del self._buffer[0]
                continue
            if len(self._buffer) < total:
                break

            frames.append(bytes(self._buffer[:total]))
            del self._buffer[:total]

        return frames

    def run(self) -> None:
        print("=" * 60)
        print("MQTT版本 Zigbee网关桥接器")
        print("=" * 60)
        print(f"Broker:       {self.broker}:{self.port}")
        print(f"订阅(网关):   {GATEWAY_UPLINK_TOPIC}")
        print(f"发布(应用):   {APP_UPLINK_PREFIX}/{{device}}/data")
        print("=" * 60)
        self.client.connect_async(self.broker, self.port, MQTT_KEEPALIVE)
        self.client.loop_forever()


if __name__ == "__main__":
    MqttBridge(MQTT_BROKER, MQTT_PORT).run()
