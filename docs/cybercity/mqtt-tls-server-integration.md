# Optional verified MQTT TLS for Cyber City

This incremental change uses the existing city broker settings and current paho-mqtt operations.
No existing building, pin, firmware, or MQTT topics are changed.

## Server configuration
1. Install an appropriate CA certificate bundle on the LabTech server.
2. Configure the broker on the Control VM with a certificate whose hostname matches the existing city MQTT broker address. Prefer DNS hostname rather than IP unless certificate SAN contains the IP.
3. In the existing Cyber City edit form, set the broker port (normally 8883), enable **MQTT TLS**, and optionally set the absolute **server-local CA certificate path**. Leaving it empty uses the host operating system's default trust store.
4. Configure the city broker username/password as before. Set appropriate topic ACLs on Control VM.
5. Check the existing city broker status, manually trigger one noncritical attack monitor, and inspect retained pin status.

The new boolean `mqtt_use_tls` defaults to False, preserving preexisting cities.

## Not yet a complete rollout

- The MicroPython `BuildingController` still uses non-TLS `umqtt.simple`. **Do not cut over the city broker to TLS-only until ESP32 TLS hostname/certificate verification is tested on the actual board firmware.**
- Existing v1 firmware endpoints still expose MAC-only access. Restrict them before using production networks.
- LabTech currently stores city broker passwords in a plain model field. Review secret handling at rest.
- Host CA path is configured by authorized administrators and must point to a trusted server-local file. Avoid uploading arbitrary certificates from untrusted users.
- Run `python manage.py makemigrations --check --dry-run`, `python manage.py check`, and focused TLS tests on staging. Broker certificate verification, version compatibility and network access must be tested before deployment.
