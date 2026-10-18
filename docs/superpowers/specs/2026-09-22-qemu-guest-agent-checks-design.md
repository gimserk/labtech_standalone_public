# QEMU Guest-Agent Lab Checks Design

**Date:** 2026-09-22  
**Status:** Proposed for implementation  
**Repository:** gimserk/labtech  
**Branch:** codex/qemu-guest-checks-design

## Summary

LabTech will add required, per-step validation of student work inside Linux and Windows lab VMs through the Proxmox QEMU guest agent. Instructors configure checks from an allow-listed catalog and attach each check to a lab step and lab machine. Students run the checks from the lab page and receive only safe, instructor-authored guidance. A student cannot finish a checked lab until all current checks have passed, and Finish Lab revalidates every active check against current VM state before cleanup starts.

The first release is deliberately not a remote scripting system. Instructors cannot enter Bash, PowerShell, executable paths, or command templates. Gradebook scoring, optional checks, and an external plugin API are also outside this scope.

## Goals

- Validate concrete VM state without requiring instructors to inspect machines manually.
- Support Linux and Windows guests through one application-facing interface.
- Provide a safe predefined catalog for file, service, identity, package, process, and network checks.
- Make every active configured check required for lab completion.
- Give students useful hints without revealing expected values, private paths, commands, or guest output.
- Revalidate all checks when the student finishes the lab.
- Treat QEMU agent and Proxmox failures as infrastructure failures, never as student failures.
- Give instructors an exact, sanitized attempt history and a way to preview checks on their own lab instance.
- Keep the subsystem isolated from the existing large views module and suitable for adding new built-in check types later.

## Non-goals

- Arbitrary Bash, PowerShell, or instructor-authored scripts.
- Instructor-editable command templates.
- Gradebook points or automatic grading.
- Optional or extra-credit checks.
- Testing directly against shared Proxmox templates.
- A public third-party plugin contract.
- Live Proxmox access in continuous integration.
- Automatic attempt-history retention or archival policy in v1.

## Product behavior

### Instructor configuration

Checks are managed within the existing instructor step-management flow. An instructor can:

1. Select a step and lab machine.
2. Select a check type supported by the machine's configured guest OS.
3. Complete a type-specific form.
4. Provide a required student-facing label and failure hint.
5. Save, reorder, activate, deactivate, or remove the check.
6. Test the saved check against the instructor's own active instance through **Test on My Lab**.

"Remove" is a soft removal that deactivates the check. This preserves attempt history. Testing is encouraged but is not a publishing requirement.

The form is generated from the selected registry entry. Unknown fields, unsupported combinations, values over configured size limits, invalid encodings, and control characters are rejected. Fields designated secret by a check type are write-only after creation and masked in instructor screens.

### Student experience

Each lab step with active checks shows:

- The public labels for its checks.
- The latest status for the current definition of each check.
- A single **Check Work** action.
- The instructor-authored hint for failed checks.
- A neutral retry-later message for infrastructure or configuration failures.

The button is disabled while a run owns the instance validation lease. A configurable cooldown, defaulting to 10 seconds per student, instance, and step, limits repeated submissions. Unlimited retries are allowed after the cooldown.

The **Finish Lab** action is unavailable until the latest results show a pass for every active check at its current definition revision. Clicking Finish Lab then runs every active check again. Cleanup begins only after that fresh run passes in full. A student failure returns the student to the first affected step. An infrastructure or configuration error leaves the instance active and retryable. Labs with no active checks keep their current finish behavior.

### Instructor history

Instructors can review a sanitized attempt history ordered newest first and filter it by student, lab, step, outcome, and run context. History contains:

- Student and lab identifiers.
- Step, machine, and public check-label snapshots.
- Run context: student step, finish revalidation, or instructor preview.
- Pass, fail, infrastructure error, configuration error, or abandoned outcome.
- Start and finish timestamps and duration.
- Safe operational error codes.

History never contains raw commands, raw guest output, credentials, decrypted secret values, or private expected values.

## Check catalog

The initial registry contains these typed checks:

