# Cyber City Milestone 1: bundled QGA polling rollout

The server-side QEMU Guest Agent collector operates on each **existing** building CyberCityMachine. It uses an explicit allowlist of machine IDs and their guest OS, avoiding blanket scans and guest-installed monitor software.

## Configuration (staging only)

Add to Django settings using your deployment's settings convention:

```python
CYBERCITY_QGA_MONITORING_ENABLED = False  # change to True only after staging dry-run passes
CYBERCITY_QGA_MACHINE_OS_MAP = {42: "linux", 53: "windows"}  # replace IDs with actual machines
```

The allowlist must be a dict of exact CyberCityMachine IDs to `linux` or `windows`. These entries are **not Proxmox VMIDs**; LabTech reads the existing machine's current clone VMID at poll time. The service refuses a non-running VM, source template VMID, and unknown monitor types. Failed guest checks are omitted rather than treated as a rearmed monitor.

## Test commands

```bash
python manage.py test app.test_cybercity_qga_collector app.test_cybercity_qga_poll app.test_cybercity_qga_enrollment app.test_cybercity_monitor_evaluator app.test_cybercity_milestone1_event_outbox
python manage.py poll_cybercity_qga_enrolled
```

For live application, enable the setting first, then run `python manage.py poll_cybercity_qga_enrolled --apply` on one isolated staging city. Applying monitor results can enqueue MQTT events; it must not be enabled indiscriminately.

## Scheduling

Use the deployment scheduler to invoke the **one-shot** command. Example systemd units (adapt paths/user to your installation):

```ini
# /etc/systemd/system/labtech-cybercity-qga.service
[Unit]
Description=LabTech Cyber City QEMU monitoring pass
After=network-online.target

[Service]
Type=oneshot
User=labtech
Group=www-data
WorkingDirectory=/opt/labtech
ExecStart=/opt/venv/bin/python manage.py poll_cybercity_qga_enrolled --apply
TimeoutStartSec=180
```

```ini
# /etc/systemd/system/labtech-cybercity-qga.timer
[Unit]
Description=Cyber City QGA monitoring every 60 seconds

[Timer]
OnBootSec=90s
OnUnitInactiveSec=60s
Unit=labtech-cybercity-qga.service
Persistent=false

[Install]
WantedBy=timers.target
```

Enable the timer **only after** staging, broker ACL, and firmware checks:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now labtech-cybercity-qga.timer
systemctl list-timers | grep cybercity
journalctl -u labtech-cybercity-qga.service -n 100 --no-pager
```

For distributed installations use a shared Django cache with atomic add (e.g., Redis); a local in-memory cache lock is process-local and does not prevent multiple hosts polling together. The lock TTL is 120 seconds; investigate slow/stuck polls and reentrancy before deploying multiple workers.

## Acceptance

1. Run the dry-run and verify service/hash values for one staging building.
2. Prove a non-matching observation changes to matching only once and creates one outbox entry; repeat matching reports and verify no requeue.
3. Confirm MQTT outbox dispatcher is actively scheduled **separately**; the poller enqueues, but does not publish.
4. Run local-broker/simulated-ESP32 tests from PR #108. Repeat with actual VM changes and the staging broker.
5. With one physical ESP32, verify output GPIO and incoming status on the building UI.
6. Verify the correct existing building machine remains associated when reset from its source template.

The broker/Proxmox/ESP32 end-to-end integration has **not** been executed by this PR. These unit tests have not been executed in the target deployment. No release gate is complete until observed results are recorded.
