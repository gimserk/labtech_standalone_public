"""Host-side provisioning tests: python -m unittest discover -s firmware/cybercity/tools."""
import importlib.util
import pathlib
import tempfile
import unittest
from unittest.mock import patch

MODULE = pathlib.Path(__file__).with_name("prepare_device.py")
spec = importlib.util.spec_from_file_location("prepare_device", MODULE)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


class PrepareDeviceTests(unittest.TestCase):
    def test_rejects_http_before_request(self):
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            tool.get_config("http://example.test", "AA:BB:CC:11:22:33", "key")

    def test_rejects_invalid_mac(self):
        with self.assertRaisesRegex(ValueError, "MAC"):
            tool.get_config("https://example.test", "invalid", "key")

    def test_prepare_files_and_refuse_overwrite(self):
        config = {
            "mac_address": "AA:BB:CC:11:22:33",
            "city": {"id": 1, "name": "DNCC"},
            "building": {"id": 1, "name": "City Hall"},
            "mqtt": {"host": "mqtt.example.test", "port": 1883, "base_topic": "dncc/cityhall"},
            "pins": [{"number": 2, "name": "Light", "type": "LED", "topic": "dncc/cityhall/light"}],
        }
        with tempfile.TemporaryDirectory() as parent:
            path = pathlib.Path(parent) / "device"
            tool.prepare(path, config, "https://labtech.example.test", "secret", "wifi", "pass")
            self.assertTrue((path / "assignment.json").is_file())
            self.assertIn("DEVICE_KEY", (path / "bootstrap_config.py").read_text())
            with self.assertRaises(FileExistsError):
                tool.prepare(path, config, "https://labtech.example.test", "secret", "wifi", "pass")


if __name__ == "__main__":
    unittest.main()
