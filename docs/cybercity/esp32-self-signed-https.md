# Cyber City ESP32 — LabTech HTTPS with a self-signed certificate

The ESP32 connects to LabTech's **HTTPS firmware API**, separate from its
MQTT connection to the Cyber City broker. The same trusted HTTPS client is used
for provisioning, runtime firmware reports, manifest checks and OTA downloads.

## On the LabTech/Nginx server

1. Configure Nginx on 443 with the self-signed certificate whose
   subjectAltName includes `labtech.lccc-itp.org`. The current ESP32 hostname
   must match that SAN. The device should use:
   `LABTECH_URL = "https://labtech.lccc-itp.org"`.
2. Copy **only the public certificate**, NOT the private key, to a trusted
   workstation. Example source: `/etc/ssl/certs/labtech-selfsigned.crt`.
3. Convert it into DER (MicroPython's documented `cadata` format):

   ```bash
   openssl x509 -in labtech-selfsigned.crt -outform DER -out labtech-ca.der
   ```

4. Place `labtech-ca.der` alongside `bootstrap_config.py` and
   `labtech_https.py` from the latest **Basic ESP32 Firmware** ZIP.
   Configure:

   ```python
   WIFI_SSID = "YOUR_WIFI"
   WIFI_PASSWORD = "YOUR_PASSWORD"
   LABTECH_URL = "https://labtech.lccc-itp.org"
   LABTECH_CA_CERT_FILE = "labtech-ca.der"
   DEVICE_KEY = "YOUR_PROVISIONING_KEY"
   ```

5. Flash a recent, tested MicroPython ESP32 build that supports
   `ssl.SSLContext`, `load_verify_locations(cadata=...)`,
   `ssl.CERT_REQUIRED`, and `wrap_socket(..., server_hostname=...)`.
   **Set the ESP32 RTC accurately** before TLS validation. Example from
   the connected workstation: `mpremote connect COM5 rtc --set` (check
   your mpremote version's RTC command), or sync with NTP over Wi-Fi.
6. Use the included installer from the extracted ZIP, after configuring
   `mqtt_secrets.py`:

   ```bash
   python tools/usb_install.py --port COM5 --directory . --install
   ```

7. From the MicroPython REPL:
   ```python
   import device_startup
   device_startup.run()
   ```

The ESP32's HTTPS code **does not use `verify=False` or `CERT_NONE`**.
Instead, it explicitly trusts the self-signed LabTech certificate via a local
DER file and requires certificate verification with the configured hostname.
If the firmware's TLS stack doesn't support that, startup fails closed.

### Optional workstation-side provisioning helper

If using `tools/prepare_device.py` from this repository instead of editing
`bootstrap_config.py` manually, pass `--ca-cert labtech-selfsigned.crt`
along with `--labtech`, `--mac`, and `--output`. The helper will use the
certificate to validate the LabTech HTTPS response and create
`labtech-ca.der` in the private output directory.

### Verify before classroom use

- Confirm good CA and exact hostname connect successfully.
- Replace `labtech-ca.der` with another certificate and confirm connection
  is rejected.
- Change `LABTECH_URL` to a mismatched hostname and confirm rejection.
- Confirm the ESP32 clock is correct, otherwise an otherwise valid cert may
  fail the validity window check.
- Confirm OTA status checks and firmware downloads use the same trusted HTTPS
  path, and that MQTT broker authentication is configured separately.
- Do **not** turn on unattended OTA until the exact board rejects invalid and
  mismatched certificates, and power-loss recovery has been tested.

**Certificate rotation:** When the Nginx certificate is renewed, provision
the new public certificate on devices in a controlled maintenance window
before switching the server certificate. A board pinned to the old one will
correctly reject the new certificate until updated.

**Important:** This does not change MQTT TLS. For a broker on 1883, existing
MQTT authentication and topic ACLs must still be configured separately.
