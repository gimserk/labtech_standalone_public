"""Authenticated ESP32 firmware staging without activation.

Requires firmware-specific verified HTTPS on the target MicroPython build.
No downloaded main.py is executed or installed by this module.
"""
import network
import ubinascii
import os

try:
    import urequests as requests
except ImportError:
    import requests

from bootstrap_config import LABTECH_URL, DEVICE_KEY
from ota_staging import validate_manifest, prepare_staging, commit_staged_file

MAX_FILE_BYTES = 256 * 1024
MAX_TOTAL_BYTES = 1024 * 1024


def wifi_mac():
    iface = network.WLAN(network.STA_IF)
    iface.active(True)
    raw = ubinascii.hexlify(iface.config("mac")).decode().upper()
    return ":".join(raw[i:i + 2] for i in range(0, 12, 2))


def _base_url():
    url = LABTECH_URL.rstrip("/")
    if not url.startswith("https://") or len(url.split("/", 3)) < 3 or not url.split("/", 3)[2] or "@" in url.split("/", 3)[2]:
        raise ValueError("LabTech URL must be HTTPS without credentials")
    return url


def _same_origin(url, base):
    # Require identical origin and absolute API paths, not just a prefix
    # like https://labtech.example.edu.attacker.invalid.
    base_origin = base.split("/", 3)[:3]
    target_origin = url.split("/", 3)[:3]
    return base_origin == target_origin and url.startswith(base + "/api/firmware/v2/")


def request_manifest(mac):
    url = _base_url() + "/api/firmware/v2/manifest/?mac=" + mac
    response = requests.get(url, headers={"Authorization": "Bearer " + DEVICE_KEY})
    try:
        if response.status_code != 200:
            raise OSError("Manifest rejected: HTTP %s" % response.status_code)
        return response.json()
    finally:
        response.close()


def _download_to_temp(url, target):
    response = requests.get(url, headers={"Authorization": "Bearer " + DEVICE_KEY},
                            stream=True)
    total = 0
    try:
        if response.status_code != 200:
            raise OSError("Download failed: HTTP %s" % response.status_code)
        with open(target, "wb") as output:
            # MicroPython urequests.raw supports read(n). Verify this on
            # the installed urequests build before hardware deployment.
            stream = response.raw
            while True:
                chunk = stream.read(4096)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_FILE_BYTES:
                    raise ValueError("Firmware file too large")
                output.write(chunk)
    finally:
        response.close()
    return total


def stage_files(manifest=None):
    """Stage a validated manifest in a new versioned folder.

    Never install or execute a downloaded file; incomplete staging is left
    isolated and will not interfere with the running application.
    """
    base = _base_url()
    if manifest is None:
        manifest = request_manifest(wifi_mac())
    if not manifest.get("files"):
        print("No active firmware assigned.")
        return None
    files = validate_manifest(manifest)
    version = manifest.get("version")
    if type(version) is not int or version < 1:
        raise ValueError("Invalid firmware version")
    for entry in files:
        if not _same_origin(entry["url"], base):
            raise ValueError("Firmware URL does not match trusted LabTech API origin")
    folder = "staging-v" + str(version)
    # Fail rather than replace a previous staged version.
    try:
        os.stat(folder)
    except OSError:
        pass
    else:
        raise ValueError("Firmware staging directory already exists")
    prepare_staging(manifest, root=folder)
    total = 0
    for entry in files:
        destination = folder + "/" + entry["path"]
        temp = destination + ".part"
        try:
            total += _download_to_temp(entry["url"], temp)
            if total > MAX_TOTAL_BYTES:
                raise ValueError("Total firmware exceeds staging limit")
            commit_staged_file(temp, destination, entry["sha256"])
        except Exception:
            try:
                os.remove(temp)
            except OSError:
                pass
            raise
    print("Firmware staged without activation:", version)
    return folder


if __name__ == "__main__":
    stage_files()
