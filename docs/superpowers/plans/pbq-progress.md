# PBQ execution ledger — plan: 2026-10-13-pbq-implementation-plan.md

User approved the complete plan and defaults on 2026-10-13. Implement inline.

Remote baseline: e5adcea74fb09f8882295cc0a41d88b52029b84d.
Local baseline: 6f59531 (source-only snapshot; NOT remote history).
Branch: codex/pbq-activities.

Ruling: direct git clone has no configured credentials. Use authenticated GitHub connector reads and an isolated source snapshot; publish only changed blobs against the real remote base tree. Never push synthetic local history. Binary/static vendor files remain unchanged in the remote base tree.
Ruling: referenced workflow helper resources were unavailable via the skill provider. Maintain the task ledger and tests directly using the skill's documented workflow.

Pre-flight interfaces: models -> services/forms/scoring/transfer use PBQActivity, PBQQuestion, PBQAnswerField, PBQChoice and PBQAcceptedAnswer consistently. Attempts -> grading/gradebook use frozen maximum and latest submitted attempt. Transfer -> package/copy/backup uses private bytes, remapped IDs, and compensating file cleanup. Artifact storage must remain outside public MEDIA_ROOT.

Task 1: implemented; model/publication tests pass.
Task 2: implemented; private upload/delivery, sanitizer, limits and file lifecycle tests pass. Deployment alias check outstanding.
Task 3: implemented; builder, mixed fields, chapter integration, scoped IDs and locking tests pass. Browser walkthrough outstanding.
Task 4: implemented; lifecycle/scoring tests pass. MariaDB concurrency CI added, not run locally.
Task 5: implemented; manual grading, revisions, audit and release-policy tests pass.
Task 6: implemented; shared gradebook, progress, navigation and achievement tests pass.
Task 7: implemented; independent copies, image remapping, v2 packages, optional grades/audit, backup and rollback tests pass.
Task 8: local verification and fresh review complete; operations guide and CI added. MariaDB CI, staging/browser and deployed file-access gates remain outstanding.

2026-10-13: Initial model RED (3 failures/errors for missing PBQ models); GREEN 3/3. Commit 291b02d.
Artifacts/attempts/scoring RED 7/7 missing modules/interfaces; GREEN 10/10 including initial models.
Ruling: implement attempt services before authoring UI so the UI uses a tested lifecycle. No feature scope change.
Baseline suite: 209 tests, two pre-existing plugin licensing failures caused by hard-coded expired September 2026 JWT fixtures; three new PBQ failures expected at baseline. Django discovery needs --top-level-directory . due to repository-root __init__.py.
Environment: OS package installation denied (setgroups/setuid). SQLite test dependencies installed in an isolated venv; MariaDB server/build libraries unavailable. Production requirements unchanged. MariaDB/staging verification remains required before merge/release.

2026-10-14: Authoring/grading RED 4 failures for missing routes/services; GREEN after implementing. A disabled story field ignores crafted input and retains the locked definition while accepting permitted metadata edits (test now asserts the valid redirect and unchanged story).
Gradebook/navigation RED 3/3 (missing registry/navigation); GREEN 3/3.
History/file lifecycle RED 3/3; GREEN 3/3. Post-cutoff submitted review, protected cascades and on-commit file deletion verified.
Transfer RED 4/4 missing module; GREEN 4/4. Embedded-image/item-policy copy RED missing policy; GREEN 5/5.
Boundary tests RED stale-grading parameter and missing certificate; GREEN 7/7. Row-lock tests added and explicitly skipped on SQLite.
Ruling: two baseline renewal tests signed already-expired September 2026 tokens. Use current-time future expiration only in those renewal fixtures; retain the deterministic entitlement boundary tests and all production signature/expiry validation. Cost if wrong: test coverage change only.
Ruling: extend attempt revisions to instructor grading forms as well as student drafts to prevent silent stale-tab overwrites. Cost if wrong: instructor must reload when another grader saves.
Ruling: use focused per-question/per-answer-field edit forms rather than inline formsets; every object is scoped to its activity and one question still supports mixed fields. Cost if wrong: more authoring page transitions, no assessment capability loss.
Ruling: retain staging and MariaDB checks as pre-merge gates because this environment cannot run MariaDB or a deployed browser walkthrough; do not claim production readiness. Cost if wrong: release remains blocked until those checks run.
Full suite checkpoint: 241 tests, 237 passed / 4 SQLite concurrency skips, no failures (`pbq-full3.log`). One additional image/policy transfer test passes (`pbq-green8.log`).

2026-10-16: Final fresh review of baseline..35f5606 completed by pbq_final_review; four Important findings accepted, one Minor deferred. One fix pass, no second reviewer.
Final: fixed bulk-date updates overwriting a concurrent first-attempt content lock — test_bulk_dates_does_not_overwrite_concurrent_content_lock RED→GREEN. Defense-in-depth test_existing_attempts_defend_against_a_missing_lock_timestamp also RED→GREEN; story/policy cannot be changed when attempts exist.
Final: fixed stale form retries promoting old answers to the latest revision — test_stale_page_cannot_promote_old_answers_to_current_revision RED→GREEN; retain the submitted revision and offer reload.
Final: fixed CKEditor removing artifact images — scripts/test_pbq_editor.cjs RED→GREEN against the shipped editor's real toolbar-configured filter; narrow img/src/alt rule survives two passes, server sanitization unchanged.
Final: fixed archived-course edits through dates/order routes — test_archived_course_rejects_bulk_dates_and_reordering RED→GREEN.
Full suite after the fix pass: 246 tests, 242 passed / 4 SQLite concurrency skips, zero failures (`pbq-final-suite.log`). Migration drift check and git diff --check clean. Editor filter check passes.
Final: minor (deferred): a first saved PBQ draft has gradebook status not_started rather than in_progress; no grade or completion is awarded, correctly.
Final: Ruling: reviewer declined to certify MariaDB locking and migration behavior — retain CI plus a rehearsal on the actual deployed database version as pre-merge gates; local SQLite results do not prove row locking — cost if wrong: concurrency or upgrade failure in production.
Final: Ruling: reviewer declined to certify private-file web-server isolation — require a deployed alias/access check because Django cannot inspect proxy aliases — cost if wrong: artifact exposure.
Final: Ruling: reviewer declined to certify actual browser/theme/mobile/accessibility behavior — require a staging walkthrough; Chromium download failed, so use the shipped CKEditor filter in jsdom only for the specific image-loss regression — cost if wrong: browser interaction or accessibility defects remain.
