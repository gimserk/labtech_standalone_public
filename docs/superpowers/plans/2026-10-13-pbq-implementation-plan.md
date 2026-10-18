# PBQ Activity Implementation Plan

> For implementation: use the executing-plans workflow and complete the checkboxes task by task. This document is a proposed design and implementation plan, not authorization to deploy.

**Goal:** Add a first-class Performance-Based Question (PBQ) chapter activity to LabTech Standalone, combining an instructor-written scenario, supporting image/text artifacts, and mixed answer types.

**Architecture:** Introduce a dedicated PBQ model family and focused authoring, attempt, grading, and artifact services. Integrate with the existing chapter navigation, completion records, gradebook, and course transfer mechanisms. Keep existing quizzes and their question models unchanged.

**Tech stack:** Existing Django application, Django templates/forms, CKEditor integration, database transactions, and Django file storage. Use existing installed image and HTML-processing libraries where suitable; verify dependencies before adding any.

**Design specification:** Sections 1–6 of this document. Requirements directly requested by the user are separated from recommended defaults.

**Repository baseline inspected:** `gimserk/labtech_standalone`, `main`, commit `e5adcea74fb09f8882295cc0a41d88b52029b84d`. Recheck the branch, repository instructions, and migration head before implementation. Current source was inspected; no application changes or runtime tests have been performed for this planning task.

## 1. Requested outcome and proposed defaults

The instructor creates a chapter activity labeled **PBQ**, writes a summarative scenario in CKEditor, attaches supporting images or text files, and authors questions using Multiple Choice, Fill in the Blank, Short Answer, and Dropdown responses.

A PBQ contains ordered questions. A question can contain one or more independently labeled answer fields, each with its own type and points. This supports both a simple multiple-choice question and a multipart question containing a dropdown, a blank, and an explanation.

### Recommended behavior to review

| Decision | Proposed initial behavior |
|---|---|
| Multiple choice | Radio buttons; exactly one correct option. Multiple-select is outside the initial scope. |
| Dropdown | One selection from instructor-defined options; a blank initial placeholder is not a scored option. |
| Fill in the blank | One text input per answer field; instructors can add several fields to a question. Accept a list of equivalent correct answers. |
| Short answer | Multiline plain text, manually graded by the instructor with partial credit and feedback. No AI grading. |
| Points | Positive whole-number maximum per answer field; manual awarded points allow two decimal places. PBQ maximum is the sum of its fields. |
| Attempts | One submission by default; instructor may set a positive maximum or `0` for unlimited. Resume an existing draft without consuming another attempt. |
| Attempt used for grade | Latest submitted attempt. A newer draft does not replace an existing submitted grade; a newer pending submission makes the grade pending. |
| Completion | A successful final submission completes the activity, even when instructor grading is pending. Completion and grade are separate. |
| Correct-answer release | Never by default; optional after grading, after due date, or after availability ends. Missing release dates keep answers hidden. |
| Artifacts | PNG, JPEG, WebP, and UTF-8 `.txt`, `.log`, and `.csv`; text is displayed as literal text. |
| Upload limits | 10 MiB per artifact, 20 artifacts and 50 MiB total per PBQ; configurable deployment settings. Images also limited to 25 million decoded pixels. |
| Editing after use | Freeze scenario, artifacts, questions, options, and scoring keys after the first student attempt starts. Duplicate the PBQ to revise it. Scheduling, title, and chapter placement remain editable. |

These are planning assumptions, not claims that the user has already approved each choice. The requested feature can be implemented from this plan once these defaults are accepted or adjusted.

## 2. Instructor and student experience

### Instructor authoring

1. Select **Add PBQ** within a chapter. Preselect that chapter and assign the next content order using the existing course conventions.
2. Enter title, CKEditor scenario, dates, attempt limit, and answer-release policy. Save as an unpublished draft.
3. Add ordered artifacts with a title, optional caption, and required image alternative text. Provide image preview/zoom and escaped text preview/download.
4. Add ordered questions with CKEditor prompts. Within each question, add one or more labeled answer fields. Each field exposes only the configuration for its selected type.
5. Preview the student experience without recording a real attempt or affecting grades.
6. Publish after validation. Offer edit, duplicate, and delete actions consistent with other chapter activities; prohibit destructive deletion of a PBQ with student attempts.

