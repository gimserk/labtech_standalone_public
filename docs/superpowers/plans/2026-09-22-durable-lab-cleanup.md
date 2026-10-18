# Durable Expired-Lab Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace fragile cron and request-thread lab cleanup with one durable, idempotent Celery lifecycle that removes expired lab resources, records audit history, retries failures, and alerts staff.

**Architecture:** A focused `app/services/labs/` package owns provider cleanup and lifecycle orchestration. Thin Celery tasks, views, and the recovery command all call that service; persistent cleanup jobs use leases to survive worker death without holding database transactions open during network calls.

**Tech Stack:** Django, MySQL, Celery, Redis, Proxmoxer, Requests, Django email, unittest/`django.test.TestCase`

**Spec:** `docs/superpowers/specs/2026-09-22-lab-lifecycle-cleanup-design.md`

## Global Constraints

- Timed cleanup is eligible at `expires_at <= timezone.now()`; there is no grace period.
- Celery Beat sweeps every 30 seconds.
- Automatic execution gets five total attempts: initial, then 1-, 5-, 15-, and 30-minute delays.
- Cleanup must be idempotent; “already absent” is success.
- Manual Finish Lab, automatic expiration, instructor retry, and recovery commands use the same lifecycle service.
- No task payload may contain a serialized model or credential; pass database IDs and cleanup-job UUIDs only.
- Resource snapshots, persisted errors, logs, pages, and email must not contain credentials, tokens, passwords, or raw provider responses.
- Live session rows are deleted only after Guacamole, Proxmox VM, and VNC cleanup are confirmed.
- Expiration must not create `ContentCompletion`, submit lab answers, or change gradebook data.
- Persistent labs are not selected by automatic cleanup.
- Celery worker and Celery Beat already run in production; no new background framework is introduced.
- MySQL remains the database; do not rely on PostgreSQL-only partial indexes or locking behavior.

## Review Focus

- A worker dying after claiming a job must leave an expiring lease that a later sweep can reclaim; test stale and unexpired leases separately in Task 3.
- A student Finish request racing the Beat sweep must create one cleanup job and one effective execution; test duplicate queue requests in Task 4.
- A lab expiring while VM creation is still running must not permit a clone to escape cleanup; test pre-clone and post-clone status checks in Task 5.
- A retry after partial success must skip resources already recorded as removed while retrying unresolved resources; test mixed outcomes in Task 3.
- Repeated final-failure processing must send one sanitized email and create no duplicate notification; test deduplication and secret removal in Task 6.

---

## File Structure

### Create

- `app/lab_cleanup_models.py` — cleanup job and immutable attempt models.
- `app/services/labs/__init__.py` — public lab-service package.
- `app/services/labs/types.py` — typed resource snapshots and cleanup results.
- `app/services/labs/providers.py` — Proxmox, Guacamole, and VNC adapters.
- `app/services/labs/lifecycle.py` — job creation, leasing, orchestration, finalization, and selection.
- `app/services/labs/alerts.py` — recipient selection and sanitized final-failure email.
- `app/lab_cleanup_views.py` — instructor dashboard and retry endpoint.
- `app/templates/labtech/lab_cleanup_dashboard.html` — cleanup operations UI.
- `app/tests/__init__.py` — Django test package marker.
- `app/tests/lab_cleanup_fixtures.py` — reusable course, lab, instance, and machine builders.
- `app/tests/test_lab_cleanup_models.py` — persistence and validation tests.
- `app/tests/test_lab_cleanup_providers.py` — provider normalization tests.
- `app/tests/test_lab_cleanup_lifecycle.py` — orchestration, concurrency, and retry-safety tests.
- `app/tests/test_lab_cleanup_tasks.py` — Beat selection, task retry, and notification tests.
- `app/tests/test_lab_cleanup_views.py` — student and instructor behavior tests.
- `app/tests/test_cleanup_expired_labs_command.py` — command-mode tests.
- `app/migrations/0125_lab_cleanup_models.py` — cleanup audit schema.
- `docs/operations/lab-cleanup.md` — deployment, monitoring, recovery, and rollback runbook.

### Modify

- `app/models.py` — re-export cleanup models.
- `app/tasks.py` — add thin cleanup request helpers and Celery tasks.
- `app/views.py` — remove cleanup threads, delegate Finish Lab, harden VM-creation race, and expose durable status.
- `app/permissions.py` — move `can_manage_course_content` to a reusable module.
- `app/urls.py` — add dashboard and retry routes.
- `app/settings.py` — add the 30-second Beat schedule.
- `app/templates/labtech/view_lab.html` — expired/deleting/retrying/failed student states.
- `app/management/commands/cleanup_expired_labs.py` — route all modes through the lifecycle service.
- `cleanup_labs_wrapper.sh` — document emergency-only use.
- `app/tests.py` — delete the empty file after creating the `app/tests/` package.

