"""Dry-run USB installer tests for a pre-flashed MicroPython ESP32."""
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

P = Path(__file__).with_name("usb_install.py")
spec = importlib.util.spec_from_file_location("usb_install", P)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class USBInstallTests(unittest.TestCase):
    def test_missing_secrets_refuses_install(self):
        with TemporaryDirectory() as d:
            for filename in mod.APPLICATION:
                (Path(d) / filename).write_text("pass\n")
            with self.assertRaisesRegex(ValueError, "Missing required"):
                mod.prepare_commands("COM5", d)

    def test_placeholder_credentials_rejected(self):
        with TemporaryDirectory() as d:
            for filename in mod.APPLICATION + mod.CONFIGURATION:
                (Path(d) / filename).write_text("REPLACE_ME")
            with self.assertRaisesRegex(ValueError, "placeholder"):
                mod.prepare_commands("COM5", d)

    def test_correct_files_and_no_boot_py(self):
        with TemporaryDirectory() as d:
            for filename in mod.APPLICATION + mod.CONFIGURATION:
                (Path(d) / filename).write_text("placeholder\n")
            (Path(d) / "bootstrap_config.py").write_text(
                'LABTECH_URL = "https://labtech.local"\\nDEVICE_KEY = "testkey"\\n'
            )
            (Path(d) / "mqtt_secrets.py").write_text(
                'MQTT_USER = "device1"\\nMQTT_PASSWORD = "secret"\\n'
            )
            cmds = mod.prepare_commands("COM5", d)
            self.assertEqual(len(cmds), 4)
            self.assertTrue(all(c[0:3] == ["mpremote", "connect", "COM5"] for c in cmds))
            self.assertNotIn("boot.py", [Path(c[-2]).name for c in cmds])
            self.assertNotIn("main.py", [Path(c[-2]).name for c in cmds])


if __name__ == "__main__":
    unittest.main()
