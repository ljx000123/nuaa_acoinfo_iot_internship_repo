"""
LoRa / LoRaWAN adapter.

Handles MQTT payloads from LoRaWAN gateways, converting them into the
unified :class:`UplinkReport` model.
"""

from __future__ import annotations

import base64
from datetime import datetime
from typing import Any

from .base import (
    Adapter,
    AdapterParseError,
    UplinkReport,
    _first_numeric,
    _first_str,
    DEVICE_ID_ALIASES,
    extract_device_id_from_topic,
    infer_type,
    infer_unit,
    parse_common_measurements,
    topic_has_segment,
)


class LoraAdapter(Adapter):
    """Adapter for LoRa / LoRaWAN device payloads."""

    name = "lora_adapter"
    source = "lora"

    # ------------------------------------------------------------------
    def match(self, topic: str, payload: dict[str, Any]) -> bool:
        """Match if *topic* contains 'lora' or payload contains LoRa fields."""
        if (
            topic_has_segment(topic, "lora")
            or topic.startswith("application/")
        ):
            return True
        return any(
            k in payload
            for k in ("devEUI", "dev_eui", "fPort", "rxInfo", "deviceInfo")
        )

    # ------------------------------------------------------------------
    def parse(self, topic: str, payload: dict[str, Any]) -> UplinkReport:
        """Parse a LoRa/LoRaWAN MQTT payload into an UplinkReport."""
        report = UplinkReport()
        report.source = "lora"
        report.adapter = "lora_adapter"
        report.topic = topic

        # -- ChirpStack deviceInfo 子对象（常见于 application/... topic） --
        device_info = payload.get("deviceInfo")
        if not isinstance(device_info, dict):
            device_info = {}

        # Keep every original payload field, then enrich it with normalized
        # device metadata and the optional 16/20-byte business frame.
        working = dict(payload)
        if device_info:
            working.setdefault("deviceName", device_info.get("deviceName"))
            working.setdefault("devEUI", device_info.get("devEui"))

        encoded = payload.get("data")
        has_binary = isinstance(encoded, str) and bool(encoded)
        if has_binary:
            try:
                binary = base64.b64decode(encoded, validate=True)
            except Exception as exc:
                raise AdapterParseError(f"invalid Base64 data: {exc}") from exc
            if binary[:2] in {b"HC", b"HP"}:
                # HC chunks and HP status packets belong to the camera
                # reassembler. Their lengths must never be interpreted as
                # the legacy environmental frame.
                working["type"] = "camera"
                working["camera_transport"] = "lorawan_hcv3"
                working["camera_packet"] = "chunk" if binary[:2] == b"HC" else "status"
                working["binary_length"] = len(binary)
                decoded = None
            else:
                decoded = parse_lora_binary(binary)
            if decoded is None and "binary_length" not in working:
                # ChirpStack may carry a device-specific frame. Keep the
                # original Base64 payload and its size instead of dropping it.
                working["binary_length"] = len(binary)
            elif decoded is not None:
                working.update(decoded)

        # -- common measurements (temperature, humidity, battery, signal, …) --
        parse_common_measurements(working, report)

        # -- device id —
        #   Prefer the stable LoRaWAN devEUI over the human-readable deviceName
        #   so scene rules can target the physical device identifier shown in
        #   MQTT topics.
        report.device_id = (
            _first_str(working, ["device_id", "devEUI", "dev_eui", "deviceName"])
            or _extract_device_info_dev_eui(payload)
            or extract_device_id_from_topic(topic)
        )

        # -- name (use deviceName as a human-readable fallback) --
        if not report.name:
            report.name = (
                device_info.get("deviceName", "")
                or working.get("deviceName", "")
            )

        # -- LoRa-specific: rxInfo[0].rssi -> signal, rxInfo[0].loRaSNR -> snr --
        _extract_rxinfo(payload, report)

        # -- ChirpStack 扩展: 提取 dev_eui（方案 B） —
        #   优先级: deviceInfo.devEui > 顶层 devEUI/dev_eui > topic
        report.dev_eui = (
            device_info.get("devEui", "")
            or _first_str(payload, ["devEUI", "dev_eui"])
            or _extract_dev_eui_from_topic(topic)
        )

        # -- ChirpStack 扩展: 提取 app_id（方案 B） —
        #   优先级: deviceInfo.applicationId > topic extraction
        report.app_id = (
            device_info.get("applicationId", "")
            or device_info.get("applicationName", "")
            or _extract_app_id_from_topic(topic)
        )

        # -- object sub-document --
        obj = payload.get("object")
        if isinstance(obj, dict):
            parse_common_measurements(obj, report)

        if not report.timestamp and isinstance(payload.get("time"), str):
            try:
                report.timestamp = int(
                    datetime.fromisoformat(payload["time"].replace("Z", "+00:00")).timestamp()
                    * 1000
                )
            except ValueError:
                pass

        # -- post-processing --
        infer_type(report)
        infer_unit(report)

        if not report.device_id:
            raise AdapterParseError("LoRa payload missing device id")

        return report


