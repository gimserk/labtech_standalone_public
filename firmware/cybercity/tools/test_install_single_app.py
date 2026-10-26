import hashlib
import importlib.util
import tempfile
from pathlib import Path
import unittest

path = Path(__file__).with_name("install_single_app.py")
spec = importlib.util.spec_from_file_location("install_single_app", path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class SingleAppTests(unittest.TestCase):
    def test_verified_app_only(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            (folder / "main.py").write_bytes(b"print(1)")
            manifest = {"files": [{"path": "main.py",
                                    "sha256": hashlib.sha256(b"print(1)").hexdigest()}]}
            self.assertEqual(mod.plan(folder, manifest)[0][1], "main.py")

    def test_bad_digest_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "main.py").write_bytes(b"bad")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                mod.plan(d, {"files": [{"path": "main.py", "sha256": "0"*64}]})

    def test_protected_file_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "main.py").write_bytes(b"ok")
            (Path(d) / "boot.py").write_bytes(b"bad")
            with self.assertRaisesRegex(ValueError, "Unsafe"):
                mod.plan(d, {"files": [
                    {"path": "main.py", "sha256": hashlib.sha256(b"ok").hexdigest()},
                    {"path": "boot.py", "sha256": hashlib.sha256(b"bad").hexdigest()}
                ]})


if __name__ == "__main__":
    unittest.main()
