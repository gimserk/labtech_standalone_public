# Live Cyber City ESP32 status listener

This is a real broker subscriber, **not a simulation**. It consumes versioned ESP32 reports from each configured pin topic `<pin.get_full_topic()>/report`. The device must actually publish MQTT JSON of this form:

```json
{"schema":1,"command_id":"valid-command-uuid","status":"executed","state":"ON"}
```

Allowed report statuses: accepted, rejected, executed, failed. Correlation uses the real command UUID, target pin, and enrolled ESP32 controller. Only an `executed` report updates the pin's last confirmed status; broker publication alone does not.

## Required prerequisites

1. Configure the city's existing Mosquitto hostname/port, MQTT TLS and valid broker credentials.
2. Enroll the building ESP32, map its physical pin and topic, and enable `use_versioned_commands` **only after its firmware parses the existing v1 command JSON and publishes v1 reports**.
3. Configure Mosquitto *publisher ACLs per device*: each ESP32 account may publish only to its assigned per-pin `/report` topic; reject generic clients publishing other devices' reports. Configure the listener credential to subscribe only to those topics. Broker credentials/TLS alone do NOT prove which device sent a report unless the ACLs enforce it.
4. Ensure unique pin MQTT topics within the city. This listener subscribes at startup; restart it after adding or changing pins.
5. From the existing dev virtual environment, run:
```bash
python manage.py check
python manage.py test app.tests.test_cybercity_live_mqtt_reports app.tests.test_cybercity_soc_device_report_persistence
python manage.py listen_cybercity_reports --city-id YOUR_CITY_ID
```

Run the listener as a supervised service with restricted credentials on a secure host. It is **not** automatically installed as a new production service by this PR. Prefer a distinct Mosquitto read-only listener account; the initial command uses the city's configured broker credentials, so they must be ACL-limited.

## Pilot verification

Use one disposable Cyber City VM and one enrolled ESP32 with updated firmware. Observe a real command published to `/command`; check the device logs for actual receipt, actual state change and a report on `/report`. Check the correlated `CyberCityCommand.status` and `CyberCityESP32Pin.last_status` in LabTech. A status of `published` is NOT execution confirmation. Verify incorrect command IDs, wrong pin topics, expired commands and disconnected devices are not reported as executed.

This listener does not automatically create SOC incidents or repair old firmware that publishes legacy raw `/status` strings. Completing that teaching workflow requires a supervised physical end-to-end test and any necessary firmware upgrade.
