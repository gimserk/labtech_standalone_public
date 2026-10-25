# Cyber City: end-to-end simulation completion specification

Status: implementation roadmap / acceptance contract, not certification of a working system.

## Student story
1. Instructor selects an **existing `CyberCityMachine` listed on the Cyber City building details page**. Its `proxmox_template` is the golden template for the building machine; this is NOT a separately provisioned student lab or course machine.
2. Student interacts with the running clone belonging to that same `CyberCityMachine` via its existing Cyber City Guacamole console/visualizer. A building machine can have an active student user, but does not become a separate lab asset.
3. Machine agent reports the changed observation with authentication and a bounded payload.
4. LabTech validates machine/building authorization and evaluates *transition-based* conditions; persists an event and an outbox command in one DB transaction.
5. A background dispatcher publishes an idempotent command with an event ID, unique command ID, desired state, TTL and QoS 1 to the assigned building's topic through broker-authenticated TLS.
6. Only the ESP32 whose credentials grant that building topic applies the command and reports an acknowledgment and actual pin state.
7. A persistent MQTT consumer validates topic/source, consumes heartbeat/state/ack and stores last-seen timestamps and correlated command statuses. Student and instructor UI display desired vs actual state, last seen, failed/missing acknowledgment and event history.
8. Reset: instructor chooses **Reset to Template** on the building's existing `CyberCityMachine`. The system stops/deletes only that machine's current linked clone (`proxmox_vmid`), creates a new linked clone from its configured `proxmox_template`, and updates the *same CyberCityMachine record* with fresh VMID/VNC/console bindings. The `CyberCityBuilding` membership and the machine's monitors, attack mappings, pin targets, firmware and other Cyber City configuration remain intact. No regular student lab record or gradebook machine is created or touched.

## Existing source evidence and gaps
- `app/views.py:api_report_machine_state` publishes directly inside a database transaction, lacks TLS settings for this publish, and fires every matched report. This is not reliable event delivery or edge triggering.
- `app/views.py:cybercity_machine_action_view` supports 'start' and 'stop'; stopping destroys the instance, but there is no one-click atomic/async reset transaction with tracked progress and recreation.
- `app/cybercity_provisioning.py` provides authenticated v2 configuration, manifest, SHA256 firmware downloads and status report, but does not issue validated per-device MQTT credentials.
- `app/cybercity_firmware_bundle.py` warns that automatic OTA activation/rollback and I2C peripherals are incomplete. Preserve this warning until physical integration tests pass.
- Legacy firmware endpoints in `app/urls.py` (`/api/firmware/get-config/`, `/api/firmware/download/`, `/api/firmware/download/library/`) appear to expose device config or firmware without per-device auth; assess usage then deprecate/disable securely. Do not return broker passwords from a MAC-only query.
- `CyberCityESP32.building` currently permits more than one device per building; decide migration handling then enforce one device per building.

## System boundaries and object ownership
- Everything belongs to **LabTech → Cyber City → City → Building → Machine**, with the physical controller on the same Building details page. Never route this workflow through course labs, student lab VM instances, gradebook sessions, or another lab machine model.
- The primary VM is `CyberCityMachine`, linked to `CyberCityBuilding`, with `proxmox_template`, live `proxmox_vmid`, status, console/VNC mapping and optional `active_user`. State monitors use `MachineStateMonitor(machine=CyberCityMachine)`; triggers use `CyberCityAttackMonitor` mapped to the building's `CyberCityESP32Pin`.
- The reset replaces the **Proxmox clone only**, not the Cyber City building machine row or any of its configured educational scenario wiring. Retain `active_user` according to an explicit authorized reset policy, never silently clear a student's session.
- Student access is through Cyber City and its scoped permissions/visualizer. The instructor configures and controls reset from Building details.

## Durable event protocol
**Agent report** POST /api/machine/report-state/ with Bearer per-machine key:
```json
{"states":{"123":"active"}}
```
Enforce HTTPS, payload type/size bounds, and valid monitor IDs belonging to the authenticated VM. Normalize typed state values, evaluate equals/not-equals/contains without arbitrary code execution, and update observations. New event only on false -> true; a matching unchanged heartbeat is not another event. A false condition re-arms the rule. Persist events and outbox rows atomically. For external publish, rely on outbox workers rather than publishing inside a Django DB transaction.

**Command** MQTT `<building-base>/<pin-subtopic>/command` JSON:
```json
{"schema":1,"command_id":"uuid","event_id":"uuid","action":"set","value":"on","expires_at":"RFC3339"}
```
Validate action against configured output type, require deduplication by command_id, reject expired commands, and fail closed on unexpected pins/topics. The ESP32 should not run arbitrary code received from MQTT.

