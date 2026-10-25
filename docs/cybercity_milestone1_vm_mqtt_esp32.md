# Milestone 1 — VM → MQTT → ESP32 verification

## Stage A: automated local-broker integration

This stage **really publishes messages through a disposable MQTT broker** and uses the repository's Django-side command encoder, ESP32 command decoder and server ACK validator. It simulates the GPIO output rather than driving physical pins. It does **not** currently exercise the Django event monitor, durable outbox dispatcher or device status database consumer, so it must not be reported as a completed VM-to-device end-to-end test.

Prerequisites: Docker Compose, Python 3.10+, `paho-mqtt>=2,<3`. Run this on a lab/dev workstation, not on a production broker.

```bash
cd firmware/cybercity/tests
docker compose up -d broker
cd ../../..
python -m pip install 'paho-mqtt>=2,<3'
TZ=UTC python firmware/cybercity/tools/test_mqtt_broker_integration.py -v
cd firmware/cybercity/tests
docker compose down
```

The test broker listens only on host `127.0.0.1:18884`; it deliberately permits anonymous access, has no persistence, and **must never be exposed to students, the network or production**. The test refuses a non-loopback broker. Ensure the test host's clock is synchronized and timezone is UTC, because the current firmware decoder uses UTC expiry timestamps and `time.mktime`.

Pass criteria: a fresh UUID command is received via MQTT on `<base>/pins/led/command`, the simulator changes GPIO-state variable to 1, a correlated non-retained `executed` ACK is accepted, and retained pin status is received. Failure/timeout is a failed test, not an automatic retry.

## Stage B: one actual Cyber City building — instructor checklist

Use one dedicated staging building and the **existing CyberCityMachine already listed under its building details**. Do not create a separate student lab machine.

1. Record Cyber City ID, building ID, CyberCityMachine ID, existing linked-clone VMID, Proxmox template VMID, monitor ID, ESP32 MAC, GPIO pin, MQTT topic and broker address. Never put secrets in test evidence.
2. Verify the Control VM broker's ACLs, credentials, TLS certificate checks and routes. Confirm UTC time on VM, LabTech and ESP32.
3. From a permitted student session, start the existing building VM; trigger a reversible monitored event (for example, create the lab-approved marker file) and record its event timestamp.
4. Confirm LabTech recognizes exactly one edge transition and records/enqueues the expected command. Capture command UUID, outbox entry state and topic; verify there is no duplicate event without rearming.
5. Confirm the dispatcher publishes to the correct building pin `.../command` topic. Verify a **physical** LED/output changes, not just a synthetic ACK.
6. Observe ESP32 `.../status` and `.../ack` topics, correlate ACK by UUID, and verify the building UI reflects state/last-seen correctly. For deployments still using legacy plaintext, document that v1 ACK correlation is **not validated** until the server's versioned-command flag and firmware are compatible.
7. Test wrong command ID, wrong building topic, broker outage/reconnect, and duplicate command handling. Verify no other building's ESP32 is touched.
8. Reset **that existing building machine** from its source template using the normal authorized flow; verify VMID ownership, monitor rearm and unchanged building association.
9. Record time, command UUID, expected/actual pin state, screenshot/serial log, HTTP/MQTT outcome and test operator for each step.

## Evidence and release gates

- **Gate A:** Broker-simulator test passes locally.
- **Gate B:** One actual VM event is observed by LabTech and results in the expected command in the outbox.
- **Gate C:** A physical ESP32 executes the command, and the server receives/reconciles status and ACK (if v1 is enabled).
- **Gate D:** Building page shows current state and only the correct building machine is reset safely.

Only mark Milestone 1 complete after A–D pass with evidence. Broker simulation alone does not prove Proxmox, monitor/outbox scheduling, real GPIO, MQTT TLS/ACLs, or OTA rollback. Automatic OTA rollback remains disabled.
