#!/usr/bin/env python3
"""Install ONE verified Cyber City application onto a MicroPython ESP32 by USB.

The downloaded staging directory must contain main.py and optionally lib/*.py.
No A/B slots, no automatic OTA, and no changes to provisioning credentials.
An operator must explicitly supply --install.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

PROTECTED = {"boot.py", "bootstrap_config.py", "device_startup.py",
             "mqtt_secrets.py", "mqtt_tls_config.py", "mqtt_controller.py"}


def plan(staging, manifest):
    root = Path(staging).resolve()
    if not root.is_dir():
        raise ValueError("Staging directory missing")
    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries or len(entries) > 24:
        raise ValueError("Invalid manifest")
    if not any(x.get("path") == "main.py" for x in entries if isinstance(x, dict)):
        raise ValueError("Firmware must contain main.py")
    commands = []
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Malformed manifest entry")
        name, expected = entry.get("path"), entry.get("sha256")
        if not isinstance(name, str) or not isinstance(expected, str):
            raise ValueError("Invalid firmware metadata")
        parts = name.split("/")
        if name in PROTECTED or "\\" in name or ":" in name or (
            name != "main.py" and not (
                name.startswith("lib/") and name.endswith(".py") and len(parts) == 2
            )
        ) or any(not p or p.startswith(".") for p in parts) or name in seen:
            raise ValueError("Unsafe or duplicate firmware filename")
        seen.add(name)
        file = root.joinpath(*parts)
        if not file.is_file() or file.is_symlink():
            raise ValueError("Missing or symlinked firmware file: " + name)
        actual = hashlib.sha256(file.read_bytes()).hexdigest()
        if len(expected) != 64 or actual != expected.lower():
            raise ValueError("Firmware SHA-256 mismatch: " + name)
        commands.append((file, name))
    # Write main.py last so an interruption during library updates does
    # not immediately replace the entry point. This is NOT atomic.
    commands.sort(key=lambda item: item[1] == "main.py")
    return commands


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    parser.add_argument("--staging", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--install", action="store_true")
    args = parser.parse_args()
    with open(args.manifest, encoding="utf-8") as handle:
        manifest = json.load(handle)
    try:
        files = plan(args.staging, manifest)
        for source, remote in files:
            print("Copy:", source.name, "->", remote)
        if not args.install:
            print("Dry run only. Pass --install to replace the single active app.")
            return
        if shutil.which("mpremote") is None:
            parser.error("Install mpremote first (python -m pip install mpremote)")
        for source, remote in files:
            if "/" in remote:
                subprocess.run(["mpremote", "connect", args.port, "fs", "mkdir",
                                ":" + remote.rsplit("/", 1)[0]], check=False)
            subprocess.run(["mpremote", "connect", args.port, "fs", "cp",
                            str(source), ":" + remote], check=True)
        print("Files copied. Reset device manually and verify functionality.")
    except (OSError, ValueError, subprocess.CalledProcessError) as err:
        parser.error(str(err))


if __name__ == "__main__":
    main()
