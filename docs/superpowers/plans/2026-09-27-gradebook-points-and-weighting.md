# Gradebook Points and Category Weighting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every course a consistent instructor/student/CSV gradebook with per-item points and optional activity-type weights.

**Architecture:** Persist course and item grading policy separately from activity attempts. A shared gradebook service builds one read-only roster snapshot from batched course activity data. Instructor/student views and CSV render that snapshot; authoring and copy/import operations use validated policy helpers.

**Tech Stack:** Django ORM, MariaDB in production, SQLite for repository tests, Django templates/forms, Python `Decimal`, Python `csv`.

**Spec:** `docs/superpowers/specs/2026-09-27-gradebook-points-and-weighting-design.md`

## Global Constraints

- Activity categories are exactly: `textpage`, `video`, `audio`, `quiz`, `lab`, `hotspotactivity`, `draganddropactivity`, `codingactivity`, `scenarioactivity`, `flashcarddeck`, `filesubmissionactivity`.
- Default mode is `points`; weighted mode requires `100.00` total across active, positive-point categories; included items must have positive points. Values use `Decimal` with at most two fractional digits.
- Existing submissions/completions/grades stay intact; a missing grading-policy row derives safe defaults without writing during grade reads.
- Available, included unattempted work counts as zero; pending file grades have no assessed denominator and mark the grade Provisional. A course with no assessed items displays N/A.
- Content released before `as_of` remains included after `due_date` or `available_until`; future release and unpublished quiz/lab drafts remain visible but outside the denominator.
- All eleven activity types appear, including completion-only items; the existing `Grade` model's percent scores and attempts are not rewritten.
- Only the course instructor or a superuser sees/edits the instructor roster, setup, or CSV. Student grade pages remain enrollment scoped.
- Course copy and backup/import transfer grading setup with remapped content IDs; they never transfer student submissions through grading-policy copy.
- Test command throughout: `python manage.py test <test-label> --settings=app.test_settings` from repo root; no MariaDB/Redis needed. Production dependency runtime is Python 3.12 or 3.13.

## Review Focus

1. A submitted but ungraded file must show Pending, with no zero denominator; cover in Task 3 scoring and Task 5 export tests.
2. A course where all work is pending or excluded must show N/A and a provisional marker where appropriate; cover in Task 3 calculation tests.
3. Old quizzes with missing/zero question totals, and files with zero `max_score`, must not divide by zero; cover in Task 2 normalization tests.
4. An item or policy pointing into another course must be rejected, including imported IDs reused across courses; cover in Task 1 validation and Task 6 import tests.
5. Malicious spreadsheet formula prefixes hidden behind whitespace or control characters in user-provided names and item titles must export as inert text; cover in Task 5 CSV tests.

## File Map

- `app/gradebook_models.py`: policy tables and validation; import models at the bottom of `app/models.py`, consistent with `app/lab_check_models.py`.
- `app/migrations/0012_gradebook_policy.py`: policy schema, no destructive data migration.
- `app/gradebook.py`: supported content registry, default item policy, batched score loading, `Decimal` aggregation, dataclass snapshot contract.
- `app/gradebook_forms.py`: instructor policy editing and category-sum validation.
- `app/gradebook_views.py`: instructor roster, student page, setup, CSV; authorization and view rendering only.
- `app/gradebook_export.py`: CSV header/value formatting and untrusted-text neutralization.
- Existing templates: `app/templates/labtech/instructor_gradebook.html`, `app/templates/labtech/my_course_grades.html`; new `app/templates/labtech/gradebook_setup.html`.
- Existing integration: `app/urls.py`, `app/views.py`, `app/forms.py`, `app/course_importer.py`, `.github/workflows/audio-content-tests.yml`.
- Tests: `app/test_gradebook_policy.py`, `app/test_gradebook_scoring.py`, `app/test_gradebook_views.py`, `app/test_gradebook_export.py`, `app/test_gradebook_copy.py`.

### Task 1: Persist and validate grading policy

**Files:** Create `app/gradebook_models.py`, `app/migrations/0012_gradebook_policy.py`, `app/test_gradebook_policy.py`; modify `app/models.py` bottom.

**Interfaces:** Produce `CourseGradingPolicy(course, mode)`, `CourseCategoryWeight(course, category_key, weight)`, `GradebookItemPolicy(course, content_type, object_id, included_in_grade, points_possible)`, and `save_grading_policy(course: Course, mode: str, weights: dict[str, Decimal], items: dict[tuple[str, int], tuple[bool, Decimal]]) -> None` in `app/gradebook_models.py`. Reject cross-course item references and nonfinite or >2-decimal inputs. Policy saves lock the course and validate all active category weights atomically.

