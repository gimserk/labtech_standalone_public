# Audio Course Content Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a first-class audio course item that instructors can source from an upload or HTTPS URL and students can securely play, download, and manually mark complete.

**Architecture:** A dedicated `Audio` model reuses existing course timing, chapter ordering, and generic completion infrastructure. Focused services own upload validation/file lifecycle and authenticated range delivery, while existing course registries are extended explicitly so audio participates everywhere without refactoring unrelated content types.

**Tech Stack:** Django models/forms/views, Django storage API, `StreamingHttpResponse`, HTML5 audio, SQLite-backed Django tests, existing course package JSON/ZIP format.

**Spec:** `docs/superpowers/specs/2026-09-22-audio-course-content-design.md`

## Global Constraints

- Audio is a dedicated content model; do not merge it into `Video` or create a generic media hierarchy.
- Each item has exactly one source: an owned upload or an external HTTPS URL.
- Uploads accept MP3, M4A, AAC, OGG, and WAV only and default to a 250 MiB (`262144000` byte) limit through `AUDIO_MAX_UPLOAD_BYTES`.
- Validate extension, declared MIME type, and a bounded file signature; never trust a filename or MIME type alone.
- External URLs are never fetched, proxied, cached, DNS-resolved, or availability-checked by LabTech.
- Uploaded files are served only through authenticated, course-scoped endpoints; never expose storage paths or public media URLs.
- Uploaded streaming supports one byte range and constant-memory chunking; multiple or unsatisfiable ranges return `416`.
- Completion is manual, POST-only, CSRF-protected, course-scoped, and limited to an explicit supported-model allowlist.
- Uploaded file ownership is one row to one storage object; copy/import creates a distinct object and rollback removes newly written orphans.
- Existing course packages without audio remain import-compatible.
- Execute from a base that already contains `0127_lab_check_models`; the planned audio migration is therefore `0128_audio_content`.
- Do not add recording, transcoding, transcripts, waveform generation, playback tracking, listening-duration requirements, or RSS support.

## Review Focus

- A zero-byte or short spoofed upload with a valid extension/MIME must fail signature validation without leaving a storage object (Task 1 tests).
- A stored upload whose backing object disappears between authorization and open must return a generic `404`/`503`, not leak a path or crash (Task 3 tests).
- `Range: bytes=-0`, multiple ranges, and huge integer ranges must return `416` without reading the file (Task 3 tests).
- A completion request using a valid audio ID with a different course ID must return `404` and create no completion (Task 4 tests).
- A course-package ZIP with traversal paths, a missing audio member, or invalid audio bytes must fail atomically and leave no course media orphan (Task 6 tests).

---

### Task 1: Audio model, settings, and upload validation

**Files:**
- Create: `app/services/audio_content.py`
- Create: `app/migrations/0128_audio_content.py`
- Create: `app/tests/audio_content/__init__.py`
- Create: `app/tests/audio_content/fixtures.py`
- Create: `app/tests/audio_content/test_model_and_validation.py`
- Modify: `app/models.py` near `Video`
- Modify: `app/settings.py` near upload/runtime limits
- Modify: `test_settings.py`

**Interfaces:**
- Consumes: existing `ContentTiming`, `Course`, `Chapter`, Django `FileField`, and configured default storage.
- Produces: `Audio`, `validate_audio_upload(upload) -> ValidatedAudio`, `validate_external_audio_url(value: str) -> str`, `audio_upload_to(instance, filename) -> str`, and `AUDIO_MAX_UPLOAD_BYTES`.

- [ ] **Step 1: Write failing model and validation tests**

Create fixtures that use `TemporaryDirectory`, `override_settings(MEDIA_ROOT=self.media_root)`, `SimpleUploadedFile`, and minimal valid headers. Pin exact source-state, course/chapter, signature, MIME, extension, size, stream-reset, safe-name, and URL behavior:

