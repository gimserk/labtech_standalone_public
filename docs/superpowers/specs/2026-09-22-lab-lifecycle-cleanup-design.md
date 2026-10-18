# Durable Expired-Lab Cleanup Design

**Date:** 2026-09-22  
**Repository:** `gimserk/labtech`  
**Status:** Approved conversational design; written specification pending user review

## Purpose

Timed labs must release every external resource promptly and reliably when their timer expires. The same cleanup path must serve automatic expiration, the student's **Finish Lab** action, instructor-initiated cleanup, and operational recovery.

Success means:

- cleanup begins on the next 30-second sweep after `expires_at`;
- Guacamole connections, Proxmox VMs, and VNC allocations are removed;
- transient failures retry after worker or web-process restarts;
- cleanup is safe to repeat;
- instructors and site administrators can see and act on final failures;
- expiration never grants academic completion or changes gradebook results.

Persistent labs remain manual-only.

## Current Problem

The current management command calls `_finish_lab_machine(machine)` with a `LabInstanceMachine` object, while the helper expects a numeric machine ID and performs a database lookup. That mismatch prevents normal expired-lab cleanup.

The surrounding architecture also makes cleanup fragile:

- automatic cleanup depends on a shell wrapper and external cron;
- manual cleanup runs in an unmanaged thread created by a web request;
- cleanup logic lives in `views.py`;
- retry and audit state are not durable;
- partial cleanup is difficult to inspect or resume;
- a web or worker restart can abandon work.

Correcting only the bad argument would leave these operational failure modes in place.

## Scope

### Included

- One reusable lab lifecycle cleanup service
- Celery Beat expiration sweep every 30 seconds
- Per-session Celery cleanup tasks with controlled retries
- Persistent cleanup jobs and append-only attempt history
- Student cleanup status
- Instructor cleanup dashboard and retry action
- Final-failure email notifications
- Recovery-oriented management command
- Removal of request-created cleanup threads
- Migration and automated tests
- Controlled rollout and rollback procedure

### Excluded

- QEMU guest-agent validation
- Audio or podcast course content
- Academic lab completion policy changes
- Gradebook calculation changes
- A general external plugin framework
- Changes to VM creation beyond what cleanup reliability requires

## Architecture

### Lifecycle service

Create `app/services/labs/lifecycle.py` as the sole cleanup orchestration boundary.

Its public operations are:

- create or retrieve a cleanup job for a live lab session;
- take an immutable resource snapshot;
- clean one lab session idempotently;
- record an attempt and its per-resource outcomes;
- finalize success;
- finalize failure;
- requeue an authorized failed job.

Django views, Celery tasks, and management commands call this service. They do not directly delete Proxmox, Guacamole, VNC, or live-session resources.

Provider-specific operations remain behind small adapters so the lifecycle service can be tested without live infrastructure:

- Proxmox VM status, stop, and delete
- Guacamole connection delete
- VNC allocation release

The adapters normalize “already absent” responses as success and return structured, sanitized failures.

### Celery tasks

Add thin task wrappers to the existing Celery-discovered `app/tasks.py`:

- `sweep_expired_lab_instances`
- `cleanup_lab_instance`
- `send_lab_cleanup_failure_alert`

Configure `CELERY_BEAT_SCHEDULE` to run the sweep every 30 seconds.

The sweep selects timed sessions where `expires_at <= now` and no cleanup is already queued or running. It creates the durable job inside a transaction and queues cleanup through `transaction.on_commit`.

Manual **Finish Lab** and instructor cleanup actions create the same job and queue the same cleanup task. They do not create threads.

### Concurrency

Before cleanup starts, the service obtains a database row lock on the live session and its cleanup job. A second worker that encounters a queued or running job exits successfully without duplicating work.

The service always addresses resources by explicit database IDs and external IDs. Passing model objects across the task boundary is prohibited.

## Data Model

### LabCleanupJob

A cleanup job persists after the live session is removed.

Fields:

- UUID primary identifier
- nullable one-to-one link to `LabInstance` using `SET_NULL`
- snapshot of original session ID
- course, lab, and student identifiers
- trigger: `expired`, `student_finished`, `instructor_finished`, or `reconciliation`
- status: `queued`, `running`, `retrying`, `completed`, or `failed`
- requesting user when applicable
- resource snapshot containing machine database IDs, VMIDs, nodes, server IDs, Guacamole connection IDs, and VNC allocations
- attempt count
- last sanitized error
- queued, started, completed, and updated timestamps
- `failure_notified_at` for alert deduplication

The resource snapshot contains identifiers and operational metadata only. It never stores Proxmox, Guacamole, VPN, or user credentials.

### LabCleanupAttempt

Each execution appends an immutable attempt record:

- cleanup job
- attempt number
- start and finish timestamps
- outcome
- sanitized summary
- structured per-resource results

The result payload identifies the resource type and external identifier, whether cleanup succeeded, whether it was already absent, and a safe error category. Raw credentials, tokens, and unfiltered provider responses are prohibited.

### Existing status fields

A session moves to `deleting` as soon as a cleanup job is committed. It remains there during automatic retries. After final failure it moves to `error`. Live session and machine rows are deleted only after all required external resources are confirmed clean.

## Cleanup Algorithm

For each captured machine:

1. Delete its Guacamole connection when one exists.
2. Inspect the Proxmox VM.
3. Stop the VM when it is running and wait for the stopped state with a bounded timeout.
4. Delete the VM.
5. Release the VNC allocation.
6. Record each outcome independently.

An external `404`, “does not exist,” or previously released allocation is a successful idempotent result.

The service continues checking other resources after one resource fails so an attempt removes as much as safely possible. It does not delete the live database session while any required external cleanup remains unresolved.

