# Audio Course Content Design

**Date:** 2026-09-22
**Status:** Approved design, awaiting written-spec review

## Purpose

LabTech instructors need a first-class audio course item for podcast-style lessons and other recorded material. An instructor can either upload an audio file to LabTech or point to an online audio file. An enrolled student can play the item in the browser, obtain the original file, and manually mark the item complete using the same workflow as a text page or video.

Success means audio behaves like existing course content throughout authoring, ordering, scheduling, copying, backup/import, student progress, and course completion. Uploaded audio remains access-controlled and seekable without exposing its storage path. External audio does not cause LabTech to fetch untrusted URLs.

## Scope

### In scope

- A dedicated `Audio` content model.
- Instructor create, edit, delete, order, schedule, copy, export, and import flows.
- One source per item: a server upload or an external HTTPS audio-file URL.
- Uploaded MP3, M4A, AAC, OGG, and WAV files, limited to 250 MB by default.
- Native browser playback, including byte-range seeking for uploaded files.
- Student download access for both source types.
- Manual completion and inclusion in all course progress and completion calculations.
- Authorization, validation, file-lifecycle, and regression tests.

### Out of scope

- Podcast RSS feeds, episode synchronization, or subscriptions.
- Recording, editing, transcoding, waveform generation, or normalization.
- Automatic transcripts, captions, chapters, playback-position tracking, or listening analytics.
- Requiring a minimum listening duration before completion.
- Proxying or caching external audio.
- Malware scanning beyond structural file validation; deployments may scan media storage independently.
- A generic media-model refactor for existing videos.

## Selected Architecture

Use a dedicated `Audio` model alongside `TextPage` and `Video`. This keeps audio-specific validation, file ownership, rendering, and delivery separate while reusing LabTech's established `ContentTiming`, chapter, ordering, and generic completion patterns.

Extending `Video` was rejected because it would mix incompatible source choices, form rules, labels, templates, and delivery behavior. A generic media abstraction was rejected because migrating existing video behavior would add risk without helping the requested first version.

## Data Model

`Audio` inherits `ContentTiming` and contains:

- `course`: required `ForeignKey(Course, related_name="audio_items")`.
- `chapter`: optional `ForeignKey(Chapter, related_name="audio_items")`.
- `title`: `CharField(max_length=255)`.
- `description`: optional plain `TextField`.
- `source_type`: `upload` or `external_url`.
- `audio_file`: optional `FileField`, stored under a course-audio prefix using a generated storage key rather than the submitted path.
- `audio_url`: optional `URLField(max_length=1000)`.
- `original_filename`: sanitized display/download filename for uploads.
- `content_type`: validated upload MIME type used for responses.
- `file_size`: validated upload size in bytes.
- `order`, `created_at`, and `updated_at` consistent with `Video`.

A database check constraint and model validation enforce these valid states:

- `upload`: `audio_file` is set and `audio_url` is blank.
- `external_url`: `audio_url` is set and `audio_file` is blank.

An audio item's chapter must belong to its course. Source changes are supported. File metadata is blank for external sources.

`Course.audio_count` reports the number of audio items for course summaries.

## Instructor Authoring

The course-content manager gains `+ Audio` actions for chapters and uncategorized content. Audio rows use an audio icon and the existing edit/delete action pattern.

`AudioForm` receives the owning course and optional chapter, like `VideoForm`. It exposes title, chapter, description, source type, upload, URL, order, and institutional scheduling fields. The upload and URL inputs are both rendered, with small client-side behavior showing the relevant input; server validation remains authoritative.

For a new item, order defaults follow existing course/chapter behavior. Edit preserves the current upload when no replacement is submitted. Changing source from upload to URL clears the stored file after commit. Replacing or deleting an uploaded item removes the superseded file only after the database transaction commits successfully.

All create, edit, and delete actions require `can_manage_course_content`. Course, chapter, and audio identifiers are constrained together so cross-course object references return 404.

## Upload Validation

`AUDIO_MAX_UPLOAD_BYTES` is a deployment setting with a default of `262144000` bytes (250 MiB). Deployments may lower it.

Allowed uploaded formats are:

