# Milestone 1 Stage B: VM event to outbox contract

Run these tests from a configured LabTech development environment:

```bash
python manage.py test app.test_cybercity_milestone1_event_outbox
```

These tests exercise the real `enqueue_machine_command` boundary and MQTT v1 command/ack protocol while mocking persistence. They verify same-city enqueue and cross-city rejection. **They do not exercise the authenticated HTTP endpoint, monitor edge transitions, database transaction, actual command dispatcher or broker.**

Next integration gate: on a staging Django test database, issue two matching reports to `api_report_machine_state` and confirm one outbox row; report a nonmatch then match and confirm rearm. Reject foreign monitors, invalid Bearer keys and unsecured requests. Point the dispatcher to the disposable localhost broker from PR #108 with v1 command mode enabled, then assert actual outbox row lifecycle. Do not connect a production broker.

Only after these checks pass run the existing physical building acceptance in `docs/cybercity_milestone1_vm_mqtt_esp32.md`. Avoid claiming the full VM-to-ESP32 workflow is proven until authenticated event, outbox dispatch, physical GPIO and status consumer have all passed.
