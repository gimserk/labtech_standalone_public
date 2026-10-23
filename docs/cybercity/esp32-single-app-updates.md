# Cyber City: single ESP32 application update

This replaces the proposed A/B slot approach with a straightforward
**single active application** installation workflow.

The city **Download Basic ESP32 Firmware** ZIP includes
`tools/install_single_app.py`. After an authenticated, verified v2 firmware
download has been staged and its manifest saved on a trusted workstation,
the installer validates every file again against SHA-256 and can copy
`main.py` plus `lib/*.py` over USB to the ESP32.

Example:

```bash
python tools/install_single_app.py --port COM5 --staging ./staged-v2 --manifest ./manifest.json
python tools/install_single_app.py --port COM5 --staging ./staged-v2 --manifest ./manifest.json --install
```

The first command is a dry run. The second requires an explicit operator
action. On successful completion, manually reset the device.

**This is not unattended OTA.** There is only one application copy:
updating a library and the entry point is not atomic. If power or USB
connection fails during an install, the app may be inconsistent. Recover by
flashing the generic bootstrap and re-installing the known-good application
over USB. The utility does not overwrite `boot.py`, network secrets, device
credentials or permanent bootstrap modules.

Server manifest download and workstation transfer must happen over verified
HTTPS; this helper only validates *local* copies. Test on a disposable ESP32
before use. No A/B slots or boot supervisor are required.
