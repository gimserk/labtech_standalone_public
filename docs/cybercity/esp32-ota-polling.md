# ESP32 OTA polling — opt-in pilot

`ota_polling.py` is included in the **Download Basic ESP32 Firmware**
ZIP. It checks the existing authenticated LabTech v2 manifest through
`ota_single_app.check_update()` at a minimum 5-minute interval.

From the REPL, a safe read-only check is:

```python
import ota_polling
print(ota_polling.run_manual_poll())
```

For integration in a future device event loop, retain one `OTAPoller`
instance and call `poller.poll()` periodically. The default is
**report-only**; it will not install or reboot firmware.

The optional `allow_install=True` argument can trigger the previously
introduced single-`main.py` installer when a newer version is found.
Do not enable this flag in a production Cyber City deployment until
on-device HTTPS certificate verification, interrupted-update recovery,
application entry-point behavior and MQTT reconnection have been tested.

No automatic background timer or server-side push is installed by this
change. Firmware checks require calling the poller from a running event
loop or manually. The existing device startup and MQTT control remain
unchanged. Version checks and rate limiting use the board clock; special
handling for MicroPython tick wrap and clock resets remains to be tested.
