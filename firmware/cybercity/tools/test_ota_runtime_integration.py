"""Static integration contract checks for the MicroPython controller."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent / "esp32"


class IntegrationTests(unittest.TestCase):
    def test_report_only_runtime_wiring(self):
        startup = (ROOT / "device_startup.py").read_text()
        mqtt = (ROOT / "mqtt_controller.py").read_text()
        config = (ROOT / "ota_runtime_config.example.py").read_text()
        self.assertIn("OTA_CHECK_ENABLED = False", config)
        self.assertIn("OTAPoller(interval_seconds=", startup)
        self.assertIn("controller.run(on_idle=idle_callback)", startup)
        self.assertIn("def run(self, on_idle=None)", mqtt)
        self.assertNotIn("allow_install=True", startup)
        self.assertNotIn("update_once(", startup)


if __name__ == "__main__":
    unittest.main()
