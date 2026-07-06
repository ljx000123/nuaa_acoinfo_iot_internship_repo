from dataclasses import asdict
from typing import Any, Dict

from .schema import DeviceCommand, DeviceData


def mqtt_payload_to_vsoa_model(device_data: DeviceData) -> Dict[str, Any]:
    return {
        "resource": f"/devices/{device_data.protocol}/{device_data.device_id}",
        "method": "updateTelemetry",
        "body": asdict(device_data),
    }


def vsoa_command_to_mqtt_payload(command: DeviceCommand) -> Dict[str, Any]:
    return {
        "request_id": command.request_id,
        "device_id": command.device_id,
        "command": command.command,
        "params": command.params,
    }


def build_downlink_topic(template: str, command: DeviceCommand) -> str:
    return template.format(protocol=command.protocol, device_id=command.device_id)
