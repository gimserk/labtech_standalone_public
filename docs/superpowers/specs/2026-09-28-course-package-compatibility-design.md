# Course packages and cloning: compatibility design

## Purpose

Allow an instructor to carry an existing LabTech `.coursepkg` into the standalone
application without silently losing course content. Reject unsafe or unsupported
archives before creating a course. Make a copy of a current course without
reusing unique enrollment codes or student activity.

## Evidence and format

The provided legacy package is a ZIP containing `manifest.json` and `media/`.
Its manifest has `model: Course`, `pk`, `fields`, and arrays of chapters,
activities, resources and enrollments. There is no format version. It contains
legacy enrollment records with blank email addresses; mapping those to a local
user with a blank address caused a unique-enrollment error in an isolated import.
Content imported when the local instructor had a nonblank email. Cloning the
imported code-enrollment course failed because the clone reused its unique code.
The old source repository is not available to this GitHub installation, so
compatibility is established against this actual legacy package and the current
serializer, not asserted for every historical release.

## Import/export contract

- Keep the existing ZIP layout and missing-version legacy format. New exports
  identify the package format; reject unsupported future versions explicitly.
- Read ZIP metadata, member paths, sizes and the manifest before extraction or
  database writes. Bound upload, member count, inflated size and manifest size;
  disallow duplicate members, symlinks, traversal, encrypted members and files
  outside `media/` plus the root manifest. Validate record shape, model names,
  supported fields, IDs, chapter and nested references, and referenced media.
- Preserve older model defaults when fields are absent; ignore only documented
  platform-specific course fields. Report missing local student accounts and
  Proxmox templates. Empty or ambiguous email addresses cannot identify a
  student, so skip those enrollments and their grades with a warning. Never
  create accounts implicitly or attach grades to the wrong account.
- Use the same package checks for uploaded files and marketplace downloads.
  Read file content through Django storage when exporting, including resources
  on non-local storage. An export must not claim to contain a file it omitted.
- Import is atomic for database rows; remove any newly written files on failure.
  If validation fails, keep the file and existing courses untouched.
- The current exporter does not include every kind of student attempt even when
  grades are selected. Clearly label the export as course content and optional
  enrollments/completion records rather than promising a complete student
  grade history.

## Clone contract

- Copy the course, chapters, activities, nested quiz/lab content, grading
  policy, resources and announcements, without enrollments or attempts.
- Generate a fresh enrollment code for a code-required course, leave the copy
  inactive, and keep all original data intact. Copy uploaded files to owned
  storage paths where necessary so deleting the source does not break the copy.
- New guest-agent step checks may contain encrypted secrets bound to a server
  key. Do not export or copy secret material to another server silently; copy
  portable checks and mark secret-dependent checks inactive pending instructor
  review. No history of student check attempts is copied.

## Verification

Test invalid and hostile archives, empty and ambiguous emails, existing old
package import, current export/import round trip including resources, clone of
the supplied legacy course, unique enrollment code, nested content and grading
policy, and rollback after an invalid import. Use isolated SQLite and temporary
media, never a live installation.