---

### Task 1: Persist Cleanup Jobs and Attempts

**Files:**
- Create: `app/lab_cleanup_models.py`
- Create: `app/migrations/0125_lab_cleanup_models.py`
- Create: `app/tests/__init__.py`
- Create: `app/tests/lab_cleanup_fixtures.py`
- Create: `app/tests/test_lab_cleanup_models.py`
- Modify: `app/models.py`
- Delete: `app/tests.py`

**Interfaces:**
- Consumes: existing `Course`, `Lab`, `LabInstance`, and user models.
- Produces: `LabCleanupJob`, `LabCleanupAttempt`, status/trigger constants, `LabCleanupJob.can_be_claimed(now)`.

- [ ] **Step 1: Convert the empty test module into a package**

Delete `app/tests.py`, create `app/tests/__init__.py`, and add fixture helpers with the exact public signatures:

```python
def create_cleanup_fixture(*, timed=True, expires_at=None):
    """Return (user, course, lab, instance) with required institution records."""

def add_machine(instance, *, vmid=9001, connection_id="guac-1", vnc_port=5901):
    """Return a LabInstanceMachine attached to the fixture session."""
```

Use the repository's required model fields rather than bypassing model validation.

- [ ] **Step 2: Write failing model tests**

```python
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone

from app.models import LabCleanupAttempt, LabCleanupJob
from app.tests.lab_cleanup_fixtures import create_cleanup_fixture


class LabCleanupModelTests(TestCase):
    def test_job_keeps_snapshot_after_live_session_is_deleted(self):
        user, course, lab, instance = create_cleanup_fixture(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        job = LabCleanupJob.objects.create(
            lab_instance=instance,
            session_id_snapshot=instance.pk,
            course=course,
            lab=lab,
            student=user,
            trigger=LabCleanupJob.TRIGGER_EXPIRED,
            status=LabCleanupJob.STATUS_QUEUED,
            resource_snapshot=[],
        )

        instance.delete()
        job.refresh_from_db()

        self.assertIsNone(job.lab_instance_id)
        self.assertEqual(lab.pk, job.lab_id)
        self.assertEqual(user.pk, job.student_id)

    def test_attempt_numbers_are_unique_per_job(self):
        _, course, lab, instance = create_cleanup_fixture()
        job = LabCleanupJob.objects.create(
            lab_instance=instance,
            session_id_snapshot=instance.pk,
            course=course,
            lab=lab,
            student=instance.user,
            trigger=LabCleanupJob.TRIGGER_STUDENT_FINISHED,
            status=LabCleanupJob.STATUS_RUNNING,
            resource_snapshot=[],
        )
        LabCleanupAttempt.objects.create(job=job, attempt_number=1, outcome="failed", results=[])

        with self.assertRaises(Exception):
            LabCleanupAttempt.objects.create(job=job, attempt_number=1, outcome="failed", results=[])
```

Add tests for allowed status/trigger values, default timestamps, blank secret-free snapshots, and `can_be_claimed()` for queued, retrying, failed, running-with-live-lease, and running-with-expired-lease states. Failed is not claimable until the retry view resets it to queued.

- [ ] **Step 3: Run the tests and verify failure**

Run:

```bash
python manage.py test app.tests.test_lab_cleanup_models -v 2
```

Expected: import failure because the cleanup models do not exist.

- [ ] **Step 4: Implement the cleanup models**

Define `LabCleanupJob` with:

```python
class LabCleanupJob(models.Model):
    TRIGGER_EXPIRED = "expired"
    TRIGGER_STUDENT_FINISHED = "student_finished"
    TRIGGER_INSTRUCTOR_FINISHED = "instructor_finished"
    TRIGGER_RECONCILIATION = "reconciliation"

    STATUS_QUEUED = "queued"
    STATUS_RUNNING = "running"
    STATUS_RETRYING = "retrying"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lab_instance = models.OneToOneField(
        LabInstance, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="cleanup_job",
    )
    session_id_snapshot = models.PositiveBigIntegerField(db_index=True)
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="lab_cleanup_jobs")
    lab = models.ForeignKey(Lab, on_delete=models.PROTECT, related_name="cleanup_jobs")
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="lab_cleanup_jobs",
    )
    trigger = models.CharField(max_length=24, choices=TRIGGER_CHOICES)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, db_index=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
        related_name="requested_lab_cleanups",
    )
    resource_snapshot = models.JSONField(default=list)
    attempt_count = models.PositiveIntegerField(default=0)
    lease_token = models.UUIDField(null=True, blank=True)
    lease_expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_error_code = models.CharField(max_length=64, blank=True)
    last_error_summary = models.CharField(max_length=500, blank=True)
    queued_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    failure_notified_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def can_be_claimed(self, now):
        if self.status in {self.STATUS_QUEUED, self.STATUS_RETRYING}:
            return True
        return (
            self.status == self.STATUS_RUNNING
            and self.lease_expires_at is not None
            and self.lease_expires_at <= now
        )
```

