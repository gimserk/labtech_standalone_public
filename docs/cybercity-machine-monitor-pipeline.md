# Cyber City machine-monitor → ESP32 delivery

This change does not change the Cyber City machine/ESP32 schema or any student lab provisioning.

Pipeline:
Building machine -> agent HTTP GET `/api/machine/get-monitors/` -> agent HTTP POST `/api/machine/report-state/` -> `evaluate_monitor_observations` (false-to-true edge) -> `CyberCityCommand` outbox -> scheduled `app.tasks.dispatch_cybercity_pending_commands` -> city MQTT broker -> target building ESP32 pin.

Important:
- The VM must run the downloaded `agent.py` with `config.ini` generated from **that exact Cyber City machine's** monitor page; an old machine record may have a different API key.
- Service/file hash checks are supported by the downloaded agent. **DB Query checks are not implemented** in this agent. Do not rely on them as an attack trigger.
- For services, Linux uses `systemctl is-active -- <name>`; Windows uses `psutil.win_service_get`. Agent refetches monitor configuration on each loop.
- On first matching state the monitor sends an attack. Additional matching samples do not re-fire until a nonmatching value is observed (edge-triggered). Resetting a clone may preserve last observation unless reset flow clears monitor states.
- The MQTT outbox is **not delivered by the report HTTP request itself**. One Celery Beat scheduler must dispatch pending commands.

## Before enabling production dispatch

1. Run `python manage.py test app.test_cybercity_monitor_agent_delivery app.test_cybercity_monitor_evaluator` and `python manage.py check` in the private source.
2. Compile and publish changed modules including `app/views`, `app/tasks`, `app/forms`, `app/settings`, the template, and the new test if distributing tests.
3. Ensure LabTech Celery worker is running and `celery -A app inspect registered` includes `app.tasks.dispatch_cybercity_pending_commands`.
4. Inspect the **existing** pending CyberCityCommand queue for stale/unsafe entries. Publishing old pending commands can actuate devices. Do not enable scheduling with an unknown backlog.
5. Add `CYBERCITY_COMMAND_DISPATCH_ENABLED=True` to an appropriate runtime environment, restart the Celery Beat process (not just worker), and ensure only **one** beat scheduler owns this schedule. Default is False.
6. Test one noncritical ESP32 output in a sandbox city: create an Attack Monitor with a pin, assign it to a machine State Monitor, configure an agent in that VM, then verify an unmatched reading and a matching reading. Observe outbox pending -> published and actual ESP32 status/ack.
7. For a monitor page that fails to render, inspect `journalctl -u labtech.service` for a Django traceback. The code changes here do not prove the user-specific page error is fixed.

## Safety
- The agent does not run arbitrary DB SQL for `db_query` monitors.
- `app/mediafiles`, existing monitor records, attack mappings, firmware and Cyber City machine IDs are preserved.
- MQTT legacy commands may be published at least once; avoid commands that are unsafe when repeated. Status feedback or firmware acknowledgement is needed to verify execution.
