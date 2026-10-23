"""Best-effort authenticated ESP32 firmware version check-in to LabTech."""
try:
    import ujson as json
except ImportError:
    import json

try:
    import urequests as requests
except ImportError:
    import requests

from bootstrap_config import LABTECH_URL, DEVICE_KEY


def report_firmware(status="running"):
    from ota_single_app import _read_version
    from secure_stage import wifi_mac
    if not LABTECH_URL.startswith("https://"):
        raise ValueError("HTTPS required for firmware reporting")
    if status not in ("running", "update_failed", "restarted"):
        raise ValueError("Invalid report status")
    # Version 0 means no OTA installation has been recorded yet; report
    # unknown rather than implying the ESP32 actually runs version zero.
    version = _read_version()
    payload = json.dumps({"installed_version": version or None, "status": status})
    url = LABTECH_URL.rstrip("/") + "/api/firmware/v2/report/?mac=" + wifi_mac()
    response = requests.post(url, data=payload, headers={
        "Authorization": "Bearer " + DEVICE_KEY,
        "Content-Type": "application/json",
    })
    try:
        if response.status_code != 200:
            raise OSError("Firmware check-in rejected: HTTP %s" % response.status_code)
        return True
    finally:
        response.close()