Define `LabCleanupAttempt` with a job foreign key, unique `(job, attempt_number)`, outcome choices, `results` JSON, safe summary/code fields, and start/finish timestamps. Add indexes for dashboard filters on `(course, status, updated_at)` and recovery on `(status, lease_expires_at)`.

Re-export both models at the bottom of `app/models.py`, following the existing gradebook-model pattern.

- [ ] **Step 5: Generate and inspect the migration**

Run:

```bash
python manage.py makemigrations app --name lab_cleanup_models
python manage.py sqlmigrate app 0125
```

Verify the SQL contains normal MySQL-compatible indexes and one-to-one/unique constraints, with no conditional index.

- [ ] **Step 6: Run model tests**

Run:

```bash
python manage.py test app.tests.test_lab_cleanup_models -v 2
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add app/models.py app/lab_cleanup_models.py app/migrations/0125_lab_cleanup_models.py app/tests
git rm app/tests.py
git commit -m "feat: add durable lab cleanup audit models"
```

---

### Task 2: Normalize Provider Cleanup

**Files:**
- Create: `app/services/labs/__init__.py`
- Create: `app/services/labs/types.py`
- Create: `app/services/labs/providers.py`
- Create: `app/tests/test_lab_cleanup_providers.py`
- Modify: `app/proxmox_guac_api.py`
- Modify: `app/guacamole_api.py`
- Modify: `app/port_utils.py`

**Interfaces:**
- Consumes: `ProxmoxServer`, `delete_guacamole_connection()`, and `release_vnc_port()`.
- Produces: `MachineResourceSnapshot.from_dict()`, `ResourceCleanupResult`, and `DjangoLabCleanupProviders.cleanup_guacamole|cleanup_vm|cleanup_vnc(snapshot)`.

- [ ] **Step 1: Write failing type and provider tests**

```python
from unittest.mock import Mock, patch
from django.test import TestCase

from app.services.labs.providers import DjangoLabCleanupProviders
from app.services.labs.types import MachineResourceSnapshot


class LabCleanupProviderTests(TestCase):
    def setUp(self):
        self.snapshot = MachineResourceSnapshot(
            machine_id=11,
            proxmox_server_id=3,
            proxmox_node="pve1",
            proxmox_vmid=9001,
            guacamole_connection_id="guac-1",
            vnc_port=5901,
        )

    @patch("app.services.labs.providers.get_proxmox_api_client")
    def test_vm_404_is_already_absent_success(self, client_factory):
        client_factory.return_value.nodes.return_value.qemu.return_value.status.current.get.side_effect = (
            ResourceException("not found", status_code=404)
        )

        result = DjangoLabCleanupProviders().cleanup_vm(self.snapshot)

        self.assertTrue(result.success)
        self.assertEqual("already_absent", result.outcome)

    @patch("app.services.labs.providers.delete_guacamole_connection", return_value=False)
    def test_guacamole_false_is_retryable_failure(self, _delete):
        result = DjangoLabCleanupProviders().cleanup_guacamole(self.snapshot)

        self.assertFalse(result.success)
        self.assertEqual("guacamole_delete_failed", result.error_code)
        self.assertNotIn("token", result.error_summary.lower())
```

Also test a stopped VM, a running VM that reaches stopped state, stop timeout, non-404 Proxmox failure, missing connection ID, missing VNC port, and repeated VNC release.

- [ ] **Step 2: Run provider tests and verify failure**

Run:

```bash
python manage.py test app.tests.test_lab_cleanup_providers -v 2
```

Expected: import failure for `app.services.labs`.

- [ ] **Step 3: Implement immutable types**

```python
@dataclass(frozen=True)
class MachineResourceSnapshot:
    machine_id: int
    proxmox_server_id: int
    proxmox_node: str
    proxmox_vmid: int
    guacamole_connection_id: str | None
    vnc_port: int | None

    @classmethod
    def from_dict(cls, value: dict) -> "MachineResourceSnapshot":
        return cls(**value)


@dataclass(frozen=True)
class ResourceCleanupResult:
    resource_type: str
    identifier: str
    outcome: Literal["removed", "already_absent", "skipped", "failed"]
    error_code: str = ""
    error_summary: str = ""

    @property
    def success(self) -> bool:
        return self.outcome != "failed"
```

Add `as_dict()` methods that emit JSON-safe primitive values only.

- [ ] **Step 4: Implement provider methods**