Publishing requires a nonempty scenario, at least one question and answer field, valid scoring configuration, and a positive total maximum. Artifacts are optional. MC/dropdown fields need at least two nonempty options and exactly one correct option. Fill-in fields need at least one nonempty accepted answer. Short-answer fields need private marking guidance or a model answer for the grader.

Allow blank chapter assignment to preserve the existing unassigned-content workflow, while the primary entry point is the chapter menu. Validate course/chapter ownership on both form and service paths.

### Student experience

Open the PBQ from chapter navigation; read the scenario, inspect artifacts, and answer questions in order. Use a two-column scenario/artifact and response layout on wide screens, stacked on mobile, with keyboard-accessible controls and the existing appearance themes.

Provide **Save progress**, **Resume**, and a distinct **Submit PBQ** action. Initial scope uses explicit saving, with a warning for unsaved navigation; background autosave is not required. Drafts may contain unanswered fields. Final submission requires every answer field to be answered, with an error summary and focus moved to the first invalid field.

After submission, lock student responses. Display submitted responses, submission time, and either final score or **Pending grading**. Withhold correct options, accepted answer lists, and private marking guidance until permitted. Treat instructor feedback as deliberately student-visible once grading is finalized; label that clearly in the grading interface.

### Worked example

**PBQ: Investigate a suspected account compromise.** The story describes suspicious sign-ins. Artifacts include a network diagram, authentication log, and incident notes.

| Question | Answer field | Type | Maximum |
|---|---|---|---:|
| Identify the activity | Most likely attack | Multiple choice | 2 |
| Identify evidence | Suspicious source IP | Fill in the blank | 2 |
| Recommend a response | First containment action | Dropdown | 2 |
| Recommend a response | Explain why that action fits the evidence | Short answer | 4 |

If automated fields earn 4/6 and the instructor awards 3/4, the final score is 7/10. If the gradebook item is configured for 20 points, that contributes 14/20. Before manual grading, the PBQ is complete but its grade is pending.

## 3. Data design and scoring rules

Use model names and reverse relations consistently across every integration:

| Model | Responsibility and key fields |
|---|---|
| `PBQActivity` | Extends `ContentTiming`; `course`, nullable `chapter`, `title`, `scenario` using the existing CKEditor rich-text approach, `order`, `is_published`, `max_attempts`, `show_answers_after`, `content_locked_at`, timestamps. Reverse name `pbq_activities` on course/chapter; content-type key `pbqactivity`. |
| `PBQArtifact` | Activity FK; private stored `file`, title, caption, alt text, original filename, validated MIME, size, order. Generated storage name independent of user filename. |
| `PBQQuestion` | Activity FK, rich-text `prompt`, order; related name `questions`. |
| `PBQAnswerField` | Question FK, label, order, `answer_type` (`mcq`, `fill_blank`, `short_answer`, `dropdown`), maximum points, case-sensitivity setting, private marking guidance. Related name `answer_fields`. |
| `PBQChoice` | Answer-field FK, plain text, order, correctness flag; related name `choices`. |
| `PBQAcceptedAnswer` | Fill-in field FK, accepted text; related name `accepted_answers`. |
| `PBQAttempt` | Activity and user FKs, attempt number, state (`draft`, `submitted`, `graded`), start/submission/grading times, frozen maximum, earned points when final, optimistic draft revision counter. |
| `PBQResponse` | Attempt and answer-field FKs, optional selected choice, text response, automatic score, final awarded points, student-visible feedback, grader and grading time. Unique `(attempt, answer_field)`. |
| `PBQGradeEvent` | Append-only response/attempt grading history: actor, time, previous and new score, previous and new feedback, and required reason for a finalized-grade correction. |

Register PBQ models through `app/models.py` before gradebook-model initialization, following the existing separated-model pattern. Use string model references where needed to avoid circular imports. Use MariaDB-compatible constraints; do not rely on partial unique constraints to enforce one draft.

