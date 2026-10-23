# Cyber City ESP32 firmware reporting

The Cyber City **building detail** page now displays each registered ESP32,
its recorded installed firmware version, the currently active LabTech release,
whether a higher version is available, and the timestamp of its last report.

The installed version is **device-reported**, not independently attested.
An ESP32 reports to the HTTPS-only authenticated
`POST /api/firmware/v2/report/?mac=<MAC>` endpoint using its existing
per-device bearer credential. Payload example:

```json
{"installed_version": 3, "status": "running"}
```

`installed_version: null` means the device has not recorded a successful
OTA installation. This is different from the available version configured
on the server. The `firmware_last_seen` field indicates **last report**;
it is not reliable proof that the device is currently online.

A best-effort check-in occurs when `device_startup.run()` connects to
LabTech. A reporting error does not disable MQTT control. In the current
firmware, startup is invoked manually from the ESP32 REPL unless configured
by an operator; a reset alone does not guarantee a new report.

Run Django migrations and tests on deployment:

```bash
python manage.py migrate
python manage.py test app.test_cybercity_firmware_reporting
```

The basic firmware ZIP includes `firmware_report.py`. Already-provisioned
ESP32 boards must receive the updated module and `device_startup.py` to
begin reporting. No continuous device heartbeat or error history is
implemented in this first version.
