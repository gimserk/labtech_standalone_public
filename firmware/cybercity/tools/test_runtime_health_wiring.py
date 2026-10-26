"""Structural regression tests for post-MQTT runtime check-in wiring.

These tests read source only; target-device MQTT and HTTPS tests remain required.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent / "esp32"


class RuntimeHealthWiringTests(unittest.TestCase):
    def test_controller_only_reports_after_mqtt_online_publish(self):
        code = (ROOT / "mqtt_controller.py").read_text()
        self.assertIn("def run(self, on_idle=None, on_connected=None)", code)
        online = code.index('self._publish(self.state_topic, "online")')
        callback = code.index("on_connected()", online)
        self.assertGreater(callback, online)
        self.assertIn("except (OSError, ValueError, ImportError)", code[callback:callback + 280])

    def test_startup_reports_only_from_connected_callback(self):
        code = (ROOT / "device_startup.py").read_text()
        self.assertIn("def report_connected_runtime():", code)
        self.assertIn("report_firmware(status='running')", code)
        self.assertIn("on_connected=report_connected_runtime", code)
        self.assertEqual(code.count("report_firmware("), 1)


if __name__ == "__main__":
    unittest.main()