`DjangoLabCleanupProviders` loads `ProxmoxServer` by `snapshot.proxmox_server_id`. Implement:

```python
def cleanup_guacamole(self, snapshot) -> ResourceCleanupResult:
    if not snapshot.guacamole_connection_id:
        return ResourceCleanupResult("guacamole", "", "skipped")
    server = self._server(snapshot)
    guac = server.assigned_guacamole_server or GuacamoleServer.objects.filter(is_default=True).first()
    if guac is None:
        return ResourceCleanupResult(
            "guacamole", snapshot.guacamole_connection_id, "failed",
            "guacamole_server_missing", "No Guacamole server is configured.",
        )
    if delete_guacamole_connection(guac, snapshot.guacamole_connection_id):
        return ResourceCleanupResult("guacamole", snapshot.guacamole_connection_id, "removed")
    return ResourceCleanupResult(
        "guacamole", snapshot.guacamole_connection_id, "failed",
        "guacamole_delete_failed", "Guacamole did not confirm deletion.",
    )
```

Implement `cleanup_vm()` with bounded stop polling and 404 normalization. Implement `cleanup_vnc()` so missing allocations are `already_absent`. Reuse `get_proxmox_api_client()`; do not construct a second authentication path.

- [ ] **Step 5: Run provider tests**

Run:

```bash
python manage.py test app.tests.test_lab_cleanup_providers -v 2
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/services/labs app/tests/test_lab_cleanup_providers.py app/proxmox_guac_api.py app/guacamole_api.py app/port_utils.py
git commit -m "feat: add idempotent lab resource cleanup providers"
```

---

### Task 3: Implement the Lifecycle Service

**Files:**
- Create: `app/services/labs/lifecycle.py`
- Create: `app/tests/test_lab_cleanup_lifecycle.py`

**Interfaces:**
- Consumes: cleanup models and provider interfaces from Tasks 1–2.
- Produces:
  - `create_cleanup_job(instance_id: int, trigger: str, requested_by_id: int | None = None) -> tuple[LabCleanupJob, bool]`, where the boolean is true only for a newly created job
  - `claim_cleanup_job(job_id: UUID, *, now=None, lease_seconds=600) -> CleanupClaim | None`
  - `execute_claim(claim: CleanupClaim, providers=None) -> CleanupExecutionResult`
  - `mark_job_retrying(job_id: UUID, claim_token: UUID, result: CleanupExecutionResult) -> None`
  - `mark_job_failed(job_id: UUID, claim_token: UUID, result: CleanupExecutionResult) -> None`
  - `select_expired_instance_ids(*, now=None) -> list[int]`

- [ ] **Step 1: Write failing lifecycle tests**

Use a fake provider with per-resource call counters:

```python
class FakeProviders:
    def __init__(self, outcomes=None):
        self.outcomes = outcomes or {}
        self.calls = []

    def _result(self, kind, snapshot):
        key = f"{kind}:{snapshot.machine_id}"
        self.calls.append(key)
        return self.outcomes.get(
            key,
            ResourceCleanupResult(kind, str(snapshot.machine_id), "removed"),
        )

    def cleanup_guacamole(self, snapshot):
        return self._result("guacamole", snapshot)

    def cleanup_vm(self, snapshot):
        return self._result("proxmox_vm", snapshot)

    def cleanup_vnc(self, snapshot):
        return self._result("vnc", snapshot)
```

Add tests that pin:

- snapshot creation and immediate `LabInstance.STATUS_DELETING`;
- duplicate `create_cleanup_job()` calls returning the same job;
- unexpired running lease cannot be claimed;
- expired running lease can be reclaimed;
- successful execution deletes the live instance and retains the completed job;
- partial failure retains the live instance;
- retry skips resource keys recorded successful in the prior attempt;
- a completed job is a no-op;
- persistent labs are absent from `select_expired_instance_ids()`;
- expiration creates no `ContentCompletion` or gradebook decision rows.

The mixed-outcome test must assert exact calls:

```python
self.assertEqual(
    ["guacamole:11", "proxmox_vm:11", "vnc:11"],
    first_provider.calls,
)
self.assertEqual(
    ["proxmox_vm:11"],
    retry_provider.calls,
)
```

when Guacamole and VNC succeeded but VM deletion failed on the first attempt.

- [ ] **Step 2: Run lifecycle tests and verify failure**

Run:

```bash
python manage.py test app.tests.test_lab_cleanup_lifecycle -v 2
```

Expected: import failure for lifecycle functions.

- [ ] **Step 3: Implement safe job creation and snapshots**

Inside `transaction.atomic()`, lock the `LabInstance`, return its existing cleanup job when present, otherwise snapshot machines with:

