# QEMU Guest-Agent Lab Checks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add secure, required, per-step Linux and Windows VM checks that use the Proxmox QEMU guest agent and revalidate before lab cleanup begins.

**Architecture:** Store typed check definitions and sanitized run history in Django models, resolve check behavior through an internal validator registry, and isolate Proxmox guest execution behind a bounded executor. Thin student and instructor views call one validation service; the existing finish endpoint hands off to cleanup only after a fresh all-pass run.

**Tech Stack:** Python, Django ORM/forms/views/templates, proxmoxer, cryptography/Fernet authenticated encryption, JavaScript fetch, Django TestCase and unittest.mock.

**Spec:** `docs/superpowers/specs/2026-09-22-qemu-guest-agent-checks-design.md`

## Global Constraints

- Support Linux and Windows guests through one registry-facing interface.
- Only application-owned commands and PowerShell snippets may execute; instructors cannot provide scripts, executable paths, or command templates.
- The initial catalog is file/directory state, file content, service state, user/group, package state, process state, and listening port.
- Every active check is required; gradebook scoring and optional checks are out of scope.
- Student step cooldown is 10 seconds, per-command timeout is 5 seconds, whole-run deadline is 45 seconds, guest output is capped at 64 KiB, text-file reads are capped at 64 KiB, and stale leases expire after 60 seconds.
- Finish Lab must re-run every active current-revision check and may request cleanup only after an all-pass run.
- Proxmox, VM, QEMU-agent, timeout, transport, malformed-response, and saved-configuration failures never become student failures.
- Raw commands, guest output, credentials, decrypted secrets, and private expected values must never enter normal logs, responses, ValidationRun, or ValidationResult.
- Existing labs without checks and the merged expired-lab cleanup lifecycle must keep their current behavior.

## Review Focus

- A check edited after a student pass must invalidate that pass without losing historical results; Task 1 and Task 5 pin revision behavior.
- Concurrent step and finish requests for the same instance must never overlap or enqueue cleanup twice; Task 5 pins lease acquisition and idempotency.
- A malicious path, name, expected value, address, or port must remain data and never alter the executable or script; Tasks 2 through 4 pin injection cases.
- Missing/stopped VMs, absent guest agents, command timeouts, oversized output, and worker loss must be retryable infrastructure/abandoned outcomes; Tasks 4 and 5 pin each classification.
- Cross-user, cross-course, cross-step, cross-instance, and cross-machine IDs must return 403/404 without revealing object existence; Tasks 6 and 7 pin authorization boundaries.

## File Map

- `app/lab_check_models.py`: check definitions, leases, runs, and sanitized per-check results.
- `app/models.py`: re-export lab-check models and add the nullable `LabMachine.guest_os` field.
- `app/migrations/0126_lab_check_models.py`: schema, constraints, and indexes; no guessed OS backfill.
- `app/services/lab_checks/types.py`: immutable commands, raw results, decisions, and public run summaries.
- `app/services/lab_checks/registry.py`: validator protocol, registration, lookup, and configuration normalization.
- `app/services/lab_checks/validators.py`: the seven built-in cross-platform validator definitions.
- `app/services/lab_checks/windows_scripts.py`: static application-owned PowerShell source only.
- `app/services/lab_checks/executor.py`: bounded Proxmox QEMU guest-agent adapter.
- `app/services/lab_checks/secrets.py`: authenticated JSON encryption and masked/write-only behavior.
- `app/services/lab_checks/service.py`: authorization-independent orchestration, cooldowns, leases, persistence, and finish outcome.
- `app/services/lab_checks/selectors.py`: current-revision state and sanitized history queries.
- `app/lab_check_forms.py`: metadata and type-specific instructor forms.
- `app/lab_check_views.py`: student run, instructor CRUD/preview/history endpoints.
- `app/views.py`: lab context and guarded finish/cleanup handoff only.
- `app/urls.py`: student and instructor check routes.
- `app/templates/labtech/view_lab.html`: student check panels and finish state.
- `app/templates/labtech/manage_step_checks.html`: ordered instructor list.
- `app/templates/labtech/lab_check_form.html`: typed create/edit form.
- `app/templates/labtech/lab_check_history.html`: sanitized filters and results.
- `app/static/labtech/js/lab_checks.js`: check submission, cooldown, and accessible state updates.
- `app/checks.py` and `app/apps.py`: deployment checks for registry integrity and encryption settings.
- `docs/operations/qemu-lab-checks.md`: guest prerequisites, settings, rollout, and troubleshooting.
- `app/tests/lab_checks/`: focused model, registry, validator, executor, service, view, and security tests.

---

## Execution Files

This implementation plan is intentionally split only to stay within the repository connector's file-size limit. The three documents are one ordered plan:

1. `docs/superpowers/plans/2026-09-22-qemu-guest-agent-checks-foundation.md` — Tasks 1–4: persistence, registry, validators, and Proxmox executor.
2. `docs/superpowers/plans/2026-09-22-qemu-guest-agent-checks-integration.md` — Tasks 5–8: orchestration, student UI, instructor UI, deployment checks, and verification.

Execute Tasks 1 through 8 without reordering. Every task contains its exact files, interfaces, red-green test cycle, verification command, and commit boundary. The foundation file produces the interfaces consumed by the integration file.

