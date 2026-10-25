# Milestone 1: database-backed VM event → outbox → MQTT integration

## What this package tests

The Django `TestCase` fixture creates an isolated Cyber City, its **existing building CyberCityMachine**, source template, ESP32, pin, attack monitor and machine state monitor in the temporary **test database**. It sends observations through the real shared evaluator, confirms one outbox record for a false-to-true edge, and runs the actual `dispatch_pending` function. The external MQTT network call is mocked while the actual versioned MQTT payload is decoded by the firmware protocol module. It tests retry status on publisher failure and rejects a wrong-building ESP32 pin.

It is a database-backed integration test, **not** a live Proxmox, real broker, or physical GPIO test.

```bash
# Development/staging environment with its own isolated test database:
python manage.py test app.test_cybercity_m1_db_dispatch app.test_cybercity_m1_chain app.test_cybercity_qga_poll app.test_cybercity_qga_enrollment
```

Never run test database commands against an unbacked-up production database or with unexpected database settings. Inspect test DB configuration before enabling them.

## Dispatcher deployment — separately scheduled from the QGA poller

The existing command `python manage.py dispatch_cybercity_commands` dispatches queued MQTT messages. Simply running the QGA monitor timer does **not** send commands. Install the following systemd units on your **staging LabTech server** after verifying the executable paths:

```ini
# /etc/systemd/system/labtech-cybercity-mqtt.service
[Unit]
Description=LabTech Cyber City MQTT outbox dispatch
After=network-online.target

[Service]
Type=oneshot
User=labtech
Group=www-data
WorkingDirectory=/opt/labtech
ExecStart=/opt/venv/bin/python manage.py dispatch_cybercity_commands
TimeoutStartSec=120
```

```ini
# /etc/systemd/system/labtech-cybercity-mqtt.timer
[Unit]
Description=LabTech Cyber City MQTT outbox dispatch every 30 seconds

[Timer]
OnBootSec=90s
OnUnitInactiveSec=30s
Unit=labtech-cybercity-mqtt.service
Persistent=false

[Install]
WantedBy=timers.target
```

Run `sudo systemctl daemon-reload` and `sudo systemctl enable --now labtech-cybercity-mqtt.timer` **only after** staging broker, topic and ACL checks. Verify with `systemctl list-timers` and `journalctl -u labtech-cybercity-mqtt.service -n 50 --no-pager`.

## Four separate pass gates

- Gate A: Django database test suite passes: one event, one outbox row, no duplicates while matched, rearm, retry and pin isolation.
- Gate B: Real MQTT publishing to localhost Mosquitto plus simulated ESP32 passes (PR #108 harness).
- Gate C: Real staging QGA poll of the existing Cyber City clone changes a real monitor state, persists an outbox row and the dispatcher produces a correlated device message.
- Gate D: A physical building ESP32 actuates the correct output and returns its status; the building UI reflects the change, with no other building affected.

The actual **Control VM** broker and actual hardware require on-site staging credentials and access. Do not report Milestone 1 finished without pass evidence for all four gates.

## Known issues to verify before release

Confirm that the existing Proxmox Guest Agent collector's `guest-exec` shape, exit-status handling, Windows service output and UTC deadlines match your deployed Proxmox and ESP32 firmware. Confirm shared cache locking, TLS broker credentials and MQTT ACK listener deployment. Publication status is **not** execution confirmation.
