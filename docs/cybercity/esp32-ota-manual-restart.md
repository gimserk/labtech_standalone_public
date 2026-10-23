# Explicit OTA restart for the single-application ESP32

The Cyber City basic firmware ZIP includes `ota_restart.py`, which wraps
the existing authenticated `ota_single_app.update_once()` operation.

On a disposable board **after verifying TLS certificate enforcement**,
use the REPL:

```python
import ota_restart
ota_restart.install_and_restart(approve=True, restart=True)
```

Both explicit flags are required. The helper only calls the MicroPython
hardware reset when an installer reports a successful new installation
and `restart_required=True`. A missing update or failed installation
will not restart the device.

This is **not unattended OTA**. The default running MQTT loop remains
report-only and never calls this helper. It does not alter `boot.py`,
the permanent bootstrap, credentials, or GPIO topics.

A key requirement before production: the boot-time execution path for
`main.py` must be tested with the exact MicroPython image. If the active
`main.py` does not reconnect to LabTech and MQTT correctly, USB recovery
may be needed. A single-application install is not power-loss atomic,
and no rollback is provided.

Run host tests:

```bash
python -m unittest discover -s firmware/cybercity/tools -p 'test_*.py'
```
