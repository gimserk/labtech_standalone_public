"""Tests for the non-executing activation gate."""
import hashlib
import importlib.util
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parent.parent / "esp32"

def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

import sys
sys.modules["ota_staging"] = load("ota_staging")
activation = load("ota_activation")


class ActivationTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.original = os.getcwd()
        os.chdir(self.temp.name)
        os.mkdir("staging-v3")
        Path("staging-v3/main.py").write_bytes(b"print('candidate')\n")
        self.manifest = {"version": 3, "files": [{
            "path": "main.py",
            "sha256": hashlib.sha256(Path("staging-v3/main.py").read_bytes()).hexdigest(),
            "url": "https://labtech.example.test/api/firmware/v2/download/3/"
        }]}

    def tearDown(self):
        os.chdir(self.original)
        self.temp.cleanup()

    def test_requires_explicit_approval(self):
        with self.assertRaises(ValueError):
            activation.prepare_activation(self.manifest, "staging-v3")
        self.assertFalse(Path("ota-pending.json").exists())

    def test_tampering_rejected(self):
        Path("staging-v3/main.py").write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "integrity"):
            activation.prepare_activation(self.manifest, "staging-v3", approve=True)

    def test_pending_gate_does_not_install(self):
        record = activation.prepare_activation(self.manifest, "staging-v3", approve=True)
        self.assertEqual(record["state"], "pending")
        self.assertTrue(Path("ota-pending.json").exists())
        self.assertFalse(Path("main.py").exists())
        with self.assertRaisesRegex(ValueError, "already pending"):
            activation.prepare_activation(self.manifest, "staging-v3", approve=True)
        activation.cancel_activation()
        self.assertFalse(Path("ota-pending.json").exists())


if __name__ == "__main__":
    unittest.main()
