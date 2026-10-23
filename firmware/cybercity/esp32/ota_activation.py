"""Explicit, reboot-independent activation guard for staged ESP32 applications.

This module NEVER imports a staged app, overwrites boot.py/main.py or
reboots. It prepares a single pending activation record that a separately
tested boot supervisor can consume after physical hardware validation.
"""
import os
try:
    import ujson as json
except ImportError:
    import json
from ota_staging import validate_manifest, _sha256_file


STATE_FILE = "ota-pending.json"
TEMP_FILE = "ota-pending.tmp"
PROTECTED = ("boot.py", "bootstrap_config.py", "device_startup.py",
             "mqtt_controller.py", "mqtt_secrets.py", "mqtt_tls_config.py")


def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False


def prepare_activation(manifest, folder, approve=False):
    """Explicitly approve a fully verified staged release for later testing.

    A pending record is not sufficient to execute code. No code is executed
    until a separate boot supervisor is written, installed, and validated.
    """
    if approve is not True:
        raise ValueError("Explicit approve=True is required")
    version = manifest.get("version")
    if type(version) is not int or version < 1:
        raise ValueError("Invalid firmware version")
    if folder != "staging-v" + str(version):
        raise ValueError("Staging directory does not match firmware version")
    if _exists(STATE_FILE) or _exists(TEMP_FILE):
        raise ValueError("An activation is already pending")
    files = validate_manifest(manifest)
    for entry in files:
        path = entry["path"]
        if path in PROTECTED:
            raise ValueError("Cannot replace permanent bootstrap")
        if not _exists(folder + "/" + path):
            raise ValueError("Staged file missing: " + path)
        if _sha256_file(folder + "/" + path).lower() != entry["sha256"].lower():
            raise ValueError("Staged file integrity failure: " + path)
    record = {"version": version, "directory": folder,
              "state": "pending", "files": [
                  {"path": e["path"], "sha256": e["sha256"]} for e in files
              ]}
    with open(TEMP_FILE, "w") as handle:
        handle.write(json.dumps(record))
    os.rename(TEMP_FILE, STATE_FILE)
    return record


def cancel_activation():
    """Cancel pending activation without removing running code or staging."""
    if _exists(STATE_FILE):
        os.remove(STATE_FILE)
