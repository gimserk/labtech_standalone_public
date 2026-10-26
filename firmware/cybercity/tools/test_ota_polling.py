"""Host-only tests of update polling and opt-in behavior."""
import importlib.util
from pathlib import Path
import unittest

P = Path(__file__).resolve().parent.parent / "esp32" / "ota_polling.py"
spec = importlib.util.spec_from_file_location("ota_polling", P)
polling = importlib.util.module_from_spec(spec)
spec.loader.exec_module(polling)


class PollingTests(unittest.TestCase):
    def test_never_installs_by_default(self):
        calls = []
        poller = polling.OTAPoller(check_fn=lambda: {"available": True},
                                    install_fn=lambda **kw: calls.append(kw),
                                    clock=lambda: 100)
        self.assertEqual(poller.poll()["status"], "update_available")
        self.assertEqual(poller.poll()["status"], "not_due")
        self.assertEqual(calls, [])

    def test_install_requires_opt_in(self):
        calls = []
        poller = polling.OTAPoller(allow_install=True,
                                    check_fn=lambda: {"available": True},
                                    install_fn=lambda **kw: calls.append(kw) or {"installed": 3},
                                    clock=lambda: 100)
        self.assertEqual(poller.poll()["status"], "restart_required")
        self.assertEqual(calls, [{"approve": True}])

    def test_reject_short_interval(self):
        with self.assertRaises(ValueError):
            polling.OTAPoller(interval_seconds=10)

    def test_failed_network_does_not_busy_loop(self):
        count = []
        def failing():
            count.append(1)
            raise OSError("offline")
        poller = polling.OTAPoller(check_fn=failing, clock=lambda: 100)
        with self.assertRaises(OSError):
            poller.poll()
        self.assertEqual(poller.poll()["status"], "not_due")
        self.assertEqual(len(count), 1)


if __name__ == "__main__":
    unittest.main()
