# Cyber City status listener deployment

Cyber City pin state collection should run outside the Django web request lifecycle. The `listen_cybercity_status` management command supports a persistent MQTT connection and resubscribes after network interruptions. Run **one supervised listener per Cyber City**, not one per building.

Example for Cyber City ID 1:

```bash
/opt/venv/bin/python /opt/labtech/manage.py listen_cybercity_status --city-id 1 --forever
```

Example systemd unit (adjust Python path and user to match your installation):

```ini
[Unit]
Description=LabTech Cyber City 1 ESP32 MQTT Status Listener
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=labtech
Group=www-data
WorkingDirectory=/opt/labtech
ExecStart=/opt/venv/bin/python /opt/labtech/manage.py listen_cybercity_status --city-id 1 --forever
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

To deploy, save as `/etc/systemd/system/labtech-cybercity-status-1.service`, run `sudo systemctl daemon-reload`, then `sudo systemctl enable --now labtech-cybercity-status-1`, and inspect with `journalctl -u labtech-cybercity-status-1 -f`. Repeat per city, substituting the city ID.

This listener accepts **only** configured `/status` pin topics, records reported values and timestamps on existing `CyberCityESP32Pin` rows, and uses the city's broker authentication and TLS settings. An MQTT broker must restrict publish rights to the correct controller and building topics. **A status packet is device-reported data, not cryptographically verified proof of a specific command's execution.** Correlated command acknowledgments require further work.

**Operational limits**:
- Restart the listener after adding/removing pins or changing building MQTT topics; its subscribed topic map is loaded at worker startup.
- Incoming broker-retained status is not a fresh heartbeat. The current listener treats receipt time as the observation timestamp; freshness/retained-message handling must be improved before declaring a device online.
- Use a secure broker, per-device ACLs and TLS. Do not expose unauthenticated MQTT on production networks.
- This listener is separate from `dispatch_cybercity_commands`. Schedule that command independently; this listener does not send commands.
- The firmware must publish status to `<building-topic>/<pin-subtopic>/status`; otherwise the subscriber receives nothing.
- Deploy to development and validate with a real ESP32 and MQTT broker before treating this as production-ready.