- [ ] **Step 1: Add failing database/validation tests** to `app/test_gradebook_policy.py`: `test_course_without_policy_defaults_to_points`, `test_rejects_cross_course_and_invalid_point_values`, `test_weight_sum_and_zero_point_inclusion_rejected_atomically`, `test_item_policy_unique_per_content_item`. Assert `Decimal('100.00')` accepted, `Decimal('99.99')`, negative, `Decimal('1.001')`, and cross-course item rejected without persisting partial changes.
- [ ] **Step 2: Run** `python manage.py test app.test_gradebook_policy --settings=app.test_settings`; expect failures for absent policy models/service.
- [ ] **Step 3: Implement** the three models and atomic `save_grading_policy`; create and commit migration `0012_gradebook_policy.py`. A missing policy is represented by a read-only default, not inserted on gradebook GET.
- [ ] **Step 4: Run** `python manage.py test app.test_gradebook_policy --settings=app.test_settings` and `python manage.py makemigrations --check --dry-run --settings=app.test_settings`; expect passes and “No changes detected”.
- [ ] **Step 5: Commit** model, migration, and tests (`feat: store per-course and per-item gradebook policy`).

### Task 2: Inventory every activity and normalize its score

**Files:** Create `app/gradebook.py`, `app/test_gradebook_scoring.py`; consume Task 1 models.

**Interfaces:** `ACTIVITY_TYPES: tuple[tuple[str, type[Model]], ...]` in spec order; `default_item_policy(item: Model) -> tuple[bool, Decimal]`; `load_course_items(course: Course, *, as_of: datetime) -> list[GradebookItem]`; `load_student_item_results(course: Course, students: Sequence[User], items: Sequence[GradebookItem]) -> dict[int, dict[tuple[str, int], ItemResult]]`. `GradebookItem` contains `category_key`, `item`, `included`, `points_possible`, `released`; `ItemResult` contains `status`, `earned`, `possible`, `score_percent`, `complete`. Status is one of `not_yet_included`, `completion_only`, `not_started`, `in_progress`, `submitted`, `pending`, `graded`.

- [ ] **Step 1: Add failing fixture tests** `test_all_eleven_activity_types_in_inventory`, `test_completion_items_earn_configured_points`, `test_latest_attempt_and_failed_submission_are_distinct_from_missing_work`, `test_pending_file_has_no_denominator`, `test_zero_question_quiz_and_zero_max_file_do_not_divide`, `test_closed_availability_retains_grade`, `test_future_and_unpublished_are_excluded`, `test_orphan_completion_and_cross_course_grade_do_not_count`. Create one real instance per supported model, rather than mocking model classes; use factories local to test module.
- [ ] **Step 2: Run** `python manage.py test app.test_gradebook_scoring --settings=app.test_settings`; expect inventory/result tests to fail because the service does not exist.
- [ ] **Step 3: Implement** registry, default points (100 for previously graded categories, positive quiz question sum/file `max_score` when available, zero/ungraded for completion-only categories), course-owned inventory, and batched score/completion loading. Use existing latest-attempt/step-answer semantics. For a lab with guest-agent checks, let existing lab completion govern completion status; do not create check-level grade columns.
- [ ] **Step 4: Run** `python manage.py test app.test_gradebook_scoring --settings=app.test_settings`; expect score/status tests to pass. Add an enrolled 10-student fixture and assert query count grows by no more than a small constant relative to 1 student, then run the test again.
- [ ] **Step 5: Commit** scoring reader and tests (`feat: normalize all course activity scores`).

### Task 3: Aggregate points, weighted categories, and completion

**Files:** Modify `app/gradebook.py`, `app/test_gradebook_scoring.py`.

**Interfaces:** `build_gradebook(course: Course, students: Sequence[User] | None = None, *, as_of: datetime | None = None) -> GradebookSnapshot`; `GradebookSnapshot.items`, `.students`, `.chapters`, `.as_of`, `.mode`, `.weights`; each `StudentGradeRow` exposes `.item_results[(category_key, item_id)]`, `.category_results[category_key]`, `.course_grade: Decimal | None`, `.earned_points`, `.possible_points`, `.course_completion`, `.chapter_completion`, `.provisional`. All views/export use this contract; reading it never writes.