```python
{
    "machine_id": machine.pk,
    "proxmox_server_id": machine.proxmox_server_id,
    "proxmox_node": machine.proxmox_node,
    "proxmox_vmid": machine.proxmox_vmid,
    "guacamole_connection_id": machine.guacamole_connection_id,
    "vnc_port": machine.vnc_port,
}
```

Create the job, set the session status to `deleting`, and save only that field.

- [ ] **Step 4: Implement leasing without long transactions**

`claim_cleanup_job()` locks only long enough to validate state, assign a fresh UUID token, set `lease_expires_at = now + 10 minutes`, increment `attempt_count`, and commit. Return an immutable `CleanupClaim` containing job ID, token, attempt number, and parsed snapshots.

Do not hold a database transaction while calling Proxmox or Guacamole.

- [ ] **Step 5: Implement execution and finalization**

`execute_claim()` loads successful resource keys from prior attempts, skips them, calls all unresolved provider operations, and appends one attempt row.

On all-success finalization, verify the claim token under a row lock, mark the job completed, clear the lease, delete the live session, and retain the job. On failure, return safe error code `resource_cleanup_failed` and a summary listing failed resource types without provider response bodies.

Emit structured log records for claim, resource result, retry, final failure, and completion with `cleanup_job_id`, `session_id`, `lab_id`, `student_id`, `machine_id`, `vmid`, `attempt_number`, `trigger`, `outcome`, and safe `error_code` fields.

- [ ] **Step 6: Run lifecycle tests**

Run:

```bash
python manage.py test app.tests.test_lab_cleanup_lifecycle -v 2
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add app/services/labs/lifecycle.py app/tests/test_lab_cleanup_lifecycle.py
git commit -m "feat: add durable lab cleanup lifecycle service"
```

---

### Task 4: Add Celery Sweep, Execution, and Retry Scheduling

**Files:**
- Modify: `app/tasks.py`
- Modify: `app/settings.py`
- Create: `app/tests/test_lab_cleanup_tasks.py`

**Interfaces:**
- Consumes: Task 3 lifecycle functions.
- Produces:
  - `request_lab_cleanup(instance_id, trigger, requested_by_id=None) -> LabCleanupJob`
  - Celery task `app.tasks.sweep_expired_lab_instances`
  - Celery task `app.tasks.cleanup_lab_instance`
  - Celery task `app.tasks.send_lab_cleanup_failure_alert`

- [ ] **Step 1: Write failing task tests**

Mock `.delay()` and lifecycle boundaries. Cover:

```python
@patch("app.tasks.cleanup_lab_instance.delay")
def test_duplicate_requests_queue_one_effective_job(self, delay):
    first = request_lab_cleanup(
        self.instance.pk,
        LabCleanupJob.TRIGGER_STUDENT_FINISHED,
        self.user.pk,
    )
    second = request_lab_cleanup(
        self.instance.pk,
        LabCleanupJob.TRIGGER_EXPIRED,
    )

    self.assertEqual(first.pk, second.pk)
    self.assertEqual(1, delay.call_count)
```

Also test:

- sweep queues sessions exactly at expiration;
- persistent sessions are ignored;
- stale running leases are requeued;
- successful execution does not retry;
- failures use countdowns `60`, `300`, `900`, and `1800`;
- fifth failure calls `mark_job_failed()` and queues one alert task;
- task arguments contain only string UUIDs/integers.

Use `transaction.captureOnCommitCallbacks(execute=True)` when asserting queued work.

- [ ] **Step 2: Run task tests and verify failure**

Run:

```bash
python manage.py test app.tests.test_lab_cleanup_tasks -v 2
```

Expected: missing cleanup task functions.

- [ ] **Step 3: Implement request and sweep wrappers**

```python
RETRY_DELAYS_SECONDS = (60, 300, 900, 1800)


def request_lab_cleanup(instance_id, trigger, requested_by_id=None):
    job, created = create_cleanup_job(
        instance_id=instance_id,
        trigger=trigger,
        requested_by_id=requested_by_id,
    )
    if created:
        transaction.on_commit(lambda: cleanup_lab_instance.delay(str(job.pk)))
    return job
```

`create_cleanup_job()` returns `(job, created)` exactly; never infer first-queue behavior from mutable status. The sweep iterates expired IDs and stale leases in bounded batches, calls `request_lab_cleanup()`, and returns counts for logging.

- [ ] **Step 4: Implement the bound cleanup task**

Use `@shared_task(bind=True, max_retries=4)`. Claim, execute, and either finalize success or mark retrying. Select the delay with `RETRY_DELAYS_SECONDS[self.request.retries]`. On the final exhausted attempt, mark failed and queue the alert through `transaction.on_commit`.

Do not use Celery `autoretry_for=(Exception,)`; provider errors are normalized results, while unexpected programming errors should be logged and handled deliberately.

