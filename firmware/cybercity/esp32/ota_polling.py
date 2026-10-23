"""Optional single-application OTA update checks for DNCC ESP32.

Checks run only when called by an operator/application loop. Defaults to
report-only mode; installation requires explicit opt-in and a verified TLS
stack. This module never changes boot.py or provisioning credentials.
"""
import time

CHECK_INTERVAL_SECONDS = 3600
MIN_CHECK_INTERVAL_SECONDS = 300


class OTAPoller:
    def __init__(self, interval_seconds=CHECK_INTERVAL_SECONDS,
                 allow_install=False, check_fn=None, install_fn=None,
                 clock=None):
        if type(interval_seconds) is not int or interval_seconds < MIN_CHECK_INTERVAL_SECONDS:
            raise ValueError("OTA interval must be at least 300 seconds")
        self.interval_seconds = interval_seconds
        self.allow_install = allow_install is True
        self.check_fn = check_fn
        self.install_fn = install_fn
        self.clock = clock or time.time
        self.next_check = None

    def poll(self):
        """At most one update check per interval; never silently install."""
        now = self.clock()
        if self.next_check is not None and now < self.next_check:
            return {"status": "not_due"}
        # Schedule next attempt before network I/O so failures cannot
        # cause busy-loop requests to the LabTech API.
        self.next_check = now + self.interval_seconds
        if self.check_fn is None:
            from ota_single_app import check_update
            checker = check_update
        else:
            checker = self.check_fn
        result = checker()
        if not result.get("available"):
            return {"status": "up_to_date", "result": result}
        if not self.allow_install:
            return {"status": "update_available", "result": result}
        if self.install_fn is None:
            from ota_single_app import update_once
            installer = update_once
        else:
            installer = self.install_fn
        installed = installer(approve=True)
        return {"status": "restart_required", "result": installed}


def run_manual_poll(interval_seconds=CHECK_INTERVAL_SECONDS):
    """One report-only check from REPL (does not install or reboot)."""
    return OTAPoller(interval_seconds=interval_seconds).poll()
