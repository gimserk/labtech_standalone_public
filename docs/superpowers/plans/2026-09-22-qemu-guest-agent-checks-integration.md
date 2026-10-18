# QEMU Guest-Agent Lab Checks — Integration Tasks 5–8

> Part of `docs/superpowers/plans/2026-09-22-qemu-guest-agent-checks.md`. Read the main plan, approved spec, and foundation task interfaces first. Execute these tasks in order.

### Task 5: Validation orchestration, leases, history, and finish gate

**Files:**
- Create: `app/services/lab_checks/service.py`
- Create: `app/services/lab_checks/selectors.py`
- Modify: `app/tasks.py`
- Create: `app/tests/lab_checks/test_service.py`
- Create: `app/tests/lab_checks/test_finish_gate.py`

**Interfaces:**
- Consumes: Tasks 1-4 models, secrets, registry, validators, and executor.
- Produces: `run_step_checks(*, actor, lab_instance, step, executor=None) -> ValidationRun`.
- Produces: `run_finish_checks(*, actor, lab_instance, executor=None) -> ValidationRun`.
- Produces: `run_instructor_preview(*, actor, lab_instance, check, executor=None) -> ValidationRun`.
- Produces: `current_check_state(lab_instance) -> dict[int, CurrentCheckState]` keyed by StepCheck ID.
- Produces: `finish_and_request_cleanup(*, actor, lab_instance, executor=None) -> FinishCheckResult`.

- [ ] **Step 1: Write failing lease, cooldown, stale-run, and current-revision tests**

```python
def test_instance_lease_blocks_overlapping_step_and_finish_runs(self):
    self.make_live_lease(expires_at=timezone.now() + timedelta(seconds=30))
    with self.assertRaises(ValidationBusy):
        run_finish_checks(actor=self.user, lab_instance=self.instance, executor=self.executor)

def test_stale_lease_abandons_old_run_and_allows_retry(self):
    old = self.make_live_lease(expires_at=timezone.now() - timedelta(seconds=1))
    run = run_step_checks(actor=self.user, lab_instance=self.instance, step=self.step, executor=self.executor)
    old.run.refresh_from_db()
    self.assertEqual(old.run.outcome, "abandoned")
    self.assertEqual(run.outcome, "pass")

def test_old_revision_pass_does_not_unlock_finish(self):
    self.make_pass_result(check=self.check, revision=1)
    self.check.definition_revision = 2
    self.check.save(update_fields=["definition_revision"])
    self.assertFalse(current_check_state(self.instance)[self.check.pk].passed)
```

Add tests for 10-second step cooldown, retries after cooldown, no cooldown on finish, stable check ordering, all outcome aggregations, deactivated checks, zero-check labs, and one result per active check.

- [ ] **Step 2: Run service tests and verify failure**

Run: `python manage.py test app.tests.lab_checks.test_service --settings=test_settings -v 2`

Expected: FAIL because the orchestration service does not exist.

- [ ] **Step 3: Implement atomic lease acquisition and run finalization**

```python
@transaction.atomic
def _start_run(*, actor, instance, step, context, now):
    locked = LabInstance.objects.select_for_update().get(pk=instance.pk)
    lease = ValidationLease.objects.select_related("run").filter(lab_instance=locked).first()
    if lease and lease.expires_at > now:
        raise ValidationBusy()
    if lease:
        ValidationRun.objects.filter(pk=lease.run_id, status="running").update(
            status="finished", outcome="abandoned", finished_at=now)
        lease.delete()
    run = ValidationRun.objects.create(
        lab_instance=locked, actor=actor, step=step, context=context,
        deadline_at=now + timedelta(seconds=45))
    ValidationLease.objects.create(
        lab_instance=locked, run=run, expires_at=now + timedelta(seconds=60))
    return run
```

Perform all Proxmox calls after `_start_run` commits. Decrypt only immediately before command construction, convert executor exceptions to safe result codes, persist snapshots, finalize counts/outcome, and delete the lease in a short transaction.

- [ ] **Step 4: Implement selectors using the latest result at the current revision**

