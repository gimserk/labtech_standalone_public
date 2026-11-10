# Cyber City ESP32 — HTTPS on a classroom lab network

LabTech's basic ESP32 application uses `labtech_https.py` for authenticated
firmware configuration, runtime reports, and firmware downloads. HTTPS remains
the protocol in both modes. **The default is now unverified HTTPS for isolated,
trusted classroom networks**, including self-signed and expired certificates.

## Quick start: no certificate file (requested lab mode)

1. Download the latest **Basic ESP32 Firmware** ZIP after LabTech has been
   updated. The ZIP includes the updated `labtech_https.py` and USB installer.
2. Configure `bootstrap_config.py` (keep the provisioning key private):

   ```python
   WIFI_SSID = "YOUR_WIFI"
   WIFI_PASSWORD = "YOUR_WIFI_PASSWORD"
   LABTECH_URL = "https://labtech.lccc-itp.org"
   LABTECH_TLS_VERIFY = False
   DEVICE_KEY = "YOUR_PROVISIONING_KEY"
   ```

3. Configure `mqtt_secrets.py` with the device's broker account and ACLs.
   No `LABTECH_CA_CERT_FILE` setting or `labtech-ca.der` is required.
4. On a workstation where `mpremote` is installed:

   ```powershell
   cd C:\CyberCity\ESP32
   & "C:\Users\johnt\AppData\Local\Python\pythoncore-3.14-64\python.exe" tools/usb_install.py --port COM5 --directory . --install
   ```

   The installer invokes `sys.executable -m mpremote`, so a Windows PATH
   entry for the standalone `mpremote` command is not required.

5. From Thonny or the REPL:

   ```python
   import device_startup
   device_startup.run()
   ```

An existing `bootstrap_config.py` without `LABTECH_TLS_VERIFY` also defaults
to the unverified lab mode once the new `labtech_https.py` is uploaded. This
removes the previous “Set LABTECH_CA_CERT_FILE” startup failure.

## Optional: enable certificate verification

To require that the ESP32 recognize your LabTech server's public certificate,
set `LABTECH_TLS_VERIFY = True` and:

1. Copy only the Nginx server's public certificate (never its private key).
2. Convert PEM to DER, for example:

   ```bash
   openssl x509 -in labtech-selfsigned.crt -outform DER -out labtech-ca.der
   ```

3. Set `LABTECH_CA_CERT_FILE = "labtech-ca.der"` in `bootstrap_config.py`.
4. Place the DER file alongside the other app files and re-run the installer.

This verified mode requires a MicroPython SSL build able to use
`ssl.SSLContext`, `load_verify_locations`, and `ssl.CERT_REQUIRED`.
Synchronize the device RTC and test hostname rejection for your exact board.

## Security and scope

Unverified HTTPS **does not authenticate the LabTech server**. An attacker on
the network could impersonate the LabTech host, intercept the ESP32 device key,
send malicious configuration, or replace firmware during an OTA download.
This is **not safe on shared campus, guest, internet, or untrusted Wi-Fi**.

The request client continues to require HTTPS and restrict API requests to
the configured LabTech firmware origin; it never follows redirects. However,
those checks do not protect against TLS man-in-the-middle attacks.

Do not enable unattended OTA in unverified mode. Physical classroom pilots
should use noncritical LED loads and have a way to recover over USB.

**MQTT broker authentication, topics, permissions, and MQTT TLS are separate**
from LabTech HTTPS and are unaffected by this setting.