- [ ] **Step 5: Configure Beat**

Add:

```python
from celery.schedules import schedule

CELERY_BEAT_SCHEDULE = {
    "sweep-expired-lab-instances": {
        "task": "app.tasks.sweep_expired_lab_instances",
        "schedule": schedule(30.0),
    },
}
```

Preserve any existing Beat entries by merging rather than overwriting if the deployment branch has gained them.

- [ ] **Step 6: Run task tests**

Run:

```bash
python manage.py test app.tests.test_lab_cleanup_tasks -v 2
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add app/tasks.py app/settings.py app/tests/test_lab_cleanup_tasks.py
git commit -m "feat: schedule durable expired-lab cleanup"
```

---

### Task 5: Replace Request Threads and Close the VM-Creation Race

**Files:**
- Modify: `app/views.py`
- Modify: `app/permissions.py`
- Modify: `app/templates/labtech/view_lab.html`
- Create: `app/tests/test_lab_cleanup_views.py`

**Interfaces:**
- Consumes: `request_lab_cleanup()` and cleanup-job status.
- Produces: thread-free Finish Lab behavior, durable status JSON, and creation cancellation when cleanup begins.

- [ ] **Step 1: Extract the reusable permission helper**

Move `can_manage_course_content(user, course)` from `app/views.py` to `app/permissions.py` without changing its behavior. Import it back into `views.py`. Add a focused test proving superuser, institution admin, assigned instructor, unrelated user, and anonymous behavior remains unchanged.

- [ ] **Step 2: Write failing student-flow and race tests**

Cover:

- POST Finish Lab marks deleting and queues one job;
- Finish Lab starts no `threading.Thread`;
- deletion status returns `retrying` from the cleanup job;
- expired lab page contains “Time expired—your lab environment is being cleaned up.”;
- machine action endpoint rejects deleting/error sessions;
- pre-clone creation check aborts when session changed from building to deleting;
- post-clone check persists enough resource identity and immediately queues cleanup if expiration raced with cloning.

For the thread regression:

```python
@patch("app.views.threading.Thread")
@patch("app.views.request_lab_cleanup")
def test_finish_lab_queues_cleanup_without_thread(self, request_cleanup, thread):
    response = self.client.post(
        reverse("finish_lab_session", args=[self.course.pk, self.instance.pk])
    )

    self.assertEqual(302, response.status_code)
    request_cleanup.assert_called_once_with(
        self.instance.pk,
        LabCleanupJob.TRIGGER_STUDENT_FINISHED,
        self.user.pk,
    )
    thread.assert_not_called()
```

- [ ] **Step 3: Run view tests and verify failure**

Run:

```bash
python manage.py test app.tests.test_lab_cleanup_views -v 2
```

Expected: thread assertion fails and retrying UI/status is absent.

- [ ] **Step 4: Delegate Finish Lab and status polling**

Replace `_background_finish_lab` and `_finish_lab_machine` use from the HTTP flow with `request_lab_cleanup()`. Remove those cleanup functions after the management command has no callers.

Update `get_lab_deletion_status_view()` to return:

```python
{
    "status": job.status if job else lab_session.status,
    "job_id": str(job.pk) if job else None,
}
```

When the live instance is gone, resolve the latest job by `session_id_snapshot` and current user before returning `completed`; never expose another student's job.

- [ ] **Step 5: Guard VM creation**

At the start of `_create_single_machine_thread()`, reload the session and return before cloning unless status is `building` or `active`.

After Proxmox cloning but before declaring success, reload the session. If it is now `deleting` or `error`, persist the machine row with VMID/node/server/connection/VNC identity, then call `request_lab_cleanup()`. This ensures the new external VM is included in a refreshed snapshot. Update `create_cleanup_job()` to merge newly observed machine resources into an existing non-completed job snapshot under a row lock.

- [ ] **Step 6: Update the student template**

Render distinct copy for:

- expired/deleting: “Time expired—your lab environment is being cleaned up.”
- retrying: “Cleanup is retrying automatically. You may safely leave this page.”
- failed: “Cleanup needs staff attention. Your instructor has been notified.”

Disable machine action forms and the Finish button for all three states. Continue polling while deleting or retrying; reload on completed or failed.

- [ ] **Step 7: Run student/view tests**

Run:

```bash
python manage.py test app.tests.test_lab_cleanup_views -v 2
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add app/views.py app/permissions.py app/templates/labtech/view_lab.html app/tests/test_lab_cleanup_views.py
git commit -m "refactor: route lab finish through durable cleanup"
```

---

### Task 6: Add Instructor Dashboard, Retry, and Alerts