`current_check_state` must treat the latest matching result as authoritative: a pass followed by fail is not passed. Filter active, nonremoved checks for the instance's lab, bulk-load results, and never query per check. Add a query-count test to prevent N+1 behavior.

- [ ] **Step 5: Write failing finish/cleanup boundary tests**

```python
@mock.patch("app.services.lab_checks.service.request_lab_cleanup")
def test_finish_requests_cleanup_only_after_fresh_all_pass(self, cleanup):
    self.executor.results = [passing_guest_result()]
    result = finish_and_request_cleanup(actor=self.user, lab_instance=self.instance, executor=self.executor)
    self.assertEqual(result.outcome, "pass")
    cleanup.assert_called_once_with(
        self.instance.pk, LabCleanupJob.TRIGGER_STUDENT_FINISHED, self.user.pk)

@mock.patch("app.services.lab_checks.service.request_lab_cleanup")
def test_fail_or_infrastructure_never_requests_cleanup(self, cleanup):
    for decision in ("fail", "infrastructure_error", "configuration_error"):
        self.executor.decision = decision
        result = finish_and_request_cleanup(actor=self.user, lab_instance=self.instance, executor=self.executor)
        self.assertEqual(result.outcome, decision)
    cleanup.assert_not_called()
```

Also prove repeated all-pass finish requests create only one cleanup job through existing idempotency rules and that no-check labs call the current cleanup path unchanged.

- [ ] **Step 6: Implement the guarded cleanup handoff and run focused tests**

Hold the per-instance validation lease until a short final transaction locks LabInstance, confirms it is still active, confirms the owning run is a fresh all-pass finish run, and invokes the existing `request_lab_cleanup`. Do not change the cleanup provider/task behavior.

Run: `python manage.py test app.tests.lab_checks.test_service app.tests.lab_checks.test_finish_gate app.tests.test_lab_cleanup_lifecycle --settings=test_settings -v 2`

Expected: PASS.

- [ ] **Step 7: Commit orchestration**

```bash
git add app/services/lab_checks app/tasks.py app/tests/lab_checks
git commit -m "feat: orchestrate required lab validation"
```

---

### Task 6: Student endpoints, lab page, and completion behavior

**Files:**
- Create: `app/lab_check_views.py`
- Modify: `app/views.py`
- Modify: `app/urls.py`
- Modify: `app/templates/labtech/view_lab.html`
- Create: `app/static/labtech/js/lab_checks.js`
- Create: `app/tests/lab_checks/test_student_views.py`
- Create: `app/tests/lab_checks/test_student_template.py`

**Interfaces:**
- Consumes: Task 5 `run_step_checks`, `current_check_state`, and `finish_and_request_cleanup`.
- Produces: POST route `run_lab_step_checks` and JSON `{run_id, outcome, checks, retry_after_seconds}`.
- Modifies: existing `finish_lab_session_view` to use the guarded finish service when active checks exist.

Add the route as:

```python
path(
    "courses/<int:course_id>/lab-instances/<int:instance_id>/steps/<int:step_id>/check/",
    lab_check_views.run_lab_step_checks_view,
    name="run_lab_step_checks",
)
```

- [ ] **Step 1: Write failing ownership, CSRF, cooldown, response-redaction, and finish tests**

```python
def test_student_cannot_run_checks_for_another_users_instance(self):
    response = self.client.post(reverse("run_lab_step_checks", args=[self.course.pk, self.instance.pk, self.step.pk]))
    self.assertEqual(response.status_code, 404)

def test_failed_response_contains_hint_but_not_expected_value_or_output(self):
    response = self.owner_client.post(self.step_url)
    payload = response.json()
    self.assertEqual(payload["checks"][0]["hint"], "Create the requested file")
    serialized = json.dumps(payload)
    self.assertNotIn("flag{private}", serialized)
    self.assertNotIn("guest stdout", serialized)

@mock.patch("app.views.finish_and_request_cleanup")
def test_finish_failure_keeps_instance_active_and_does_not_redirect_to_cleanup(self, finish):
    finish.return_value = FinishCheckResult(outcome="fail", first_failed_step_id=self.step.pk)
    response = self.owner_client.post(self.finish_url)
    self.instance.refresh_from_db()
    self.assertEqual(self.instance.status, LabInstance.STATUS_ACTIVE)
    self.assertEqual(response.status_code, 302)
```

