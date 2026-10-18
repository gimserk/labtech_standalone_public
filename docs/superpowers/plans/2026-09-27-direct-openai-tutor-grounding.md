# Direct OpenAI and Course Grounded Tutor Implementation Plan

**Goal:** Restore reliable AI scenario/tutor connectivity and add admin-tuned,
course-grounded tutoring with direct OpenAI as a selectable provider.

**Architecture:** A shared provider adapter supplies URLs, auth and model
configuration to the existing AI paths. A bounded, read-only course search
extracts student-visible text on demand; the tutor proxy owns system instructions
and course access checks. The UI keeps its current streaming behavior.

**Spec:** `docs/superpowers/specs/2026-09-27-direct-openai-tutor-grounding-design.md`

## Task 1: Provider settings and admin diagnostics

- [x] Write failing tests for OpenWebUI defaults, direct OpenAI endpoint/key,
  missing credentials and staff-only connection testing.
- [x] Add provider, behavior, instructions and grounding fields with migration;
  expose them in staff management and Django admin.
- [x] Add a connection test and shared provider adapter, keeping old configurations.

## Task 2: Scenario and generation transport

- [x] Reproduce direct provider failure in scenario role-play/judge and AI
  course-generation tests.
- [x] Route those requests through the provider adapter and configured model;
  preserve scenario completion and generation behavior.

## Task 3: Tutor grounding and authorization

- [x] Write tests for enrolled-course selection, unauthorized course IDs,
  student-visible material retrieval, private/answer exclusion and document
  extraction limits.
- [x] Add server-owned teaching instructions, course chooser and bounded
  material search with labeled sources.

## Task 4: Streaming and integration

- [x] Reproduce split SSE events and prevent loss of streamed tokens.
- [x] Fix browser parsing and remove server-side transcript printing.
- [x] Run the full app tests, migration check and provider-contract tests;
  publish a reviewable PR with operations notes.
