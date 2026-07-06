from dataclasses import asdict
from typing import Dict, List, Optional

from .schema import DeviceCommand, DeviceData


class MockVsoaService:
    """Local mock used before replacing this file with the real VSOA SDK."""

    def __init__(self) -> None:
        self.latest_data: Dict[str, dict] = {}
        self.command_history: List[dict] = []

    def update_device_data(self, device_data: DeviceData) -> dict:
        key = f"{device_data.protocol}:{device_data.device_id}"
        self.latest_data[key] = asdict(device_data)
        return {"status": "ok", "key": key}

    def query_device_data(self, protocol: str, device_id: str) -> Optional[dict]:
        return self.latest_data.get(f"{protocol}:{device_id}")

    def receive_command(self, command: DeviceCommand) -> dict:
        record = asdict(command)
        record["status"] = "accepted"
        self.command_history.append(record)
        return record
