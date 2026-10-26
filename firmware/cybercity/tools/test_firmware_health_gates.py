"""Unit tests for advisory-only ESP32 firmware startup health gates."""
import importlib.util
from pathlib import Path
import unittest

module = Path(__file__).resolve().parent.parent / "esp32" / "firmware_health_gates.py"
spec = importlib.util.spec_from_file_location("firmware_health_gates", module)
gates = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gates)


class HealthGateTests(unittest.TestCase):
    def setUp(self):
        self.checks = {key: True for key in gates.REQUIRED_CHECKS}
        self.pending = {"version": 12, "attempts": 1, "confirmed": False}

    def test_all_checks_advisory_success(self):
        self.assertTrue(gates.evaluate_health(12, 12, self.checks)["healthy"])
        self.assertTrue(gates.preview_confirmation(12, 12, self.checks, self.pending)["eligible"])

    def test_missing_or_false_check_rejected(self):
        for key in gates.REQUIRED_CHECKS:
            checks = dict(self.checks)
            checks[key] = False
            self.assertFalse(gates.evaluate_health(12, 12, checks)["healthy"])
            del checks[key]
            self.assertFalse(gates.evaluate_health(12, 12, checks)["healthy"])

    def test_version_mismatch_and_boolean_version_rejected(self):
        self.assertFalse(gates.evaluate_health(12, 11, self.checks)["healthy"])
        self.assertFalse(gates.evaluate_health(12, True, self.checks)["healthy"])

    def test_no_pending_matching_attempt_rejected(self):
        for state in (None, {}, {"version": 11, "attempts": 1, "confirmed": False},
                      {"version": 12, "attempts": 0, "confirmed": False},
                      {"version": 12, "attempts": 1, "confirmed": True}):
            self.assertFalse(gates.preview_confirmation(12, 12, self.checks, state)["eligible"])

    def test_no_missing_checks_coercion(self):
        self.assertFalse(gates.evaluate_health(12, 12, None)["healthy"])
        checks = dict(self.checks)
        checks["mqtt_connected"] = 1
        self.assertFalse(gates.evaluate_health(12, 12, checks)["healthy"])


if __name__ == "__main__":
    unittest.main()