Use a CSRF-enforcing client for the POST route; add cross-course, cross-step, inactive/expired instance, missing machine, busy lease, and infrastructure-message cases.

- [ ] **Step 2: Run student view tests and verify route/import failures**

Run: `python manage.py test app.tests.lab_checks.test_student_views --settings=test_settings -v 2`

Expected: FAIL because the route and view do not exist.

- [ ] **Step 3: Add thin views and exact public response mapping**

```python
@require_POST
@login_required
def run_lab_step_checks_view(request, course_id, instance_id, step_id):
    instance = get_object_or_404(
        LabInstance.objects.select_related("lab", "lab__course"),
        pk=instance_id, user=request.user, lab__course_id=course_id,
        status=LabInstance.STATUS_ACTIVE)
    step = get_object_or_404(Step, pk=step_id, lab=instance.lab)
    try:
        run = run_step_checks(actor=request.user, lab_instance=instance, step=step)
    except ValidationBusy as exc:
        return JsonResponse({"error": "check_in_progress", "retry_after_seconds": exc.retry_after}, status=409)
    return JsonResponse(public_run_payload(run))
```

Map fail to the stored hint, infrastructure/configuration to one generic message, and omit config/code/output fields. Update the finish view to preserve the current no-check path and otherwise call the guarded finish service.

- [ ] **Step 4: Add failing template and JavaScript behavior tests**

Assert that checked steps render labels/statuses/data URLs, the finish control is disabled until current-revision passes exist, no-check labs render the current finish control, and the JavaScript uses `textContent` rather than HTML insertion for server messages.

- [ ] **Step 5: Render check panels and implement accessible submission/cooldown UI**

Add prefetched check state to `view_lab_view`. Render one button per checked step, `aria-live="polite"` result regions, pass/fail/infrastructure classes, and a disabled finish explanation. In `lab_checks.js`, submit CSRF-protected fetch requests, disable during execution, display returned public values with `textContent`, and count down `retry_after_seconds`.

- [ ] **Step 6: Run student tests plus existing lab/cleanup views and commit**

Run: `python manage.py test app.tests.lab_checks.test_student_views app.tests.lab_checks.test_student_template app.tests.test_lab_cleanup_views --settings=test_settings -v 2`

Expected: PASS.

```bash
git add app/lab_check_views.py app/views.py app/urls.py app/templates/labtech/view_lab.html app/static/labtech/js/lab_checks.js app/tests/lab_checks
git commit -m "feat: add student lab check workflow"
```

---

### Task 7: Instructor configuration, preview, and sanitized history

**Files:**
- Create: `app/lab_check_forms.py`
- Modify: `app/lab_check_views.py`
- Modify: `app/urls.py`
- Modify: `app/templates/labtech/manage_lab_steps.html`
- Create: `app/templates/labtech/manage_step_checks.html`
- Create: `app/templates/labtech/lab_check_form.html`
- Create: `app/templates/labtech/lab_check_history.html`
- Create: `app/tests/lab_checks/test_instructor_forms.py`
- Create: `app/tests/lab_checks/test_instructor_views.py`
- Create: `app/tests/lab_checks/test_history.py`

**Interfaces:**
- Consumes: Task 2 registry schemas, Task 1 encryption, Task 5 preview/history services.
- Produces: `StepCheckMetadataForm` and `build_config_form(check_type, guest_os, data=None, initial=None)`.
- Produces instructor routes for list/create/edit/reorder/deactivate/preview/history.

Use these route names and shapes so templates/tests share one contract:

