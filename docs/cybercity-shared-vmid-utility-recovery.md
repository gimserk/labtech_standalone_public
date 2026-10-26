# Cyber City follow-up: shared VMIDs, utility recovery, release gate

This change continues after merged PR #125. It is **private LabTech source only** and does not modify student lab VM provisioning. New worker functions remain Cyber City-specific.

## Improvements

- City-level pfSense, Control and Management VMs and building machines now acquire the **same** Cyber City VMID lock before requesting a Proxmox cluster-wide nextid. Both check Proxmox inventory and existing LabTech building/utility/student reservations.
- Utility worker uses Proxmox cluster inventory, not any failed `vm.config.get()`, to decide whether a VM exists; confirms VM node and expected name before configuring VNC.
- When utility provisioning fails, its VMID and port remain recorded. The utility's Retry Provisioning action sends that **same VMID** to Celery for safe completion; it never allocates a fresh VM on retry.
- While a utility is provisioning, Stop/Backup/Restore/Delete controls are unavailable and backend rejects those actions.
- The release-gate script checks that Python 3.13 compiled public build includes utility, building and reset task modules and confirms all tasks register with Celery in runtime mode.

## Checks required before compiling and publishing

Run these in the **private uncompiled** environment (not the public compiled checkout):

```bash
python manage.py test app.test_cybercity_building_provisioning app.test_cybercity_utility_provisioning
python manage.py check
```

After running your usual Python 3.13 compilation flow, verify the **actual public build directory**, not the private source tree:

```bash
python deploy/cybercity/check_release_tasks.py /path/to/compiled-public-build
```

Copy the script into your release pipeline or invoke it from the private source checkout. The script is not automatically wired into an existing CI workflow by this PR.

On the production server **after deployment**, run:

```bash
cd /opt/labtech
source /opt/venv/bin/activate
python /path/to/check_release_tasks.py /opt/labtech --runtime
celery -A app inspect registered | grep -i cybercity
```

Check all three:
`app.cybercity_building_tasks.provision_cybercity_building_task`
`app.cybercity_utility_tasks.provision_cybercity_utility_task`
`app.cybercity_reset_tasks.reset_cybercity_machine_task`

## Controlled test

1. Inventory all old `cc-*` orphaned Proxmox VMs; do not delete blindly or reuse their VMIDs.
2. Test one new **building** VM, then a city-level **utility** VM, one at a time.
3. Confirm the DB records VMID+port immediately, Proxmox clone task reaches OK, VNC configuration succeeds, and status becomes running.
4. Stop/Start existing clones; assert no duplicate VMs.
5. Simulate a worker exception in development: status should become error while retaining the VMID, and Retry Provisioning should act on the existing reservation.
6. Verify Guacamole separately after provisioning.

## Remaining risks

- This **shared lock coordinates only Cyber City** utility and building allocations. Student-lab allocation is unchanged and may allocate concurrently from separate configured pools; the helper avoids *already reserved* student VMIDs but cannot prevent an external allocator race between reads.
- Proxmox `cluster.nextid` itself is not a transactional reservation across external clients. The worker's VM name and node checks prevent taking over an existing conflicting VM.
- After a hard worker shutdown, a job may remain `provisioning`. **Do not requeue blindly.** Review Proxmox UPIDs and current worker activity first. A separate reconciliation feature is still planned.
- Console routing, firewall reachability, and Guacamole are separate integration gates; no success claims without live tests.
- No tests or CI results have yet been executed through this GitHub integration.

Do not deploy before the private test suite and compiled release gate pass. Keep `app/mediafiles`, production database, runtime configs and secrets protected during upgrades.
