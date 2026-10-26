# Cyber City building provisioning — PR #125 release gate

This release changes **only Cyber City building machine provisioning** and registers a new Celery task in `app/tasks.py`. Student labs and their VMID allocation are unchanged.

## Before compiling the public release

1. Run the private source tests: `python manage.py test app.test_cybercity_building_provisioning`.
2. Run `python manage.py check` and any required existing regression suites.
3. Verify `app/cybercity_building_tasks.py` and `app/cybercity_utility_tasks.py` both enter the Python 3.13 compiled public package. `app/tasks.py` in that package must register **both** provisioning tasks.
4. Check the full public release against the private source revision; do not assume a successful build published new files.
5. Back up production database, uploaded media, configuration and current release before deployment. Do not clean or reset `app/mediafiles`.

## After deploying the public release

On the production host:

```bash
cd /opt/labtech
source /opt/venv/bin/activate
git log -1 --oneline
find app -maxdepth 1 -name 'cybercity_*tasks*' -print
python manage.py check
sudo systemctl restart labtech.service labtech-celery.service
celery -A app inspect registered | grep -i cybercity
```

Expected registered tasks include:
- `app.cybercity_reset_tasks.reset_cybercity_machine_task`
- `app.cybercity_utility_tasks.provision_cybercity_utility_task`
- `app.cybercity_building_tasks.provision_cybercity_building_task`

If the building task is missing, **do not test Start**: the published build is incomplete.

## First-time building-machine test

1. Choose a dedicated test machine in a building with a valid Proxmox template, **no assigned VMID**, and no previous orphaned clone bearing its name. Identify and inventory any orphaned `cc-building-*` VMs before starting.
2. Start once. Confirm Cyber City immediately records the VMID, VNC port, and status `provisioning`.
3. Check `sudo journalctl -u labtech-celery.service -n 150 --no-pager` for the corresponding background job and exact error, if any.
4. Check Proxmox task completion and that the clone is running. Confirm Cyber City changes its same machine record to status `running` and preserves VMID.
5. Confirm VNC port is configured and Guacamole reaches the desktop.
6. Stop the existing VM and Start it again; verify no second clone is created.
7. If the task fails, confirm status `error` **retains the VMID**. Investigate the error before using **Retry Provisioning**, which must reuse the same VMID.

## Safety and rollback

- Never repeatedly click Start on the older public build; it could create untracked clones.
- No automatic VM deletion is performed after failure. Confirm the Proxmox VMID and expected name before manual cleanup.
- Do not use Delete, Backup, Restore, or change the template while provisioning is active.
- If a worker is killed during a clone, status might remain `provisioning`. Before any manual status correction or task replay, inspect Proxmox's running tasks and VMID. Do not enqueue a second clone against an active Proxmox task.
- If the production test fails, preserve its VMID and capture the Celery traceback, Proxmox task UPID, VM name and node, and the Cyber City machine status.
- Rollback of application code does **not** automatically undo Cyber City VM reservations or Proxmox clones. Reconcile persistent VMs explicitly before attempting a new Start.

## Known limitations

- Building cloning intentionally targets the template's source node, which is required for local-storage linked clones. It does not implement student-lab cross-node placement.
- A cluster-wide Proxmox VMID request is not an atomic reservation on Proxmox. This PR serializes **building-to-building** reservations in LabTech, but concurrent utility and student-lab allocations use different allocation flows; high-concurrency deployment needs further coordination.
- Interrupted workers may leave a durable `provisioning` status requiring operator recovery after Proxmox task inspection.
- Mocked unit tests are not proof that the live Proxmox or Guacamole integration works.
