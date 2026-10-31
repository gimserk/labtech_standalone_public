# Guacamole reconciliation fix for managed lab node migration

When a Proxmox node migration succeeds but the migration is
`needs_attention` with `guacamole_update_failed`, **do not migrate the
VM a second time or release its VMID/VNC reservation**.

The original Guacamole updater read `GET /connections/{id}` and assumed
that response included the VNC settings. JDBC Guacamole exposes those
settings at `GET /connections/{id}/parameters`. The previous code could
PUT an incomplete parameters object, and its verification then read the
metadata endpoint again, which could not confirm the destination.

This update:
- Reads metadata and the separate VNC parameters map before PUT.
- Preserves existing connection ID, name, parent, attributes and all VNC
  parameters other than `hostname` and `port`.
- Verifies the new hostname/port by re-fetching `/parameters`.
- Rejects incomplete parameter maps and masked credentials rather than
  overwriting connection settings blindly.
- Displays categorized failures (`guacamole_permission_denied`,
  `guacamole_connection_not_found`, `guacamole_parameters_read_failed`,
  `guacamole_connection_write_failed`, etc.) with no API token or
  connection secrets included in error messages.
- Preflights the Guacamole connection/parameters before shutting down a
  *new* migration, so an unreachable or unreadable REST connection blocks
  before downtime.

## Recovering an already moved lab

1. In **Cluster Utilization**, open the lab migration history. Verify the
   live Proxmox cluster shows the VM's correct name/VMID on the target node.
   For the reported incident this was machine **1405**, moving ITP-PM7 to
   ITP-PM6. The VM may still be stopped because restart is intentionally
   after Guacamole reconciliation.
2. Deploy the tested fix on dev/beta first, then production using normal
   change management. No schema migration was needed for this fix.
3. Open the existing `needs_attention` migration entry and click
   **Retry / Reconcile**. This should **not issue another Proxmox migrate
   request** if the guest is already confirmed on ITP-PM6. It will verify
   the target VM, restore/update Guacamole connection parameters, and
   restore the pre-migration running/stopped state.
4. If retry still fails, inspect the new *specific* `guacamole_...` error.
   Verify that the Guacamole server configured for the machine is the
   correct one and its REST API service credentials have permission to
   read and modify that existing connection.
5. Verify the student console. For JWT SSO the destination hostname
   comes from `LabInstanceMachine.proxmox_node` and the existing
   `vnc_port`. Check node DNS resolution and allow the same VNC TCP
   port from the Guacamole host. Neither VNC port nor VMID is reallocated.

### Read-only inspect command

```bash
cd /opt/labtech
/opt/venv/bin/python manage.py shell <<'PY'
from app.models import LabInstanceMachine, LabNodeMigrationJob

machine = LabInstanceMachine.objects.select_related('proxmox_server').get(pk=1405)
print('Machine:', machine.pk, machine.name)
print('VMID:', machine.proxmox_vmid)
print('Recorded node:', machine.proxmox_node)
print('VNC TCP port:', machine.vnc_port)
print('LabTech state:', machine.status)
print('Guacamole ID:', machine.guacamole_connection_id or '(none)')
for job in LabNodeMigrationJob.objects.filter(machine_ids__contains=[1405]).order_by('-created_at')[:5]:
    print('Job:', job.pk, job.status, job.stage, job.last_error,
          'source:', job.source_node, 'target:', job.target_node)
PY
```

If the JSON containment operator is unsupported by the database backend,
find the job through `LabNodeMigrationJob.objects.filter(
instance_id_snapshot=machine.lab_instance_id)` instead.

Do not print or share Guacamole authentication tokens, passwords, or raw
parameter responses.

## Validation before deployment

```bash
/opt/venv/bin/python manage.py check
/opt/venv/bin/python manage.py test app.test_lab_node_migration \
    --settings=app.test_settings
```

Test the repaired REST updater against a disposable connection on the
configured Guacamole server. The new code has no production access from
GitHub; merging cannot repair the stopped VM by itself.
