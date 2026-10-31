# Enable live Cyber City ESP32 status ingestion on Ubuntu

The report listener is a **real** paho MQTT client. This unit runs one process per Cyber City ID, automatically restarts after failures and reconnects with bounded backoff. It is not automatically deployed by this PR.

## Preconditions

* City MQTT broker address, TLS CA, and credentials configured in LabTech.
* Broker publisher ACLs bind **each ESP32** to its own /report topics. Do not depend on topic names for authentication without ACLs.
* MQTT credentials available to the listener must permit subscriptions to only approved device reports.
* Enrolled pins have unique topics and their firmware uses versioned commands and emits matching JSON reports.
* LabTech's existing production venv and settings remain unchanged.

## Installation (manual, after dev validation)

Inspect and adjust `User`, `Group`, `WorkingDirectory` and Python binary in the unit for the existing installation; **do not rebuild the venv**.

```bash
sudo install -m 0644 deploy/systemd/labtech-cybercity-mqtt@.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now labtech-cybercity-mqtt@YOUR_CITY_ID.service
sudo systemctl status labtech-cybercity-mqtt@YOUR_CITY_ID.service
sudo journalctl -u labtech-cybercity-mqtt@YOUR_CITY_ID.service -f
```

Replace YOUR_CITY_ID with a real numeric city ID. The sample unit assumes `/opt/venv/bin/python` and `/opt/labtech/manage.py`; use the **existing** production environment rather than creating another.

Service reads current pin subscriptions at startup. Restart it after changing enrolled pins or MQTT topic mappings:

```bash
sudo systemctl restart labtech-cybercity-mqtt@YOUR_CITY_ID.service
```

Confirm device report actually changes `CyberCityCommand.status` to `executed` and updates `CyberCityESP32Pin.last_status`. Merely connecting to Mosquitto or publishing a command does not confirm execution. Test one isolated physical ESP32 building before broad rollout.

No production setup is performed by merging this PR.