```python
path("courses/<int:course_id>/labs/<int:lab_id>/steps/<int:step_id>/checks/", manage_step_checks_view, name="manage_step_checks")
path("courses/<int:course_id>/labs/<int:lab_id>/steps/<int:step_id>/checks/new/", create_step_check_view, name="create_step_check")
path("courses/<int:course_id>/labs/<int:lab_id>/checks/<int:check_id>/edit/", edit_step_check_view, name="edit_step_check")
path("courses/<int:course_id>/labs/<int:lab_id>/steps/<int:step_id>/checks/reorder/", reorder_step_checks_view, name="reorder_step_checks")
path("courses/<int:course_id>/labs/<int:lab_id>/checks/<int:check_id>/deactivate/", deactivate_step_check_view, name="deactivate_step_check")
path("courses/<int:course_id>/labs/<int:lab_id>/checks/<int:check_id>/remove/", remove_step_check_view, name="remove_step_check")
path("courses/<int:course_id>/labs/<int:lab_id>/checks/<int:check_id>/preview/", preview_step_check_view, name="preview_step_check")
path("courses/<int:course_id>/labs/<int:lab_id>/check-history/", lab_check_history_view, name="lab_check_history")
```

- [ ] **Step 1: Write failing typed-form and secret write-only tests**

```python
def test_file_content_form_separates_expected_value_as_secret(self):
    form = build_config_form("file_content", "linux", data={
        "path": "{home}/answer.txt", "match": "exact", "expected": "flag{private}"})
    self.assertTrue(form.is_valid(), form.errors)
    public, secret = form.normalized_configs()
    self.assertEqual(public, {"path": "{home}/answer.txt", "match": "exact"})
    self.assertEqual(secret, {"expected": "flag{private}"})

def test_edit_form_never_repopulates_existing_secret(self):
    form = build_config_form("file_content", "linux", initial_public=self.check.public_config,
                             has_existing_secret=True)
    self.assertNotIn("flag{private}", form.as_p())
    self.assertEqual(form.fields["expected"].initial, "")
```

Test all seven form schemas, OS filtering, machine/step same-lab validation, exact choices, size limits, and blank secret-on-edit preserving the existing encrypted value.

- [ ] **Step 2: Implement metadata and seven type-specific forms backed by registry normalization**

Each form exposes only schema fields. `save_step_check` encrypts secret config, calls `full_clean`, and increments the revision only when type, machine, public config, or effective secret config changes.

```python
def build_config_form(check_type, guest_os, *, data=None, initial_public=None, has_existing_secret=False):
    validator = get_validator(check_type)
    if guest_os not in validator.supported_os:
        raise ConfigError("unsupported_guest_os")
    form_class = CONFIG_FORMS[check_type]
    return form_class(data=data, initial=initial_public or {}, has_existing_secret=has_existing_secret)
```

- [ ] **Step 3: Write failing instructor authorization, CRUD, preview-isolation, and history-redaction tests**

```python
def test_preview_uses_instructors_instance_not_template_or_student_instance(self):
    response = self.instructor_client.post(self.preview_url)
    self.assertEqual(response.status_code, 302)
    run = ValidationRun.objects.get(context="instructor_preview")
    self.assertEqual(run.lab_instance, self.instructor_instance)

def test_history_is_sanitized_and_filterable(self):
    response = self.instructor_client.get(self.history_url, {"outcome": "infrastructure_error"})
    self.assertContains(response, "agent_unavailable")
    self.assertNotContains(response, "guest stdout")
    self.assertNotContains(response, "flag{private}")
```

Add non-instructor denials, wrong-course IDs, soft-remove history preservation, reorder bounds, missing instructor instance, and no direct template execution.

- [ ] **Step 4: Add instructor views, routes, templates, and history selector**

Reuse the repository's existing instructor/course permission helper. CRUD views fetch Step through Course, restrict machine choices to the same Lab, and use POST for reorder/deactivate/preview. History uses `select_related`/`prefetch_related`, allow-listed filter values, pagination, and result snapshots only.

- [ ] **Step 5: Run instructor tests and commit**

Run: `python manage.py test app.tests.lab_checks.test_instructor_forms app.tests.lab_checks.test_instructor_views app.tests.lab_checks.test_history --settings=test_settings -v 2`

