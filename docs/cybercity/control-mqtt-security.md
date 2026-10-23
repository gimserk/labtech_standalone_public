# Cyber City Control VM — MQTT security rollout

This deployment-only increment uses the **existing** CyberCity
`mqtt_broker_address`, `mqtt_broker_port`, building
`mqtt_base_topic`, and `CyberCityESP32Pin.mqtt_subtopic`.
It does not replace LabTech's MQTT attack monitor or status polling code.

## Broker template and authorization

Use `deploy/cybercity/mosquitto/mosquitto.conf.example` as the Control
VM's Mosquitto starting configuration, and `acl.example` as a
single-building ACL example. Neither file contains operational secrets.
Install Mosquitto on the Control VM template and provision server TLS
certificate/key plus a trusted CA chain before enabling the service.

The broker uses port **8883** for TLS MQTT, not the current default
1883. Set the city's MQTT broker port in the existing LabTech city
settings only when all LabTech and device-side clients support TLS.

For each device:
1. Register it in the existing Cyber City building and assign pins.
2. Create a unique broker username and random broker password with
   `mosquitto_passwd`; keep both secret.
3. Permit reads on its assigned `<pin-topic>/command`, and writes
   only on its assigned `<pin-topic>/status` and its own device status.
4. Create a distinct LabTech service account for the city, with the
   minimum read/write privileges needed for configured pins.
5. Test denied publishing to another building or device.

## Existing client integration gaps

**Do not switch the broker to TLS-only yet.** Existing LabTech Python
`paho-mqtt` connection calls in `app/views.py` currently specify
host/port/credentials but do not configure TLS. The current
MicroPython `BuildingController` uses `umqtt.simple` without TLS
or certificate validation. Setting city port to 8883 now would break
these clients.

Prior to cutover, add a trusted-CA TLS transport to both client paths,
verify hostname/certificate validation on the actual ESP32 build,
and validate the retained status and command roundtrip. Current
LabTech GUI still stores the service account username/password in
the city record; secret protection at rest should be reviewed before
deployment.

## Other limitations

- Topic ACLs are explicit examples; generate actual ACLs from stored
  ESP32 pin assignments. Every topic under the current building topic
  must be evaluated for collision across multiple ESP32 devices.
- Isolation protects against devices controlling one another but
  does not make unsafe physical actuators suitable for testing.
- Broker credentials are distinct from the LabTech API's ESP32
  provisioning key and must not be logged or committed.
- Devices still require robust reconnect, secure TLS verification,
  and eventually automatic firmware update rollback.
- Run `mosquitto -c <config-file> -v` on a disposable Control VM
  and positive/negative pub/sub tests before deploy. Never place
  real secrets in the example files.