```python
@override_settings(AUDIO_MAX_UPLOAD_BYTES=8)
def test_upload_limit_is_configurable(self):
    upload = SimpleUploadedFile("episode.mp3", b"ID3" + b"x" * 6, "audio/mpeg")
    with self.assertRaisesMessage(ValidationError, "Audio files may not exceed"):
        validate_audio_upload(upload)

def test_spoofed_and_short_uploads_are_rejected_without_storage_write(self):
    for name, body, mime in [
        ("episode.mp3", b"not-mp3", "audio/mpeg"),
        ("episode.wav", b"RIFF", "audio/wav"),
        ("episode.ogg", b"", "audio/ogg"),
    ]:
        with self.subTest(name=name):
            with self.assertRaises(ValidationError):
                validate_audio_upload(SimpleUploadedFile(name, body, mime))

def test_audio_requires_exactly_one_source_and_same_course_chapter(self):
    external = Audio(course=self.course, title="Episode", source_type="external_url",
                     audio_url="https://cdn.example.test/episode.mp3")
    external.full_clean()
    external.audio_file = SimpleUploadedFile("episode.mp3", b"ID3abc", "audio/mpeg")
    with self.assertRaises(ValidationError):
        external.full_clean()
    external.chapter = self.other_course_chapter
    external.audio_file = None
    with self.assertRaises(ValidationError):
        external.full_clean()
```

Also cover valid MP3 ID3/frame-sync, M4A `ftyp`, AAC ADTS, OGG `OggS`, WAV `RIFF` plus its size field and `WAVE`, case-normalized extensions, every allowed MIME, disallowed MIME/extension pairs, NUL/path filenames, credentialed/non-HTTPS/localhost/private-IP URLs, and `upload.tell() == 0` after validation.

- [ ] **Step 2: Run model/validation tests and verify RED**

Run: `python manage.py test app.tests.audio_content.test_model_and_validation --settings=test_settings -v 2`

Expected: import failure because `Audio` and `app.services.audio_content` do not exist.

- [ ] **Step 3: Implement focused validation helpers**

In `app/services/audio_content.py`, define immutable validation output and bounded header inspection:

```python
@dataclass(frozen=True)
class ValidatedAudio:
    original_filename: str
    content_type: str
    file_size: int

def audio_upload_to(instance, filename: str) -> str:
    extension = Path(filename).suffix.lower()
    return f"course_audio/{instance.course_id}/{uuid.uuid4().hex}{extension}"
```

Implement `validate_audio_upload(upload) -> ValidatedAudio` and `validate_external_audio_url(value: str) -> str`. Read no more than 32 bytes for signatures, reject empty files and values above `settings.AUDIO_MAX_UPLOAD_BYTES`, and restore the input position in `finally`. Use `urlsplit`; require `https`, hostname, no username/password, and reject `localhost` plus non-global IP literals without resolving hostnames.

- [ ] **Step 4: Add the model, constraint, setting, and migration**

Add `Audio(ContentTiming)` beside `Video`, with `SOURCE_UPLOAD`, `SOURCE_EXTERNAL_URL`, choices, fields from the spec, `clean()` for exact-source and chapter ownership, and a `CheckConstraint` named `audio_exactly_one_source`. Override `save()` only to call `full_clean()`; file deletion belongs in the service/task that owns the transaction.

Add:

```python
AUDIO_MAX_UPLOAD_BYTES = int(os.getenv("AUDIO_MAX_UPLOAD_BYTES", "262144000"))
```

Generate `0128_audio_content.py`, inspect it, and remove unrelated dependency-generated operations.

- [ ] **Step 5: Run model/validation and migration checks**

Run: `python manage.py test app.tests.audio_content.test_model_and_validation --settings=test_settings -v 2`

Expected: all tests pass.

Run: `python manage.py makemigrations --check --dry-run --settings=test_settings`

Expected: `No changes detected`.

- [ ] **Step 6: Commit Task 1**

```bash
git add app/models.py app/settings.py test_settings.py app/services/audio_content.py app/migrations/0128_audio_content.py app/tests/audio_content
git commit -m "feat: add validated audio course model"
```

### Task 2: Instructor authoring and transaction-safe file lifecycle

