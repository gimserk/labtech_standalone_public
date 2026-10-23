"""Read-only Cyber City ESP32 OTA boot supervisor preview.

Deliberately NEVER imports, executes, renames or activates downloaded code.
It reports what a future supervisor would do, while leaving the permanent
bootstrap and current application intact. Safe for manual REPL inspection.
"""
try:
    import ujson as json
except ImportError:
    import json

from ota_staging import validate_manifest, _sha256_file

PENDING_FILE = "ota-pending.json"


def inspect_pending(open_file=open):
    """Inspect the pending OTA record and verify all candidate hashes again."""
    try:
        with open_file(PENDING_FILE, "r") as fh:
            record = json.loads(fh.read())
    except OSError:
        return {"decision": "current", "reason": "No candidate pending"}

    if not isinstance(record, dict) or record.get("state") != "pending":
        return {"decision": "current", "reason": "Pending record invalid"}

    version = record.get("version")
    directory = record.get("directory")
    if type(version) is not int or version < 1 or directory != "staging-v" + str(version):
        return {"decision": "current", "reason": "Version or directory mismatch"}

    files = record.get("files")
    if not isinstance(files, list):
        return {"decision": "current", "reason": "Missing file list"}
    manifest = {"files": []}
    for entry in files:
        if not isinstance(entry, dict):
            return {"decision": "current", "reason": "Malformed candidate file"}
        manifest["files"].append({
            "path": entry.get("path"),
            "sha256": entry.get("sha256"),
            "url": "https://localhost/api/firmware/v2/verification-placeholder",
        })
    try:
        validate_manifest(manifest)
        for entry in manifest["files"]:
            filename = directory + "/" + entry["path"]
            if _sha256_file(filename).lower() != entry["sha256"].lower():
                return {"decision": "current", "reason": "Candidate digest mismatch"}
    except (OSError, ValueError, TypeError, KeyError):
        return {"decision": "current", "reason": "Candidate verification failed"}

    # Validity does not imply permission to execute untrusted code.
    return {"decision": "candidate-verified", "version": version,
            "reason": "Ready for future supervisor testing; activation disabled"}


if __name__ == "__main__":
    print(inspect_pending())