**Files:**
- Create: `app/services/labs/alerts.py`
- Create: `app/lab_cleanup_views.py`
- Create: `app/templates/labtech/lab_cleanup_dashboard.html`
- Modify: `app/urls.py`
- Modify: `app/tasks.py`
- Modify: `app/tests/test_lab_cleanup_views.py`
- Modify: `app/tests/test_lab_cleanup_tasks.py`

**Interfaces:**
- Consumes: cleanup jobs, `can_manage_course_content()`, and `request_lab_cleanup()`.
- Produces:
  - `failure_recipients(job) -> tuple[str, ...]`
  - `send_cleanup_failure_email(job_id: UUID) -> bool`
  - course dashboard view
  - POST-only retry view

- [ ] **Step 1: Write failing alert tests**

Create a failed job whose error text contains `token=secret-value`. Add an assigned instructor, active superuser, inactive superuser, and unrelated user.

Assert:

```python
self.assertEqual(
    ("admin@example.test", "instructor@example.test"),
    failure_recipients(job),
)
```

Patch `send_mail`, call the alert twice, and assert one send. Assert neither the email body nor persisted `last_error_summary` contains `secret-value`, `password`, or `token=`.

- [ ] **Step 2: Write failing dashboard and retry tests**

Cover:

- assigned instructor and institution admin can view;
- unrelated and anonymous users cannot view;
- dashboard is course-scoped;
- retry is POST-only;
- retrying a failed job preserves previous attempts;
- repeated retry submissions queue one effective task;
- job from another course cannot be retried.

- [ ] **Step 3: Run alert/view tests and verify failure**

Run:

```bash
python manage.py test app.tests.test_lab_cleanup_tasks app.tests.test_lab_cleanup_views -v 2
```

Expected: missing alert and dashboard modules/routes.

- [ ] **Step 4: Implement sanitization and recipient selection**

Use one sanitizer for persistence, logs, UI, and email. Redact case-insensitive key/value forms for `password`, `token`, `secret`, `authorization`, and `api_key`, and cap summaries at 500 characters.

Recipient query:

```python
instructor_emails = job.course.instructors.filter(
    user__is_active=True,
).exclude(
    user__email="",
).values_list("user__email", flat=True)

admin_emails = get_user_model().objects.filter(
    is_active=True,
    is_superuser=True,
).exclude(
    email="",
).values_list("email", flat=True)

return tuple(sorted(set(instructor_emails) | set(admin_emails)))
```

Inside a transaction, lock the job and set `failure_notified_at` before sending so duplicate tasks cannot double-send. If sending raises, clear the timestamp under lock and let the alert task retry.

- [ ] **Step 5: Implement dashboard and retry views**

Add:

```python
@login_required
def lab_cleanup_dashboard_view(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    if not can_manage_course_content(request.user, course):
        return HttpResponseForbidden(...)
    jobs = LabCleanupJob.objects.filter(course=course).select_related(
        "lab", "student", "requested_by"
    ).order_by("-updated_at")
    return render(request, "labtech/lab_cleanup_dashboard.html", {...})


@require_POST
@login_required
def retry_lab_cleanup_view(request, course_id, job_id):
    ...
```

Retry must lock the job, require `failed`, set `queued`, clear its lease and error summary, preserve attempts, and queue `cleanup_lab_instance.delay(str(job.pk))` through `transaction.on_commit`.

Add URLs:

```python
path(
    "courses/<int:course_id>/lab-cleanups/",
    lab_cleanup_views.lab_cleanup_dashboard_view,
    name="lab_cleanup_dashboard",
),
path(
    "courses/<int:course_id>/lab-cleanups/<uuid:job_id>/retry/",
    lab_cleanup_views.retry_lab_cleanup_view,
    name="retry_lab_cleanup",
),
```

- [ ] **Step 6: Build the dashboard template**

Use the existing Bootstrap layout. Include status filters, timestamps, student, lab, trigger, attempts, VMIDs from the snapshot, sanitized failure summary, and a CSRF-protected Retry Cleanup form only for failed jobs.

Do not render provider hostnames, usernames, passwords, tokens, or raw result JSON.

- [ ] **Step 7: Run alert and dashboard tests**

Run:

```bash
python manage.py test app.tests.test_lab_cleanup_tasks app.tests.test_lab_cleanup_views -v 2
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add app/services/labs/alerts.py app/lab_cleanup_views.py app/templates/labtech/lab_cleanup_dashboard.html app/urls.py app/tasks.py app/tests
git commit -m "feat: add lab cleanup alerts and dashboard"
```

---

### Task 7: Refactor the Recovery Command and Document Operations

**Files:**
- Modify: `app/management/commands/cleanup_expired_labs.py`
- Modify: `cleanup_labs_wrapper.sh`
- Create: `app/tests/test_cleanup_expired_labs_command.py`
- Create: `docs/operations/lab-cleanup.md`

