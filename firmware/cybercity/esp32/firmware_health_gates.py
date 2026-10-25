"""Strict, side-effect-free candidate firmware health evaluation for ESP32 pilots.

This is an *advisory* gate, not a trusted health attestation. It does not
connect to MQTT, update a journal, confirm firmware or modify boot.py.
"""
REQUIRED_CHECKS = ("wifi_connected", "config_valid", "mqtt_connected",
                   "gpio_initialized", "firmware_version_matches")


def evaluate_health(expected_version, observed_version, checks):
    """Return reasons for failing a complete set of local startup checks."""
    if type(expected_version) is not int or expected_version <= 0:
        return {"healthy": False, "reason": "invalid_expected_version"}
    if type(observed_version) is not int or observed_version != expected_version:
        return {"healthy": False, "reason": "firmware_version_mismatch"}
    if not isinstance(checks, dict):
        return {"healthy": False, "reason": "missing_health_checks"}
    for key in REQUIRED_CHECKS:
        if checks.get(key) is not True:
            return {"healthy": False, "reason": "check_failed:" + key}
    return {"healthy": True, "reason": "all_local_checks_reported"}


def preview_confirmation(expected_version, observed_version, checks,
                         journal_state):
    """Reject mismatched/unattempted candidates; never confirm automatically."""
    if not isinstance(journal_state, dict):
        return {"eligible": False, "reason": "no_journal"}
    if (journal_state.get("version") != expected_version or
            journal_state.get("confirmed") is not False or
            type(journal_state.get("attempts")) is not int or
            not 1 <= journal_state["attempts"] <= 3):
        return {"eligible": False, "reason": "candidate_not_pending"}
    assessment = evaluate_health(expected_version, observed_version, checks)
    return {"eligible": assessment["healthy"], "reason": assessment["reason"]}
