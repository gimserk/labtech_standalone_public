# Cyber City ESP32 firmware manifest and downloads (v2)

This change builds on the existing ESP32Firmware and ESP32Library models.
It does not change the existing v1 endpoints, building UI or MQTT mappings.

- `GET /api/firmware/v2/manifest/?mac=<MAC>`
- `GET /api/firmware/v2/download/<firmware_id>/?mac=<MAC>`
- `GET /api/firmware/v2/library/<library_id>/?mac=<MAC>`

All three require HTTPS and `Authorization: Bearer <DEVICE_KEY>`.
The downloads are authorized against the MAC's device and its active
firmware (not merely against the numeric object ID).

The manifest returns the active firmware version and the `main.py` and
library paths, SHA-256 hashes and URLs.

The optional MicroPython `secure_stage.py` diagnostic stages only
`main.py` and never executes it. Library installation, rollback and
activation are deliberately deferred.

## Limitations that block unattended OTA

1. Verify actual TLS certificate validation on the MicroPython build.
   Merely using HTTPS does not guarantee certificate verification.
2. Add authenticated device-to-broker credentials and topic ACLs.
3. Add atomic installation, persistent version tracking, power-failure
   recovery, rollback and libraries.
4. Constrain firmware/library upload sizes and file destinations.
5. Restrict/deprecate the original MAC-only v1 firmware and config routes;
   they remain accessible and are not secured by v2.
6. Test actual ESP32 memory limits, downloads and restart behavior.

Use `python manage.py check`, `python manage.py test
app.test_cybercity_provisioning` and a disposable database to check
the Django endpoint behavior before deployment.
