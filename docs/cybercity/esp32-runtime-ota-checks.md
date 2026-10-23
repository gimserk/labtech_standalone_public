# Optional report-only OTA checks in the ESP32 runtime

Copy `ota_runtime_config.example.py` to `ota_runtime_config.py` and set
`OTA_CHECK_ENABLED = True` only after validating the ESP32's HTTPS client
and certificate verification. The default remains **False**.

When enabled, the existing MQTT controller's idle loop periodically calls
the rate-limited `OTAPoller`. A newer firmware version is reported to the
serial console. It does **not** download, install, reboot, or activate
firmware automatically.

### Current limitations

- HTTP requests are synchronous and can delay MQTT message handling while
  waiting on the network. Do not enable with timing-sensitive hardware.
- No background thread, watchdog or asynchronous networking is introduced.
- No A/B slots. Automatic install/restart remains disabled.
- Host tests are structural; full functional and physical ESP32 tests are
  still required before shipping unattended updates.
