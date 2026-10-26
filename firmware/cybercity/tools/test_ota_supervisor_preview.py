"""Host-side tests for read-only firmware supervisor preview."""
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

BASE = Path(__file__).resolve().parent.parent / "esp32"

def load(name):
    spec = importlib.util.spec_from_file_location(name, BASE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

sys.modules["ota_staging"] = load("ota_staging")
preview = load("ota_supervisor_preview")


class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.previous = os.getcwd()
        os.chdir(self.temp.name)

    def tearDown(self):
        os.chdir(self.previous)
        self.temp.cleanup()

    def test_no_pending_defaults_to_current(self):
        self.assertEqual(preview.inspect_pending()["decision"], "current")

    def test_verified_candidate_is_never_activated(self):
        Path("staging-v4").mkdir()
        payload = b"print('not executed')\n"
        Path("staging-v4/main.py").write_bytes(payload)
        Path("ota-pending.json").write_text(json.dumps({
            "state": "pending", "version": 4, "directory": "staging-v4",
            "files": [{"path": "main.py", "sha256": hashlib.sha256(payload).hexdigest()}]
        }))
        self.assertEqual(preview.inspect_pending()["decision"], "candidate-verified")
        self.assertFalse(Path("main.py").exists())

    def test_corrupted_candidate_falls_back(self):
        Path("staging-v4").mkdir()
        Path("staging-v4/main.py").write_bytes(b"corrupted")
        Path("ota-pending.json").write_text(json.dumps({
            "state": "pending", "version": 4, "directory": "staging-v4",
            "files": [{"path": "main.py", "sha256": "a"*64}]
        }))
        self.assertEqual(preview.inspect_pending()["decision"], "current")

if __name__ == "__main__":
    unittest.main()