**Automatic scoring:** MCQ/dropdown compare the submitted option with the server-side key, after validating that the option belongs to this field. Fill-in uses Unicode NFC normalization and trimming of outer whitespace, plus Unicode case folding unless case-sensitive matching is enabled. Preserve internal whitespace and punctuation. Compare with normalized accepted alternatives; do not use fuzzy matching, regex, or substring matching. Each automatically graded field receives full points or zero.

**Manual scoring:** Permit a numeric score from zero through that field's maximum, including partial credit. Reject negative values, excessive precision, nonfinite values, and over-maximum values. Save unfinished instructor grading as a draft; finalize the attempt only when every short-answer field has a valid score. A deliberate correction to a finalized grade records grader/time and an old/new score audit event.

**Submission integrity:** Starting, saving, submitting, and grading are service operations inside transactions. Lock the relevant activity while reserving attempt numbers or freezing content, then the attempt as needed, in a consistent order. Enforce one resumable draft per user/activity in the service and a unique `(activity, user, attempt_number)` constraint. Concurrent starts must resolve to the same draft. Reject stale draft saves using the revision counter. Duplicate final submissions return the original result without consuming another attempt or duplicating completion. Revalidate enrollment, publication, availability, attempt limits, ownership, and answer membership on every write.

When no manual fields exist, a valid final submission transitions directly to `graded`; otherwise it transitions to `submitted` and remains pending. Due dates label work as late; `available_until` is the submission cutoff. Previously saved drafts remain stored if the cutoff passes. Result access remains available to the enrolled owner after cutoff, but answers follow the release rule. Archived courses are read-only.

## 4. Integration and file safety

### Repository findings

The current `Question` is directly tied to `Quiz` and supports MCQ/TF/SA. PBQ should not overload this model. The existing `ContentCompletion` and gradebook provide suitable integration points. Gradebook categories, chapter lists, copy routines, and package schemas contain explicit activity lists, so adding only a model and template would leave the feature incomplete.

The current gradebook already represents pending file submissions separately and marks totals provisional. Extend that pattern for PBQs: released unattempted graded PBQs count as zero; drafts count as in progress with zero until submission; pending submitted PBQs are excluded from assessed numerator/denominator and flagged provisional; graded PBQs use their earned/maximum ratio. Future/unpublished PBQs stay excluded. Keep completion-only item policies working.

Add `pbqactivity` to category keys and labels. In points mode use summed answer-field points as the default. In weighted courses default the new PBQ category to zero and exclude new PBQs until an instructor configures inclusion/weight, preserving existing weight totals. Do not silently redistribute weights.

### Artifact and rich-text handling

Store PBQ assets outside publicly served `MEDIA_ROOT`, using a configurable private Django storage location. Deliver preview/download through authenticated course-scoped views; never expose raw storage paths or public media URLs. Check enrollment, published state, and availability for active work; allow an owner of a submitted attempt to review its associated artifacts after cutoff while enrollment remains valid. Instructors use course-management permissions.

Validate file extensions, decoded content, MIME consistency, actual size, image dimensions, and text encoding. Reject SVG/HTML/executable files, malformed images, binary content masquerading as text, and invalid UTF-8. Text previews must escape markup and limit rendering to 100 KiB; downloads may include the full validated file. Apply `nosniff`, safe disposition filenames, and private cache controls.

Use the existing CKEditor widget/assets for scenario and question prompts, with a PBQ-scoped toolbar/configuration. Disable its generic public upload/browser endpoints for PBQ content. Insert uploaded PBQ images via the protected artifact picker. Sanitize rich text server-side through a documented allowlist preserving paragraphs, lists, tables, emphasis, code blocks, and safe links; reject scripts, event handlers, unsafe URL schemes, arbitrary embeds, and foreign PBQ asset references. Enforce these rules for forms and imports, not just browser input.

Use artifact identifiers that can be remapped in copied/exported rich text. Treat uploaded bytes and DB rows as separate resources: clean up newly written files after rollback and delete old files only after a successful commit and only when no retained object references them.

### Course movement and history

PBQs must survive whole-course cloning, selected-content copying, course ZIP export/import, and content backup/restore. Copy owned artifacts to independent storage keys, remap questions/fields/options and embedded artifact references, and carry item grading policies. Ordinary copies omit students, attempts, and grades; copies start with unlocked PBQ content inside the destination's existing publication workflow.

