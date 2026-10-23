# Copy to ota_runtime_config.py on the ESP32 to enable report-only checks.
# Do not enable on production boards until HTTPS certificate validation is tested.
OTA_CHECK_ENABLED = False
OTA_INTERVAL_SECONDS = 3600

# DANGEROUS until HTTPS validation, USB recovery and power-loss testing.
# Explicit opt-in for single-app installation; disabled by default.
OTA_AUTO_INSTALL_ENABLED = False
