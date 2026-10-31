# Cyber City — City Services lifecycle and recovery

Scope: **only** Firewall (pfSense), Control (MQTT broker/control), and
Management on `/labtech/cybercity/<city_id>/`. Does not alter building
machine provisioning, building reset logic, student lab VM paths, or ESP32
firmware/MQTT execution.

## Root cause

The old `cybercity_detail_view` probed only `template.node` for two
services on a GET request and cleared VMIDs if Proxmox raised a resource
exception. A VM could already exist on another node or the API could fail
transiently. The page then lost the pointer, while Proxmox retained the
guest and LabTech retained its allocated VNC port. Control/MQTT wasn't
included in the live status check. The action handler also assumed
`template.node` instead of a verified current node, and the Delete
action released VMIDs/VNC as soon as Proxmox accepted deletion, before
the guest was confirmed absent.

## What changes

City-level models record an independent actual node, safe error reason,
and start timestamp for each service. Migration `0036_cybercity_service_recovery`
adds nullable fields without changing existing VMIDs or VNC allocations.

- **City page GET is read-only** for City Service VM records.
- **Start / Provision** clones from the configured template node, keeps
  the already reserved VMID and VNC port, and waits for clone, VNC
  setup, and guest start to finish. If the matching existing clone is
  on a different node, the worker uses its verified actual node instead
  of cloning another VM or contacting the template node.
- **Inspect / Recover** shows LabTech VMID, allocated VNC port, recorded
  node, live Proxmox node/power status, and safe reason codes.
- **Reconcile live status / node** updates only the recorded node and
  power state after exact VMID + VM name confirmation. If missing, it
  records an error without clearing VMID/VNC.
- **Recover Existing Reservation** requeues the same VMID when status
  is `error`. A stale `provisioning` or `resetting` state requires
  at least 30 minutes and a successful Celery inspection proving no
  matching build/reset task is active, reserved, or scheduled.
- **Reattach Existing Proxmox VM** appears when a legacy city page
  cleared the VMID. It requires one strict matching VM name such as
  `cc-1-control-7180`, verifies the actual Proxmox configuration,
  rejects VMIDs belonging to another City Service, building or lab VM,
  and checks VNC allocation references. After explicit reattachment,
  Recover reconciles and starts it.
- **Stop, Backup Snapshot, Restore Snapshot** operate on the verified
  actual node and wait for Proxmox tasks (not merely task submission).
  Snapshot restore is destructive and requires confirmation.
- **Reset to Template** uses a dedicated asynchronous Cyber City
  utility task. It verifies ownership, shuts down and deletes the
  existing clone, waits for confirmed cluster-wide absence, then
  reuses the original VMID/VNC reservation to rebuild from template.
  This *wipes existing guest data*, including firewall and broker
  configurations. Do not use this simply to fix a stale pointer.
- **Delete VM** requires confirmation and waits for Proxmox to report
  absence cluster-wide before clearing the stored VMID/node/port.
  An unverified deletion leaves a recovery error and retains the
  reservation for investigation.
- **Guacamole SSO** uses the last verified actual node, not the source
  template node. Broker connectivity remains a separate check.

## Recommended procedure for existing City #1

1. Deploy to dev/beta, apply migration `0036` and run checks below.
2. Open `/labtech/cybercity/1/`; for each City Service select
   **Inspect / Recover**. Never click Delete or Reset just to fix an
   existing VM pointer.
3. If a VMID is recorded and the VM is correctly named but on a new
   node, click **Reconcile live status / node**.
4. If status is error and VMID is recorded, use **Recover Existing
   Reservation**. This reuses the existing VMID and VNC reservation.
5. If the VMID is blank but a uniquely named orphan exists, review the
   name, node and port and select **Reattach Existing Proxmox VM**.
   Then Recover. If more than one candidate appears, investigate
   manually—nothing is adopted automatically.
6. Confirm Guacamole console and network connectivity. For Control,
   verify MQTT broker status separately; a VM in `running` state does
   not prove the broker daemon or TLS/ESP32 command path is healthy.

## Deployment and tests

```bash
cd /opt/labtech
/opt/venv/bin/python manage.py migrate
/opt/venv/bin/python manage.py check
/opt/venv/bin/python manage.py makemigrations --check --dry-run --settings=app.test_settings
/opt/venv/bin/python manage.py test \
  app.test_cybercity_city_service_management \
  app.test_cybercity_utility_provisioning \
  app.test_cybercity_building_provisioning \
  app.test_cybercity_machine_action_security \
  --settings=app.test_settings
```

Confirm the new `app.cybercity_city_service_reset.reset_cybercity_service_task`
Celery task is registered in the **compiled production build** as well.
Start with a disposable City Service VM with a shared-storage template;
test first provision, failed clone, same-VMID recovery, snapshots,
console and confirmed deletion. Do not test Reset to Template against
an existing production broker/firewall.

If a City Service VM on Proxmox has a nonstandard name, the safe
identity check intentionally blocks ownership and destructive actions.
Review manually rather than renaming a foreign guest on a guess.
