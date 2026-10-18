# PBQ activities

A PBQ combines a CKEditor scenario, private image/text evidence, and ordered
questions. A question can contain several independently scored answer fields.

## Instructor workflow

1. In **Manage Content**, expand a chapter and choose **+ PBQ**.
2. Save the title, scenario, chapter, dates, attempt limit, and answer-release
   policy. A new activity is an unpublished draft. `0` allows unlimited attempts.
3. Add artifacts. Images require alternative text. To embed an uploaded image,
   edit the story or question, select its CKEditor, and use the artifact button.
4. Add questions and answer fields. Order numbers control their display order.
5. Use **Student preview** to check the scenario and all fields without creating
   a student attempt, then **Publish PBQ**. Publication checks for a nonempty story,
   questions, positive points, and complete scoring configuration.

| Answer field | Configuration and grading |
|---|---|
| Multiple Choice | At least two options, one per line; select the correct option by its number. Single selection, automatically graded. |
| Dropdown | The same options/key configuration, displayed as a select menu. The initial blank is not an answer. |
| Fill in the Blank | One or more accepted answers, one per line. Unicode normalization and outer whitespace trimming; case insensitive unless selected. Internal whitespace is preserved. No regex or fuzzy matching. |
| Short Answer | Private marking guidance required. Instructor awards 0 through the field maximum, with up to two decimal places and optional feedback. |

Each maximum is a positive whole number. A question may combine all four types.
Images can be opened at full size. In the student workspace, text artifacts are
read in full inside the evidence panel; downloads are optional. The separate
legacy text preview used on management/results pages still shows up to 100 KiB.

## Student workspace

The scenario appears above two equal columns: numbered artifact tabs on the left
and numbered question tabs on the right. The columns stack on small screens.
Click a number or use Left/Right arrows, Home, and End while a tab is focused.
Previous/Next buttons also move between questions. All answer fields stay in the
same form when switching tabs.

A question is **Complete** only when every answer field contains an answer;
whitespace-only text and the dropdown placeholder do not count. Completed tabs
show a checkmark, and the progress indicator counts completed questions. This is
answer completion, not a correctness score or an indication that work is saved.
At **100% — ready to submit**, the Submit PBQ button becomes available. Clearing
an answer updates the indicator and disables submission until it is answered.
Server-side validation remains authoritative.

Use **Save progress** before leaving. The workspace marks edits as unsaved and
keeps the existing navigation warning. On resume it opens the first unfinished
question; server validation errors open the affected question. Instructor preview
uses the same layout without saving answers or allowing submission.

Text files load on demand through authenticated artifact URLs and are inserted as
literal text, including HTML-looking content. A failed load offers Retry. With
JavaScript disabled, questions remain visible together and text uses an inline
viewer; saving/submission continues to use the normal server validation.

## Attempts, grading, and progress

Students explicitly start a PBQ, use **Save progress**, and return to the same draft
before the activity closes. Saving a draft does not consume another attempt or
complete the activity. A final submission requires every field and records
completion immediately, even when short answers await grading. Both student
saves and instructor grading pages reject stale revisions from another tab.

Review submissions from **Manage PBQ & grade** or the gradebook. Save partial
grading work, then finalize when every short answer has a score. Corrections to
a finalized grade require a reason; the previous score and feedback are retained
in the grading audit. Scores and feedback are visible to students after grading
is finalized. Correct answers are hidden by default, with optional release after
grading, the due date, or availability cutoff. A missing release date keeps keys
hidden. Release also requires the attempt to be fully graded.

The gradebook uses the **latest submitted attempt**. A newer draft preserves
the prior submitted grade; a newer pending submission makes the item pending.
Pending items are excluded from assessed points and mark the course grade
provisional. For example, a 7/10 PBQ configured for 20 gradebook points earns
14/20. Existing weighted courses give the new PBQ category zero weight until an
instructor configures it. An item can instead be completion only.

When the first attempt starts, the story, questions, answer keys, artifacts,
attempt limit, and answer-release policy are locked. Title, dates, and chapter
placement remain editable. **Duplicate PBQ** creates an unlocked, unpublished
copy for revisions. Activity and chapter deletion are blocked when they would
erase PBQ attempts. Whole-course content overwrite/restore is also blocked; use
a new course. The application's explicit whole-course deletion remains destructive.

After cutoff, a still-enrolled learner can review submitted attempts and their
artifacts. Removing enrollment removes that access. PBQ assessment content and
answer keys are excluded from tutor material extraction.

## Private storage and deployment

PBQ artifacts must not be served by a public `/media/`, `/static/`, web-server
alias, object bucket, or CDN. The application checks that `PBQ_PRIVATE_ROOT` is
outside its configured public media/static roots. Operators must also verify
their reverse-proxy configuration; Django cannot detect a custom public alias.

