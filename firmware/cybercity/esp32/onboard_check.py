"""DNCC ESP32 onboarding diagnostics (MicroPython).

This first-stage client intentionally does NOT execute remotely downloaded code.
Current LabTech endpoints use MAC-based lookup, not authenticated enrollment.
"""
import network
import ubinascii
import ujson
import time
try:
    import urequests as requests
except ImportError:
    import requests

# Copy the companion config.example.py to bootstrap_config.py and edit it.
from bootstrap_config import WIFI_SSID, WIFI_PASSWORD, LABTECH_URL

def connect_wifi(timeout_s=25):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        for _ in range(timeout_s):
            if wlan.isconnected():
                break
            time.sleep(1)
    if not wlan.isconnected():
        raise OSError("Could not connect to Wi-Fi")
    return wlan

def mac_address(wlan):
    raw = ubinascii.hexlify(wlan.config("mac")).decode().upper()
    return ":".join(raw[i:i+2] for i in range(0, 12, 2))

def fetch_json(url):
    response = requests.get(url)
    try:
        if response.status_code != 200:
            raise OSError("HTTP status %s from %s" % (response.status_code, url))
        return response.json()
    finally:
        response.close()

def check_assignment():
    if not LABTECH_URL.startswith("https://"):
        raise ValueError("Provisioning requires an HTTPS LabTech URL")
    wlan = connect_wifi()
    mac = mac_address(wlan)
    print("DNCC Wi-Fi MAC:", mac)
    # LabTech's existing /api/firmware/check/ expects mac and version.
    url = (LABTECH_URL.rstrip("/") + "/api/firmware/check/?mac="
           + mac + "&version=0")
    manifest = fetch_json(url)
    print("Device recognized:", manifest.get("update_available") is not None)
    print("Update available:", manifest.get("update_available", False))
    if manifest.get("update_available"):
        print("Assigned firmware version:", manifest.get("version"))
        # Do NOT fetch or execute these files before authenticated
        # enrollment and integrity verification exist on the server.
        print("Files offered:", len(manifest.get("files", [])))
    return manifest

if __name__ == "__main__":
    check_assignment()
