from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bridge.bridge_service import BridgeService
from bridge.config_loader import load_config


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    config = load_config(PROJECT_ROOT / "config" / "bridge_config.yaml")
    service = BridgeService(config)

    lora_payload = (PROJECT_ROOT / "examples" / "uplink_lora.json").read_text(encoding="utf-8")
    zigbee_payload = (PROJECT_ROOT / "examples" / "uplink_zigbee.json").read_text(encoding="utf-8")
    command_payload = read_json(PROJECT_ROOT / "examples" / "downlink_command.json")

    print("\n=== MQTT -> VSOA: LoRa uplink ===")
    print(json.dumps(service.handle_mqtt_uplink("iot/lora/node-001/uplink", lora_payload), ensure_ascii=False, indent=2))

    print("\n=== MQTT -> VSOA: ZigBee uplink ===")
    print(json.dumps(service.handle_mqtt_uplink("iot/zigbee/cc2530-001/uplink", zigbee_payload), ensure_ascii=False, indent=2))

    print("\n=== VSOA -> MQTT: Downlink command ===")
    print(json.dumps(service.handle_vsoa_downlink(command_payload), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