- [ ] **Step 1: Add failing calculation tests**: with a completed 5-point and uncompleted 15-point text page plus a 60%-scored 100-point quiz, assert points `65/120 = 54.166...%` and weighted Text Pages `20%` / Quizzes `80%` yields `53%`. Test 0 for unattempted, weighted denominator proportionality, excluded/zero-point category, only pending category N/A, one pending weighted category with effective reweighting and Provisional, and completion remaining independent of points.
- [ ] **Step 2: Run** `python manage.py test app.test_gradebook_scoring --settings=app.test_settings`; expect new aggregation tests to fail.
- [ ] **Step 3: Implement** read-only `Decimal` aggregation; avoid rounding until presentation and use the single `as_of` for the full snapshot. Derive default points policy without writes; assess released missing work as zero; exclude pending. Use stable item order by chapter order, item order, category key, ID.
- [ ] **Step 4: Run** `python manage.py test app.test_gradebook_scoring --settings=app.test_settings` and `python manage.py makemigrations --check --dry-run --settings=app.test_settings`; expect passes/no model drift.
- [ ] **Step 5: Commit** aggregation and tests (`feat: calculate points and weighted course grades`).

### Task 4: Instructor setup and synchronized student/instructor screens

**Files:** Create `app/gradebook_forms.py`, `app/gradebook_views.py`, `app/templates/labtech/gradebook_setup.html`, `app/test_gradebook_views.py`; modify `app/urls.py`, `app/views.py`, `app/templates/labtech/instructor_gradebook.html`, `app/templates/labtech/my_course_grades.html`, `app/forms.py`, `.github/workflows/audio-content-tests.yml`.

**Interfaces:** `instructor_gradebook_view(request, course_id)`, `my_course_grades_view(request, course_id)`, `gradebook_setup_view(request, course_id)` in `app/gradebook_views.py`. Keep existing URL names `instructor_gradebook` and `my_course_grades`; add `gradebook_setup`. Form `GradebookSetupForm(course, data=None)` validates a complete atomic policy payload for all current course items and returns typed `mode`, `weights`, `items` consumed by Task 1 `save_grading_policy`. Export URL stays reserved for Task 5.

- [ ] **Step 1: Add failing client tests**: gradebook defaults to an enrolled-student roster; selecting another course's student returns 404; another course's instructor gets 403/redirect; student sees own points/percent/status and cannot open setup; setting a 5-point Text Page then completing it changes instructor/student grades identically; weighted POST totals `99.99` and negative inputs return validation errors with no partial writes; pending file links to existing grading flow; `FileSubmissionActivityForm` rejects changing `max_score` after graded submissions. Verify zero-student/zero-item screens render.
- [ ] **Step 2: Run** `python manage.py test app.test_gradebook_views --settings=app.test_settings`; expect new view/UI tests to fail.
- [ ] **Step 3: Implement** focused forms/views/templates backed only by `build_gradebook`, instructor search/filter and sticky roster column, categorical totals, item points/status, and read-only student explanation. Route existing URL names to new views. Keep the old `_get_gradebook_data` helper until Task 5 moves the existing export; remove the duplicated helpers only after their last caller is gone. Retire unrouted `course_gradebook_view` or delegate it to the service if callers are found. Protect file `max_score` in the existing form.
- [ ] **Step 4: Run** `python manage.py test app.test_gradebook_views app.test_gradebook_scoring app.test_audio --settings=app.test_settings`; expect passes. Update CI test invocation to include gradebook modules, and run `python manage.py check --settings=app.test_settings`.
- [ ] **Step 5: Commit** screens, setup, routes, and tests (`feat: unify instructor and student gradebook views`).

### Task 5: Fix and verify CSV export

**Files:** Create `app/gradebook_export.py`, `app/test_gradebook_export.py`; modify `app/gradebook_views.py`, `app/urls.py`, `app/views.py`, `app/templates/labtech/instructor_gradebook.html`.

**Interfaces:** `instructor_gradebook_export_csv(request, course_id) -> HttpResponse` routes existing name `instructor_gradebook_export_csv`, calls Task 3 `build_gradebook`; `render_gradebook_csv(snapshot: GradebookSnapshot) -> HttpResponse` in `app/gradebook_export.py`. Spreadsheet text sanitizer `csv_safe_text(value: str) -> str` runs on all untrusted text, including header components; numeric cells stay numeric.

