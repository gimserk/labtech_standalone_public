# Optional automatic single-application OTA policy

The default ESP32 runtime configuration includes:

```python
OTA_CHECK_ENABLED = False
OTA_AUTO_INSTALL_ENABLED = False
OTA_INTERVAL_SECONDS = 3600
```

After verified TLS trust, USB recovery rehearsals and on-device testing,
operators can explicitly enable both flags to authorize automatic update
installation from LabTech's already-active firmware release. The running
MQTT controller polls at the configured interval. When an update is
available, the existing OTA client stages it, checks SHA-256, and installs
a **single main.py**. If installation returns a confirmed success, the MQTT
loop exits, sets outputs to safe/off, disconnects and requests a reset.

**Warnings:** The network check and firmware transfer are synchronous and
may block MQTT. The update cannot guarantee atomicity on MicroPython
filesystems; loss of power may require manual USB recovery. No A/B slots
or automatic rollback. Only single-file releases can be installed through
this mechanism. Certificate/hostname verification has not been proven on
actual boards, and boot-time behavior of the downloaded main.py must be
validated. Do not enable this on safety-critical hardware.

To stay report-only, set OTA_CHECK_ENABLED=True and leave
OTA_AUTO_INSTALL_ENABLED=False. Unset/missing flags remain disabled.
