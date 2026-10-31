# Real Cyber City MQTT readiness check

This command performs a **real TLS/authentication connection** to the city's configured Mosquitto broker. It does not send simulated events or trigger physical pins.

From the existing LabTech virtual environment:

```bash
python manage.py check_cybercity_live_mqtt --city-id CITY_ID
```

It reports enrolled ESP32 controllers, mapped pins, versioned report topics, recent persisted command states, and whether the production host can authenticate to the configured MQTT broker. It rejects duplicate versioned report topics.

**This does not prove ESP32 presence or firmware compatibility.** For a physical acceptance test, start the per-city report listener installed in the previous PR, trigger an approved nonhazardous pin from a disposable Cyber City VM and observe the hardware, device serial log, Mosquitto report topic, LabTech command status and last confirmed pin status.

No broker configuration or credentials are printed. Do not enable versioned command mode until ESP32 firmware consumes JSON command envelopes and reports actual execution to its own ACL-protected `/report` topic.
