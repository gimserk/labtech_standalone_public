# Optional ESP32 MQTT TLS wiring

This increment extends existing `BuildingController` and
`device_startup.py`. It **does not** alter Cyber City building and pin
models, attack commands or MQTT topics.

## Changes

- `BuildingController` accepts optional `tls_params` for the existing
  MicroPython `umqtt.simple.MQTTClient` implementation.
- If TLS parameters are supplied, the controller checks that
  `server_hostname` equals the configured MQTT host and
  `cert_reqs` equals `ssl.CERT_REQUIRED`. A MicroPython build unable to
  express that requirement fails closed.
- `device_startup.py` optionally imports local `mqtt_tls_config.py`.
  By default MQTT continues with the original plaintext configuration.
  The startup rejects plaintext when the configured broker port is 8883.
- The broker continues to run on the city's Control VM. Broker host/port
  continue to originate from the existing authenticated LabTech v2 device
  configuration endpoint. Credentials remain local to the ESP32.

## Actual TLS support is board-dependent

The standard `umqtt.simple` client and MicroPython `ssl` module differ
between board firmware versions. On some builds, `ssl_params` does not
accept these keywords or cannot load a trusted CA; in those cases TLS
will fail, and you must install/test a compatible MQTT transport rather
than disabling verification.

**This change does not establish that hostname or certificate validation
works on an actual ESP32.** Test the trusted-CA connection, wrong-CA
rejection, and mismatched-hostname rejection on the exact production
MicroPython/ESP32 version. Some builds can silently omit hostname checks.

## Test plan

1. Verify the Control VM broker is reachable and has a valid server
   certificate matching the configured broker hostname.
2. Set up a unique device account with read-only permission on assigned
   command topics and write-only permission on status topics.
3. Confirm that plaintext configurations still work against the current
   non-TLS test broker on port 1883.
4. With a compatible device TLS build, enable `mqtt_tls_config.py` and
   confirm that the device can connect over port 8883.
5. Reject expired, untrusted CA, and wrong-hostname broker certificates.
6. Verify existing attack monitor command/status exchange and reconnect
   behavior after a broker restart.
7. Do not enable automatic power-on boot or connect critical actuators
   until these checks and fail-safe behavior pass.

## Remaining work

- TLS for LabTech's device HTTPS request must also be validated on the
  MicroPython runtime.
- Device credential issuance and MQTT ACL automation remain manual.
- Physical device, Django, and broker integration tests are outstanding.
- Current v1 MAC-only firmware endpoints require separate hardening.
