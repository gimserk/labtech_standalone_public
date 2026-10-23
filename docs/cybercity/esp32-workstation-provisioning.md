# ESP32 first-flash workstation helper

## What this is

This host-side utility reduces manual setup without changing the existing
Cyber City database, ESP32 registration workflow, v2 configuration endpoint,
firmware management, or MQTT topic conventions.

It contacts LabTech using the **workstation's verified HTTPS stack**, checks
that the returned MAC matches the registered ESP32 and writes a private
bundle containing `bootstrap_config.py`, `local_config.py` and
`assignment.json`. It neither downloads executable firmware nor flashes
hardware. It never prints the provisioning key or Wi-Fi password.

## Use

1. Register the actual ESP32 Wi-Fi MAC under the building's ESP32 section.
2. Generate its provisioning key using the existing command:
   `python manage.py issue_cybercity_esp32_key AA:BB:CC:11:22:33`.
3. On a trusted workstation, run:

   ```bash
   python firmware/cybercity/tools/prepare_device.py \
     --labtech https://labtech.example.edu \
     --mac AA:BB:CC:11:22:33 \
     --output ./private-devices/cityhall-01
   ```

4. Supply the key, SSID and Wi-Fi password when prompted.
5. Review the downloaded building pin assignments in `assignment.json`.
6. Independently provision the MQTT credentials and the existing
   `device_startup.py` / `mqtt_controller.py` modules to the device
   using your tested serial flashing tool.
7. Run `import device_startup; device_startup.run()` manually in REPL.

## Safety and compatibility limits

- New output directory required to prevent silent credential overwrite.
- Keep the output folder and generated Python files **outside Git**; both
  `bootstrap_config.py` and `local_config.py` are sensitive.
- The tool validates HTTPS against the workstation trust store. It does not
  repair TLS verification weaknesses in the MicroPython runtime.
- No automatic firmware download, activation, reboot or rollback is enabled.
- The MQTT credentials are not downloaded and must be installed separately.
- Do not enable auto-boot or connect real actuators before physical testing.
- The existing legacy MAC-only v1 endpoints still require hardening.

## Local tests

```bash
python -m unittest discover -s firmware/cybercity/tools -p 'test_*.py'
```

## Download basic firmware directly from Cyber City

On the staff Cyber City detail page, click **Download Basic ESP32 Firmware**.
This provides a ZIP of the current generic MicroPython source files:
`device_startup.py`, `mqtt_controller.py`, `secure_stage.py`, and
configuration examples, plus `README-FIRST.txt`.

The endpoint is `/labtech/cybercity/<city_id>/esp32/basic-firmware/`
and requires a staff login. The archive is generated from files deployed
alongside LabTech; no network fetch and no Wi-Fi, enrollment or MQTT
secrets are embedded. It is the **application bundle**, not an ESP32
MicroPython board-flashing `.bin` image. Flash MicroPython separately
with a tested image appropriate to the board, then copy these files and
configure the device.

The zip can be downloaded from any city but is generic; the device gets
its building-specific topic and pin configuration after authenticated
provisioning. This avoids generating separate hardcoded applications for
City Hall, Taco Bell, and other buildings.