| Category | Check behavior |
| --- | --- |
| File or directory state | Confirm that a file or directory exists or does not exist. |
| File content | Confirm bounded text content using exact or contains matching. Regular expressions are excluded in v1. |
| Service state | Confirm that a named service is running or stopped. |
| User and group | Confirm user existence, group existence, or user membership in a group. |
| Package state | Confirm that a package is installed or absent using supported platform inventory. |
| Process state | Confirm that a named process is running or not running. |
| Listening port | Confirm that a TCP or UDP port is listening or not listening, with an optional local address. |

Paths may be absolute or use a single application-defined home placeholder resolved from the selected LabMachine username. Instructors cannot define environment-variable expansion. File content reads are byte-capped and treated as text only.

Each registry entry has an immutable identifier and defines:

- Supported guest operating systems.
- Public and secret configuration schemas.
- Instructor form fields and validation.
- Linux and Windows command builders.
- Output parser.
- Safe result and error codes.
- A definition revision strategy.

New built-in types are added by registering another validator. This registry is an internal extension boundary, not the future public plugin API.

## Architecture

The feature is split into focused modules rather than added to the existing general views module.

### Check registry

The registry resolves immutable check-type identifiers to validator implementations. It rejects duplicate identifiers at application startup. A validator type cannot be removed while stored checks still reference it; a deployment system check reports that condition.

### Guest-agent executor

The executor is the only component that calls the Proxmox guest-agent API. It accepts a validator-produced command specification rather than arbitrary text and returns a bounded execution result.

Responsibilities include:

- Resolve the selected LabInstanceMachine and its Proxmox server, node, and VM ID.
- Enforce an application-owned executable allow-list.
- Apply command, whole-run, and output-size limits.
- Invoke Linux executables with fixed argument arrays and no shell.
- Invoke only application-owned Windows PowerShell snippets, passing instructor data as a validated encoded payload rather than interpolated script.
- Normalize Proxmox, timeout, missing VM, stopped VM, agent unavailable, exit, and malformed-response conditions.
- Discard raw stdout and stderr after parsing.

### Validation service

The validation service is the only application entry point for running checks. It:

- Authorizes the actor and verifies instance, step, and machine ownership.
- Acquires an expiring per-instance validation lease.
- Enforces the student step cooldown.
- Creates a ValidationRun before external I/O.
- Releases database transactions before calling Proxmox.
- Resolves and executes active checks in stable order.
- Persists sanitized results.
- Releases the lease and derives the overall run outcome.
- Marks expired running records abandoned on a later request.
- Supplies the completion gate with current-revision status.
- Starts the existing cleanup workflow only after a fresh finish run passes.

Views handle request/response concerns only. Instructor and student endpoints call this service and do not construct commands or interpret guest output.

### Secret configuration service

Fields marked secret by a validator are separated from public configuration and encrypted with authenticated encryption using an application-managed key. The service provides encrypt, decrypt-for-execution, masked-display, and key-validation operations. Decrypted values exist only for the duration of a check. The application refuses to save secret fields if the encryption key is missing or invalid.

Key rotation tooling is not included in v1; deployment documentation must state that the key must be backed up and kept stable.

## Data model

### LabMachine changes

Add a nullable guest_os field with linux and windows values. It is logically required before a machine can receive checks, but remains nullable in v1 so existing rows can be classified explicitly. The migration must not guess from template names.

### StepCheck

A StepCheck belongs to one Step and one LabMachine and contains:

- Immutable check-type identifier.
- Schema-validated public configuration.
- Encrypted secret configuration, when applicable.
- Student-facing label and failure hint.
- Display order.
- Active and soft-removed state.
- Definition revision and timestamps.

The selected machine must belong to the same lab as the step. Every active check is required. Editing execution-affecting configuration, machine, type, or expected values increments the definition revision. Editing only the public label or hint does not invalidate a previous technical pass.

### ValidationLease

A ValidationLease has a unique one-to-one relationship with a LabInstance, an owning run, and an expiry. It serializes all validation work for one instance, including step checks and finish validation. Acquisition and stale-lease replacement are atomic. No database lock remains held during Proxmox calls.

### ValidationRun

A ValidationRun stores:

- LabInstance and initiating user.
- Optional step for a step-scoped run.
- Context: student_step, finish, or instructor_preview.
- Status and overall outcome.
- Start, deadline, and finish timestamps.
- Safe summary counts.

