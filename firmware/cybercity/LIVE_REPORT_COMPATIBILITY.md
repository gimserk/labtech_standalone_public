# Live ESP32 execution reports — firmware / backend compatibility

The actual MicroPython controller resides in `firmware/cybercity/esp32/mqtt_controller.py` and is included in the downloadable Cyber City firmware bundle.

## Fixed mismatch

Previously firmware published versioned execution results to `<pin-topic>/ack`, while LabTech's live MQTT listener subscribed to `<pin-topic>/report`. The controller now publishes versioned results to `/report`, matching the existing listener. It continues to publish actual GPIO state separately to the existing retained `/status` topic.

**Firmware on already-flashed boards does not update merely by merging code.** Upgrade the affected ESP32(s) using the existing firmware update/OTA process and verify installed version and behavior. Do not switch on `use_versioned_commands` until the board has correct firmware and a synchronized UTC clock.

For each physical pin:
- Command input: `<pin-topic>/command` — v1 JSON with UUID, action, value and UTC expiry.
- Actual execution acknowledgment: `<pin-topic>/report` — v1 JSON with command UUID, status and actual GPIO state.
- Legacy retained state: `<pin-topic>/status` — existing raw state value.

Mosquitto publisher ACL must permit the board to publish its `/report` and `/status` only and subscribe to its assigned `/command` topics; LabTech listener must subscribe to those `/report` topics. Use the existing city TLS configuration. A broker `published` command is not a confirmed `executed` action.

## Live validation

1. Install updated firmware on an authorized test board, with a nonhazardous LED output.
2. Start the real `labtech-cybercity-mqtt@CITY_ID` listener.
3. Trigger a real QEMU monitor event on an isolated VM, or issue an authorized command using the existing live path.
4. Confirm the board changes the physical LED; inspect the board's `/report` JSON and the corresponding LabTech `CyberCityCommand.status == 'executed'`.
5. Confirm the SOC dashboard displays the latest confirmed pin state, not merely broker publication.

No physical hardware was accessed as part of this source-code PR.
