"""Host-side validation of MicroPython staging helpers."""
import importlib.util
import pathlib
import tempfile
import unittest

module_path = pathlib.Path(__file__).resolve().parent.parent / "esp32" / "ota_staging.py"
spec = importlib.util.spec_from_file_location("ota_staging", module_path)
staging = importlib.util.module_from_spec(spec)
spec.loader.exec_module(staging)


class StageTests(unittest.TestCase):
    def manifest(self, path="main.py"):
        return {"files": [{
            "path": path,
            "sha256": "0" * 64,
            "url": "https://labtech.example.test/api/firmware/v2/download/1/",
        }]}

    def test_rejects_escape(self):
        for path in ("../main.py", "/main.py", "lib/../../x.py", "boot.py",
                     "lib\\evil.py", "lib/.py"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                staging.validate_manifest(self.manifest(path))

    def test_rejects_duplicate(self):
        m = self.manifest()
        m["files"].append(m["files"][0].copy())
        with self.assertRaises(ValueError):
            staging.validate_manifest(m)

    def test_valid_lib(self):
        m = self.manifest()
        m["files"].append({"path": "lib/sensor.py",
                           "sha256": "a"*64,
                           "url": "https://labtech.example.test/lib"})
        self.assertEqual(len(staging.validate_manifest(m)), 2)

    def test_digest_mismatch_does_not_activate(self):
        with tempfile.TemporaryDirectory() as root:
            source = pathlib.Path(root) / "download.part"
            target = pathlib.Path(root) / "main.py"
            source.write_bytes(b"hello")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                staging.commit_staged_file(str(source), str(target), "0"*64)
            self.assertFalse(target.exists())
            self.assertTrue(source.exists())


if __name__ == "__main__":
    unittest.main()
