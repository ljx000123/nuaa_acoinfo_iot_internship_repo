from dataclasses import dataclass, field
from typing import Any, Dict, List


class SchemaError(ValueError):
    pass


@dataclass
class DeviceData:
    protocol: str
    device_id: str
    timestamp: str
    data: Dict[str, Any]
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DeviceCommand:
    protocol: str
    device_id: str
    command: str
    params: Dict[str, Any]
    request_id: str = "manual-test"


def validate_required(payload: Dict[str, Any], required_fields: List[str]) -> None:
    missing = [field for field in required_fields if field not in payload]
    if missing:
        raise SchemaError(f"Missing required fields: {', '.join(missing)}")


def parse_device_data(payload: Dict[str, Any], required_fields: List[str]) -> DeviceData:
    validate_required(payload, required_fields)
    if not isinstance(payload["data"], dict):
        raise SchemaError("Field 'data' must be an object")

    return DeviceData(
        protocol=str(payload["protocol"]),
        device_id=str(payload["device_id"]),
        timestamp=str(payload["timestamp"]),
        data=payload["data"],
        meta=payload.get("meta", {}),
    )


def parse_device_command(payload: Dict[str, Any], required_fields: List[str]) -> DeviceCommand:
    validate_required(payload, required_fields)
    if not isinstance(payload["params"], dict):
        raise SchemaError("Field 'params' must be an object")

    return DeviceCommand(
        protocol=str(payload["protocol"]),
        device_id=str(payload["device_id"]),
        command=str(payload["command"]),
        params=payload["params"],
        request_id=str(payload.get("request_id", "manual-test")),
    )
