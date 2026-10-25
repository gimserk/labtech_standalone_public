"""Rate-limited, opt-in sustained health observation for Cyber City ESP32.

Reports device self-observation only. Does not confirm boot journal health,
control a watchdog, or trigger firmware rollback. Disabled unless wired.
"""
try:
    import utime as time
except ImportError:
    import time

MIN_INTERVAL_MS = 60000


class HealthObserver:
    def __init__(self, reporter, interval_ms=300000):
        if type(interval_ms) is not int or interval_ms < MIN_INTERVAL_MS:
            raise ValueError("Health observation interval must be >= 60 seconds")
        self.reporter = reporter
        self.interval = interval_ms
        self.last = None
        self.successes = 0
        self.failures = 0

    def poll(self, connected=True):
        if connected is not True:
            return False
        now = time.ticks_ms()
        if self.last is not None and time.ticks_diff(now, self.last) < self.interval:
            return False
        # Record the attempt, not only successful transmissions, to avoid
        # rapid repeated HTTP calls when LabTech cannot be reached.
        self.last = now
        try:
            self.reporter(status="running")
            self.successes += 1
            return True
        except (OSError, ValueError) as exc:
            self.failures += 1
            print("Firmware health check-in failed:", str(exc))
            return False
