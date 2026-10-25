# Cyber City end-to-end acceptance gate

This plan uses the existing **CyberCityMachine associated with the building**, not a separate student lab machine. The Control VM hosts the broker, and the building's one ESP32 executes pin commands. This PR adds contract tests only; the following scenarios require a staging environment and real hardware.

## Automated checks (no Proxmox or broker required)

Run from a configured Django virtual environment:

```bash
python manage.py test app.test_cybercity_workflow_contract app.test_cybercity_mqtt_protocol app.test_cybercity_device_health
```

The tests validate command-to-ack correlation, rejection of unrelated IDs, failed acknowledgments, firmware version mismatch, update failure, stale reports, and unsupported commands. They do not prove broker reliability, device execution or VM observation.

## Staging acceptance checklist

1. **Preflight:** Record the building ID, assigned CyberCityMachine, linked-clone VMID/template, monitor definition, target ESP32 MAC/pin/topic, broker TLS/ACL configuration and firmware version. Verify Cyber City staff permissions and the single ESP32 belongs to that building.
2. **VM detection:** Start the building's existing linked clone; create the configured file/service/database transition. Verify one authenticated agent observation causes exactly one edge-triggered event. Repeat without rearming and verify no duplicate event; revert and trigger again.
3. **Queue and publish:** Verify the durable command outbox persists the event and dispatcher sends the expected command to the correct building topic. Check failure/retry/deadline handling when the broker is unavailable.
4. **ESP32:** With validated firmware, clock and broker security, verify the correct physical GPIO changes. Verify retained messages do not replay stale actions and that a duplicate command ID is safely handled (especially across resets).
5. **Status and ack:** Verify the ESP32 publishes a correlated non-retained execution ACK and reported pin state. Check that LabTech rejects wrong IDs/buildings/pins, stale responses and malformed status.
6. **Instructor UI:** Verify the existing building page reflects the reported state; firmware check-in age and target version are accurate, including the 30-second fragment update and permission restrictions.
7. **Clone reset:** Request reset of **that building machine** only. Verify student session ownership, explicit confirmation, guest shutdown, linked-clone deletion, and recreation from the original template. Ensure its machine association, broker, and ESP32 mapping remain stable. Confirm no other student's VM is touched.
8. **Faults:** Disconnect MQTT, take the Control VM offline, power-cycle ESP32, make the HTTP report endpoint unavailable, and interrupt OTA staging. Verify visible failure/retry behavior and safe GPIO defaults.
9. **Firmware recovery:** On a spare ESP32 with working serial rescue, deploy a bad candidate, interrupt the file rename and reboot cycles, and verify known-good restoration before enabling any unattended behavior. The current recovery modules are *not* an automatic rollback mechanism.

## Release blockers

- Hardware MQTT/TLS and HTTPS certificate validation.
- Real GPIO output and status/ack tests; clock synchronization.
- Proxmox template reset lifecycle and isolation.
- Actual Django, browser, and broker integration tests.
- Power-loss-safe firmware boot and recovery. **Do not enable unattended OTA or auto rollback based on these contract tests.**

Record evidence for every test (VMID, monitor ID, command UUID, timestamps, MQTT topic, GPIO observation, expected/actual result, and tester). Never include credentials or student personal data in test reports.