**Files:**
- Create: `app/templates/labtech/audio_form.html`
- Create: `app/tests/audio_content/test_instructor_audio.py`
- Modify: `app/services/audio_content.py`
- Modify: `app/forms.py`
- Modify: `app/views.py` imports and content CRUD area
- Modify: `app/urls.py`
- Modify: `app/templates/labtech/manage_course_content.html`
- Modify: `app/templates/labtech/partials/content_item_actions.html`

**Interfaces:**
- Consumes: Task 1 `Audio`, validators, and `audio_upload_to`.
- Produces: `AudioForm`, `save_audio_form(form, *, course) -> Audio`, `delete_audio(audio) -> None`, and routes `labtech_add_audio`, `labtech_edit_audio`, `labtech_delete_audio`.

- [ ] **Step 1: Write failing form, CRUD, authorization, and cleanup tests**

Cover create for upload/external, chapter filtering, default order, institutional date fields, invalid source pairs, edit without replacement, replacement, upload-to-URL, URL-to-upload, delete, archived-course behavior, unauthorized user, and mismatched course/audio IDs.

Use `captureOnCommitCallbacks(execute=True)` and a temporary storage directory to prove lifecycle behavior:

```python
def test_replacing_upload_deletes_old_file_only_after_commit(self):
    old_name = self.audio.audio_file.name
    with self.captureOnCommitCallbacks(execute=False) as callbacks:
        response = self.client.post(self.edit_url, self.valid_upload_post("replacement.mp3"))
        self.assertTrue(default_storage.exists(old_name))
    for callback in callbacks:
        callback()
    self.assertFalse(default_storage.exists(old_name))
    self.audio.refresh_from_db()
    self.assertTrue(default_storage.exists(self.audio.audio_file.name))

def test_failed_save_removes_new_orphan_but_preserves_current_file(self):
    # Patch Audio.save to fail after storage receives the replacement.
    # Assert the old key remains and the replacement key does not.
```

- [ ] **Step 2: Run instructor tests and verify RED**

Run: `python manage.py test app.tests.audio_content.test_instructor_audio --settings=test_settings -v 2`

Expected: import/reverse failures for missing form, views, and routes.

- [ ] **Step 3: Implement form and lifecycle service**

`AudioForm` accepts `course` and optional `chapter`, removes institutional schedule fields for public courses, filters chapter choices, and invokes Task 1 validators. It must preserve an existing upload when editing `source_type=upload` without a new file.

Implement `save_audio_form(form: AudioForm, *, course: Course) -> Audio` and `delete_audio(audio: Audio) -> None` so views do not manipulate storage directly. Use this concrete deferred-delete primitive:

```python
def schedule_storage_delete(storage, name: str) -> None:
    if name:
        transaction.on_commit(lambda: _safe_delete(storage, name))
```

If a new file is written and database persistence raises, delete only that new key. Never delete the old key until commit. Log safe row/course IDs, not user filenames or backend credentials.

- [ ] **Step 4: Add instructor views, routes, and templates**

Follow the `Video` CRUD pattern but use `request.FILES`, service functions, strict course scoping, `can_manage_course_content`, and archived-course rejection. Add chapter and uncategorized `+ Audio`, audio icon, and edit/delete actions. The form uses `multipart/form-data` and a small script to show the selected source input; both inputs stay server-validated.

- [ ] **Step 5: Run instructor and model suites**

Run: `python manage.py test app.tests.audio_content.test_model_and_validation app.tests.audio_content.test_instructor_audio --settings=test_settings -v 2`

Expected: all tests pass and temporary media directories contain only current owned objects.

- [ ] **Step 6: Commit Task 2**

```bash
git add app/services/audio_content.py app/forms.py app/views.py app/urls.py app/templates/labtech/audio_form.html app/templates/labtech/manage_course_content.html app/templates/labtech/partials/content_item_actions.html app/tests/audio_content/test_instructor_audio.py
git commit -m "feat: add instructor audio authoring"
```

### Task 3: Authenticated audio streaming and downloads

**Files:**
- Create: `app/audio_delivery.py`
- Create: `app/tests/audio_content/test_delivery.py`
- Modify: `app/urls.py`

**Interfaces:**
- Consumes: Task 1 `Audio` metadata and existing enrollment/content-management permissions.
- Produces: `parse_single_range(header: str | None, size: int) -> ByteRange | None`, `audio_stream_view`, and `audio_download_view`.

