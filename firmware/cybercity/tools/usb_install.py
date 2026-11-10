#!/usr/bin/env python3
"""Copy the downloaded basic Cyber City application to a MicroPython ESP32.

Requires the optional `mpremote` program on the workstation and a device
that is already running MicroPython. This NEVER flashes board firmware,
erases the filesystem, or enables automatic startup.
"""
import argparse
import ast
from pathlib import Path
import subprocess
import sys

# Every baseline runtime dependency must be installed, not only the entry point.
APPLICATION = (
    "device_startup.py", "labtech_https.py", "mqtt_controller.py",
    "command_protocol.py", "firmware_report.py", "ota_single_app.py",
    "secure_stage.py", "ota_staging.py",
)
CONFIGURATION = ("bootstrap_config.py", "mqtt_secrets.py")
OPTIONAL = ("mqtt_tls_config.py", "ota_runtime_config.py", "ota_polling.py",
            "health_observer.py")


def _verify_tls_enabled(bootstrap):
    """Parse the literal opt-in flag without executing configuration code."""
    try:
        nodes = ast.parse(bootstrap).body
    except SyntaxError as exc:
        raise ValueError("Invalid bootstrap_config.py: %s" % exc)
    enabled = False
    for node in nodes:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "LABTECH_TLS_VERIFY"
            for target in node.targets
        ):
            if not isinstance(node.value, ast.Constant) or type(node.value.value) is not bool:
                raise ValueError("LABTECH_TLS_VERIFY must be a literal True or False")
            enabled = node.value.value
    return enabled


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
    if _verify_tls_enabled(bootstrap):
        if "LABTECH_CA_CERT_FILE" not in bootstrap:
            raise ValueError("Verified HTTPS requires LABTECH_CA_CERT_FILE")
        cert = directory / "labtech-ca.der"
        if not cert.is_file() or not cert.read_bytes():
            raise ValueError("Verified HTTPS requires a nonempty labtech-ca.der")
        files.append("labtech-ca.der")
    files.extend(name for name in OPTIONAL if (directory / name).is_file())
    return [
        [sys.executable, "-m", "mpremote", "connect", port,
         "fs", "cp", str(directory / name), ":" + name]
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
        for cmd in commands:
            # Pass an argv list to prevent shell interpretation of paths.
            subprocess.run(cmd, check=True)
        print("Application copied. Use REPL to run: import device_startup; device_startup.run()")
    except (ValueError, subprocess.CalledProcessError) as err:
        p.error(str(err))


if __name__ == "__main__":
    main()