Running records that exceed their deadline are marked abandoned on the next service interaction and never count as passes.

### ValidationResult

Each result belongs to one run and references a StepCheck. It snapshots the check identifier, definition revision, public label, step, and machine so history remains understandable after later edits. It stores outcome, safe result code, and duration. It does not store command text, raw output, or decrypted configuration.

The current completion state is derived only from successful results matching each active check's current definition revision. There is no automatic history purge in v1.

## Runtime flows

### Student step run

1. Receive a CSRF-protected POST for a step.
2. Verify authentication, instance ownership, active instance state, lab membership, and target-machine membership.
3. Verify cooldown and atomically acquire the instance lease.
4. Create the run and commit the transaction.
5. Execute active step checks through the registry and guest-agent executor.
6. Persist one sanitized result per check and the overall outcome.
7. Release the lease.
8. Return public labels, outcomes, and instructor hints or generic infrastructure messages.

If the request process ends unexpectedly, the lease and run expire at their stored deadline. A later request marks the run abandoned and safely reacquires the lease.

### Finish run

1. Receive the existing finish request.
2. If the lab has no active checks, follow the current behavior.
3. Otherwise authorize and acquire the instance lease.
4. Run every active check at its current revision.
5. If any check fails, keep the lab active and return the affected step.
6. If any check has an infrastructure or configuration error, keep the lab active and return a retryable generic error.
7. Only after an all-pass result invoke the existing finish/cleanup transition.
8. Make repeated finish submissions idempotent through the existing instance-state rules plus the validation lease.

The validation service must not mark the lab completed or deleting before it has the all-pass result. The narrow gap between validation and cleanup transition is closed by rechecking and updating LabInstance state in one short database transaction after validation.

### Instructor preview

The instructor preview uses the same service, registry, executor, limits, and result persistence. It differs only in authorization, run context, and use of the instructor's own active LabInstance. It never targets the shared LabMachine template directly.

## Security requirements

- No request or stored model field accepts executable paths, shell fragments, PowerShell source, or command templates.
- Every command is selected from application code by a registered validator.
- Linux commands use executable and argument arrays with no shell.
- Windows checks use static application-owned scripts and data-only encoded inputs.
- Configuration is validated on save and again immediately before execution.
- Control characters, oversized values, unsupported encodings, unknown fields, and unsupported OS/type combinations are rejected.
- Authorization and object ownership are verified on every endpoint.
- Student responses expose only public labels, pass/fail state, instructor hints, and generic operational messages.
- Logs and history use safe codes and identifiers only.
- Guest output is capped before parsing and discarded afterward.
- Secret fields use authenticated encryption at rest and are write-only in normal UI.
- CSRF protection applies to every state-changing endpoint.
- Per-instance leases and cooldowns prevent overlapping or abusive execution.
- Proxmox credentials remain server-side and follow the existing configuration path.

## Failure semantics

| Outcome | Meaning | Student effect |
| --- | --- | --- |
| pass | The VM state matches the configured requirement. | The current check revision is satisfied. |
| fail | The VM answered successfully but its state does not match. | Show the instructor hint and allow retry. |
| infrastructure_error | Proxmox, VM, QEMU agent, timeout, transport, or response failure. | Show a generic retry-later message; do not count against the student. |
| configuration_error | The stored check cannot be validated or resolved safely. | Show a generic message; direct instructors to the affected check. |
| abandoned | A running request exceeded its deadline or lost its worker. | Ignore for completion and allow retry after lease expiry. |

A nonzero guest-command exit is interpreted by the validator. Expected negative probes can produce fail rather than infrastructure_error. Transport and protocol failures never produce student fail.

## Configuration defaults

The implementation exposes settings for:

- Step cooldown: 10 seconds.
- Per-command timeout: 5 seconds.
- Whole-run deadline: 45 seconds.
- Maximum guest output: 64 KiB per command.
- Maximum text-file read: 64 KiB.
- Validation lease and stale-run duration: 60 seconds.
- Secret encryption key: a dedicated authenticated-encryption key supplied through deployment settings.