- [ ] **Step 1: Write failing delivery and range tests**

Test anonymous redirect, enrolled access, managing instructor access, unrelated-user denial, cross-course 404, availability start/end enforcement, full GET, HEAD, `0-3`, `4-`, `-4`, out-of-bounds, reversed, `-0`, multiple, nonnumeric, and huge ranges.

```python
def test_enrolled_student_can_seek_uploaded_audio(self):
    response = self.client.get(self.stream_url, HTTP_RANGE="bytes=3-6")
    self.assertEqual(response.status_code, 206)
    self.assertEqual(response["Content-Range"], f"bytes 3-6/{self.audio.file_size}")
    self.assertEqual(response["Accept-Ranges"], "bytes")
    self.assertEqual(b"".join(response.streaming_content), self.payload[3:7])

def test_pathological_ranges_return_416_without_opening_storage(self):
    for value in ("bytes=-0", "bytes=0-1,3-4", "bytes=9-2", "bytes=999999999999999999999-"):
        with self.subTest(value=value), patch.object(default_storage, "open") as opened:
            response = self.client.get(self.stream_url, HTTP_RANGE=value)
            self.assertEqual(response.status_code, 416)
            opened.assert_not_called()
```

Also remove the backing file and simulate `OSError` on open/read; assert generic response bodies do not contain media paths or filenames. Assert chunk sizes remain bounded for a multi-megabyte fake file.

- [ ] **Step 2: Run delivery tests and verify RED**

Run: `python manage.py test app.tests.audio_content.test_delivery --settings=test_settings -v 2`

Expected: import/reverse failures for missing delivery module and routes.

- [ ] **Step 3: Implement range parsing and bounded iteration**

Define:

```python
@dataclass(frozen=True)
class ByteRange:
    start: int
    end: int
```

Implement `parse_single_range(header: str | None, size: int) -> ByteRange | None` and `iter_file_range(file_obj, byte_range: ByteRange, chunk_size: int = 64 * 1024)`. Reject malformed/multiple/empty ranges with a dedicated exception before opening storage. Cap integer token length before conversion. `iter_file_range` seeks once and reads `min(chunk_size, remaining)` until exactly the requested count is exhausted.

- [ ] **Step 4: Implement authorization and response views**

Resolve `Audio` through `course_id`, require `source_type=upload`, and permit enrollment or `can_manage_course_content`. For students, apply the same effective course/item window as `course_detail_view` through a small shared predicate rather than duplicating date logic.

Return safe `Content-Type`, `Content-Length`, `Accept-Ranges`, `Content-Range`, and RFC-safe `Content-Disposition`. `HEAD` closes the opened file without iterating. Missing objects return 404; unexpected storage failures log safe identifiers and return a generic 503.

- [ ] **Step 5: Run delivery and security tests**

Run: `python manage.py test app.tests.audio_content.test_delivery --settings=test_settings -v 2`

Expected: all tests pass.

- [ ] **Step 6: Commit Task 3**

```bash
git add app/audio_delivery.py app/urls.py app/tests/audio_content/test_delivery.py
git commit -m "feat: stream protected course audio"
```

### Task 4: Student curriculum, manual completion, progress, and certificates

**Files:**
- Create: `app/tests/audio_content/test_student_audio.py`
- Create: `app/tests/audio_content/test_completion_integration.py`
- Modify: `app/models.py` `Course` count properties
- Modify: `app/views.py` course-detail, completion, dashboards, progress, and gradebook registries
- Modify: `app/management/commands/awardcerts.py`
- Modify: `app/templates/labtech/partials/course_main_content.html`
- Modify: curriculum/sidebar templates that branch on model name

**Interfaces:**
- Consumes: Task 1 `Audio`, Task 3 delivery route names, `ContentCompletion`, existing course detail context.
- Produces: audio rendering and explicit `MANUALLY_COMPLETABLE_MODELS` course resolver used by `mark_content_complete_view`.

- [ ] **Step 1: Write failing curriculum and rendering tests**

