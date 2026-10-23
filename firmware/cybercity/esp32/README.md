# Cyber City ESP32 — first integration milestone

This folder contains an initial, **read-only onboarding diagnostic**, not a
production OTA updater. It deliberately uses LabTech's existing models and
API routes without changing those server routes.

## Existing LabTech integration

- `CyberCityESP32.mac_address` identifies a registered controller belonging
  to a `CyberCityBuilding`.
- `/api/firmware/check/?mac=<MAC>&version=0` returns the active firmware
  version, file URLs, and the existing `config_url`.
- `/api/firmware/get-config/?mac=<MAC>` generates the city's MQTT broker
  address, the building's MQTT base topic, and ESP32 pin subtopics.
- `/api/firmware/download/<id>/` and
  `/api/firmware/download/library/<id>/` serve existing uploaded firmware.
- Attack monitors publish text command payloads to
  `<building.mqtt_base_topic>/<pin.mqtt_subtopic>/command`.
  Building status polling expects pin reports on the corresponding `/status`
  topic, ideally retained so it can be read on demand.
- The MQTT broker is hosted on the Cyber City **Control VM** (planned utility
  machine role). Its address is already stored in `CyberCity.mqtt_broker_address`.

## Testing on ESP32 (diagnostics only)

1. Flash an appropriate MicroPython build with HTTPS-capable TLS support.
2. Copy `bootstrap_config.example.py` to `bootstrap_config.py` and set
   Wi-Fi and HTTPS LabTech URL.
3. Copy `onboard_check.py` and `bootstrap_config.py` to the device.
4. Register its Wi-Fi MAC in the existing building ESP32 administration page.
5. Run `import onboard_check; onboard_check.check_assignment()`.
6. Confirm the correct active firmware version is displayed.

The existing API currently trusts the MAC supplied in a request. **Do not**
enable automatic code installation or distribute MQTT credentials through
these routes until authenticated enrollment, authorization, manifest integrity
and atomic update/rollback are implemented. Device MAC is an identifier, not
an authentication credential. Do not expose the current config endpoint over
untrusted networks.

## Next compatible changes

1. Add Control VM as a third city utility role using the existing
   Firewall/Management lifecycle and Guacamole patterns.
2. Add secure, one-time enrollment and per-device credentials to the existing
   firmware API; keep current routes compatible during migration.
3. Return complete pin types/config via structured JSON, preserving the current
   topic composition and legacy Python config for existing clients.
4. Add verified download, atomic installation, rollback and MQTT status/command
   handling to the permanent MicroPython bootstrap.
5. Integration-test retained pin statuses and attack monitor commands through
   the broker on Control.

## Current limitations

This diagnostic does not install firmware or connect to MQTT. It does not
claim that Guacamole or the broker are working. Those require server and VM
integration testing.
