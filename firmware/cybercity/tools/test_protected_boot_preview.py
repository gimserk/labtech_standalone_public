"""Host-only protected boot preview tests. No ESP32 execution or recovery."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

module_dir = Path(__file__).resolve().parent.parent / "esp32"
journal = types.ModuleType("boot_journal")
journal.snapshot = lambda: None
recovery = types.ModuleType("boot_recovery")
recovery.inspect_boot_files = lambda: {"app_present": True, "backup_present": False}
sys.modules["boot_journal"] = journal
sys.modules["boot_recovery"] = recovery
spec = importlib.util.spec_from_file_location("protected_boot_preview",
                                                module_dir / "protected_boot_preview.py")
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)


class ProtectedBootPreviewTests(unittest.TestCase):
    def test_missing_app_does_not_auto_restore(self):
        with patch.object(preview, "inspect_boot_files",
                          return_value={"app_present": False, "backup_present": True}):
            self.assertEqual(preview.preview()["reason"], "missing_app_backup_available")

    def test_corrupt_journal_fails_closed(self):
        with patch.object(preview, "snapshot", side_effect=ValueError("corrupt")):
            self.assertEqual(preview.preview()["action"], "stop_manual_recovery")

    def test_pending_candidate_never_authorizes_boot(self):
        with patch.object(preview, "inspect_boot_files",
                          return_value={"app_present": True, "backup_present": True}), \
             patch.object(preview, "snapshot",
                          return_value={"version": 7, "confirmed": False, "attempts": 1}):
            self.assertEqual(preview.preview()["action"], "stop_manual_recovery")

    def test_retry_limit_is_manual_recovery(self):
        with patch.object(preview, "inspect_boot_files",
                          return_value={"app_present": True, "backup_present": True}), \
             patch.object(preview, "snapshot",
                          return_value={"version": 7, "confirmed": False, "attempts": 3}):
            self.assertEqual(preview.preview()["reason"], "retry_limit")

    def test_confirmed_record_does_not_intercept_existing_boot(self):
        with patch.object(preview, "snapshot",
                          return_value={"version": 7, "confirmed": True, "attempts": 2}):
            self.assertEqual(preview.preview()["action"], "no_supervision")


if __name__ == "__main__":
    unittest.main()