Expected: PASS.

```bash
git add app/lab_check_forms.py app/lab_check_views.py app/urls.py app/templates/labtech app/tests/lab_checks
git commit -m "feat: add instructor lab check management"
```

---

### Task 8: Deployment checks, operations documentation, and complete verification

**Files:**
- Create: `app/checks.py`
- Modify: `app/apps.py`
- Modify: `app/settings.py`
- Create: `docs/operations/qemu-lab-checks.md`
- Create: `app/tests/lab_checks/test_system_checks.py`
- Create: `app/tests/lab_checks/test_security_regressions.py`
- Modify: relevant existing lab cleanup regression tests if fixture setup requires `guest_os`.

**Interfaces:**
- Consumes: all prior tasks.
- Produces Django deployment checks `labchecks.E001` for a missing/invalid secret key, `labchecks.E002` for duplicate registry IDs, and `labchecks.E003` for stored active checks whose type is no longer registered.
- Produces operator documentation with QEMU-agent prerequisites and safe troubleshooting.

- [ ] **Step 1: Write failing deployment-check and end-to-end security regression tests**

```python
@override_settings(LAB_CHECK_SECRET_KEY="")
def test_missing_key_is_deployment_error_when_secret_checks_exist(self):
    self.make_file_content_check()
    ids = {error.id for error in run_checks(tags=[Tags.security])}
    self.assertIn("labchecks.E001", ids)

def test_hostile_catalog_inputs_never_change_command_or_leak(self):
    hostile = ["; rm -rf /", "$(id)", "`whoami`", "'\"; Write-Host pwned", "line\nnext"]
    for value in hostile:
        with self.subTest(value=value):
            self.assert_rejected_or_data_only(value)
            self.assertNotIn(value, self.captured_logs())
```

Add a full flow test: instructor creates and previews a check, student fails then passes it, finish revalidates, and exactly one cleanup job is queued. Add a separate infrastructure flow proving cleanup is not queued.

- [ ] **Step 2: Implement system checks and settings parsing**

Register checks from `AppConfig.ready()` without performing network I/O. In `app/settings.py`, read `LAB_CHECK_SECRET_KEY` from the environment and expose numeric limits with the spec defaults. The checks must avoid decrypting every secret; validate key shape and decrypt one existing token only when present.

- [ ] **Step 3: Write operator documentation with exact prerequisites and failure meanings**

Document enabling and verifying the QEMU guest agent for Linux and Windows templates, configuring `LabMachine.guest_os`, setting and backing up `LAB_CHECK_SECRET_KEY`, the 10/5/45/64-KiB/60 defaults, why templates are never preview targets, safe error-code meanings, and how to distinguish student failure from infrastructure trouble. State explicitly that arbitrary commands and gradebook scoring are unsupported.

- [ ] **Step 4: Run focused security and end-to-end tests**

Run: `python manage.py test app.tests.lab_checks --settings=test_settings -v 2`

Expected: all lab-check tests PASS with zero failures and zero errors.

- [ ] **Step 5: Run the complete Django and static verification suite**

Run: `python manage.py test --settings=test_settings -v 2`

Expected: all tests PASS.

Run: `python manage.py check`

Expected: no new errors; the repository's existing CKEditor warning may remain.

Run: `python manage.py makemigrations --check --dry-run`

Expected: `No changes detected`.

Run: `python -m compileall -q app`

Expected: exit code 0.

- [ ] **Step 6: Review the diff against the spec and commit final integration**

Confirm every active check is required, finish always revalidates, infrastructure cannot become fail, history is sanitized, preview uses only the instructor instance, no-check labs are unchanged, and no arbitrary command input exists.

```bash
git add app docs/operations/qemu-lab-checks.md requirements.txt test_settings.py
git commit -m "docs: complete QEMU lab check rollout"
```

- [ ] **Step 7: Prepare review evidence**

Record the focused/full test counts, Django check output, migration check output, compile result, migration number, new settings, and manual rollout steps in the pull-request description. Do not open or merge a pull request until the human partner has reviewed the completed branch.

