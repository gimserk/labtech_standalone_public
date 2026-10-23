#!/usr/bin/env python3
"""Copy the downloaded basic Cyber City application to a MicroPython ESP32.

Requires the optional `mpremote` program on the workstation and a device
that is already running MicroPython. This NEVER flashes board firmware,
erases the filesystem, or enables automatic startup.
"""
import argparse
from pathlib import Path
import shutil
import subprocess

APPLICATION = ("device_startup.py", "mqtt_controller.py")
CONFIGURATION = ("bootstrap_config.py", "mqtt_secrets.py")
OPTIONAL = ("mqtt_tls_config.py",)


def prepare_commands(port, directory):
    directory = Path(directory).resolve()
    missing = [name for name in APPLICATION + CONFIGURATION
               if not (directory / name).is_file()]
    if missing:
        raise ValueError("Missing required files: " + ", ".join(missing))
    if not port or port.startswith("-"):
        raise ValueError("Explicit serial port required (e.g. COM5 or /dev/ttyUSB0)")
    # Do not silently install template or placeholder credentials.
    bootstrap = (directory / "bootstrap_config.py").read_text(encoding="utf-8")
    broker = (directory / "mqtt_secrets.py").read_text(encoding="utf-8")
    for value in ("REPLACE_ME", "REPLACE_WITH_DEVICE_KEY", "labtech.example.edu"):
        if value in bootstrap:
            raise ValueError("Bootstrap configuration contains placeholder: " + value)
    if "REPLACE_ME" in broker:
        raise ValueError("MQTT credentials still contain placeholders")
    if "LABTECH_URL" not in bootstrap or "DEVICE_KEY" not in bootstrap:
        raise ValueError("Bootstrap configuration missing required fields")
    if "MQTT_USER" not in broker or "MQTT_PASSWORD" not in broker:
        raise ValueError("MQTT credentials missing required fields")
    files = list(APPLICATION + CONFIGURATION)
    files.extend(name for name in OPTIONAL if (directory / name).is_file())
    return [
        ["mpremote", "connect", port, "fs", "cp", str(directory / name), ":" + name]
        for name in files
    ]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port", required=True, help="Serial device, e.g. COM5")
    p.add_argument("--directory", required=True, help="Folder containing configured files")
    p.add_argument("--install", action="store_true",
                   help="Perform the copy; otherwise print a file plan only")
    args = p.parse_args(argv)
    try:
        commands = prepare_commands(args.port, args.directory)
        if not args.install:
            print("Dry run: these files would be copied to the ESP32:")
            for cmd in commands:
                print("  ", Path(cmd[-2]).name, "->", cmd[-1])
            print("Pass --install to copy. Boot-time execution remains disabled.")
            return
        if shutil.which("mpremote") is None:
            p.error("Install mpremote on the workstation: python -m pip install mpremote")
        for cmd in commands:
            # Pass an argv list to prevent shell interpretation of paths.
            subprocess.run(cmd, check=True)
        print("Application copied. Use REPL to run: import device_startup; device_startup.run()")
    except (ValueError, subprocess.CalledProcessError) as err:
        p.error(str(err))


if __name__ == "__main__":
    main()
