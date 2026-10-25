# ESP32 controller acknowledgment compatibility

The controller now understands **both** existing raw `ON` / `OFF` / `0` / `1` / PWM commands and versioned JSON v1 commands. Legacy raw commands still publish `/status` but cannot acknowledge a command ID.

JSON command example:

```json
{"schema":1,"command_id":"550e8400-e29b-41d4-a716-446655440000","action":"set","value":"ON","expires_at":"2026-10-25T23:00:00+00:00"}
```

For supported JSON commands the ESP32 publishes a **non-retained** `<pin-topic>/ack` with the matching `command_id`, `status` (`executed` or `failed`), and optional reported `state`. The existing `<pin-topic>/status` publication remains supported.

## Security and operational notes

- The controller rejects expired JSON commands and rejects all versioned commands when its RTC is not synchronized. Sync the MicroPython RTC against a trusted UTC NTP/time source **before enabling v1 JSON dispatch**. The application does not silently accept unsynchronized clocks.
- MQTT transport authentication/TLS and per-building broker ACLs are required. JSON command IDs by themselves are **not authentication**.
- For this pilot, duplicate command IDs are remembered only in RAM (64 entries). A reset or cache eviction can permit repeated execution. Do not use non-idempotent physical actions until persistent deduplication is implemented and tested.
- Current LabTech outbox still sends legacy raw-string commands, so installing this firmware alone does **not** activate server-side command correlation. Switching server dispatch to JSON requires a separate explicit capability/rollout.
- This controller supports simple LED/PWM only. I2C outputs and safe atomic OTA rollback are still incomplete.
- Add `command_protocol.py` alongside `mqtt_controller.py` and other firmware bundle files on the ESP32.
- Validate hardware MQTT connections, NTP/RTC, broker ACLs, restart behavior, and OTA packaging on a real ESP32 before enabling JSON messages in production.
