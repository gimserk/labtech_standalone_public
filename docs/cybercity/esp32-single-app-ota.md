# Cyber City: single-application OTA pilot

This module is the first **real on-device replacement** step for OTA,
not yet an unattended update daemon.

Included in **Download Basic ESP32 Firmware**:
`ota_single_app.py`. This uses the existing authenticated firmware v2
manifest, `secure_stage.py` downloader, and SHA-256 verification.
It supports exactly one firmware payload named `main.py`.
`lib/*.py` may be staged, but automatic multi-file installation is
refused until safe sequencing is tested. No A/B slots are created.

## Manual board trial (isolated, recoverable ESP32 only)

1. Install MicroPython, `urequests` and `umqtt.simple` on the device,
   and configure Wi-Fi, LabTech v2 key and MQTT credentials.
2. Confirm HTTPS certificates and hostnames are **actually verified**
   by the installed MicroPython build; also test rejection of invalid certs.
3. Upload a small, known-good `main.py` firmware release to LabTech.
4. From the ESP32 REPL, inspect:
   `import ota_single_app; print(ota_single_app.check_update())`
5. Only if the version and file are correct:
   `print(ota_single_app.update_once(approve=True))`
6. Manually restart and verify the application connects to LabTech and MQTT.
   Use the USB installer to restore the application if it cannot start.

### Safety limitations

- This is **not automatic push** or polling yet. It requires a manual REPL
  call with `approve=True`. It does not restart the board automatically.
- There is **one live main.py**. The replacement cannot be atomic on all
  MicroPython filesystems: power loss after removing the previous main.py
  may require USB recovery. No automatic rollback is promised.
- Only `main.py` is replaced. `boot.py`, `bootstrap_config.py`,
  `device_startup.py`, broker credentials and `mqtt_controller.py`
  remain separate and untouched.
- A genuine application entry point / boot configuration must be validated
  on the particular ESP32 before deploying; the existing startup runs
  manually from the REPL and is not reconfigured by this PR.
- Prior to unattended enablement, provide a safe operation window,
  persistent version/check states, tested transport trust, explicit LabTech
  release policy and reboot/health-check behavior.