After all machines are clean:

1. append the successful attempt;
2. mark the job completed;
3. delete the live `LabInstance`, cascading its machine rows;
4. retain the cleanup job and attempt history.

Repeated execution after completion returns success without new destructive calls.

## Retry and Failure Policy

There are five total automatic attempts:

1. initial execution;
2. retry after 1 minute;
3. retry after 5 minutes;
4. retry after 15 minutes;
5. retry after 30 minutes.

While retries remain, the job status is `retrying` and the session status remains `deleting`.

After the fifth failure:

- mark the job `failed`;
- mark the live session `error`;
- retain all state for investigation;
- prevent a replacement instance of the same lab from starting;
- create a dashboard alert;
- email the course instructors and active site administrators once.

An authorized instructor may select **Retry Cleanup**. This requeues the same job, preserves its prior attempt history, and applies the same idempotent cleanup logic.

## User Experience

### Student

When a timed lab expires:

- VM controls and lab actions become unavailable;
- the page displays: **Time expired—your lab environment is being cleaned up.**
- the status endpoint reports deleting, retrying, or cleanup failed;
- the student cannot start a duplicate instance while cleanup is unresolved;
- after successful cleanup, a new instance may be started only if normal course availability permits.

Expiration does not submit lab answers, create a `ContentCompletion`, or award gradebook credit.

### Instructor

Add a course-scoped **Lab Cleanup** dashboard showing:

- queued and running jobs;
- pending retries;
- completed jobs;
- failed jobs;
- course, student, session, machine, VMID, last attempt, and safe error summary.

The dashboard uses the existing course-management permission boundary. Authorized instructors can retry a failed job. Users who cannot manage the course receive no cleanup details.

### Email

After final failure, send one message to course instructors and active site administrators. The message identifies the course, lab, student, job ID, and failure category and links to the dashboard. It excludes credentials and raw provider error responses.

## Management Command

Refactor `cleanup_expired_labs` to use the lifecycle service.

Supported modes:

- default: synchronously process eligible expired sessions for recovery;
- `--enqueue`: create jobs and queue Celery tasks;
- `--dry-run`: list eligible sessions and resources without mutation;
- `--instance-id ID`: target one live session.

The command returns a nonzero exit status when requested cleanup finishes with unresolved failures. The existing shell wrapper may temporarily invoke this command as an emergency fallback, but normal operation uses Celery Beat.

## Observability

Structured logs include:

- cleanup job UUID;
- live session ID;
- lab ID;
- student ID;
- machine ID;
- VMID;
- attempt number;
- trigger;
- outcome and safe error category.

Operational metrics should be derivable from job rows and logs:

- cleanup latency after expiration;
- queued and retrying job counts;
- completed and failed cleanup counts;
- retry count by provider;
- oldest unresolved cleanup age.

## Security

- Only server-side configured provider clients may perform cleanup.
- Task payloads contain database IDs, not credentials or serialized model objects.
- Dashboard and retry endpoints enforce course-management permission.
- Error data is sanitized before persistence, logs, UI display, or email.
- Cleanup actions are POST-only and CSRF-protected.
- Resource identifiers are validated against the job snapshot and lab session.
- Cleanup never executes guest commands; QEMU guest-agent checks are a separate project.

## Testing

### Service tests

- complete cleanup succeeds;
- VM already absent is successful;
- Guacamole connection already absent is successful;
- VNC allocation already released is successful;
- partial failure preserves the session;
- successful resources remain safe on retry;
- repeated completed cleanup is a no-op;
- all attempt records are append-only;
- raw secrets are excluded from stored errors;
- concurrent cleanup requests result in one active execution.

### Task and scheduler tests

- the sweep selects sessions at or before `expires_at`;
- there is no ten-minute delay;
- persistent labs are excluded;
- duplicate jobs are not queued;
- retry delays follow 1, 5, 15, and 30 minutes;
- final failure queues one notification;
- worker restart can resume queued or retrying jobs.

### View and permission tests

- student Finish Lab queues cleanup and does not start a thread;
- expired student controls are disabled;
- instructors can view their course cleanup dashboard;
- unauthorized users cannot view or retry jobs;
- retry action is POST-only;
- expiration does not create completion or grade records.

### Command tests

- dry run performs no writes or external calls;
- one instance can be targeted;
- enqueue mode creates tasks;
- unresolved synchronous failures return a nonzero status.

## Rollout

1. Deploy schema, services, tasks, dashboard, and tests with the Beat entry disabled.
2. Run migrations.
3. Run `cleanup_expired_labs --dry-run` and review all existing expired sessions.
4. Exercise manual and automatic cleanup against a controlled lab.
5. Enable the 30-second Beat schedule.
6. Monitor worker logs, cleanup latency, retrying jobs, and final failures.
7. Retire the cron entry after the Celery path is stable.
8. Keep the management command for emergency recovery.

## Rollback

Disable the Beat schedule to stop new automatic cleanup jobs. Existing jobs remain visible and may be handled through the management command. Because the lifecycle service is idempotent, safely retrying a partially completed cleanup remains possible after rollback.

Schema rollback is not part of the operational response because removing audit records would destroy diagnostic evidence.

## Acceptance Criteria

The work is accepted when:

- a timed lab begins cleanup within 30 seconds after expiration under normal worker operation;
- manual and automatic cleanup share one service;
- a worker or web restart does not abandon cleanup;
- already-missing resources do not cause failure;
- partial failures retry automatically;
- final failures appear in the dashboard and produce one email alert;
- staff can retry cleanup;
- successful cleanup leaves no VM, Guacamole connection, VNC allocation, or live session row;
- audit history remains after success;
- expiration has no academic effect;
- all automated tests pass.
