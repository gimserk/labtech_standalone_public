# Cyber City: automatic MQTT status + WS2811 addressable LED strips

## Automatic status listener

The production Cyber City MQTT status ingestion process is
`labtech-cybercity-status.service`. It subscribes to all configured cities and
refreshes its subscription list every 15 seconds. New cities, enrolled ESP32s
and changed GPIO topics are discovered without an instructor running a console.
It uses LabTech's existing broker credentials and optional verified MQTT TLS
settings; no browser session is involved.

Fresh `<pin-topic>/status` publications update `last_status` and
`last_status_timestamp`. Retained broker values update **last known** status
only and **do not claim a new timestamp**. JSON execution acknowledgments
arriving at `<pin-topic>/ack` are matched to the command id.

For new native installations, `install.sh` installs and enables this service.
`deploy/update.sh` creates/enables/restarts the managed unit without rewriting
the existing environment or replacing the main web/worker/beat service units.

For existing installations updated with a bare `git pull`, perform a **one-time**
systemd registration (service then survives boot and autorestarts):

```bash
sudo install -m 0644 /opt/labtech/deploy/systemd/labtech-cybercity-status.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now labtech-cybercity-status
sudo systemctl status labtech-cybercity-status
sudo journalctl -u labtech-cybercity-status -f
```

The service's shell launcher detects `/opt/labtech/venv` or legacy
`/opt/venv` without creating a new virtual environment. For current
`/etc/labtech/deployment_settings.py` installations it also sets the
deployment settings module. One process handles all cities; do **not** run
`listen_cybercity_status --city-id ... --forever` simultaneously in
production unless isolating a temporary diagnostic.

## WS2811 strip configuration

Open Cyber City → Building → ESP32 → **Device Settings & Pins**:

1. Select **WS2811 addressable RGB LED strip** for the pin.
2. Set the ESP32 **data GPIO** (use GPIO18/19/23/25/26 when available;
   avoid UART GPIO3 and boot-strapping pins on a typical original ESP32).
3. Set the **addressable LED count** (1–300), matching the number of
   individually controlled pixels (not always the number of physical LEDs on
   a 12V WS2811 strip).
4. Set maximum **brightness** from 1–255 (default 64), which limits each
   channel, and configure a unique MQTT subtopic.
5. Save, then restart `device_startup.run()` on the ESP32 so it fetches
   the new settings.

Predefined case-insensitive MQTT payloads to the strip's `/command` topic:

| Mode | Approximate color | Suggested use |
|---|---|---|
| OFF | Off | No indication |
| NORMAL | Green | Healthy / all operational |
| WARNING | Amber/yellow | Partial outage or attention |
| ERROR | Red | Critical failure |
| INFO | Blue | Informational |
| MAINTENANCE | Purple | Scheduled work |
| BUSY | Orange | Processing or active operation |
| RECOVERY | Cyan | System restoring |
| WHITE | White | Hardware test (highest combined current) |

Legacy `ON` and `1` map to `NORMAL`; `OFF` and `0` map to `OFF`.
The default firmware applies one solid color to the entire strip; animations,
pixel-specific commands and live color mixing are not yet implemented.
The GPIO status retains the **mode name**, not a numeric pin value.
Existing simple LEDs and PWM output commands are unaffected.

A strip uses the MicroPython `neopixel` driver with 800 kHz timing. Some
older WS2811 strips use 400 kHz; verify your exact strip and board before
use. Confirm the `neopixel` module exists in your MicroPython build.

### Physical wiring and power safety

Use a separately rated LED supply (often 5V or 12V depending on strip type),
**shared ground with the ESP32**, a suitable 3.3V-to-5V data level shifter,
and manufacturer-recommended series data resistor, bulk capacitor and fusing.
Never power a long strip from an ESP32 GPIO or 3.3V pin. Budget for worst-case
full-white current before connecting the strip.

## Firmware and troubleshooting

Download Basic ESP32 Firmware again after updating LabTech. Copy the updated
`mqtt_controller.py` and `device_startup.py` alongside your existing
`bootstrap_config.py`, `mqtt_secrets.py`, `labtech_https.py`, and support
modules. Do not overwrite stored credentials with example files.

The firmware prints: broker endpoint, successful connection/subscriptions,
received command and output state, and one-time idle socket errors.
`OSError(-1)` from a nonblocking socket read is treated as an idle condition,
with MQTT heartbeat pings every 20 seconds. Genuine connection failures still
trigger safe outputs and reconnection through `device_startup.run()`.

```python
import device_startup
device_startup.run()
```

Verify live status using the LabTech building's ESP Status column and the
service's journal. Status is the **device-reported state** and does not
independently prove that a load or external circuit is electrically healthy.

The HTTPS certificate verification policy is independent of MQTT broker TLS.
Continue to use restricted broker credentials/ACLs. Avoid unattended firmware
updates on the unverified HTTPS classroom configuration.