Extend `app/course_packages.py` with an explicit nested PBQ section and private-file collection/validation. A PBQ-containing package uses format version 2; continue accepting historical unversioned and version-1 packages. Continue writing version 1 for packages without PBQs where their schema is unchanged. Older clients will require an upgrade to import PBQ packages; do not claim backward readability by old clients.

When the existing export UI requests enrollments and grades, explicitly serialize PBQ attempts, responses, grading state, and ID mappings. Restore only for resolved users, report unresolved users, and recreate completion only for valid submitted attempts. Do not infer that the current generic export already preserves these details.

Content-only backups include PBQ definitions and artifact bytes, with bounded validation on restore, but omit attempts. Protect existing PBQ attempt history: block whole-course content restore/overwrite, activity deletion, or chapter cascade deletion that would erase PBQ attempts. Offer restore/import into a new course or moving the PBQ before chapter deletion. Explicit whole-course deletion remains subject to the application's existing destructive-action flow.

Keep PBQ correct answers and marking guidance out of AI tutor material extraction, student JSON, HTML attributes, and preview payloads. Initial scope excludes PBQ assessment content from tutor retrieval entirely.

## 5. File map

New files proposed:

| Path | Responsibility |
|---|---|
| `app/pbq_models.py` | PBQ models and DB constraints. |
| `app/pbq_forms.py` | Instructor forms/formsets and student response validation. |
| `app/pbq_services.py` | Draft lifecycle, publication, content locking, permissions, submission, and grading transactions. |
| `app/pbq_scoring.py` | Pure normalization and automatic scoring functions. |
| `app/pbq_artifacts.py` | Private storage, upload validation, safe rich text, and file lifecycle. |
| `app/pbq_transfer.py` | Nested PBQ serialization, restoration, copying, and artifact-reference remapping. |
| `app/pbq_views.py`, `app/pbq_urls.py` | Instructor, student, grading, preview, and protected-file endpoints. |
| `app/templates/labtech/pbq/` | `form.html`, `questions.html`, `take.html`, `result.html`, `grade.html`, and shared field/artifact partials. |
| `app/static/labtech/pbq.js` | Authoring controls, artifact viewer, draft revision handling, and unsaved-change warning; no answer keys. |
| `app/test_pbq_*.py` | Models, authoring, artifacts, attempts, scoring, gradebook, transfer, and access tests. |
| `docs/operations/pbq-activities.md` | Instructor/admin instructions, file limits, grading, and deployment notes. |

Modify `app/models.py`, `app/forms.py` (ordering helper), `app/settings.py`, `app/urls.py`, `app/views.py` (integration adapters only), `app/gradebook_models.py`, `app/gradebook.py`, `app/course_packages.py`, and `app/course_importer.py`. Review `app/gradebook_export.py`, `app/gradebook_views.py`, `app/tutor_materials.py`, `app/templatetags/course_extras.py`, and achievement commands for explicit type lists.

Template integration includes `manage_course_content.html`, `partials/content_item_actions.html`, `partials/course_main_content.html`, `partials/sidebar.html`, `instructor_gradebook.html`, and the selected-content import interface. Add migrations from the actual current leaf; do not hard-code a migration number from this planning snapshot.

## 6. Scope boundaries and review focus

Initial scope excludes drag-and-drop simulations, terminal/VM interaction, learner-uploaded evidence, multiselect scoring, AI grading, regex answers, randomized question banks, timed examination/proctoring, and a general activity-plugin redesign. CKEditor migration or unrelated quiz fixes are separate work.

Five high-risk conditions must be exercised by the tasks below:

1. Two tabs saving/submitting concurrently must not overwrite a newer draft or create duplicate attempts.
2. Foreign course/question/option IDs and guessed asset URLs must not grant access or change another learner's work.
3. Editing or deleting content after attempts exist must preserve the meaning and recoverability of grades.
4. A pending manual response must not become an accidental zero or inflate course completion/grade calculations.
5. Copy/import failure after private files are written must leave neither partial course data nor leaked files.

## 7. Implementation sequence

Each task follows the cycle: add the listed failing tests, run them, implement the smallest passing change, rerun the targeted tests, inspect the diff, and commit a coherent change. Tests below are proposed test modules, not existing or already passing tests.

