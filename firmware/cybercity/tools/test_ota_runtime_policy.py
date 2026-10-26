"""Regression contract for opt-in automatic OTA in the ESP32 runtime."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent / "esp32"


class RuntimePolicyTests(unittest.TestCase):
    def test_defaults_are_disabled(self):
        cfg = (ROOT / "ota_runtime_config.example.py").read_text()
        self.assertIn("OTA_CHECK_ENABLED = False", cfg)
        self.assertIn("OTA_AUTO_INSTALL_ENABLED = False", cfg)

    def test_only_successful_install_requests_restart(self):
        src = (ROOT / "device_startup.py").read_text()
        self.assertIn("allow_install=OTA_AUTO_INSTALL_ENABLED is True", src)
        self.assertIn("restart_requested[0] = True", src)
        self.assertIn("if restart_requested[0]:", src)
        self.assertIn("result['result'].get('restart_required') is True", src)

    def test_mqtt_cleanup_before_restart(self):
        mqtt = (ROOT / "mqtt_controller.py").read_text()
        startup = (ROOT / "device_startup.py").read_text()
        self.assertIn("if on_idle() is True:", mqtt)
        self.assertIn("self.safe_outputs()", mqtt)
        self.assertIn("controller.run(on_idle=idle_callback)", startup)
        self.assertIn("from machine import reset", startup)


if __name__ == "__main__":
    unittest.main()
