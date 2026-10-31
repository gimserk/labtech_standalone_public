# Cyber City: automatic VM monitors → ESP32 attacks → OTA configuration

Scope: Cyber City building monitoring, ESP Attacks, ESP32 management and
device status only. **No changes to building VM creation or city-level
Firewall/Control/Management VM lifecycles.**

## Fixed issues

- Existing Machine Monitor configuration did **not automatically poll**
  QEMU Guest Agent: it depended on an external per-machine ID map and a
  separate systemd timer. Each existing CyberCityMachine now has:
  *`monitor_enabled` (off by default), `monitor_os_family` (Linux/Windows),
  last poll/error, and a durable DB poll claim.*
- New Celery Beat sweep dispatches QEMU-agent scans approximately every
  30 seconds for enabled, running building VMs with active supported
  monitor definitions. The full scan does not block HTTP requests.
  Database claims prevent overlapping scans on a given VM.
- Supported checks: service status, bounded file content, file SHA-256, and file existence
  (returns `exists` or `missing`). Target paths and service names
  are validated, and command argv is bounded; arbitrary scripts and DB
  queries are **not supported** by this safe collector.
- The edge evaluator uses the existing stored observation. A transition
  from nonmatching to matching queues a CyberCityCommand for the
  configured CyberCityAttackMonitor ESP32 pin. It doesn't repeatedly
  trigger on every matching poll, and failed QGA checks do not count as
  healthy/false observations.
- The building page now separates **Machine Monitors** (per-VM
  settings, Check Now, last observation/error) and **ESP Attacks**
  (pin, last reported state, latest matching command queue status).
- The manual ESP Attack test button queues via the same durable outbox
  instead of direct, unaudited HTTP MQTT publishing. It requires an
  existing Machine Monitor association on the same building.
- Publishing a command records the latest *sent* command separately
  from last *device-reported* state. An ESP status value or v1 JSON
  ACK is needed to confirm device response; a published command alone
  does not prove execution.
- The building's pin-status HTTP endpoint reads the database and never
  opens a new five-second MQTT subscriber per browser refresh.
- The ESP32 detail template had an invalid/unmatched `{% else %}`
  in the firmware status section. That is fixed and a route/render
  regression test was added. ESP32 detail links are scoped to their
  original city/building; a genuinely stale or foreign device ID still
  returns 404 by design.

## End-to-end operation

1. Building VM is **running**, with Proxmox QEMU Guest Agent enabled,
   installed and responsive. No agent.py installation is needed.
2. Create an **ESP32** with the correct MAC address, provisioning key
   and one or more pins; make sure the MQTT base topic is configured on
   the building. Verify the device has the correct firmware and Wi-Fi.
3. Create an **ESP Attack** linked to an ESP32 pin and command
   compatible with its driver (e.g. `ON` for LEDs).
4. Create a **Machine Monitor** for a building VM, choose service /
   file_exists / file_hash, expected value (e.g. `inactive`), and
   link the ESP Attack.
5. On the building page choose the VM guest OS, enable **Auto poll**,
   Save, then click **Check Now**. The last check time and observed
   value should appear on refresh. A failed guest observation is shown
   as an error; no command is sent.
6. When the check goes from nonmatching to matching, the evaluator
   adds a pending command. Beat's command dispatch publishes via MQTT;
   the status listener processes ESP reports and correlated ACKs.
7. Observe queued/published/executed and the last reported pin state in
   the **ESP Attacks** and pin-status sections.

**Warning:** As in the existing edge-evaluator behavior, an initial
observation that already matches a condition may trigger once. Establish
a known nonmatching baseline before arming any physical alarm, motor,
relay or other hazardous output; use an isolated test LED for acceptance.

## Required server services and flags

The new automatic QGA sweep is enabled by default in server settings but
**does nothing until an instructor enables individual machines**:

```ini
CYBERCITY_QGA_AUTOPOLL_ENABLED=True
CYBERCITY_COMMAND_DISPATCH_ENABLED=True
```

`CYBERCITY_COMMAND_DISPATCH_ENABLED` remains explicitly opt-in so
existing queued commands aren't unintentionally sent during an upgrade.
Review the pending-command queue before enabling it! Exactly **one**
Celery Beat scheduler must run for the LabTech deployment, plus normal
Celery workers. Restart them after changing environment values.

The status consumer must also be running for the target Cyber City:
```bash
/opt/venv/bin/python /opt/labtech/manage.py listen_cybercity_status --city-id=1 --forever
```
Run it under a supervised, restartable service, not an interactive
shell. The included `deploy/cybercity/cybercity-status-listener@.service`
is an optional systemd service template; after adjusting its Python
path/user, install it as `labtech-cybercity-status@1.service`.
If no listener is running, the last ESP pin report is stale even though
commands may be published.

## ESP32 firmware and pin configuration (important)

The ESP32 page allows editing device settings and pin mappings, editing
and publishing a new main.py OTA firmware release, uploading a firmware
bundle, reviewing version history, and viewing reported installed
version/timestamps.

The authenticated `/api/firmware/v2/config/` supplies the latest
pin configuration. **Existing firmware downloads this on startup**, not
whenever the instructor presses Save. The OTA controller's polling and
auto-install are opt-in in the device's `ota_runtime_config.py`,
and require verified HTTPS/TLS. Consequently:
- Saving pins **does not live-push GPIO changes onto a running ESP32**.
  Confirm a safe device restart or explicit supported configuration
  refresh, then verify the device reports with the new mapping.
- Publishing firmware is a **desired OTA target**, not proof of a
  successful update. Confirm `firmware_reported_version` and freshness.
- A firmware/device that lacks a verified OTA poller will not auto-install.
- Some pin types (I2C LED/screen) require device-specific drivers; the
  default MQTT controller explicitly skips unsupported types.

No silent bootloader edits, arbitrary code execution or forced OTA
reboots have been added. Pin changes and OTA installation need a
physical-device validation gate before claims of a completed update.

## Validation

```bash
cd /opt/labtech
/opt/venv/bin/python manage.py migrate
/opt/venv/bin/python manage.py check
/opt/venv/bin/python manage.py makemigrations --check --dry-run \
  --settings=app.test_settings
/opt/venv/bin/python manage.py test \
  app.test_cybercity_monitors_end_to_end \
  app.test_cybercity_qga_collector \
  app.test_cybercity_qga_poll \
  app.test_cybercity_monitor_evaluator \
  app.test_cybercity_m1_db_dispatch \
  app.test_cybercity_esp32_health_refresh \
  app.test_cybercity_device_health \
  --settings=app.test_settings
```

Then test on one disposable running building VM and one actual
non-hazardous ESP32 LED. Prove: QGA works, initial nonmatching state,
change creates one command, command is published, pin reports or ACKs,
and a repeated matching check does NOT send another command. Re-arm
with a nonmatching state, then trigger again. Check the broker and
firmware version independently; this simulated test suite does not
validate real GPIO, HTTPS trust, network ACLs or OTA activation.

Do not roll these features into production before staged checks pass.

MQTT pin subtopics are validated as relative segments: no `+` / `#` broker wildcards, control characters, or absolute paths. This prevents a newly configured pin from accidentally targeting unrelated MQTT namespaces.
