# Copy to bootstrap_config.py on the ESP32 (never commit real secrets).
WIFI_SSID = "DNCC-IOT"
WIFI_PASSWORD = "REPLACE_ME"
LABTECH_URL = "https://labtech.lccc-itp.org"

# Isolated Cyber City lab mode: accept any HTTPS certificate, including
# self-signed ones, without validation. This is vulnerable to impersonation
# and credential interception. Do NOT use across untrusted networks.
LABTECH_TLS_VERIFY = False

# Optional: turn verification back on and provide the public DER certificate:
# LABTECH_TLS_VERIFY = True
# LABTECH_CA_CERT_FILE = "labtech-ca.der"

# Generate with: python manage.py issue_cybercity_esp32_key <MAC>
DEVICE_KEY = "REPLACE_WITH_DEVICE_KEY"