def parse_lora_binary(payload: bytes) -> dict[str, Any] | None:
    """Decode the LoRa group's legacy/environment business frames."""
    if len(payload) == 37 and payload[:3] == b"\x02\x05\x02":
        analog_1 = int.from_bytes(payload[29:31], "big", signed=False)
        analog_2 = int.from_bytes(payload[31:33], "big", signed=False)
        analog_3 = int.from_bytes(payload[33:35], "big", signed=False)
        return {
            "temperature": int.from_bytes(payload[3:5], "little", signed=True) / 1000.0,
            "humidity": int.from_bytes(payload[5:7], "little", signed=False) / 100.0,
            "frame_type": "ebyte_env_v2",
            "frame_counter": int.from_bytes(payload[8:10], "big", signed=False),
            "status_code": payload[22],
            "mode_code": payload[23],
            "sensor_code": int.from_bytes(payload[24:26], "little", signed=True),
            "analog_1": analog_1,
            "analog_2": analog_2,
            "analog_3": analog_3,
            "analog_1_percent": round((4095 - analog_1) * 100 / 4095, 1),
            "analog_2_percent": round((4095 - analog_2) * 100 / 4095, 1),
            "analog_3_percent": round((4095 - analog_3) * 100 / 4095, 1),
            "tail_code": int.from_bytes(payload[35:37], "big", signed=False),
            "raw_frame_hex": payload.hex(),
        }
    if len(payload) >= 37 and payload[0] in (2, 3):
        flags = payload[1]
        temperature = int.from_bytes(payload[21:23], "big", signed=True) / 10.0
        humidity = int.from_bytes(payload[23:25], "big", signed=False) / 10.0
        soil_moisture = int.from_bytes(payload[25:27], "big", signed=False) / 10.0
        precipitation = int.from_bytes(payload[27:29], "big", signed=False) / 10.0
        return {
            "version": 2,
            "frame_type": "s3_lorawan_v2",
            "joined": bool(flags & 0x01),
            "motor_running": bool(flags & 0x02),
            "led_on": bool(flags & 0x04),
            "application_retry": bool(flags & 0x08),
            "flags": hex(flags),
            "seq": int.from_bytes(payload[2:4], "big", signed=False),
            "boot_id": hex(int.from_bytes(payload[4:8], "big", signed=False)),
            "temperature": temperature,
            "humidity": humidity,
            "soil_moisture": soil_moisture,
            "soil": soil_moisture,
            "precipitation": precipitation,
            "rainfall": precipitation,
            "rain": precipitation,
            "motor": payload[33],
            "servo": payload[34],
            "led": payload[35],
            "signal": int.from_bytes(payload[36:37], "big", signed=True),
            "raw_frame_hex": payload.hex(),
        }
    if len(payload) not in {16, 20}:
        return None
    decoded = {
        "seq": int.from_bytes(payload[0:2], "big"),
        "boot_id": hex(int.from_bytes(payload[2:6], "big")),
        "send_time_ms": int.from_bytes(payload[6:10], "big"),
        "lorawan_retry_count": payload[10],
        "temperature": int.from_bytes(payload[11:13], "big", signed=True) / 10.0,
        "humidity": int.from_bytes(payload[13:15], "big") / 10.0,
    }
    flags_index = 15
    if len(payload) == 20:
        decoded.update({
            "soil_moisture": int.from_bytes(payload[15:17], "big") / 10.0,
            "precipitation": int.from_bytes(payload[17:19], "big") / 10.0,
        })
        flags_index = 19
    decoded.update({
        "joined": bool(payload[flags_index] & 0x01),
        "application_retry": bool(payload[flags_index] & 0x08),
        "flags": hex(payload[flags_index]),
    })
    return decoded


def _extract_rxinfo(payload: dict[str, Any], report: UplinkReport) -> None:
    """Extract signal / snr from ``rxInfo`` array into ``report.raw`` if not already set."""
    rx_info = payload.get("rxInfo")
    if not isinstance(rx_info, list) or not rx_info:
        return
    first = rx_info[0]
    if not isinstance(first, dict):
        return
    if "signal" not in report.raw:
        report.raw["signal"] = _first_numeric(first, ["rssi"])
    if "snr" not in report.raw:
        snr_val = _first_numeric(first, ["loRaSNR", "snr"])
        if snr_val is not None:
            report.raw["snr"] = float(snr_val) if isinstance(snr_val, (int, float)) else snr_val




def _extract_dev_eui_from_topic(topic: str) -> str:
    """从 ChirpStack topic 提取 DevEUI。

    ChirpStack topic: application/{app_id}/device/{dev_eui}/event/up
    DevEUI 在 index 3。
    """
    parts = topic.rstrip("/").split("/")
    if len(parts) >= 4 and parts[0] == "application" and parts[2] == "device":
        return parts[3]
    return ""


def _extract_app_id_from_topic(topic: str) -> str:
    """从 ChirpStack topic 提取 application ID。

    ChirpStack topic: application/{app_id}/device/{dev_eui}/event/up
    app_id 在 index 1。
    """
    parts = topic.rstrip("/").split("/")
    if len(parts) >= 4 and parts[0] == "application" and parts[2] == "device":
        return parts[1]
    return ""


def _extract_device_info_dev_eui(payload: dict[str, Any]) -> str | None:
    device_info = payload.get("deviceInfo")
    if not isinstance(device_info, dict):
        return None
    return _first_str(device_info, ["devEui", "devEUI", "dev_eui"])
