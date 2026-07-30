"""
Integration tests — offline full pipeline validation.

These tests start a bridge instance in --no-mqtt mode, inject LoRa
and Zigbee messages via TCP 9090, then verify via VSOA RPC.

Requires: vsoa-python library and pytest.
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent  # bridge-merged/
MAIN = ROOT / "src" / "main.py"
CONFIG = ROOT / "config.yaml"

BRIDGE_HOST = "127.0.0.1"
VSOA_PORT = 3001
TCP_INJECT_PORT = 9090
LORA_DEV_EUI = "24e124136d000001"

# VSOA Server unification completed — UplinkVsoaServer + RpcServer now share
# the unified vsoa.Server instance managed by main.py.
# vsoa is imported inside fixtures (not at module level) to avoid a
# pytest-on-Windows issue where module-level import affects the bridge
# subprocess's VSOA server socket binding.


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

def _free_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((BRIDGE_HOST, 0))
        return int(s.getsockname()[1])


@pytest.fixture(scope="session")
def bridge_process(tmp_path_factory):
    """Start the bridge in --no-mqtt mode for the test session."""
    global VSOA_PORT, TCP_INJECT_PORT
    VSOA_PORT = _free_tcp_port()
    TCP_INJECT_PORT = _free_tcp_port()
    config_path = tmp_path_factory.mktemp("bridge-config") / "config.yaml"
    config_path.write_text(
        f"""
bridge:
  name: "MQTT-VSOA Bridge"
  version: "1.0.0"
vsoa:
  server:
    bind_host: "{BRIDGE_HOST}"
    port: {VSOA_PORT}
  business_server:
    auto_start: false
uplink:
  tcp_inject_port: {TCP_INJECT_PORT}
  max_devices: 64
  adapters: ["lora", "zigbee", "generic"]
scene_engine:
  enabled: false
chirpstack:
  enabled: true
