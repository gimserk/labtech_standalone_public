"""Single-active-application OTA installer for a controlled ESP32 pilot.

Call manually over REPL only after verifying HTTPS certificate enforcement.
Stages via existing authenticated API. Never modifies bootstrap/credentials.
No A/B slots; failure during install may require USB recovery.
"""
import os
try:
    import ujson as json
except ImportError:
    import json

from ota_staging import _sha256_file
from secure_stage import request_manifest, wifi_mac, stage_files

VERSION_FILE = "ota-installed-version.json"
ENTRY_POINT = "main.py"


def _read_version():
    try:
        with open(VERSION_FILE, "r") as handle:
            data = json.loads(handle.read())
        number = data.get("version", 0)
        return number if type(number) is int and number >= 0 else 0
    except (OSError, ValueError, TypeError):
        return 0


def check_update():
    """Report update availability without writing anything."""
    manifest = request_manifest(wifi_mac())
    version = manifest.get("version")
    if not manifest.get("files"):
        return {"available": False, "reason": "No firmware assigned"}
    if type(version) is not int or version < 1:
        raise ValueError("Invalid remote version")
    return {"available": version > _read_version(),
            "version": version, "installed": _read_version()}


def install_staged_main(manifest, folder, approve=False):
    """Promote verified staged main.py; never touch provisioning data.

    Intentionally supports only main.py. Multi-file OTA needs transaction
    handling and is rejected rather than risking partial library updates.
    """
    if approve is not True:
        raise ValueError("Explicit approve=True required")
    files = manifest.get("files")
    if not isinstance(files, list) or len(files) != 1 or files[0].get("path") != ENTRY_POINT:
        raise ValueError("Automatic multi-file installation is not supported")
    version = manifest.get("version")
    if type(version) is not int or version <= _read_version():
        raise ValueError("Version must be newer than installed")
    if folder != "staging-v" + str(version):
        raise ValueError("Version and folder mismatch")
    candidate = folder + "/" + ENTRY_POINT
    if _sha256_file(candidate).lower() != files[0]["sha256"].lower():
        raise ValueError("Firmware integrity failed")
    # The staged application is already on the same filesystem.
    # Some MicroPython filesystems cannot rename over an existing file.
    # A power loss after removal requires USB recovery.
    try:
        os.stat(ENTRY_POINT)
    except OSError:
        pass
    else:
        os.remove(ENTRY_POINT)
    os.rename(candidate, ENTRY_POINT)
    with open(VERSION_FILE + ".tmp", "w") as handle:
        handle.write(json.dumps({"version": version}))
    try:
        os.remove(VERSION_FILE)
    except OSError:
        pass
    os.rename(VERSION_FILE + ".tmp", VERSION_FILE)
    return version


def update_once(approve=False):
    """One explicit update check, staging and install; does not auto-reboot."""
    if approve is not True:
        raise ValueError("Explicit approve=True required")
    check = check_update()
    if not check.get("available"):
        return check
    manifest = request_manifest(wifi_mac())
    if manifest.get("version") != check["version"]:
        raise ValueError("Firmware changed during update check; retry")
    # The OTA installer supports only one main.py payload. Reject unsupported
    # releases BEFORE downloading or creating a staging directory.
    files = manifest.get("files")
    if not isinstance(files, list) or len(files) != 1 or not isinstance(files[0], dict) or files[0].get("path") != ENTRY_POINT:
        raise ValueError("This device only supports single-main.py OTA releases")
    folder = stage_files(manifest=manifest)
    if folder != "staging-v" + str(check["version"]):
        raise ValueError("Staging version mismatch")
    return {"installed": install_staged_main(manifest, folder, approve=True),
            "restart_required": True}
