# Durable lab cleanup operations

Timed labs use a durable cleanup job. Student Finish Lab, instructor Finish, the recovery command, and the optional Celery Beat sweep all call the same lifecycle service. A job stores resource identifiers and append-only attempts after the live session is deleted; it never stores provider credentials. Persistent labs are excluded from expiration.

## Rollout

Deploy the schema, web and workers with `LAB_CLEANUP_BEAT_ENABLED=False` (the default). Run migrations and inspect eligible sessions before enabling the schedule:

```bash
python manage.py migrate
python manage.py cleanup_expired_labs --dry-run
CONTROLLED_INSTANCE_ID=123  # replace with a verified disposable, expired timed session
python manage.py cleanup_expired_labs --instance-id "$CONTROLLED_INSTANCE_ID"
```

The default command runs one synchronous attempt per eligible session and exits nonzero if cleanup remains unresolved. It never waits through retry delays. Manual Finish and queued jobs continue to work with the sweep disabled. Exercise a controlled lab and confirm its Guacamole connection, Proxmox VM, VNC allocation, and live session are gone; inspect the retained job. Then set `LAB_CLEANUP_BEAT_ENABLED=True` for the Beat process, restart Beat, and retire the old 10-minute cron wrapper. Keep the command for recovery.

The migration records the currently assigned Guacamole server for existing connections. Review preexisting live sessions if Guacamole assignments were changed before migration; an older connection may belong to a different server and require correcting its `guacamole_server` link before cleanup.

Beat runs `app.tasks.sweep_expired_lab_instances` every 30 seconds. It selects timed sessions whose `expires_at <= now` and redelivers due queued or retrying jobs and expired leases, so a lost broker message or worker restart does not permanently strand them. Provider calls occur outside transactions. Five automatic attempts use delays of 60, 300, 900, and 1800 seconds. A final failure retains the session, blocks replacement, appears in the instructor's Lab Cleanup dashboard, and sends one email to assigned active instructors and active superusers.

Alert delivery uses a reclaimable lease and a stable email Message-ID per failure cycle. An SMTP handoff immediately before a worker crash can be retried and delivered twice; inspect the job history before manually sending another alert.

## Monitoring and recovery

Use **Manage Labs → Lab Cleanup** to inspect job IDs, session IDs, VMIDs, attempts, safe error categories, and next retry times. Confirm Beat and worker logs show `lab_cleanup_resource` entries. Check jobs stuck in queued/retrying, old running leases, and final failures; the dashboard's **Retry Cleanup** action requeues a failed job after the provider issue is corrected.

For queue-only recovery:

```bash
python manage.py cleanup_expired_labs --enqueue
python manage.py cleanup_expired_labs --instance-id 123 --enqueue
```

A failed job requires the dashboard retry action; the command does not silently reset its attempt history. The older `cleanup_labs_wrapper.sh` can invoke the synchronous command during an emergency, but should not be scheduled alongside Beat.

## Rollback

Set `LAB_CLEANUP_BEAT_ENABLED=False` on the Beat process and restart it to stop new automatic expiration jobs. Existing jobs remain for manual recovery and audit. Keep the migration and job rows in place while external resources may still exist.