Create a course with text, audio, and video across chapters and unassigned content. Assert audio ordering, availability, previous/next links, description, native `<audio controls preload="metadata">`, uploaded stream/download URLs, external HTTPS `src`, safe `target="_blank" rel="noopener noreferrer"`, course audio count, and manual-completion button.

Patch `requests`, `urllib`, and the storage open method for an external item and assert rendering makes no server-side network/storage call.

- [ ] **Step 2: Write failing completion/progress tests**

```python
def test_completion_is_course_scoped_and_allowlisted(self):
    wrong_course_url = reverse("mark_content_complete", args=[self.other_course.pk, "audio", self.audio.pk])
    self.assertEqual(self.client.post(wrong_course_url).status_code, 404)
    self.assertFalse(ContentCompletion.objects.filter(user=self.student, object_id=self.audio.pk).exists())
    unsupported = self.client.post(reverse("mark_content_complete", args=[self.course.pk, "user", self.student.pk]))
    self.assertEqual(unsupported.status_code, 404)

def test_audio_completion_updates_course_and_certificate_totals(self):
    # Complete every item except audio, assert course incomplete; complete audio, assert 100% and award path invoked.
```

Cover idempotency, GET rejection, CSRF behavior, chapter completion, student dashboard, instructor progress, gradebook rows, and certificate command totals.

- [ ] **Step 3: Run student/completion tests and verify RED**

Run: `python manage.py test app.tests.audio_content.test_student_audio app.tests.audio_content.test_completion_integration --settings=test_settings -v 2`

Expected: audio absent from curriculum and completion totals; cross-course completion currently demonstrates the security regression.

- [ ] **Step 4: Integrate Audio into curriculum rendering**

Add Audio to the course detail flattened list, `ContentType` map, structured chapters, summaries, and icon branches. Render uploaded sources through Task 3 routes; render external sources directly. Show the same manual completion control as text/video. Add `Course.audio_count`.

- [ ] **Step 5: Harden completion and update every progress registry**

Define an explicit mapping:

```python
MANUALLY_COMPLETABLE_MODELS = {
    "textpage": TextPage,
    "video": Video,
    "audio": Audio,
    "lab": Lab,
    # Include only currently supported completion models verified in existing flows.
}
```

Resolve `model.objects.filter(pk=object_id, course_id=course_id)` before creating `ContentCompletion`. Keep POST/CSRF/enrollment decorators. Add Audio to every existing course-content total and progress/certificate registry, including `awardcerts.py`; do not accidentally add grade points.

- [ ] **Step 6: Run focused and existing completion suites**

Run: `python manage.py test app.tests.audio_content.test_student_audio app.tests.audio_content.test_completion_integration --settings=test_settings -v 2`

Expected: all tests pass; existing gradebook semantics are unchanged except audio completion inclusion where content completion is displayed.

- [ ] **Step 7: Commit Task 4**

```bash
git add app/models.py app/views.py app/management/commands/awardcerts.py app/templates/labtech app/tests/audio_content/test_student_audio.py app/tests/audio_content/test_completion_integration.py
git commit -m "feat: add student audio lessons"
```

### Task 5: Ordering, bulk scheduling, and course-content copy

**Files:**
- Create: `app/tests/audio_content/test_content_integration.py`
- Modify: `app/forms.py` ordering and import selection
- Modify: `app/views.py` management/reorder/bulk-date/import-copy registries
- Modify: `app/templates/labtech/import_content.html`
- Modify: `app/services/audio_content.py`

**Interfaces:**
- Consumes: Task 1 `Audio`, Task 2 lifecycle primitives.
- Produces: `copy_audio_item(source: Audio, *, destination_course: Course, chapter: Chapter | None) -> Audio` used by `copy_content_item`.

- [ ] **Step 1: Write failing ordering, schedule, and copy tests**

Assert `get_next_course_content_order` considers audio, management prefetch/list sorting includes it, reorder accepts `type=audio` but rejects cross-course IDs, bulk dates update audio, JSON import selection labels it `audio`, and copy-all/selected paths include it.

For uploads:

