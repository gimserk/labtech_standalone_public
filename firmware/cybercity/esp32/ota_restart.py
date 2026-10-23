"""Explicitly authorized single-app OTA install and reboot for ESP32 pilot.

No periodic unattended installation is enabled. Any interruption during the
single main.py replacement may require USB recovery.
"""
def install_and_restart(approve=False, restart=False, update_fn=None, reset_fn=None):
    if approve is not True or restart is not True:
        raise ValueError("Explicit approve=True and restart=True required")
    if update_fn is None:
        from ota_single_app import update_once
        update_fn = update_once
    result = update_fn(approve=True)
    if not isinstance(result, dict) or result.get("restart_required") is not True:
        return result
    if type(result.get("installed")) is not int or result["installed"] < 1:
        raise ValueError("OTA installer did not confirm an installed version")
    # Hardware reset is permitted only after an explicit successful install.
    if reset_fn is None:
        from machine import reset
        reset_fn = reset
    reset_fn()
    return result
