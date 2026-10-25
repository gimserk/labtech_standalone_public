# Cyber City versioned MQTT commands — controlled rollout

The existing **Cyber City → Building → ESP32** form now has an opt-in `use_versioned_commands` option. **Default is off** for all existing boards. When off, the outbox continues sending the existing plain-text commands.

When enabled for a controller, the outbox publishes JSON v1 messages with the stored `CyberCityCommand.command_id`, action `set`, the configured command payload as its value, and a UTC deadline five minutes from publication. The ESP32 firmware from PR #81 responds on the pin's `/ack` topic. Its exact acknowledgment can be correlated to an outbox row.

Before enabling for a controller:
1. Install and verify the updated MicroPython controller from PR #81 (including `command_protocol.py`).
2. Ensure a reliable UTC RTC/NTP sync **before** starting command handling.
3. Enable broker TLS certificate validation, per-device MQTT credentials, and topic ACLs. Verify the device publishes to only its building's `/ack` and `/status`.
4. Confirm a test JSON command triggers one intended output and the command state changes to `executed` in the database.
5. Only then enable the checkbox for the device in Cyber City.

**Important limitations:** This is an opt-in protocol, not an automatic compatibility negotiation. This firmware stores a bounded command-ID deduplication cache in RAM; resets can cause repeated actuation. The dispatcher has retry semantics but does not yet have complete crash-safe idempotency or a dashboard showing acknowledgment progression. Acknowledgments and reported pin values are not independent verification of a physical output.

Run Django migrations before testing this feature.
