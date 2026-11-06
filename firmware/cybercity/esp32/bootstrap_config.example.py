# Copy to bootstrap_config.py on the ESP32 (do not commit real secrets).
WIFI_SSID = "DNCC-IOT"
WIFI_PASSWORD = "REPLACE_ME"
LABTECH_URL = "https://labtech.lccc-itp.org"
# Copy ONLY the public self-signed certificate (DER), never the private key.
# Convert PEM to DER: openssl x509 -in labtech-selfsigned.crt -outform DER -out labtech-ca.der
LABTECH_CA_CERT_FILE = "labtech-ca.der"

# Generate with: python manage.py issue_cybercity_esp32_key <MAC>
DEVICE_KEY = "REPLACE_WITH_DEVICE_KEY"
