"""Pure host-side tests for the isolated ESP32 boot ledger."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from os import chdir, getcwd

MODULE = Path(__file__).resolve().parent.parent / "esp32" / "boot_attempts.py"
spec = importlib.util.spec_from_file_location("boot_attempts", MODULE)
ledger = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ledger)


class AttemptLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = getcwd()
        chdir(self.tmp.name)

    def tearDown(self):
        chdir(self.old)
        self.tmp.cleanup()

    def test_no_ledger_never_assumes_success(self):
        self.assertEqual(ledger.status()["state"], "not_initialized")
        with self.assertRaises(ValueError):
            ledger.record_attempt(2, approve=True)

    def test_approval_and_version_are_required(self):
        with self.assertRaises(ValueError):
            ledger.begin_candidate(2)
        with self.assertRaises(ValueError):
            ledger.begin_candidate(True, approve=True)
        ledger.begin_candidate(2, approve=True)
        with self.assertRaises(ValueError):
            ledger.begin_candidate(3, approve=True)

    def test_attempts_persist_and_stop_after_three(self):
        ledger.begin_candidate(2, approve=True)
        for count in (1, 2, 3):
            self.assertEqual(ledger.record_attempt(2, approve=True)["attempts"], count)
        self.assertEqual(ledger.status()["state"], "retry_limit_reached")
        self.assertEqual(ledger.record_attempt(2, approve=True)["action"],
                         "manual_recovery_required")
        self.assertEqual(ledger.status()["attempts"], 3)

    def test_wrong_version_and_unverified_success_rejected(self):
        ledger.begin_candidate(2, approve=True)
        with self.assertRaises(ValueError):
            ledger.record_attempt(3, approve=True)
        with self.assertRaises(ValueError):
            ledger.confirm_healthy(2, approve=True, healthy=True)
        ledger.record_attempt(2, approve=True)
        with self.assertRaises(ValueError):
            ledger.confirm_healthy(2, approve=True)
        with self.assertRaises(ValueError):
            ledger.confirm_healthy(3, approve=True, healthy=True)
        self.assertEqual(ledger.confirm_healthy(2, approve=True, healthy=True)["state"],
                         "confirmed")
        with self.assertRaises(ValueError):
            ledger.record_attempt(2, approve=True)

    def test_corrupt_ledger_fails_closed(self):
        Path(ledger.LEDGER).write_text("broken")
        with self.assertRaisesRegex(ValueError, "corrupt"):
            ledger.status()
        with self.assertRaises(ValueError):
            ledger.begin_candidate(2, approve=True)
