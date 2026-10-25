"""Opt-in recovery primitives for the Cyber City ESP32 boot supervisor.

Not imported by boot.py or main.py automatically. Designed for controlled
REPL/hardware validation before any unattended startup hook is installed.
Does not touch enrollment credentials, boot.py, or broker settings.
"""
import os

APP = "main.py"
BACKUP = "main.py.ota-backup"


def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False


def inspect_boot_files():
    """Read-only inspection; never declares a candidate healthy merely for existing."""
    app = _exists(APP)
    backup = _exists(BACKUP)
    if app and backup:
        status = "candidate_unconfirmed"
    elif app:
        status = "app_present_no_backup"
    elif backup:
        status = "app_missing_recovery_available"
    else:
        status = "no_recoverable_application"
    return {"status": status, "app_present": app, "backup_present": backup}


def restore_missing_app(approve=False):
    """Restore an old application *only* if main.py is absent.

    A missing main.py could result from interruption between rename operations.
    Never overwrite a candidate, and never infer that an existing candidate
    is healthy. A later boot supervisor must implement confirmed-boot logic.
    """
    if approve is not True:
        raise ValueError("Explicit approve=True required")
    state = inspect_boot_files()
    if state["app_present"]:
        raise ValueError("Refusing to overwrite existing main.py")
    if not state["backup_present"]:
        raise ValueError("No recovery backup is available")
    os.rename(BACKUP, APP)
    return {"restored": True, "restart_required": True}


def confirm_boot_and_release_backup(approve=False, healthy=False):
    """Explicit maintenance operation only, NOT an automatic health detector."""
    if approve is not True or healthy is not True:
        raise ValueError("Explicit approval and externally verified health required")
    state = inspect_boot_files()
    if not state["app_present"] or not state["backup_present"]:
        raise ValueError("Application and backup must both exist")
    os.remove(BACKUP)
    return {"backup_released": True}
