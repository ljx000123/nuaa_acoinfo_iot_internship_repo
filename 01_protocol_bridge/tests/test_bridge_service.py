import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bridge.bridge_service import BridgeService
from bridge.config_loader import load_config
from bridge.schema import SchemaError


def make_service() -> BridgeService:
    config = load_config(PROJECT_ROOT / "config" / "bridge_config.yaml")
    return BridgeService(config)


def test_mqtt_uplink_to_vsoa() -> None:
    service = make_service()
    payload = (PROJECT_ROOT / "examples" / "uplink_lora.json").read_text(encoding="utf-8")

    result = service.handle_mqtt_uplink("iot/lora/node-001/uplink", payload)

    assert result["result"]["status"] == "ok"
    assert result["vsoa_model"]["method"] == "updateTelemetry"
    assert result["vsoa_model"]["body"]["device_id"] == "node-001"


def test_vsoa_downlink_to_mqtt() -> None:
    service = make_service()
    payload = json.loads((PROJECT_ROOT / "examples" / "downlink_command.json").read_text(encoding="utf-8"))

    result = service.handle_vsoa_downlink(payload)

    assert result["topic"] == "iot/zigbee/cc2530-001/downlink"
    assert result["payload"]["command"] == "set_led"
    assert result["command_result"]["status"] == "accepted"


def test_invalid_uplink_missing_field() -> None:
    service = make_service()
    invalid_payload = json.dumps({"protocol": "lora", "device_id": "node-001"})

    try:
        service.handle_mqtt_uplink("iot/lora/node-001/uplink", invalid_payload)
    except SchemaError as exc:
        assert "Missing required fields" in str(exc)
    else:
        raise AssertionError("Expected SchemaError")

