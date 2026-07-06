import json
from typing import Any, Dict, Optional

from .logger import setup_logger
from .schema import SchemaError, parse_device_command, parse_device_data
from .transformer import build_downlink_topic, mqtt_payload_to_vsoa_model, vsoa_command_to_mqtt_payload
from .vsoa_adapter import MockVsoaService


class BridgeService:
    def __init__(self, config: Dict[str, Any], vsoa_service: Optional[MockVsoaService] = None) -> None:
        self.config = config
        self.vsoa_service = vsoa_service or MockVsoaService()
        self.logger = setup_logger()

    def handle_mqtt_uplink(self, topic: str, payload_text: str) -> Dict[str, Any]:
        self.logger.info("Received MQTT uplink topic=%s payload=%s", topic, payload_text)

        try:
            raw_payload = json.loads(payload_text)
            device_data = parse_device_data(raw_payload, self.config["schema"]["required_uplink_fields"])
            vsoa_model = mqtt_payload_to_vsoa_model(device_data)
            result = self.vsoa_service.update_device_data(device_data)
        except json.JSONDecodeError as exc:
            raise SchemaError(f"Invalid JSON payload: {exc}") from exc

        self.logger.info("Converted MQTT uplink to VSOA model=%s result=%s", vsoa_model, result)
        return {"vsoa_model": vsoa_model, "result": result}

    def handle_vsoa_downlink(self, command_payload: Dict[str, Any]) -> Dict[str, Any]:
        self.logger.info("Received VSOA command payload=%s", command_payload)

        command = parse_device_command(command_payload, self.config["schema"]["required_command_fields"])
        mqtt_payload = vsoa_command_to_mqtt_payload(command)
        topic = build_downlink_topic(self.config["mqtt"]["downlink_topic_template"], command)
        command_result = self.vsoa_service.receive_command(command)

        result = {
            "topic": topic,
            "payload": mqtt_payload,
            "command_result": command_result,
        }
        self.logger.info("Converted VSOA command to MQTT downlink=%s", result)
        return result