Set these environment variables before enabling PBQs:

```dotenv
PBQ_PRIVATE_ROOT=/var/lib/labtech/private_pbq
PBQ_MAX_UPLOAD_BYTES=10485760
PBQ_MAX_TOTAL_BYTES=52428800
PBQ_MAX_ARTIFACTS=20
PBQ_MAX_IMAGE_PIXELS=25000000
```

Create that directory with ownership for the existing application service user
and restrictive permissions. Do not make it world writable. If not set, the
private root defaults to `private_pbq` beneath the application's base directory.
Supported files: PNG, JPEG, WebP, and UTF-8 `.txt`, `.log`, `.csv`. Uploads are
checked by extension, MIME type, decoded contents, byte count, and pixel count.
SVG, HTML, executable and binary text artifacts are rejected. Rich text is
sanitized on authoring/import. The PBQ editor has no public upload/browser control.

Using the installation's existing virtual environment and production settings:

```bash
python manage.py check
python manage.py migrate --plan
python manage.py migrate
python manage.py collectstatic --noinput
```

Migrations `0019_pbq_activities` and `0020_alter_coursecategoryweight_category_key_and_more`
are additive. Rehearse the upgrade against an isolated copy of the deployment's
MariaDB version and take the usual database backup before release. Restart services
using the existing installation procedure, after the deployment is approved.

The current CKEditor integration is reused. Django's existing CKEditor 4 support
warning still applies; this feature does not migrate the site's editor.

## Copies, course packages, and backups

Whole-course clone, selected-content copy, and PBQ duplication carry the PBQ
definition and independently owned artifact files. Image references and nested
IDs are remapped; ordinary copies omit attempts. Explicit item point policies
are preserved. Copies need publication before student use.

PBQ-containing ZIP packages use **format 2**, with evidence in a separate
`private_pbq/` archive tree. Packages without PBQs continue using format 1; the
importer accepts historical unversioned and version-1 packages. Older LabTech
installations cannot read PBQ packages and must be upgraded first.

When exporting content plus enrollments and grades, PBQ attempts, responses,
manual grades and grading audit are included. Import resolves students by a
unique local email and only restores attempts for successfully restored
enrollments. Unresolved/ambiguous users are reported. Imported courses start
inactive. Review their enrollments before publication.

Content-only course backups contain PBQ definitions and bounded artifact bytes,
but no attempts. Restore into a new course when student PBQ history exists.
Failed transfers remove newly created files; deletion of old artifacts waits
until the database transaction commits.

For disaster recovery, back up the **database and private PBQ directory together**.
A database-only backup cannot recover artifact bytes. Keep the private directory
out of source control. Preserve PBQ data during rollback; do not reverse PBQ
migrations after student use. Prefer disabling access and correcting forward.

## Verification and release gate

Fast local checks:

```bash
python manage.py test app --top-level-directory . --settings=app.test_settings
python manage.py check --settings=app.test_settings
python manage.py makemigrations --check --dry-run --settings=app.test_settings
```

The shipped CKEditor toolbar's content filter also has a DOM regression check:

```bash
npm install --prefix /tmp/pbq-dom jsdom@26.1.0 --ignore-scripts
NODE_PATH=/tmp/pbq-dom/node_modules PYTHON_BIN=python node scripts/test_pbq_editor.cjs
```

This checks image and alternative-text retention through two filter passes; it
does not replace the browser walkthrough below.

The student workspace also has a Chromium regression check using the dependencies
from the [appearance checks](appearance.md):

```bash
python scripts/render_pbq_workspace.py /tmp/pbq-workspace.json
NODE_PATH="$PWD/scripts/theme-tests/node_modules" node scripts/test_pbq_workspace.cjs /tmp/pbq-workspace.json /tmp/pbq-workspace-results
```

It covers numbered tabs, keyboard navigation, literal text loading/retry, progress
and whitespace handling, multi-question form submission, saved/error states,
preview, no-JavaScript fallback, four palettes, and narrow-screen layout. The
server suite separately exercises private text access and real save/submit posts.
The UI update needs static collection and a web-service restart, with no schema
migration or new runtime dependency.

`.github/workflows/pbq-tests.yml` runs the regression suite, upgrades an isolated
MariaDB 11.4 database from schema 0018, and tests PBQ row locking. The four
concurrency tests intentionally skip on SQLite. CI database settings are
`app.pbq_mariadb_settings` and require `PBQ_CI_DB_PASSWORD`; never use them against
a deployment database.

Before release, verify CI and rehearse on the deployment database version. Perform
an instructor/student walkthrough with image and text artifacts, a multipart
question, save/resume, grading, gradebook/CSV, clone, package import and backup
restore. Check narrow screens, keyboard operation, dark mode, CKEditor image
insertion, and direct-file denial through the actual web server. These deployment
and browser checks are not established by the SQLite suite.
