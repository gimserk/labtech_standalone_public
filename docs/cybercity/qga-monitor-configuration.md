# Cyber City — QEMU Guest Agent machine-monitor configuration

Scope: **Cyber City building machine monitoring only**. No changes to
Proxmox building VM creation, management, student labs, or the ESP32
firmware/OTA pipeline.

## Where to configure

Open Cyber City → Building → existing VM → **Configure Monitors**.
The building's **Machine Monitors** section also provides a
**Configure Checks** link to the exact same page for each VM.

On this page:
1. Under **Create QEMU Agent Check**, choose a name, check type, exact
   target, condition (Equals, Does Not Equal, Contains), expected
   value and an optional ESP Attack attached to this same building.
   Save. A definition without an ESP Attack still records readings.
2. Under **QEMU Agent — Automatic Monitoring**, select Linux or
   Windows, check **Automatically check this VM**, and save. Both
   controls are on this page; you do not need the old agent.py script.
3. Click **Check Now — QEMU Agent** on a running VM. Only one job may
   hold the VM polling claim at once. Refresh to review the time,
   observed value or per-check error.
4. The automatic Celery Beat poller scans enabled, running machines
   with supported active checks about every 30 seconds.
5. When a later reading changes from **nonmatching** to **matching**,
   the existing edge evaluator queues the selected ESP Attack in the
   existing MQTT outbox. The first QGA reading establishes a baseline
   and does **not** generate a physical attack.
6. Inspect the ESP Attack and status listener for published/acknowledged
   or executed status. A queued command is **not** a physical-state
   acknowledgment.

## Types and expected values

| Type | Target example | Expected value |
|---|---|---|
| Service status | `sshd` / `nginx` | `active`, `inactive`, etc |
| File exists | `/etc/hosts` | `exists` or `missing` |
| File content | `/var/log/app.log` | first 255 characters, usually Contains |
| SHA-256 hash | `/etc/hosts` | full 64-character hexadecimal digest |

The form validates paths using the same Linux/Windows target restrictions
as the QGA collector. SQL/DB-query monitors are intentionally disabled.
Editing a check's target, expected value, comparison, action or enabled
flag invalidates its previous observation so it must be sampled again.

## How checks execute

LabTech's Celery worker calls Proxmox QEMU Guest Agent `guest-exec`.
Proxmox inventory is inspected to resolve the **current node** of the
VMID, and the deterministic
`cc-building-<building_id>-machine-<machine_id>-<vmid>` clone name
must match. It never runs against the source template or an unrelated
VMID. If QGA is offline, the inventory is inconsistent, or the VM was
stopped, no synthetic observation is submitted and **no ESP Attack**
is queued. The page shows the last error until a valid check succeeds.

This feature requires the QEMU guest agent enabled in Proxmox and
installed and running in the guest:
- Linux: `systemctl is-active qemu-guest-agent`
- Windows: QEMU Guest Agent service running
- VM must be provisioned and running, not its source template
- Exactly one LabTech Celery Beat instance and active workers

In the existing configuration, `CYBERCITY_QGA_AUTOPOLL_ENABLED=True`
permits automatic checks. Automatic command delivery to real ESP32s
still requires explicit `CYBERCITY_COMMAND_DISPATCH_ENABLED=True`
and an MQTT status/ACK listener. **Review pending commands before
enabling command dispatch.**

## Validation before production

```bash
cd /opt/labtech
/opt/labtech/venv/bin/python manage.py check
/opt/labtech/venv/bin/python manage.py test \
  app.test_cybercity_qga_collector \
  app.test_cybercity_qga_poll \
  app.test_cybercity_qga_monitoring \
  app.test_cybercity_monitors_end_to_end \
  --settings=app.test_settings
```

Test first with a disposable Linux VM and a harmless ESP32 LED:
create a check `sshd` equals `inactive`, enroll the VM, confirm
the first reading is a baseline, change service status to trigger,
and verify exactly one queued command. Repeating the same state must
not queue additional commands. Test failure/offline QGA as well as
Proxmox VM migration and wrong-VMID/name collision.

No database migration is required for this PR; monitor enrollment and
observation fields were introduced in existing migration 0037.
