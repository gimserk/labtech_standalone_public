"""OTA manifest consistency regression tests for single-app updating."""
import importlib.util
import hashlib
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

BASE = Path(__file__).resolve().parent.parent / "esp32"
staging = types.ModuleType("ota_staging")
staging._sha256_file = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
remote = types.ModuleType("secure_stage")
remote.wifi_mac = lambda: "AA:BB:CC:DD:EE:FF"
remote.request_manifest = lambda mac: {}
remote.stage_files = lambda manifest=None: None
sys.modules["ota_staging"] = staging
sys.modules["secure_stage"] = remote
spec = importlib.util.spec_from_file_location("ota_single_app", BASE / "ota_single_app.py")
ota = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ota)


class ConsistencyTests(unittest.TestCase):
    def test_one_manifest_used_for_staging_and_install(self):
        payload = b"updated application"
        digest = hashlib.sha256(payload).hexdigest()
        manifest = {"version": 3, "files": [{"path": "main.py", "sha256": digest}]}
        seen = []
        with tempfile.TemporaryDirectory() as tmp:
            from os import getcwd, chdir
            old = getcwd()
            try:
                chdir(tmp)
                Path("staging-v3").mkdir()
                Path("staging-v3/main.py").write_bytes(payload)
                def stage(manifest=None):
                    seen.append(manifest)
                    return "staging-v3"
                with patch.object(ota, "check_update", return_value={"available": True, "version": 3}), \
                     patch.object(ota, "request_manifest", return_value=manifest), \
                     patch.object(ota, "stage_files", side_effect=stage):
                    answer = ota.update_once(approve=True)
                self.assertEqual(answer["installed"], 3)
                self.assertIs(seen[0], manifest)
            finally:
                chdir(old)

    def test_multifile_release_refused_before_download(self):
        manifest = {"version": 4, "files": [{"path": "main.py"}, {"path": "lib/x.py"}]}
        with patch.object(ota, "check_update", return_value={"available": True, "version": 4}), \
             patch.object(ota, "request_manifest", return_value=manifest), \
             patch.object(ota, "stage_files") as download:
            with self.assertRaisesRegex(ValueError, "single-main.py"):
                ota.update_once(approve=True)
            download.assert_not_called()


    def test_previous_main_is_retained_after_success(self):
        payload = b"new app"
        manifest = {"version": 7, "files": [{"path": "main.py",
                    "sha256": hashlib.sha256(payload).hexdigest()}]}
        with tempfile.TemporaryDirectory() as tmp:
            from os import getcwd, chdir
            previous = getcwd()
            try:
                chdir(tmp)
                Path("main.py").write_bytes(b"old app")
                Path("staging-v7").mkdir()
                Path("staging-v7/main.py").write_bytes(payload)
                self.assertEqual(ota.install_staged_main(manifest, "staging-v7", approve=True), 7)
                self.assertEqual(Path("main.py").read_bytes(), payload)
                self.assertEqual(Path("main.py.ota-backup").read_bytes(), b"old app")
            finally:
                chdir(previous)

    def test_existing_backup_blocks_install(self):
        payload = b"new app"
        manifest = {"version": 8, "files": [{"path": "main.py",
                    "sha256": hashlib.sha256(payload).hexdigest()}]}
        with tempfile.TemporaryDirectory() as tmp:
            from os import getcwd, chdir
            previous = getcwd()
            try:
                chdir(tmp)
                Path("main.py").write_bytes(b"old app")
                Path("main.py.ota-backup").write_bytes(b"do not overwrite")
                Path("staging-v8").mkdir()
                Path("staging-v8/main.py").write_bytes(payload)
                with self.assertRaisesRegex(ValueError, "Existing OTA backup"):
                    ota.install_staged_main(manifest, "staging-v8", approve=True)
                self.assertEqual(Path("main.py").read_bytes(), b"old app")
                self.assertEqual(Path("main.py.ota-backup").read_bytes(), b"do not overwrite")
            finally:
                chdir(previous)

    def test_promotion_failure_restores_previous_application(self):
        payload = b"new app"
        manifest = {"version": 9, "files": [{"path": "main.py",
                    "sha256": hashlib.sha256(payload).hexdigest()}]}
        with tempfile.TemporaryDirectory() as tmp:
            from os import getcwd, chdir
            previous = getcwd()
            try:
                chdir(tmp)
                Path("main.py").write_bytes(b"old app")
                Path("staging-v9").mkdir()
                Path("staging-v9/main.py").write_bytes(payload)
                original_rename = ota.os.rename
                def fail_promote(src, dst):
                    if src == "staging-v9/main.py":
                        raise OSError("injected promotion error")
                    return original_rename(src, dst)
                with patch.object(ota.os, "rename", side_effect=fail_promote):
                    with self.assertRaisesRegex(OSError, "injected promotion error"):
                        ota.install_staged_main(manifest, "staging-v9", approve=True)
                self.assertEqual(Path("main.py").read_bytes(), b"old app")
            finally:
                chdir(previous)



if __name__ == "__main__":
    unittest.main()