Deployments may lower these limits. Raising them requires an explicit settings change and must remain bounded. The web server and reverse proxy must allow a request to remain open for at least the 45-second run deadline.

## Observability

Structured logs include run ID, instance ID, machine ID, check identifier, context, duration, outcome, and safe error code. They exclude student-provided file content, guest output, command arguments that may contain private values, credentials, and decrypted secrets.

The instructor history supplies operational diagnosis without raw output. Aggregate database queries can report pass, fail, infrastructure, timeout, and duration counts. Integrating an external metrics platform is not required in v1.

## Testing strategy

### Registry and validator unit tests

- Schema acceptance and rejection for every check type.
- Unknown fields, size limits, control characters, invalid encodings, and OS mismatch.
- Linux and Windows command specification generation.
- Output parsing for pass, fail, expected negative probes, malformed output, and caps.
- Registry duplicate and removed-in-use checks.
- Definition revision behavior.

### Security tests

- Attempts to inject shell metacharacters, arguments, executable paths, PowerShell, control characters, and oversized payloads.
- Secret encryption, decryption-for-execution, masking, missing-key failure, and redaction.
- Proof that raw output and commands are absent from results, logs, and responses.
- Cross-user, cross-course, cross-instance, and cross-machine authorization failures.
- CSRF enforcement.

### Service tests

Use a fake guest executor to cover:

- All-pass, mixed-pass/fail, infrastructure, configuration, and abandoned runs.
- Cooldown enforcement and unlimited retries after cooldown.
- Atomic lease acquisition, duplicate suppression, stale lease recovery, and cleanup.
- Step-scoped and whole-lab execution ordering.
- Current-revision completion state.
- No database transaction held during fake external I/O.
- Instructor preview isolation.
- Finish gating and idempotent cleanup handoff.

### View and template tests

- Instructor create, edit, reorder, deactivate, remove, preview, and history flows.
- Type-specific forms and masked secret fields.
- Student labels, statuses, hints, loading state, cooldown state, and generic errors.
- Finish disabled until current checks pass.
- Labs without checks retain existing behavior.

### Proxmox adapter tests

Mock the Proxmox guest-agent client and cover successful commands, nonzero exit, missing/stopped VM, unavailable agent, timeout, malformed response, and output truncation. CI must not require a live Proxmox server or VM.

### Regression verification

Run the existing Django test suite, migration checks, system checks, compilation checks, and the expired-lab cleanup tests. Add a regression proving cleanup is invoked only after a fresh all-pass finish run.

## Rollout and migration

1. Add the new tables and nullable guest_os field.
2. Require instructors or administrators to classify existing lab machines as Linux or Windows.
3. Do not permit check creation for a machine without guest_os.
4. Keep the database column nullable in v1 for backward-compatible rollout; application validation makes it mandatory for any checked machine.
5. Deploy the feature with no checks configured; existing labs behave unchanged.
6. Allow instructors to add and preview checks incrementally.
7. A later operational migration may enforce database-level non-null after every deployment has classified its existing machines.

No data backfill guesses guest OS from template names or credentials.

## Acceptance criteria

- An instructor can configure each catalog check for a compatible Linux or Windows lab machine without entering command text.
- The same saved check can be previewed against the instructor's active instance.
- A student can run step checks repeatedly subject to cooldown and sees only safe labels and hints.
- All active checks are required and passes are valid only for the current definition revision.
- Finish Lab performs fresh whole-lab validation and cannot trigger cleanup on fail, infrastructure error, configuration error, or abandoned execution.
- QEMU agent or Proxmox failures never appear as student failures.
- Instructors can review full sanitized attempt history.
- Raw guest output, commands, credentials, and decrypted expected values are absent from persistence, responses, and normal logs.
- Existing labs without checks and the merged expired-lab cleanup behavior remain unchanged.
- The complete automated suite passes without live Proxmox infrastructure.

## Deferred work

- Gradebook scoring and graded check weights.
- Optional or extra-credit checks.
- Custom scripts and command templates.
- Public plugin packaging and third-party validator discovery.
- Additional guest operating systems.
- Scheduled or automatic background validation.
- History retention, export, and archival controls.
- Encryption-key rotation tooling.