| Format | Extensions | Accepted MIME types | Required signature |
| --- | --- | --- | --- |
| MP3 | `.mp3` | `audio/mpeg`, `audio/mp3` | ID3 header or a valid MPEG audio frame sync |
| M4A | `.m4a` | `audio/mp4`, `audio/x-m4a` | ISO base-media `ftyp` box with an audio-compatible brand |
| AAC | `.aac` | `audio/aac`, `audio/x-aac` | ADTS frame sync |
| OGG | `.ogg`, `.oga` | `audio/ogg`, `application/ogg` | `OggS` capture pattern |
| WAV | `.wav` | `audio/wav`, `audio/x-wav`, `audio/wave` | RIFF container with `WAVE` form type |

Validation checks size, normalized extension, declared MIME type, and a bounded header read. It resets the uploaded stream position before saving. A mismatch or unknown signature produces a form error and no database or storage write. Filenames are reduced to a safe basename for display; storage keys are application-generated.

The form rejects URLs that are not HTTPS, contain user-info credentials, use `localhost`, or use a loopback, link-local, or private IP literal. LabTech does not resolve the hostname or make an outbound validation request. External availability and server response headers can therefore change independently after save.

## Student Experience

Audio participates in the same flattened and chapter-structured course lists as other content. The focused content panel shows:

- title and description;
- native `<audio controls preload="metadata">` playback;
- an uploaded-file `Download audio` action, or an external `Open/download source` action;
- Previous and Next navigation; and
- the existing `Mark as Complete` or completed-state control.

The player supplies one source with the validated MIME type for uploads. External playback uses the stored HTTPS URL directly. The external link uses safe new-tab attributes. Because LabTech does not proxy third-party files, the remote host controls whether the browser plays inline or downloads the file and may later make the item unavailable.

Audio respects the course and item availability windows already applied to other content. Unavailable items do not render their player or download action for students. Instructors who manage the course retain their existing preview behavior.

## Uploaded Playback and Download Delivery

Uploaded files are not linked through a public media URL. Two course-scoped endpoints deliver them:

- a streaming endpoint with inline disposition; and
- a download endpoint with attachment disposition.

Both endpoints accept `GET` and `HEAD` and require an authenticated user who is either enrolled in the course or allowed to manage it. They resolve audio through the course in the URL and enforce the effective availability window for ordinary students.

The streaming endpoint supports one RFC-style byte range. A satisfiable range returns `206`, `Content-Range`, `Accept-Ranges: bytes`, the exact `Content-Length`, and the validated content type. A full request returns `200`; an invalid, unsatisfiable, or multiple-range request returns `416` with `Content-Range: bytes */<size>`. Streaming reads bounded chunks and does not load the full file into application memory. `HEAD` returns the same headers without a body.

The download endpoint streams the full file with a sanitized filename and `Content-Disposition: attachment`. It never accepts a filesystem path from the request. Missing storage objects return 404 without leaking backend details. The configured storage backend must provide a readable, seekable file object for range playback in v1.

## Completion, Progress, and Certificates

`Audio` is added to the explicit supported types for manual completion. The completion endpoint is hardened while being extended:

- it remains POST-only and CSRF-protected;
- it uses an explicit supported-model allowlist rather than accepting an arbitrary Django `ContentType` name;
- it resolves the content object through the course from the URL; and
- it applies the existing enrollment requirement.

Marking an audio item complete creates the existing unique `ContentCompletion` record. Audio is included anywhere LabTech counts or reports course content: course-detail percentages, chapter completion, dashboards, course completion and certificate checks, instructor progress, gradebook completion reporting, and certificate-management commands. No grade points or listening-duration evidence are introduced.

## Course-Content Integration

The implementation must update each explicit content registry/list currently used by LabTech, including:

- course-detail flattened content and `ContentType` maps;
- chapter and uncategorized management lists;
- content ordering and reorder validation;
- bulk scheduling/date updates;
- instructor/student progress views and exports;
- generic action and icon templates;
- achievement and certificate content totals;
- course content import/copy selection; and
- course backup/export/import serialization.

Copying an uploaded audio item creates a new storage object and new database row; it must not point two rows at the same owned file. External items copy only their URL and metadata. Course export archives include uploaded audio bytes under a deterministic media path plus metadata in the course manifest. Import validates archived paths and file content with the same rules as a new upload, creates new storage keys, and rejects missing, oversized, or invalid media without leaving partial rows or files. External URLs are revalidated structurally on import.

