"""Offline-safe validation and transactional staging helpers for MicroPython.

Files are only staged. No boot.py/main.py replacement or execution occurs.
The caller must have authenticated the manifest and verified TLS separately.
"""
import os
try:
    import uhashlib as hashlib
    import ubinascii as binascii
except ImportError:
    import hashlib
    import binascii


def validate_manifest(manifest):
    files = manifest.get("files")
    if not isinstance(files, list) or not files or len(files) > 24:
        raise ValueError("Expected 1-24 firmware files")
    seen = set()
    for entry in files:
        path = entry.get("path", "")
        digest = entry.get("sha256", "")
        if not isinstance(path, str) or not path or len(path) > 128:
            raise ValueError("Invalid firmware path")
        segments = path.split("/")
        if any(segment in ("", ".", "..") or segment.startswith(".") for segment in segments):
            raise ValueError("Unsafe firmware path")
        if not (path == "main.py" or (path.startswith("lib/") and path.endswith(".py"))):
            raise ValueError("Only main.py and lib/*.py can be staged")
        if "\\" in path or ":" in path or path in seen:
            raise ValueError("Duplicate or unsafe firmware path")
        if len(digest) != 64 or any(c not in "0123456789abcdefABCDEF" for c in digest):
            raise ValueError("Invalid SHA-256 digest")
        if not isinstance(entry.get("url"), str) or not entry["url"].startswith("https://"):
            raise ValueError("HTTPS download URL required")
        seen.add(path)
    if "main.py" not in seen:
        raise ValueError("Firmware must include main.py")
    return files


def _mkdir(path):
    try:
        os.mkdir(path)
    except OSError:
        # Already-existing directories are fine; still reject file paths.
        if not (os.stat(path)[0] & 0x4000):
            raise


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(4096)
            if not chunk:
                break
            digest.update(chunk)
    return binascii.hexlify(digest.digest()).decode()


def prepare_staging(manifest, root="staging"):
    """Validate first, then create a staging directory and lib subfolder."""
    files = validate_manifest(manifest)
    _mkdir(root)
    if any(e["path"].startswith("lib/") for e in files):
        _mkdir(root + "/lib")
    return files


def commit_staged_file(temp_path, target_path, expected_digest):
    """Verify complete temporary file before replacing staged destination.

    os.rename may not overwrite existing destinations on every filesystem.
    Require a fresh destination so no existing healthy staged firmware is
    destroyed when a download fails.
    """
    if _sha256_file(temp_path).lower() != expected_digest.lower():
        raise ValueError("Staged file SHA-256 mismatch")
    try:
        os.stat(target_path)
    except OSError:
        pass
    else:
        raise ValueError("Staging target already exists; use a fresh staging area")
    os.rename(temp_path, target_path)
