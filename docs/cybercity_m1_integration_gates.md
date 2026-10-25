# Cyber City Milestone 1 — integrated verification gates

## Delivered in this PR
- Regression coverage for a QEMU-observation-shaped monitor result flowing through the shared edge evaluator and MQTT command envelope to the MicroPython decoder and server ACK validator.
- Assert one command on first false-to-true match, no duplicates while matched, and a second command only after observing a nonmatch.
- Assert rejection of wrong-city targets and wrong-building pin mappings.
- Update the loopback broker simulator to recognize existing uppercase `ON`/`OFF` commands as well as lowercase spellings.

Run on a configured LabTech development environment:

```bash
python manage.py test app.test_cybercity_m1_chain app.test_cybercity_qga_poll app.test_cybercity_qga_enrollment app.test_cybercity_monitor_evaluator
```

## Important remaining acceptance gates
These unit-style tests mock the database and MQTT dispatcher; they **do not prove** a live QEMU Guest Agent is producing observations, a real outbox row is persisted, or messages reach hardware.

1. **Django database gate**: create isolated building, machine, configured active monitor, pin and trigger in staging database. Perform QGA poll with `--apply`. Assert persisted single outbox command on first match, none on repeated match, and another only after rearm. Check wrong-city pin and missing guest response.
2. **Real broker gate**: start disposable loopback broker (`firmware/cybercity/tests/compose.yaml`) and run `firmware/cybercity/tools/test_mqtt_broker_integration.py`. Verify versioned setting, command topic and ACK topic match deployment firmware.
3. **Dispatcher gate**: run the actual outbox dispatcher against the local broker, verify command marked `published` and observe a correlated `executed` ACK only when the ESP32 decoder/executor supports it. Published alone is not executed.
4. **Physical building gate**: use exactly one existing CyberCityMachine associated with a staging building; trigger a reversible service or file-hash transition, record the QGA observation, outbox UUID, MQTT topic, pin change, reply and building UI state. Verify only that building's ESP32 responds.

**Deployment note:** Ensure the QGA monitor systemd timer and the separate MQTT outbox dispatcher are configured and working. Do not use a non-TLS anonymous broker outside disposable localhost tests. Physical proof and end-to-end staging remain outstanding.