### Task 1 — Models and publish validation

**Files:** Create `app/pbq_models.py`, `app/pbq_services.py`, `app/test_pbq_models.py`; modify `app/models.py`; generate migrations.

**Interfaces:** `validate_pbq(activity) -> None` raises `ValidationError`; `publish_pbq(*, actor, activity) -> PBQActivity` validates and publishes under a lock. Introduce `can_manage_pbq(user, activity) -> bool` and `can_attempt_pbq(user, activity, at) -> bool` for consistent access decisions.

- [ ] Add tests proving all four field types persist; cross-course chapters fail; zero/negative maxima fail; empty stories/questions fail publication; MC/dropdown keys require exactly one correct option; normalized fill-in alternatives are nonempty and deduplicated; publishing an already-used definition cannot alter it.
- [ ] Run `python manage.py test app.test_pbq_models --settings=app.test_settings` and confirm the new cases fail for the missing feature.
- [ ] Implement schema, model registration, validated authoring services, and unique constraints. Confirm model loading has no circular import with gradebook initialization.
- [ ] Run that test module, `python manage.py check --settings=app.test_settings`, and `python manage.py makemigrations --check --dry-run --settings=app.test_settings` after generating migrations. Commit `feat: add PBQ models and publication validation`.

### Task 2 — Private artifacts and safe CKEditor content

**Files:** Create `app/pbq_artifacts.py`, `app/test_pbq_artifacts.py`; add artifact endpoints to `app/pbq_views.py`; modify settings.

**Interfaces:** `save_pbq_artifact(*, actor, activity, upload, metadata) -> PBQArtifact`; `sanitize_pbq_html(html, *, activity) -> str`; `deliver_pbq_artifact(request, course_id, activity_id, artifact_id, *, download=False) -> HttpResponse`.

- [ ] Test each allowed type, 10 MiB/file and 50 MiB/activity limits, 20-file limit, pixel limit, malformed images, disguised binary files, unsafe filenames/HTML, text escaping, preview truncation, unauthenticated and cross-course access, and direct-public-media denial.
- [ ] Implement private storage with generated keys, validated uploads, PBQ-scoped CKEditor asset insertion, sanitation, and transaction-aware cleanup. Verify the web server does not expose the private root.
- [ ] Run `python manage.py test app.test_pbq_artifacts --settings=app.test_settings`; verify private paths on a staging installation. Commit `feat: add protected PBQ artifacts`.

### Task 3 — Instructor builder and chapter integration

**Files:** Create `app/pbq_forms.py`, `app/pbq_urls.py`, authoring templates, JS, and `app/test_pbq_authoring.py`; modify views, URL inclusion, ordering helper, and chapter/content-action templates.

**Interfaces:** `PBQActivityForm(..., course=...)`; `PBQQuestionForm`; answer-field and choice formsets; scoped create/edit/preview/publish/duplicate endpoints. All write paths call shared services rather than bypassing validation.

- [ ] Test Add PBQ chapter preselection, question/field ordering, mixed fields within one question, foreign formset IDs, type changes clearing incompatible configuration before first use, draft preservation after errors, archived-course denial, and preview creating no attempt.
- [ ] Implement the builder and student preview. Integrate PBQ in manage-content lists, bulk date changes, content-order updates, and course content selection JSON.
- [ ] Test post-first-attempt content locking on every mutation endpoint and protected chapter/PBQ deletion, including crafted POSTs.
- [ ] Run `python manage.py test app.test_pbq_authoring app.test_content_repairs --settings=app.test_settings`; review keyboard operation, CKEditor assets, dark mode, and narrow-screen layout. Commit `feat: add PBQ instructor authoring`.

### Task 4 — Drafts, submissions, and automatic scoring

**Files:** Create `app/pbq_scoring.py`, `app/test_pbq_attempts.py`, `app/test_pbq_scoring.py`; extend services/views and student templates.

**Interfaces:** `start_pbq_attempt(*, user, activity) -> PBQAttempt`; `save_pbq_draft(*, user, attempt_id, responses, expected_revision) -> PBQAttempt`; `submit_pbq_attempt(*, user, attempt_id, responses, expected_revision) -> PBQAttempt`; `score_pbq_response(field, value) -> Decimal | None` (`None` means manual grading required).

