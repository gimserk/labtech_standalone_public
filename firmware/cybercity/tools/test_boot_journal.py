"""Host tests for redundant boot journal; actual power-loss behavior needs hardware."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from os import chdir, getcwd

p = Path(__file__).resolve().parent.parent / "esp32" / "boot_journal.py"
spec = importlib.util.spec_from_file_location("boot_journal", p)
journal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(journal)


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = getcwd()
        chdir(self.tmp.name)

    def tearDown(self):
        chdir(self.old)
        self.tmp.cleanup()

    def test_initialize_and_limit(self):
        with self.assertRaises(ValueError):
            journal.initialize(2)
        journal.initialize(2, approve=True)
        for attempt in range(1, 4):
            self.assertEqual(journal.record_attempt(2, approve=True)["attempts"], attempt)
        self.assertEqual(journal.record_attempt(2, approve=True)["action"],
                         "manual_recovery_required")

    def test_corrupt_newest_slot_requires_manual_recovery(self):
        journal.initialize(4, approve=True)
        journal.record_attempt(4, approve=True)
        newest = journal.snapshot()
        path = journal.SLOTS[newest["sequence"] % 2]
        Path(path).write_text("partially written")
        with self.assertRaisesRegex(ValueError, "manual recovery"):
            journal.snapshot()
        with self.assertRaises(ValueError):
            journal.record_attempt(4, approve=True)

    def test_all_slots_corrupt_fails_closed(self):
        Path(journal.SLOTS[0]).write_text("bad")
        Path(journal.SLOTS[1]).write_text("bad")
        with self.assertRaisesRegex(ValueError, "manual recovery"):
            journal.snapshot()
        with self.assertRaises(ValueError):
            journal.initialize(4, approve=True)

    def test_health_confirmation_requires_evidence(self):
        journal.initialize(5, approve=True)
        journal.record_attempt(5, approve=True)
        with self.assertRaises(ValueError):
            journal.confirm(5, approve=True)
        with self.assertRaises(ValueError):
            journal.confirm(4, healthy=True, approve=True)
        result = journal.confirm(5, healthy=True, approve=True)
        self.assertTrue(result["confirmed"])
        with self.assertRaises(ValueError):
            journal.record_attempt(5, approve=True)


if __name__ == "__main__":
    unittest.main()
