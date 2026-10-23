# ESP32 MQTT resilience — development milestone

This change extends the existing `BuildingController` and unified startup.
It does not alter Django models, device mappings, or MQTT topic naming.

## Changes
- Uses MQTT last-will retained `offline` on the existing device status topic.
- Publishes retained `online` after subscription setup.
- Sets configured LED and PWM outputs to zero when the controller exits.
- Reconnects Wi-Fi, re-fetches LabTech building configuration, and
  reconnects MQTT with 2-to-60-second bounded exponential backoff.

## Critical limitations
- Network partitions can leave physical outputs in their prior state until
  the firmware detects disconnection. MQTT keepalive does not guarantee an
  immediate safe state. Only test with non-critical low-power LEDs.
- `umqtt.simple` may differ between MicroPython builds; verify
  `set_last_will` support and reconnect behavior on the actual board.
- Automatic boot is **not** enabled by default because the current
  `urequests` and MQTT client do not establish verified TLS end-to-end.
- The current MQTT client does not use TLS and does not enforce broker ACLs.
- Power-loss resilience, OTA activation, rollback, and MQTT TLS require
  hardware validation before production use.

## Tests to perform
1. Power on control VM with authorized test MQTT credentials.
2. Test LED and PWM commands using existing attack monitor topics.
3. Kill ESP32 networking without a clean disconnect; confirm retained
   device `/status` becomes `offline` after broker keepalive expiry.
4. Restore networking; confirm LabTech configuration reloaded, `online`
   published, and command subscription restored.
5. Stop the controller with a simulated MQTT exception; confirm GPIO
   output is zero.
6. Re-test existing Firewall/Management/Control console operations separately.

Do not connect locks, motors, mains equipment or any life-safety devices
to this prototype.