- [ ] **Step 1: Write failing regression test using the current export**: one enrolled student with one Text Page triggers the existing `KeyError('overall_completion')`; test expected status 200 and exact header/value widths. Add tests for points/weighted numeric agreement with roster/student, scalar item fields without dict repr, unattempted zero, Pending/N/A, duplicate titles qualified by type and ID, zero enrollments (headers only), stranger and other instructor forbidden, and strings beginning with whitespace/control then `=`, `+`, `-`, `@` neutralized in every text field.
- [ ] **Step 2: Run** `python manage.py test app.test_gradebook_export --settings=app.test_settings`; expect explicit export failures, including the KeyError.
- [ ] **Step 3: Implement** CSV writer on shared snapshot with Student Name, Email, Course Grade %, Earned Points, Possible Points, Grade Status, Course Completion %, then category totals/weights, chapter completion and per-item status/earned/possible/percent columns. Preserve safe filename/`text/csv`. Enforce course-level permissions and constant column count; do not stringify dictionaries. Handle CSV escaping plus Excel formula injection separately. Remove the now-unused `_get_gradebook_data` and `_get_single_student_grade_data` helpers from `app/views.py` only after both routes are using the shared service.
- [ ] **Step 4: Run** `python manage.py test app.test_gradebook_export app.test_gradebook_views --settings=app.test_settings`; expect passes and round-trip `csv.reader` equality of header and row lengths.
- [ ] **Step 5: Commit** export and tests (`fix: export accurate and safe gradebook CSV`).

### Task 6: Preserve configuration across copy and backup/import

**Files:** Modify `app/views.py` (`copy_content_item`, `clone_course_view`), `app/course_importer.py`, `app/gradebook_models.py`; create `app/test_gradebook_copy.py`.

**Interfaces:** `copy_course_grading_policy(source: Course, target: Course, item_map: dict[tuple[str, int], Model]) -> None` in `app/gradebook_models.py`. Call once after content creation inside clone, imported course recreation, and backup restoration transactions. Package and backup dictionaries use `grading_policy: {mode, weights, items: [{type, source_id, included, points}]}`; items are applied only after new IDs exist, and older packages without the key use points defaults.

- [ ] **Step 1: Write failing clone/package/backup tests** with a weighted course, edited text page and File Submission points, and real student attempt/submission records. Assert copied/imported/restored content has distinct IDs and matching policies, no copied student submissions, no policy bound to old content; legacy package/backup without grading key imports; tampered foreign item ID fails safely without partial policy writes. Include unassigned content and File Submission definition in the package/backup fixtures.
- [ ] **Step 2: Run** `python manage.py test app.test_gradebook_copy --settings=app.test_settings`; expect policy and File Submission round trips to fail before implementation.
- [ ] **Step 3: Implement** item-ID mapping after creating content, include missing File Submission activity definitions (not uploaded student files) in clone/package/backup flows, and extend backup to preserve unassigned graded content where currently omitted. Validate import data and apply policy within existing transactions; retain previous file-storage rollback behavior. Existing `CourseBackup` JSON payload accepts the new optional grading key without a schema migration.
- [ ] **Step 4: Run** `python manage.py test app.test_gradebook_copy app.test_audio app.test_gradebook_scoring --settings=app.test_settings`; expect passes for new and existing content copy workflows.
- [ ] **Step 5: Commit** copy/import integration and tests (`feat: retain grading setup through course copies and backups`).

## Final Verification

- [ ] Run `python manage.py test app.test_gradebook_policy app.test_gradebook_scoring app.test_gradebook_views app.test_gradebook_export app.test_gradebook_copy app.test_audio app.test_lab_checks app.test_lab_cleanup --settings=app.test_settings`; inspect failing test names if any and fix before claiming readiness.
- [ ] Run `python manage.py check --settings=app.test_settings` and `python manage.py makemigrations --check --dry-run --settings=app.test_settings`.
- [ ] Manually trace one unattempted item, completed text page, 60%-scored quiz, pending file, released but closed item, and malicious CSV title through roster, individual student, student page, and parsed CSV. Ensure identical results at a frozen `as_of`.
- [ ] Review migration on a copy of existing data, verify no `Grade`/attempt/completion rewrite, and confirm migrations work on MariaDB-backed deployment before merge.

## Execution Handoff

The user approved implementation. The feature is implemented on this branch, and 99 local SQLite tests passed across gradebook, audio, lab cleanup, and lab checks. Django system and migration checks pass with existing dependency warnings. GitHub CI and a MariaDB-backed deployment migration remain to be verified before merging.