""".strip(),
        encoding="utf-8",
    )
    proc = subprocess.Popen(
        [
            sys.executable,
            str(MAIN),
            "--config",
            str(config_path),
            "--no-mqtt",
            "--uplink-only",
        ],
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # Wait for bridge to be ready
    deadline = time.time() + 10
    ready = False
    while time.time() < deadline:
        if proc.poll() is not None:
            pytest.fail("Bridge process exited before test ports were ready")
        try:
            s = socket.create_connection((BRIDGE_HOST, TCP_INJECT_PORT), timeout=0.5)
            s.close()
            ready = True
            break
        except (ConnectionRefusedError, OSError):
            time.sleep(0.3)
    if not ready:
        proc.kill()
        proc.wait()
        pytest.fail("Bridge did not start within 10 seconds")
    # Give VSOA server time to finish internal initialization
    time.sleep(1.0)
    yield proc
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture(scope="session")
def vsoa_client(bridge_process):
    """Create a VSOA client connected to the bridge.

    Depends on bridge_process to ensure the bridge is running first.
    """
    import threading
    import vsoa as _vsoa
    client = _vsoa.Client()
    client.connect(f"vsoa://{BRIDGE_HOST}:{VSOA_PORT}")
    threading.Thread(target=client.run, daemon=True).start()
    time.sleep(0.3)
    yield client


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _inject(obj: dict) -> None:
    """Send a JSON Lines command to the TCP inject port."""
    line = json.dumps(obj) + "\n"
    s = socket.create_connection((BRIDGE_HOST, TCP_INJECT_PORT), timeout=2)
    try:
        s.sendall(line.encode("utf-8"))
    finally:
        s.close()


def _fetch(client, url: str) -> dict:
    """Query a VSOA RPC URL and return the parsed reply."""
    import vsoa as _vsoa
    header, reply, status = client.fetch(url, payload=_vsoa.Payload(param={}), timeout=5.0)
    if reply and hasattr(reply, "param") and reply.param:
        if isinstance(reply.param, dict):
            return reply.param
        if isinstance(reply.param, str):
            try:
                return json.loads(reply.param)
            except json.JSONDecodeError:
                pass
    return {}


# ========================================================================
# Tests
# ========================================================================

class TestBridgeHealth:
    def test_health(self, vsoa_client):
        data = _fetch(vsoa_client, "/bridge/health")
        assert data.get("service") == "MQTT-VSOA Bridge"
        assert data.get("status") == "running"
        assert "devices" in data
        assert "version" in data

    def test_adapter_list(self, vsoa_client):
        data = _fetch(vsoa_client, "/adapter/list")
        assert data.get("count") >= 1
        assert "adapters" in data

    def test_schema(self, vsoa_client):
        data = _fetch(vsoa_client, "/uplink/schema")
        assert data.get("schema") == "uplink_report.v3"


class TestLoraEndToEnd:
    def test_lora_inject_and_query(self, vsoa_client):
        _inject({
            "cmd": "mqtt_message",
            "topic": "bridge/uplink/lora/lora_env_01/data",
            "payload": {
                "devEUI": LORA_DEV_EUI,
                "deviceName": "lora_env_01",
                "timestamp": 1783329001000,
                "fPort": 2,
                "rxInfo": [{"rssi": -57, "loRaSNR": 8.2}],
                "object": {"temperature": 23.6, "humidity": 56.2, "battery": 92},
            },
        })
        time.sleep(0.5)

        data = _fetch(vsoa_client, f"/device/{LORA_DEV_EUI}/data")
        assert data.get("device_id") == LORA_DEV_EUI
        assert data.get("name") == "lora_env_01"
        assert data.get("source") == "lora"
        assert data.get("adapter") == "lora_adapter"
        assert data["raw"]["temperature"] == 23.60
        assert data["raw"]["humidity"] == 56.20
        assert data["raw"]["battery"] == 92
        assert data["raw"]["signal"] == -57
        assert data["raw"]["snr"] == 8.20
        assert data.get("type") == "multi"


class TestZigbeeEndToEnd:
    def test_zigbee_inject_and_query(self, vsoa_client):
        _inject({
            "cmd": "mqtt_message",
            "topic": "bridge/uplink/zigbee/zigbee_env_01/data",
            "payload": {
                "ieeeAddr": "0x00124b0024c00001",
                "friendly_name": "zigbee_env_01",
                "last_seen": 1783329002000,
                "linkquality": 154,
                "battery": 85,
                "temperature": 25.1,
                "humidity": 60.4,
                "status": "online",
            },
        })
        time.sleep(0.5)

        data = _fetch(vsoa_client, "/device/zigbee_env_01/data")
        assert data.get("device_id") == "zigbee_env_01"
        assert data.get("source") == "zigbee"
        assert data.get("adapter") == "zigbee_adapter"
        assert data["raw"]["temperature"] == 25.10
        assert data["raw"]["humidity"] == 60.40
        assert data["raw"]["battery"] == 85
        assert data["raw"]["signal"] == 154


class TestErrorCases:
    def test_device_not_found(self, vsoa_client):
        data = _fetch(vsoa_client, "/device/nonexistent/data")
        assert data.get("error") == "Device not found"

    def test_ping_does_not_crash(self, vsoa_client):
        _inject({"cmd": "ping"})
        time.sleep(0.3)
        # bridge should still be healthy
        data = _fetch(vsoa_client, "/bridge/health")
        assert data.get("status") == "running"

    def test_unknown_cmd_does_not_crash(self, vsoa_client):
        _inject({"cmd": "unknown_cmd"})
        time.sleep(0.3)
        data = _fetch(vsoa_client, "/bridge/health")
        assert data.get("status") == "running"


class TestDeviceList:
    def test_device_list_includes_injected_devices(self, vsoa_client):
        # Ensure we have some devices from previous tests
        data = _fetch(vsoa_client, "/device/list")
        assert data.get("count", 0) >= 1
        dev_ids = [d["device_id"] for d in data.get("devices", [])]
        assert LORA_DEV_EUI in dev_ids
        assert "zigbee_env_01" in dev_ids

    def test_device_all_data(self, vsoa_client):
        data = _fetch(vsoa_client, "/device/all/data")
        assert data.get("count", 0) >= 1
        dev_ids = [d["device_id"] for d in data.get("data", [])]
        assert LORA_DEV_EUI in dev_ids


class TestDeviceUpdate:
    def test_report_count_increments(self, vsoa_client):
        _inject({
            "cmd": "mqtt_message",
            "topic": "bridge/uplink/lora/lora_env_01/data",
            "payload": {
                "devEUI": LORA_DEV_EUI,
                "deviceName": "lora_env_01",
                "timestamp": int(time.time() * 1000),
                "object": {"temperature": 24.0},
            },
        })
        time.sleep(0.5)

        data = _fetch(vsoa_client, f"/device/{LORA_DEV_EUI}/data")
        # report_count should have increased (at least 2 by now)
        assert data.get("report_count", 0) >= 2
