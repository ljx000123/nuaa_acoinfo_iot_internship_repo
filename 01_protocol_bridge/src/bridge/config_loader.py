from pathlib import Path
from typing import Any, Union

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - exercised when PyYAML is unavailable
    yaml = None


DEFAULT_CONFIG = {
    "project": {
        "name": "mqtt-vsoa-protocol-bridge",
        "owner": "卢静旭",
        "log_level": "INFO",
    },
    "mqtt": {
        "broker_host": "localhost",
        "broker_port": 1883,
        "client_id": "mqtt-vsoa-bridge",
        "username": "",
        "password": "",
        "uplink_topics": ["iot/lora/+/uplink", "iot/zigbee/+/uplink"],
        "downlink_topic_template": "iot/{protocol}/{device_id}/downlink",
    },
    "vsoa": {
        "mode": "mock",
        "host": "localhost",
        "port": 3000,
        "service_name": "iot_bridge_service",
    },
    "schema": {
        "required_uplink_fields": ["protocol", "device_id", "timestamp", "data"],
        "required_command_fields": ["protocol", "device_id", "command", "params"],
    },
}


def load_config(path: Union[str, Path]) -> dict:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    if yaml is None:
        return DEFAULT_CONFIG.copy()

    with config_path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}

    return data
