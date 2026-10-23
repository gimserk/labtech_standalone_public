# ESP32 building MQTT controller

## Compatibility with existing LabTech

The `BuildingController` class uses `api/firmware/v2/config/`
JSON fields `mqtt.host`, `mqtt.port`, `mqtt.base_topic`, and
each `pins[].number`, `pins[].type`, `pins[].topic`.
It subscribes to each existing `<pin-topic>/command` and publishes
the corresponding `<pin-topic>/status` as retained text. This
preserves existing building attack monitors and the pin-status poller.

The broker resides on the city's **Control VM**. LabTech already stores
its configured network address and port on the CyberCity record.

## Supported pin types (first increment)

- `LED`: payload `on`, `off`, `1`, `0`.
- `DUTY_CYCLE`: raw `0..65535` duty or `0..100%` (e.g., `50%`).
- `I2C_LED` and `I2C_SCREEN`: explicitly unsupported until I2C bus,
  address and peripheral-type configuration exists in LabTech. No GPIO
  is initialized for unsupported types.

Device publishes `<building-base>/devices/<device-id>/status` as
`online` upon connection and `offline` on a clean stop.
Unexpected power or network loss cannot publish offline without a
broker last-will configuration. Implement last will/persistent presence
tracking before considering availability monitoring reliable.

## Manual test

1. Assign a test ESP32 to an existing Cyber City building.
2. Obtain JSON from the authenticated `/api/firmware/v2/config/` API.
3. Copy the vetted JSON into a local `CONFIG` variable in
   `local_config.py`, plus unique `DEVICE_ID` and MQTT credentials.
4. Install `umqtt.simple` and `mqtt_controller.py`; run
   `mqtt_controller.example.py` (or equivalent REPL imports).
5. Publish a valid test command to a registered pin's
   `<base>/<subtopic>/command`; verify retained `/status`.
6. Trigger the existing LabTech attack monitor and confirm the GPIO
   and the building's status polling match.

## Limitations / required follow-ups

- MQTT authentication/ACL and TLS must be set up on the Control VM
  before connecting untrusted hardware; this prototype does not
  establish TLS or verify broker certificates.
- `umqtt.simple` callback runs synchronously; Wi-Fi/broker reconnection,
  rate limiting, watchdog, broker last-will and failure-safe outputs
  are not yet implemented. Only test with low-power indicators;
  do not connect locks, mains relays or critical equipment yet.
- MQTT command payloads currently follow existing attack monitor
  free-text strings; they are not JSON.
- The current Cyber City pin model does not identify GPIO inputs,
  pull resistor mode, I2C bus/address, servo PWM frequency, or active-low
  hardware. Those must be added selectively rather than inferred.
- Multiple devices inside one building must use distinct pin subtopics
  to avoid sharing the same command topic.
- Firmware is not automatically installed or activated. This module
  is a manually provisioned controller test, not production OTA.