```python
def test_copy_upload_owns_distinct_storage_object(self):
    copied = copy_audio_item(self.audio, destination_course=self.destination, chapter=None)
    self.assertNotEqual(copied.audio_file.name, self.audio.audio_file.name)
    self.assertEqual(read(copied.audio_file), read(self.audio.audio_file))
    delete_audio(copied)
    self.assertTrue(default_storage.exists(self.audio.audio_file.name))
```

Patch destination database creation to raise after storage write and assert the copied object is removed while the source remains. External copy asserts URL/metadata copy without storage access.

- [ ] **Step 2: Run content integration tests and verify RED**

Run: `python manage.py test app.tests.audio_content.test_content_integration --settings=test_settings -v 2`

Expected: audio omitted from registries and generic copy would share the source key.

- [ ] **Step 3: Implement owned audio copy**

Read source bytes through storage in bounded chunks into a temporary spooled file or `File`, validate again, and save through a new generated key. On any exception, delete a newly created destination key. Copy URL items without touching storage. Dispatch `Audio` before the generic field-copy branch in `copy_content_item`.

- [ ] **Step 4: Update ordering, scheduling, and selection registries**

Add Audio explicitly to the form helper, management prefetch/list, unassigned list, reorder model map, bulk-date content list, course import selection endpoint, selected-content model map, copy-all list, and UI JavaScript type collection. Use the canonical key `audio` for singular model names and `audio_items` for related managers; do not invent plural `audios`.

- [ ] **Step 5: Run integration and instructor suites**

Run: `python manage.py test app.tests.audio_content.test_content_integration app.tests.audio_content.test_instructor_audio --settings=test_settings -v 2`

Expected: all tests pass and storage ownership stays one-to-one.

- [ ] **Step 6: Commit Task 5**

```bash
git add app/forms.py app/views.py app/services/audio_content.py app/templates/labtech/import_content.html app/tests/audio_content/test_content_integration.py
git commit -m "feat: integrate audio course operations"
```

### Task 6: Course package export/import round trip

**Files:**
- Create: `app/tests/audio_content/test_package_round_trip.py`
- Modify: `app/course_importer.py`
- Modify: `app/views.py` only where it independently duplicates package serialization/import

**Interfaces:**
- Consumes: Task 1 validators and `Audio`; Task 2 lifecycle rules.
- Produces: course-package manifest entries under `audio_items` and safe uploaded-media restoration.

- [ ] **Step 1: Write failing uploaded/external round-trip tests**

Export a course with uploaded and external audio. Inspect the ZIP and manifest: external metadata has no media member; upload metadata references a deterministic normalized `course_audio/<course-id>/<generated-name>` archive member whose bytes match. Import and assert new rows, chapters, schedule fields, source metadata, distinct storage keys, and playable bytes.

Also prove an old no-audio package imports unchanged.

- [ ] **Step 2: Write hostile and atomic-failure package tests**

Build packages with `../escape.mp3`, absolute paths, symlink-like entries where supported, duplicate manifest destinations, missing members, oversized payloads, spoofed signatures, non-HTTPS external URLs, and a forced database failure after file creation. Assert import fails clearly, creates no usable course/audio rows, writes nothing outside the temp/media roots, and leaves no new storage object.

- [ ] **Step 3: Run package tests and verify RED**

Run: `python manage.py test app.tests.audio_content.test_package_round_trip --settings=test_settings -v 2`

Expected: audio is absent from export/import and hostile path tests expose current unsafe `extractall` behavior.

- [ ] **Step 4: Add safe ZIP extraction before audio support**

Replace raw `extractall` with a helper that rejects absolute paths, `..`, drive prefixes, symlink entries, duplicate normalized paths, and members escaping the destination after `resolve()`. Apply total/member size limits before extraction. Tests must show the helper is used for all course-package members, not audio only.

- [ ] **Step 5: Extend canonical course importer serialization**

Add `Audio` to `course_importer` imports, content maps, chapter backups, and the package serializer. Store uploaded audio as a media-relative path; external audio stores only URL/source metadata. Keep the manifest JSON serializable and deterministic.

- [ ] **Step 6: Restore audio transactionally**