**Ack** `<building-base>/<pin-subtopic>/ack`: command_id, accepted/rejected/error, timestamp.
**State** `<building-base>/<pin-subtopic>/status`: actual state, command_id when applicable, firmware version, timestamp.
**Heartbeat** `<building-base>/device/heartbeat`: device id, firmware version, uptime, health. Enforce broker ACL, topic separation, TLS hostname verification and retained-message policy. Store last-seen and broker session info, not just last commanded value.

### MQTT reliability
- Broker TLS with properly verified CA and per-device ACL credentials, scoped to building topics, distinct from LabTech publisher/consumer credentials.
- Dedicated subscriber/consumer service with reconnect and durable state ingestion, not a browser-triggered blocking subscribe.
- Commands at least once with deduplication, bounded retry/backoff, queued -> published -> acknowledged -> verified / timed-out / failed status.
- No repeat actuation on repeated agent heartbeats, broker redelivery or browser refresh.
- Treat disconnected device, stale heartbeat or mismatched actual state as warning; don't display success merely after publish.single returns.

## OTA user experience
- Building -> ESP32 -> **Firmware**: current version, reported version, last seen, health and OTA history.
- **Edit** version from a guided editor (syntax check of Python text + library path checks), or upload a `.py` and optional libraries. Save as draft. Restrict who can edit firmware.
- **Deploy** sets target release with explicit confirmation and shows queued/downloading/staged/verified/rebooting/healthy/rollback/failed.
- Device periodically checks authenticated manifest over validated HTTPS, streams files to staged paths, verifies SHA-256, atomically swaps only after complete staging, restarts, reports healthy within a grace period, otherwise restores previous image.
- Avoid transmitting Wi-Fi credentials or private keys in downloadable generic firmware ZIP; keep secrets in secure device provisioning.
- Allow canceling a pending deployment and selecting an earlier known-good version. No unsupported automatic execution claims.

## VM reset user experience and protections
- **Reset VM to Template** on the existing Cyber City building machine Actions menu for authorized instructors; show affected CyberCityMachine name, current active user, clone VMID and golden template; require explicit POST and confirmation.
- Acquire per-machine lock and register reset job; block simultaneous start/stop/reset. Validate `VMID != template.vmid` before any destructive Proxmox call, and that VM belongs to the managed machine record.
- Stop clone, wait for Proxmox task completion, delete clone, wait for cleanup, clear old bindings only after successful destruction; create fresh *linked* clone from unchanged template, reassign it to the **same existing CyberCityMachine** and allocate new console port; do not leave old allocations orphaned.
- Record stages, idempotency token, audit event, errors and manual recovery paths; don't hold DB transaction open across slow Proxmox calls.
- On failed recreation, show error/retry safely. The source template and other course/student VMs must be untouched.
- Reset/re-arm the existing CyberCityMachine's `MachineStateMonitor` observations and clear stale pending commands; preserve monitor definitions and the attached `CyberCityAttackMonitor` targets. Do not touch regular course lab resources or their gradebooks.

## Tests required before release
- Unit: transition false->true fires once; duplicate reports no-op; false->true re-arms; invalid/foreign monitor rejected; TLS publisher options; offline retry/outbox; malformed/missing payload; per-building access control.
- MQTT integration: broker ACL and TLS, correct topics, QoS1 duplication handling, ack vs state, reconnect/retained behavior, 30-second missed-ack warning.
- Device bench: real ESP32 connected to TLS broker; LED/PWM/I2C actuation and state reporting; OTA success, bad hash, failed boot, power removal, rollback.
- Proxmox integration: existing building CyberCityMachine is unchanged in database identity and building ownership; linked clone reset, source template untouched, console reconnect, VMID changed, monitor mappings retained and re-armed, two concurrent reset attempts, clone failures, recovery; unrelated student lab instances untouched.
- UI: instructor firmware editor and progress, student status overview, mobile and dark-mode, student prohibited from reset and firmware administration.

## Suggested delivery PR series
1. Harden machine-agent report endpoint, validation and trigger transitions, add event/outbox models and tests.
2. MQTT worker + broker ACL/credential provisioning + ESP32 ack/status ingestion and dashboard.
3. OTA release UX and robust MicroPython staged activation/rollback.
4. Safe asynchronous Proxmox clone reset workflow, permissions, job status and tests.
5. Full end-to-end integration suite and deployment runbooks for Control VM.

Do not merge into production as 'complete' without integration and hardware test evidence.