**Interfaces:**
- Consumes: lifecycle selection/execution and task request interfaces.
- Produces: dry-run, targeted, enqueue, and synchronous recovery modes.

- [ ] **Step 1: Write failing command tests**

Use `call_command()` and mock external providers/tasks.

Test:

- `--dry-run` prints eligible IDs and performs zero writes/external calls;
- `--instance-id` targets only one session;
- `--enqueue` calls `request_lab_cleanup()`;
- default mode executes synchronously through the lifecycle service;
- unresolved failure raises `CommandError`;
- command passes an integer ID, never a model object;
- persistent and future timed sessions are excluded.

- [ ] **Step 2: Run command tests and verify failure**

Run:

```bash
python manage.py test app.tests.test_cleanup_expired_labs_command -v 2
```

Expected: option parsing failures and the existing object-versus-ID regression.

- [ ] **Step 3: Implement command modes**

Add arguments:

```python
parser.add_argument("--dry-run", action="store_true")
parser.add_argument("--enqueue", action="store_true")
parser.add_argument("--instance-id", type=int)
```

Use `select_expired_instance_ids()` unless an instance ID is supplied. Dry run prints session/lab/student/machine/VMID identifiers from read-only queries. Enqueue mode calls `request_lab_cleanup(id, TRIGGER_RECONCILIATION)`. Default mode creates/claims/executes each job synchronously and raises `CommandError` when any result remains unresolved.

Remove the import from `app.views`.

- [ ] **Step 4: Update the wrapper and operations runbook**

Make `cleanup_labs_wrapper.sh` invoke the command with `--enqueue` and add a comment stating it is emergency fallback only.

Document exact rollout commands:

```bash
python manage.py migrate
python manage.py cleanup_expired_labs --dry-run
CONTROLLED_INSTANCE_ID=123  # replace 123 with the verified disposable lab-session ID
python manage.py cleanup_expired_labs --instance-id "$CONTROLLED_INSTANCE_ID"
sudo systemctl restart labtech-web
sudo systemctl restart celery-worker
sudo systemctl restart celery-beat
```

The runbook must tell operators to replace the service names with their deployed units after checking `systemctl list-units --type=service | grep -E 'celery|labtech'`; do not assume names silently.

Include dashboard checks, queue/log checks, disabling the Beat entry for rollback, and manual retry/recovery procedures.

- [ ] **Step 5: Run command tests**

Run:

```bash
python manage.py test app.tests.test_cleanup_expired_labs_command -v 2
```

Expected: PASS.

- [ ] **Step 6: Run the complete relevant suite**

Run:

```bash
python manage.py test app.tests app.services.gradebook.tests -v 2
python manage.py makemigrations --check
python manage.py check
```

Expected: all tests pass, no pending migrations, and no Django system-check errors.

- [ ] **Step 7: Verify no obsolete cleanup path remains**

Run:

```bash
rg -n "_background_finish_lab|_finish_lab_machine|threading\.Thread.*finish|expires_at__lt=.*timedelta" app cleanup_labs_wrapper.sh
```

Expected: no production references to the removed thread/helper or ten-minute threshold. Test names may mention the regression.

- [ ] **Step 8: Commit**

```bash
git add app/management/commands/cleanup_expired_labs.py cleanup_labs_wrapper.sh app/tests/test_cleanup_expired_labs_command.py docs/operations/lab-cleanup.md
git commit -m "docs: add lab cleanup recovery and rollout workflow"
```

---

## Final Verification and Review

- [ ] **Step 1: Run the full project test suite**

```bash
python manage.py test -v 2
```

Expected: PASS.

- [ ] **Step 2: Run static Django checks**

```bash
python manage.py check
python manage.py makemigrations --check
python -m compileall -q app
```

Expected: all commands succeed and no migration drift is reported.

- [ ] **Step 3: Inspect the branch diff**

```bash
git diff --check main...HEAD
git diff --stat main...HEAD
git log --oneline main..HEAD
```

Expected: no whitespace errors; commits correspond to Tasks 1–7.

- [ ] **Step 4: Perform whole-branch code review**

Review especially:

- no database transaction spans provider network calls;
- job leases recover stale running work;
- VM creation cannot outlive a deleting session unnoticed;
- task retries use the exact approved delays;
- only one final-failure notification is sent;
- no error or snapshot leaks credentials;
- no expiration path writes academic completion or gradebook data.

- [ ] **Step 5: Prepare the pull request**

Use title:

```text
Implement durable expired-lab cleanup
```

PR body must summarize lifecycle extraction, Celery schedule/retries, audit/dashboard/alerts, the fixed object-versus-ID defect, and exact test commands/results. Do not enable the Beat schedule in production until the runbook's dry run and controlled cleanup pass.