Before creating imported `Audio`, validate the extracted member through Task 1 helpers and save under a generated storage key. Track every new key; on any exception, roll back the database transaction and delete tracked keys. Do not trust archived `original_filename`, `content_type`, `file_size`, or storage key—recompute them from the validated file.

- [ ] **Step 7: Run package and copy suites**

Run: `python manage.py test app.tests.audio_content.test_package_round_trip app.tests.audio_content.test_content_integration --settings=test_settings -v 2`

Expected: all round-trip, compatibility, traversal, and cleanup tests pass.

- [ ] **Step 8: Commit Task 6**

```bash
git add app/course_importer.py app/views.py app/tests/audio_content/test_package_round_trip.py
git commit -m "feat: preserve audio in course packages"
```

### Task 7: Documentation, deployment checks, and end-to-end verification

**Files:**
- Create: `docs/operations/audio-course-content.md`
- Create: `app/tests/audio_content/test_security_regressions.py`
- Modify: `.env.template`
- Modify: `app/checks.py`
- Modify: `app/tests/audio_content/fixtures.py`

**Interfaces:**
- Consumes: all prior task interfaces.
- Produces: operator guidance and deployment diagnostics for the completed feature.

- [ ] **Step 1: Write failing deployment and end-to-end security tests**

Test invalid/nonpositive `AUDIO_MAX_UPLOAD_BYTES`, unwritable/nonseekable storage diagnostics where they can be checked safely without network I/O, log redaction, malicious filenames/URLs, unavailable items, cross-course IDs across CRUD/delivery/completion, no outbound external fetch, range edge cases from Review Focus, and full instructor-upload → enrolled-play/download → manual-complete flow.

```python
@override_settings(AUDIO_MAX_UPLOAD_BYTES=0)
def test_deployment_check_rejects_nonpositive_audio_limit(self):
    self.assertIn("audio.E001", {error.id for error in run_checks()})

def test_external_audio_render_never_fetches_url(self):
    with patch("requests.get") as get, patch("urllib.request.urlopen") as open_url:
        response = self.client.get(self.course_url_with_external_audio)
    self.assertEqual(response.status_code, 200)
    get.assert_not_called()
    open_url.assert_not_called()
```

- [ ] **Step 2: Run security tests and verify RED**

Run: `python manage.py test app.tests.audio_content.test_security_regressions --settings=test_settings -v 2`

Expected: missing deployment diagnostic/documentation behavior causes failures.

- [ ] **Step 3: Add deployment check and operator documentation**

Register stable audio check IDs without storage writes or network calls. Document supported formats, 250 MiB default, request-body/proxy limits, writable and seekable storage, authenticated delivery, media capacity/backup requirements, external direct-link limitations, safe error meanings, and deployment verification commands. Add `AUDIO_MAX_UPLOAD_BYTES=262144000` to `.env.template`.

- [ ] **Step 4: Run focused audio suite**

Run: `python manage.py test app.tests.audio_content --settings=test_settings -v 2`

Expected: all audio tests pass with no leaked temporary files.

- [ ] **Step 5: Run affected existing suites**

Run: `python manage.py test app.tests.test_lab_cleanup_views app.tests.lab_checks --settings=test_settings -v 1`

Expected: all tests pass; existing content, cleanup, and lab-check behavior remains unchanged.

- [ ] **Step 6: Run full verification**

Run: `python manage.py test --settings=test_settings -v 1`

Expected: full suite passes.

Run: `python manage.py check --settings=test_settings`

Expected: no issues except already-silenced baseline checks.

Run: `python manage.py makemigrations --check --dry-run --settings=test_settings`

Expected: `No changes detected`.

Run: `python -m compileall -q app test_settings.py && git diff --check`

Expected: exit 0 with no output.

- [ ] **Step 7: Inspect final diff against the merge base**

Run: `git diff --stat "$(git merge-base main HEAD)"..HEAD && git diff --check "$(git merge-base main HEAD)"..HEAD`

Expected: only approved audio-content/spec/plan files and the targeted completion/package security hardening are present; no generated media or secrets.

- [ ] **Step 8: Commit Task 7**

```bash
git add .env.template app/checks.py app/tests/audio_content docs/operations/audio-course-content.md
git commit -m "docs: complete audio course rollout"
```
