# ESP32 provisioning v2 (incremental security boundary)

This feature adds an authenticated, read-only JSON configuration endpoint. It
reuses the existing Cyber City models, firmware assignments, and MQTT topics.
It does not replace the current firmware check or firmware download endpoints.

## Set up a registered device

From the LabTech application server:

```bash
python manage.py migrate
python manage.py issue_cybercity_esp32_key AA:BB:CC:11:22:33
```

The command prints a new random device key once; securely copy it to the
ESP32 bootstrap configuration. Running the command again rotates the key.
Keys are stored hashed in the database. Keep keys out of version control.

Request device configuration through the LabTech HTTPS URL:

```bash
curl --fail --show-error \
  -H "Authorization: Bearer <DEVICE_KEY>" \
  "https://labtech.example.edu/api/firmware/v2/config/?mac=AA:BB:CC:11:22:33"
```

The response includes the assigned city, building, MQTT broker host/port/base
topic, GPIO pin numbers/types/subtopics and current firmware version.

### Security / implementation notes

- HTTPS is mandatory. For an HTTPS reverse proxy, configure Django's
  `SECURE_PROXY_SSL_HEADER` only when the proxy is trusted and sanitizes
  inbound forwarded protocol headers. Device TLS certificate validation is
  required too.
- The MAC address is an inventory lookup, not authentication. The bearer key
  is required for every v2 request.
- The v2 response intentionally omits MQTT usernames/passwords. Deliver
  per-device MQTT credentials only after broker authentication, topic ACLs
  and secure transport are tested.
- **Existing v1 endpoints are unchanged** and continue to permit MAC-only
  checks/configuration and unprotected firmware downloads. They must be
  restricted or hardened before operating outside an isolated development
  environment; a v2 bearer key does not secure those legacy endpoints.
- Firmware downloads and OTA execution are **not** enabled by this change.
  The next work item should require the same authorization for file downloads,
  verify integrity, and implement atomic device updates with rollback.
- The Control VM is the intended city MQTT broker. The address remains
  configured in existing `CyberCity.mqtt_broker_address`.
- No GPIO mapping or building attack monitor behavior is changed.

## Validation before deployment

Run `python manage.py makemigrations --check --dry-run`,
`python manage.py check`, and the new provisioning tests. Test reverse-proxy
HTTPS detection and key rotation before deploying to actual boards.