- [ ] Test start/resume, one/unlimited attempt settings, concurrent starts, stale revision rejection, double-submit idempotency, forged option IDs, enrollment/date changes between GET and POST, required final answers, and isolation between students.
- [ ] Test normalization with case-sensitive and insensitive answers, Unicode-equivalent strings, outer whitespace, preserved internal whitespace, and exact-match rejection of near matches. Verify the worked example's automatic 4/6 score.
- [ ] Implement transactional lifecycle and server-only scoring; freeze definition at first start, create completion at submission, and avoid a completion write for draft/preview.
- [ ] Run `python manage.py test app.test_pbq_attempts app.test_pbq_scoring --settings=app.test_settings`; run the concurrency cases with `TransactionTestCase` against an isolated MariaDB test database because SQLite cannot prove row-lock behavior. Commit `feat: add PBQ attempts and scoring`.

### Task 5 — Instructor grading and result release

**Files:** Extend services/views; create grading/result templates and `app/test_pbq_grading.py`.

**Interfaces:** `save_pbq_grades(*, actor, attempt_id, grades, finalize=False) -> PBQAttempt`; `build_pbq_result(*, actor, attempt, at) -> dict`, returning an explicit safe field list rather than serializing models wholesale.

- [ ] Test pending state until all short-answer scores exist, partial credit, invalid numeric scores, instructor ownership, concurrent grading, correction audit records, and disclosure for never/after-grading/due-date/until-date policies including missing dates.
- [ ] Implement grading queue, per-field marking guidance, feedback, draft grading, finalization, and protected result pages. Assert no private key appears in initial student HTML, JSON, JS data, or tutor material.
- [ ] Run `python manage.py test app.test_pbq_grading app.test_ai_tutor --settings=app.test_settings`; verify the worked example finishes at 7/10. Commit `feat: add PBQ manual grading and results`.

### Task 6 — Gradebook, completion, and navigation

**Files:** Modify gradebook models/service/export/view adapters, course/detail/dashboard lists, relevant templates and completion/achievement inventory; create `app/test_pbq_gradebook.py`.

**Interfaces:** Existing `build_gradebook` remains authoritative; add a `pbqactivity` result branch using latest submitted attempt ordered by submission time and PK. Expose an authorized PBQ result/grading link without duplicating grade arithmetic in templates.

- [ ] Test points and weighted modes; unpublished/future exclusion; unattempted zero; completion-only policy; pending provisional totals; later drafts preserving the previous submitted result; retries selecting the latest submission; and 7/10 scaling to 14/20.
- [ ] Add PBQs to chapter/course completion denominators, navigation, student activity view, and course-certificate completion checks. Prevent manual “mark complete” bypass. Do not invoke the existing achievement helper from a context where its request dependency is undefined; add a narrow adapter or repair that call boundary with a test if needed.
- [ ] Test matching grades/status across instructor UI, student summaries, and CSV, plus bounded query growth for multiple students and PBQs.
- [ ] Run `python manage.py test app.test_pbq_gradebook app.test_gradebook_scoring app.test_gradebook_policy app.test_gradebook_export app.test_gradebook_views --settings=app.test_settings`. Commit `feat: integrate PBQs with course progress and gradebook`.

### Task 7 — Copy, packages, and backups

**Files:** Create `app/pbq_transfer.py`, `app/test_pbq_transfer.py`; modify `app/course_packages.py`, `app/course_importer.py`, and copy/clone/import/restore adapters in `app/views.py`.

**Interfaces:** `serialize_pbq(activity, *, include_artifact_bytes=False) -> dict`; `restore_pbq(payload, *, course, chapter, asset_source, written_files) -> PBQActivity`; `copy_pbq(activity, *, course, chapter, written_files) -> PBQActivity`. Return/retain nested ID maps for optional attempt restoration; define the maps once in the transfer module.

