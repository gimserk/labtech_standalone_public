"""Host tests for guarded ESP32 missing-main recovery (not a boot hook)."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from os import chdir, getcwd

MODULE = Path(__file__).resolve().parent.parent / "esp32" / "boot_recovery.py"
spec = importlib.util.spec_from_file_location("boot_recovery", MODULE)
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old = getcwd()
        chdir(self.temp.name)

    def tearDown(self):
        chdir(self.old)
        self.temp.cleanup()

    def test_missing_main_restores_backup_after_approval(self):
        Path("main.py.ota-backup").write_text("working application")
        self.assertEqual(recovery.inspect_boot_files()["status"],
                         "app_missing_recovery_available")
        with self.assertRaises(ValueError):
            recovery.restore_missing_app()
        result = recovery.restore_missing_app(approve=True)
        self.assertTrue(result["restart_required"])
        self.assertEqual(Path("main.py").read_text(), "working application")

    def test_never_overwrite_existing_main(self):
        Path("main.py").write_text("new application")
        Path("main.py.ota-backup").write_text("old application")
        self.assertEqual(recovery.inspect_boot_files()["status"],
                         "candidate_unconfirmed")
        with self.assertRaisesRegex(ValueError, "overwrite"):
            recovery.restore_missing_app(approve=True)
        self.assertEqual(Path("main.py").read_text(), "new application")
        self.assertEqual(Path("main.py.ota-backup").read_text(), "old application")

    def test_missing_both_files_refuses_recovery(self):
        self.assertEqual(recovery.inspect_boot_files()["status"],
                         "no_recoverable_application")
        with self.assertRaisesRegex(ValueError, "No recovery backup"):
            recovery.restore_missing_app(approve=True)

    def test_confirmation_requires_explicit_external_health(self):
        Path("main.py").write_text("new application")
        Path("main.py.ota-backup").write_text("old application")
        with self.assertRaises(ValueError):
            recovery.confirm_boot_and_release_backup(approve=True)
        self.assertTrue(Path("main.py.ota-backup").exists())
        result = recovery.confirm_boot_and_release_backup(approve=True, healthy=True)
        self.assertTrue(result["backup_released"])
        self.assertFalse(Path("main.py.ota-backup").exists())


if __name__ == "__main__":
    unittest.main()
