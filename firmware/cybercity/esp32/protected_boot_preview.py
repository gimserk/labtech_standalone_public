"""Read-only protected-boot decision preview for Cyber City ESP32.

This is NOT boot.py, does not execute an application, install an OTA release,
reset a board, mutate a journal, or restore files. Hardware failover remains
disabled pending power-fault tests and a durable retry counter.
"""
from boot_journal import snapshot
from boot_recovery import inspect_boot_files


def preview():
    """Produce an operator-facing decision; never launch or replace firmware."""
    files = inspect_boot_files()
    try:
        record = snapshot()
    except (ValueError, OSError):
        return {"action": "stop_manual_recovery", "reason": "invalid_boot_journal"}

    if not files["app_present"]:
        if files["backup_present"]:
            return {"action": "stop_manual_recovery",
                    "reason": "missing_app_backup_available"}
        return {"action": "stop_manual_recovery", "reason": "missing_app_and_backup"}

    if record is None:
        return {"action": "no_supervision", "reason": "no_candidate_record"}
    version = record["version"]
    if record["confirmed"]:
        return {"action": "no_supervision", "reason": "confirmed_record",
                "version": version}
    if not files["backup_present"]:
        return {"action": "stop_manual_recovery", "reason": "unconfirmed_no_backup",
                "version": version}
    if record["attempts"] >= 3:
        return {"action": "stop_manual_recovery", "reason": "retry_limit",
                "version": version}
    # The redundant journal may revert to an older generation after a power
    # cut, so the preview MUST NOT authorize booting the candidate.
    return {"action": "stop_manual_recovery",
            "reason": "candidate_unconfirmed_needs_verified_boot_gate",
            "version": version}
