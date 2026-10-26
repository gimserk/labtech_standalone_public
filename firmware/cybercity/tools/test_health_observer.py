"""Host tests for optional, rate-limited self-reported health."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

path = Path(__file__).resolve().parent.parent / "esp32" / "health_observer.py"
spec = importlib.util.spec_from_file_location("health_observer", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class HealthObserverTests(unittest.TestCase):
    def test_rejects_fast_interval(self):
        with self.assertRaises(ValueError):
            module.HealthObserver(lambda **kw: True, interval_ms=100)

    def test_rate_limits_successful_reports(self):
        reports = []
        observer = module.HealthObserver(lambda status: reports.append(status),
                                         interval_ms=60000)
        with patch.object(module.time, "ticks_ms", side_effect=[100, 200, 60100]), \
             patch.object(module.time, "ticks_diff", side_effect=lambda a, b: a-b, create=True):
            self.assertTrue(observer.poll())
            self.assertFalse(observer.poll())
            self.assertTrue(observer.poll())
        self.assertEqual(reports, ["running", "running"])

    def test_error_is_throttled_and_nonfatal(self):
        calls = []
        def fail(status):
            calls.append(status)
            raise OSError("unreachable")
        observer = module.HealthObserver(fail, interval_ms=60000)
        with patch.object(module.time, "ticks_ms", side_effect=[100, 200]), \
             patch.object(module.time, "ticks_diff", side_effect=lambda a, b: a-b, create=True):
            self.assertFalse(observer.poll())
            self.assertFalse(observer.poll())
        self.assertEqual(len(calls), 1)
        self.assertEqual(observer.failures, 1)

    def test_disconnected_does_not_report(self):
        observer = module.HealthObserver(lambda status: self.fail("unexpected call"))
        self.assertFalse(observer.poll(connected=False))


if __name__ == "__main__":
    unittest.main()