- [ ] Add round-trip tests for all four answer types, a multipart question, keys/guidance, private artifact bytes, embedded artifact references, dates/order, category/item policies, and optionally exported student grades.
- [ ] Test old v0/v1 packages, v2 PBQ packages, unsupported types, missing media, invalid nested IDs, malicious paths, oversized backup bytes, rollback after a file write, and copies remaining usable after the source is deleted.
- [ ] Test content-only backups preserve PBQ definitions/artifacts and omit attempts; reject restore/overwrite when it would erase PBQ attempts, including chapter cascades. Validate before mutating existing content.
- [ ] Integrate shared transfer logic in all existing pathways, including `copy_content_item`, `clone_course_view`, selected-content copying, `serialize_course`, `recreate_course`, `serialize_course_for_backup`, and `restore_course_from_backup`.
- [ ] Run `python manage.py test app.test_pbq_transfer app.test_course_packages app.test_gradebook_copy app.test_audio --settings=app.test_settings`. Commit `feat: preserve PBQs in course transfers and backups`.

### Task 8 — Release verification and operations guide

**Files:** Create `docs/operations/pbq-activities.md`; update installation guidance for private storage configuration and backup coverage. Add PBQ test jobs to the repository's actual CI pattern after checking its current workflows.

- [ ] Run all PBQ modules and the complete existing application test suite: `python manage.py test app --settings=app.test_settings`. Record actual results, failures, or skips; never substitute planned outcomes for executed evidence.
- [ ] Apply migrations from the current release to the feature release against an isolated copy of the deployment's MariaDB version. Verify constraints, foreign keys, decimal scores, and concurrency separately from the SQLite fast suite.
- [ ] Perform an instructor/student walkthrough: create the worked example, preview, publish, save/resume, submit, grade, inspect CSV, clone/export/import, and restore into a new course. Repeat asset access tests through the deployed web server.
- [ ] Confirm theme/mobile/keyboard accessibility and that a submitted assessment cannot be changed or accidentally removed through secondary course tools.
- [ ] Document pending grading, retries, private artifact backup requirements, edit locking, package compatibility, and deployment/migration commands appropriate to the actual installation. Commit `docs: document and verify PBQ activities`.

## 8. Release acceptance and handoff

The feature is ready for review when an instructor can author the worked example entirely through the UI, students can complete all four answer types with durable draft saving, grading and CSV agree, artifacts remain protected, and course transfer/backup checks pass. Existing quizzes and gradebook behavior must pass their regression suite.

Deploy only after code review and staging verification. Back up the database and private artifact storage together. Use additive schema changes, configure storage ownership before enabling PBQs, and rehearse rollback. A rollback must preserve PBQ records and bytes; do not reverse migrations destructively after student use. Prefer disabling PBQ routes temporarily and correcting forward.

Recommended delivery order is the eight tasks above on a feature branch, with a single reviewed release after all integration paths pass. No repository commits, application changes, or deployment were performed while preparing this plan.

### Source references inspected

- [Question and course models](https://github.com/gimserk/labtech_standalone/blob/e5adcea74fb09f8882295cc0a41d88b52029b84d/app/models.py)
- [Gradebook calculation](https://github.com/gimserk/labtech_standalone/blob/e5adcea74fb09f8882295cc0a41d88b52029b84d/app/gradebook.py) and [gradebook policy](https://github.com/gimserk/labtech_standalone/blob/e5adcea74fb09f8882295cc0a41d88b52029b84d/app/gradebook_models.py)
- [Course package validation](https://github.com/gimserk/labtech_standalone/blob/e5adcea74fb09f8882295cc0a41d88b52029b84d/app/course_packages.py) and [course import/backup](https://github.com/gimserk/labtech_standalone/blob/e5adcea74fb09f8882295cc0a41d88b52029b84d/app/course_importer.py)
- [Course views and copy pathways](https://github.com/gimserk/labtech_standalone/blob/e5adcea74fb09f8882295cc0a41d88b52029b84d/app/views.py)
- [Audio file delivery pattern](https://github.com/gimserk/labtech_standalone/blob/e5adcea74fb09f8882295cc0a41d88b52029b84d/app/audio_views.py), [settings](https://github.com/gimserk/labtech_standalone/blob/e5adcea74fb09f8882295cc0a41d88b52029b84d/app/settings.py), and [isolated test settings](https://github.com/gimserk/labtech_standalone/blob/e5adcea74fb09f8882295cc0a41d88b52029b84d/app/test_settings.py)
