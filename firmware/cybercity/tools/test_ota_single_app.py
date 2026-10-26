"""Host-side tests for the explicit single-app OTA installer."""
import hashlib
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest

SOURCE = Path(__file__).resolve().parent.parent / "esp32" / "ota_single_app.py"
staging = types.ModuleType("ota_staging")
staging._sha256_file = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
remote = types.ModuleType("secure_stage")
remote.request_manifest = lambda mac: {}
remote.wifi_mac = lambda: "AA:BB:CC:DD:EE:FF"
remote.stage_files = lambda: None
sys.modules["ota_staging"] = staging
sys.modules["secure_stage"] = remote
spec = importlib.util.spec_from_file_location("ota_single_app", SOURCE)
ota = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ota)


class SingleAppOTATests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = os.getcwd()
        os.chdir(self.tmp.name)
        Path("main.py").write_bytes(b"old")
        Path("bootstrap_config.py").write_bytes(b"private")
        Path("staging-v2").mkdir()
        self.payload = b"new"
        Path("staging-v2/main.py").write_bytes(self.payload)
        self.manifest = {"version": 2, "files": [
            {"path": "main.py", "sha256": hashlib.sha256(self.payload).hexdigest()}]}

    def tearDown(self):
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def test_requires_approval(self):
        with self.assertRaisesRegex(ValueError, "approve"):
            ota.install_staged_main(self.manifest, "staging-v2")
        self.assertEqual(Path("main.py").read_bytes(), b"old")

    def test_bad_digest_leaves_current_intact(self):
        self.manifest["files"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "integrity"):
            ota.install_staged_main(self.manifest, "staging-v2", approve=True)
        self.assertEqual(Path("main.py").read_bytes(), b"old")

    def test_rejects_library_install(self):
        self.manifest["files"].append({"path": "lib/test.py", "sha256": "0" * 64})
        with self.assertRaisesRegex(ValueError, "multi-file"):
            ota.install_staged_main(self.manifest, "staging-v2", approve=True)

    def test_single_file_install_preserves_bootstrap(self):
        version = ota.install_staged_main(self.manifest, "staging-v2", approve=True)
        self.assertEqual(version, 2)
        self.assertEqual(Path("main.py").read_bytes(), b"new")
        self.assertEqual(Path("bootstrap_config.py").read_bytes(), b"private")
        self.assertEqual(ota._read_version(), 2)


if __name__ == "__main__":
    unittest.main()