Existing backups without audio remain compatible. Audio data in a newer backup must fail clearly rather than be silently discarded by a version that cannot understand it.

## File Ownership and Transaction Safety

Each uploaded storage object has exactly one owning `Audio` row. Shared file references are not allowed.

- New upload: save the row and file as one application operation; if the database save fails after a storage write, remove the new orphan.
- Replacement/source change: retain the old object until the database transaction commits, then delete it.
- Item deletion: capture the old storage key and delete it after commit.
- Failed import/copy: remove every newly written object from that operation.
- Missing old object during cleanup: log a safe warning and keep the successful database change.

Cleanup logs include the audio row and course identifiers but never storage credentials or untrusted full paths.

## Error Handling

Instructor validation errors are attached to the relevant upload or URL field. Oversized, malformed, mismatched, or unsupported files are rejected before persistence.

Student delivery uses generic 403/404 responses that do not reveal whether an unavailable item or storage object exists. Unexpected storage read failures are logged with safe identifiers and return a generic 503 response. External playback failures remain client-side; the page continues to show the description and source action.

Deletion, copy, and import operations report failures without claiming success. Their file cleanup is idempotent so retrying does not damage a current object.

## Migration and Deployment

A new migration creates `Audio` and its constraint. No existing content is transformed. Deployment must provide writable media storage and ensure the application/reverse proxy accepts requests slightly above `AUDIO_MAX_UPLOAD_BYTES`. The authenticated application endpoint, not a public media-server mapping, is authoritative for uploaded audio access.

Operators should account for uploaded media in storage-capacity planning and backups. Existing object-storage or shared-storage deployments must confirm seekable reads before enabling uploaded audio playback.

## Testing Strategy

### Model and form tests

- Valid upload and external states; invalid dual-source and no-source states.
- Chapter/course consistency.
- Every allowed format signature, extension, and MIME combination.
- Unsupported, spoofed, malformed, empty, and oversized uploads.
- Configured size-limit override.
- HTTPS URL and forbidden URL cases.
- Edit without replacement, upload replacement, and both source transitions.

### Instructor workflow tests

- Authorized create, edit, delete, order, and schedule flows.
- Unauthorized and cross-course access.
- Transaction-safe file cleanup on success and rollback.
- Audio visibility in chapter and uncategorized management lists.
- Bulk scheduling and reordering.

### Student delivery tests

- Enrolled, instructor, anonymous, and unrelated-user access.
- Effective availability-window enforcement.
- Full, `HEAD`, valid range, suffix range, open-ended range, invalid range, multiple range, and missing-object responses.
- Safe content type, length, range, and disposition headers.
- Constant-memory chunked delivery behavior.
- External player/link rendering without a server-side fetch.

### Completion and integration tests

- Manual completion is idempotent and course-scoped.
- Unsupported generic content types cannot be marked complete.
- Audio affects item, chapter, course, certificate, instructor-progress, and gradebook totals.
- Content copy duplicates uploaded bytes under a distinct storage key.
- Export/import round trips uploaded and external audio.
- Failed copy/import leaves no rows or storage objects.
- Older no-audio exports continue to import.

### Final verification

- Focused audio tests pass.
- Existing course-content, completion, certificate, gradebook, import/export, cleanup, and lab-check suites pass.
- The full repository test suite passes.
- `manage.py check`, migration-drift checks, compilation, and diff hygiene pass under the test settings.

## Acceptance Criteria

1. An authorized instructor can create an audio item from either a valid upload or valid HTTPS URL and place it in normal course order.
2. Accepted uploads are MP3, M4A/AAC, OGG, or WAV and no larger than the configured 250 MiB default.
3. An enrolled student can play available audio in the browser and obtain the source file without seeing a server storage path.
4. Uploaded playback supports seeking through byte ranges and never loads the whole file into memory.
5. Unauthorized, cross-course, and unavailable uploaded-file requests do not disclose or deliver audio.
6. A student can manually mark audio complete, and it affects all established course progress and completion calculations.
7. External URLs are never fetched or proxied by LabTech.
8. Replacement, deletion, copy, and import do not leak or accidentally share uploaded storage objects.
9. Audio survives supported course copy and backup/export/import workflows.
10. Existing content behavior and the full test suite remain green.
