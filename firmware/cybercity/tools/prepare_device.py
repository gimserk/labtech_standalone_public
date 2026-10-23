#!/usr/bin/env python3
"""Prepare a Cyber City ESP32 provisioning bundle on a trusted workstation.

Requires Python 3.10+ and only standard library. HTTPS certificate validation
uses the workstation trust store. No downloaded code is executed, and no
hardware is flashed by this tool.
"""
import argparse
import json
import os
import pathlib
import re
import ssl
import sys
import urllib.parse
import urllib.request

MAC_RE = re.compile(r"^(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")


def get_config(base_url, mac, device_key):
    if not MAC_RE.fullmatch(mac):
        raise ValueError("MAC must be AA:BB:CC:DD:EE:FF")
    parsed = urllib.parse.urlsplit(base_url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("LabTech URL must be an HTTPS origin without credentials")
    url = base_url.rstrip("/") + "/api/firmware/v2/config/?" + urllib.parse.urlencode({"mac": mac})
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + device_key})
    with urllib.request.urlopen(req, timeout=20, context=ssl.create_default_context()) as response:
        config = json.load(response)
    if config.get("mac_address", "").upper() != mac.upper():
        raise ValueError("LabTech assignment MAC does not match requested MAC")
    if not config.get("mqtt", {}).get("host") or not config.get("building", {}).get("id"):
        raise ValueError("Incomplete Cyber City assignment")
    if not isinstance(config.get("pins"), list):
        raise ValueError("Incomplete ESP32 pin assignments")
    return config


def write_private(path, content):
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(str(path), flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            output.write(content)
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def prepare(output_dir, config, base_url, device_key, ssid, wifi_password):
    output_dir = pathlib.Path(output_dir)
    output_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    # Prevent untrusted paths or uploaded Python from being introduced here.
    write_private(output_dir / "bootstrap_config.py",
                  "WIFI_SSID = " + repr(ssid) + "\n" +
                  "WIFI_PASSWORD = " + repr(wifi_password) + "\n" +
                  "LABTECH_URL = " + repr(base_url.rstrip("/")) + "\n" +
                  "DEVICE_KEY = " + repr(device_key) + "\n")
    write_private(output_dir / "local_config.py",
                  "CONFIG = " + repr(config) + "\n" +
                  "DEVICE_ID = " + repr("dncc-esp32-" + config["mac_address"].replace(":", "").lower()) + "\n" +
                  "MQTT_USER = None\nMQTT_PASSWORD = None\n")
    write_private(output_dir / "assignment.json", json.dumps(config, indent=2) + "\n")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--labtech", required=True, help="LabTech HTTPS origin")
    p.add_argument("--mac", required=True, help="Registered ESP32 Wi-Fi MAC")
    p.add_argument("--output", required=True, help="New private directory for the device")
    args = p.parse_args(argv)
    import getpass
    key = os.environ.get("DNCC_DEVICE_KEY") or getpass.getpass("ESP32 provisioning key: ")
    ssid = input("Wi-Fi SSID: ")
    password = getpass.getpass("Wi-Fi password: ")
    try:
        config = get_config(args.labtech, args.mac.upper(), key)
        prepare(args.output, config, args.labtech, key, ssid, password)
    except (OSError, ValueError, KeyError) as exc:
        p.exit(1, "Provisioning failed: " + str(exc) + "\n")
    print("Prepared device assignment for:", config["building"]["name"])
    print("Files created in:", args.output)
    print("No firmware installed. Use trusted local flashing tools to copy files to the ESP32.")
    print("MQTT credentials must still be provisioned separately; do not use anonymous broker access.")


if __name__ == "__main__":
    main()
