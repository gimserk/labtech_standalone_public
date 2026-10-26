"""Local-broker Cyber City MQTT test using simulated ESP32 GPIO.

Run ONLY against the loopback test broker. This verifies topic wiring,
v1 command decoding, physical-output simulation, retained pin status and
correlated non-retained ACK. It does not test VM agent or Proxmox.
"""
import os
import sys
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

try:
    import paho.mqtt.client as mqtt
except ImportError as exc:
    raise SystemExit("Install test dependency: pip install paho-mqtt>=2,<3") from exc

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "firmware" / "cybercity" / "esp32"))
from app.cybercity_mqtt_protocol import encode_command, decode_device_report
from command_protocol import decode_command, CommandError

HOST = os.getenv("CYBERCITY_TEST_MQTT_HOST", "127.0.0.1")
PORT = int(os.getenv("CYBERCITY_TEST_MQTT_PORT", "18884"))
if HOST not in ("127.0.0.1", "localhost", "::1"):
    raise SystemExit("Refusing non-loopback MQTT broker. Test only on an isolated local broker.")


def client(name):
    return mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=name)


class SimulatedESP32:
    def __init__(self, broker, base):
        self.base = base
        self.command_topic = base + "/pins/led/command"
        self.status_topic = base + "/pins/led/status"
        self.ack_topic = base + "/pins/led/ack"
        self.online_topic = base + "/devices/sim/status"
        self.output = 0
        self.ids = set()
        self.connected = threading.Event()
        self.client = client("cc-esp32-" + uuid.uuid4().hex[:10])
        self.client.on_connect = self._connected
        self.client.on_message = self._message
        self.client.will_set(self.online_topic, "offline", qos=1, retain=True)
        self.client.connect(broker, PORT, keepalive=30)
        self.client.loop_start()
        if not self.connected.wait(5):
            raise TimeoutError("Simulated ESP32 could not connect to test broker")

    def _connected(self, client_obj, userdata, flags, reason_code, properties):
        if reason_code == 0:
            client_obj.subscribe(self.command_topic, qos=1)
            client_obj.publish(self.online_topic, "online", qos=1, retain=True)
            self.connected.set()

    def _message(self, client_obj, userdata, message):
        try:
            command_id, command = decode_command(message.payload)
            command = command.lower()\n            if command not in ("on", "off", "1", "0"):
                return
            if command_id not in self.ids:
                self.output = 1 if command in ("on", "1") else 0
                self.ids.add(command_id)
            client_obj.publish(self.status_topic, str(self.output), qos=1, retain=True)
            report = __import__("json").dumps({
                "schema": 1, "command_id": command_id,
                "status": "executed", "state": self.output})
            client_obj.publish(self.ack_topic, report, qos=1, retain=False)
        except (CommandError, ValueError):
            pass

    def close(self):
        self.client.publish(self.online_topic, "offline", qos=1, retain=True).wait_for_publish()
        self.client.disconnect()
        self.client.loop_stop()


class BrokerSimulationTests(unittest.TestCase):
    def setUp(self):
        self.base = "cybercity/milestone1/" + uuid.uuid4().hex
        self.ack = threading.Event()
        self.status = threading.Event()
        self.responses = []
        self.states = []
        self.monitor = client("cc-test-" + uuid.uuid4().hex[:10])
        self.monitor.on_message = self._message
        self.monitor.connect(HOST, PORT, keepalive=30)
        self.monitor.subscribe([(self.base + "/pins/led/ack", 1),
                                (self.base + "/pins/led/status", 1)])
        self.monitor.loop_start()
        self.device = SimulatedESP32(HOST, self.base)

    def tearDown(self):
        self.device.close()
        self.monitor.disconnect()
        self.monitor.loop_stop()

    def _message(self, client_obj, userdata, message):
        if message.topic.endswith("/ack"):
            self.responses.append(message.payload)
            self.ack.set()
        else:
            self.states.append(message.payload.decode())
            self.status.set()

    def test_published_command_changes_simulated_gpio_and_receives_correlated_ack(self):
        command_id = uuid.uuid4()
        packet = encode_command(command_id, "set", "on",
                                datetime.now(timezone.utc) + timedelta(minutes=2))
        info = self.monitor.publish(self.device.command_topic, packet, qos=1, retain=False)
        info.wait_for_publish(timeout=5)
        self.assertTrue(self.ack.wait(8), "No ESP32 acknowledgment")
        self.assertTrue(self.status.wait(8), "No pin status")
        validated = decode_device_report(self.responses[-1], expected_command_id=command_id)
        self.assertEqual(validated["status"], "executed")
        self.assertEqual(validated["state"], 1)
        self.assertEqual(self.device.output, 1)
        self.assertIn("1", self.states)


if __name__ == "__main__":
    unittest.main()
