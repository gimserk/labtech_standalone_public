# Cluster utilization and reliable lab cleanup

The **Cluster Utilization & Lab Placement** link appears under the superuser
dashboard's Platform Management section. The page is read-only and superuser
restricted. It queries the Proxmox cluster inventory and correlates VMIDs
with live student lab sessions, students, courses, machine definitions and
VNC allocations. It also identifies Cyber City machines/services separately
and leaves other Proxmox guests explicitly untracked. Database-only lab
assignments are displayed separately because they may be failed builds,
deleted guests or stale records, not live VMs.

Metrics include node CPU usage and logical CPU count, used/total RAM, live
VM count, VM CPU/RAM/disk, Proxmox storage per node, assigned VMID-pool
capacity and reservations, and VNC utilization for the configured port
range. **Shared storage is shown on each reporting node and is not summed
across nodes**. CPU load is instantaneous utilization, not vCPU allocation.
VNC reservations outside the configured current range are shown as *legacy*
and are still maintained until their old labs finish. VMIDs can belong to
infrastructure or templates and do not all come from student pools.

One API failure is confined to its cluster; no credentials or raw Proxmox
exception text are rendered to the browser. The endpoint requires a logged-in
superuser. It does not perform any VM operation.

## Automatic cleanup improvements

Migration `0034_lab_build_completion` adds a nullable
`LabInstance.build_finished_at` timestamp. The build task sets it when it
finishes (even for failed or cancelled builds). Only after a build task
exits do remaining `building` placeholders become `error`, allowing the
normal cleanup pipeline to process their resources. That pipeline now
verifies the expected VM name and discovers its current node cluster-wide,
instead of assuming that a stale or `pending` recorded node means the VM
doesn't exist.

The cleanup sweep is enabled by default with
`LAB_CLEANUP_BEAT_ENABLED=True` and runs every 30 seconds **when a single
Celery Beat scheduler is running**. It handles expired timed labs, retry
jobs, and already-finished failed/deleting builds. A permanently stopped
worker cannot mark the build finished; no blind time-based deletion is
performed for such cases.

For older stranded sessions, **Manage All Labs → Recover Cleanup** is a
superuser-only POST action. It checks that the session is already
`deleting` or `error`, that a cleanup lease is not active, and that
existing VMs belong to the expected LabTech machine. For old sessions with
no completion marker it additionally requires the session to be at least
20 minutes old and all Celery workers to be inspectable with no build task
for that session active, reserved, or scheduled. If any verification fails,
recovery is blocked. If it succeeds, it marks only stranded placeholders
`error`, corrects stale node references and requests/retries durable
cleanup; it never directly deletes database rows.

## Deployment checklist

1. Deploy to dev/beta first. Apply `python manage.py migrate`.
2. Run `python manage.py check`,
   `python manage.py test app.test_cluster_utilization_recovery app.test_lab_cleanup --settings=app.test_settings`,
   and `python manage.py makemigrations --check --dry-run --settings=app.test_settings`.
3. Verify one Proxmox cluster's node/storage totals and a running student VM's
   owner against Proxmox. Confirm the page returns a redirect for ordinary
   student accounts. Ensure the Guacamole host can reach the configured ports.
4. Check the real service units. Installer-managed deployments use
   `labtech-worker.service` and `labtech-beat.service`; older manually
   configured servers may instead have `labtech-celery.service` and **no Beat
   service**. For those servers create a separate Beat unit using the
   existing worker's virtualenv, environment file, broker and working
   directory. Run exactly one Beat scheduler. Check with:
   `systemctl status labtech-beat`,
   `systemctl list-units '*labtech*'` and
   `journalctl -u labtech-beat -n 100 --no-pager`.
5. If `LAB_CLEANUP_BEAT_ENABLED=False` is explicitly set in an environment
   file, change it to `True` for the Beat process and restart Beat. Don't
   enable automated timed-lab deletion until the expiration behavior is
   confirmed for a disposable lab.
6. Test an intentionally failed build, observe that its cleanup job is
   automatically queued, and confirm the VM, Guacamole connection and VNC
   allocation are gone before the session disappears.
7. Watch `lab_cleanup_resource` and `lab_cleanup_dispatch_unavailable`
   messages on the worker. An unavailable Proxmox/Guacamole API is still a
   failure: the job retries and eventually needs admin intervention.

**No production machines are changed by merging the code.** The live
dashboard requires valid Proxmox credentials. Automatic scheduling requires
a running Beat service; code alone cannot start a missing service.
