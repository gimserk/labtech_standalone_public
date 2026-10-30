# Managed lab node migration (same Proxmox cluster)

Superusers can select **Cluster Utilization & Lab Placement → Migrate lab from
this node** for a live student VM, or **Manage All Labs → Migrate**. The
migration screen lists every machine assigned to the session, grouped by
Proxmox connection and source node. The administrator chooses an online
destination node **in the same cluster**. The request moves all machines for
that session on the selected source node; any machines already on other
nodes remain there.

## Design and restrictions

This first version is **offline only**. Plan a maintenance window: LabTech
asks each running VM to gracefully shut down, waits until it is stopped,
then asks Proxmox to perform an offline migration. Proxmox still handles the
VM/disk transfer; LabTech owns the durable job, identity verification,
application-layer pointers and recovery. Never interpret an accepted
Proxmox task as proof of a completed move.

On each VM, LabTech:
1. Checks its VMID, **exact VM name**, cluster, current node, destination
   online status, guest type, and compatibility with LabTech's dedicated
   `-vnc` QEMU arguments. Refuses attached host-specific PCI/USB devices or
   other custom QEMU arguments rather than overwriting them.
2. Records the VM's original power state, gracefully shuts down a running
   machine (120-second timeout, **no forced stop**), and starts Proxmox
   offline migration (`online=0`). A local disk must be movable by
   Proxmox's supported storage transfer mechanisms; incompatible storage
   stops the migration. No automatic conversion or cross-cluster backup/
   restore is attempted.
3. Waits for the migration task and confirms from cluster inventory that
   the VM with the expected name is now on the requested destination.
4. Preserves VMID and allocated VNC port, and verifies (or reasserts)
   the existing VNC display on the destination's QEMU configuration. If
   the VM has other `args` it refuses to replace them.
5. **Immediately updates LabInstanceMachine.proxmox_node** once the new
   placement is confirmed, before touching Guacamole. That way a failed
   downstream step cannot leave a stale source-node pointer.
6. Updates the **existing** Guacamole connection via GET/PUT/GET, changing
   only hostname/port and retaining its connection ID, attributes, other
   parameters, and permissions. If the student has no stored connection,
   LabTech creates one through the assigned Guacamole gateway.
   Guacamole SSO/JWT access uses LabTech's newly recorded node and port,
   and is blocked during unresolved migration.
7. Restarts only VMs that were running before migration, verifies that
   they are running, and records the completed job per machine.

A failed preflight creates a `failed` job without powering anything off.
Once a VM might have been stopped/transferred, errors become
`needs_attention` with its last safe error category. The source guest is
**not automatically deleted or rolled back**. Administrators can use
**Retry / Reconcile** after confirming no Proxmox migration task remains
in progress. The retry checks actual cluster placement and resumes service
reconciliation without migrating an already-moved VM a second time.

While a job is queued, running, or needs attention, LabTech blocks duplicate
moves, LabTech cleanup/deletion, student power actions and student Guacamole
SSO. Already connected raw VNC/Guacamole sessions might disconnect while
the VM is shut down; users should reconnect after completion.

VMIDs and VNC allocations remain attached to the same student lab. This
does **not** move VMIDs between student pools, create new clones, reset
student data, or alter Cyber City VM management.

## Deployment

This feature adds **migration 0035_lab_node_migration.py**. Test in dev/beta
against a disposable VM before production:

```bash
python manage.py migrate
python manage.py check
python manage.py makemigrations --check --dry-run --settings=app.test_settings
python manage.py test app.test_lab_node_migration app.test_lab_cleanup app.test_cluster_utilization_recovery --settings=app.test_settings
```

Ensure Celery workers are running and that the existing scheduled cleanup
sweep is active via exactly one Celery Beat service; that sweep also
redelivers queued migration jobs after a transient broker failure. If a
worker dies while a migration is marked `running`, inspect the Proxmox
task and live VM location **before** manually intervening. A running job
is not automatically replayed because the transfer could still be active.

### Test a real disposable VM

Use a test student lab with a **known-good shared datastore** first. Confirm
pre/post VMID, RAM, disk state, VNC TCP port, Proxmox node, Guacamole connection
ID/hostname and student console. Next test a VM with local disks *only* on
a compatible pair of nodes where Proxmox can migrate the storage; unsupported
storage must fail without orphaning or overwriting a guest. Test one VM that
is initially powered off and ensure it stays off.

This is an administrator-initiated operation. **Git merging does not move
any production VM**, and no migration should be attempted on production
until the integration test has passed.
