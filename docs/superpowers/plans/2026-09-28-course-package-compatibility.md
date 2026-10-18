# Course Package Compatibility Implementation Plan

**Goal:** Validate old and current course packages and reliably clone content.

**Architecture:** An archive reader validates the ZIP and manifest once and
returns a safe extracted media directory and normalized data for the existing
transactional importer. The exporter reads Django storage. The clone handler
copies course-owned records and remaps nested references.

**Spec:** `docs/superpowers/specs/2026-09-28-course-package-compatibility-design.md`

## Work

- [x] Add failing tests for the real legacy package, blank/ambiguous email
  matching, package structure validation and atomic failure.
- [x] Add a package validator and wire it into the upload and marketplace views.
- [x] Add export storage and grade-option checks, and test current round trips.
- [x] Add failing tests for clone of a code-required course with resources,
  announcements, nested content, and guest-agent checks.
- [x] Fix clone ownership and reference mapping without student records.
- [x] Run the full repository regression suite and real legacy sample probe;
  document setup and migration steps and publish a reviewable pull request.
