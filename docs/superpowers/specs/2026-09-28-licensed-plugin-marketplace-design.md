# Licensed plugin Marketplace and external connector design

**Date:** 2026-09-28  
**Status:** Approved written design; implementation planning in progress  
**Repository:** `gimserk/labtech_standalone`

## Purpose and agreed outcomes

Administrators of a licensed standalone LabTech installation can discover, install, update, enable, disable, and inspect supported connectors published by the official `wyocyberrange.com` Marketplace. Connectors extend compatibility with external applications, such as GNS3, without owning LabTech's course, student, grading, or licensing rules. The Marketplace requires an active, verified license. Already installed connectors continue operating for 30 days after ordinary license expiration; then new launches stop. An external lab that began before the deadline may finish its existing timed session, submit its result, and clean up. This design establishes the foundation before a GNS3 connector is built.

Only a LabTech administrator may manage plugins. Students and instructors use the resulting course activities but cannot install code. External activities open in a new tab from a LabTech Launch button. LabTech owns a generic External Assignment content type and computes points or category weights using its existing gradebook policy. A connector may submit a validated result; it cannot modify grading algorithms or student enrollment.

## Evidence in the current standalone application

- `app/views.py` exposes a course-package Marketplace at `/marketplace/` that fetches ZIP `.coursepkg` files using `X-Machine-Fingerprint`. It is not a code-plugin catalog or installer. Course-package imports and their compatibility checks must remain separate.
- `app/licensing_utils.py` retrieves a signed JWT containing an expiration, user limit, and feature flags. `LicenseCheckMiddleware` currently treats any stored license row with no expiration as licensed and returns early for superusers. Neither behavior can authorize the plugin Marketplace.
- `app/gradebook_models.py` has an explicit category/model catalog and `app/gradebook.py` computes results from supported activity attempts. The generic `Grade` row in `app/models.py` is not a sufficient route into the instructor gradebook. Its CSV export and course package/clone paths likewise need to recognize a new core activity type.
- Lab sessions already have background creation, status, timed expiry, and durable cleanup. A future GNS3 connector should integrate through those contracts rather than impersonate a Proxmox VM.
- The native installation keeps application code under `/opt/labtech` and configuration outside the checkout; plugin artifacts must also survive safe Git updates and installer reruns.

## Scope and boundaries

| LabTech core | Connector | Official Marketplace service |
|---|---|---|
| License state, plugin registry, admin controls, stable connector API, launch authorization, External Assignment, grades, course import/export/clone, audit history, session deadlines | External service configuration/health, provision/launch/status/result/cleanup adapters; no direct access to LabTech database | Catalog, compatibility metadata, signed release artifacts, server-side license/entitlement checks, download audit |

Initial release covers the core manager and a small reference connector, with a Marketplace contract ready for official publishing. A separate Marketplace server implementation is necessary for live listings and downloads; this repository alone cannot supply the external server. A production GNS3 connector, electronics simulator, LTI provider, arbitrary Django application loading, and general-purpose plugin-defined database models are separate follow-on work. Existing course packages and the existing course Marketplace continue to operate.

## Approaches and choice

1. **In-process Django packages:** straightforward reuse of Django applications and entry points, but package conflicts, migrations, and import failures may prevent LabTech web and workers from starting.
2. **Configuration-only HTTP connectors:** safest to load, but cannot implement project lifecycle operations or more complex orchestration without expanding core for each service.
3. **Chosen: out-of-process, trusted connector packages:** a small versioned JSON protocol on a local authenticated transport lets a connector call its external service. LabTech remains available if a connector fails, and each connector can carry its own dependencies. The extra local process and installer supervision are accepted operational costs.

Installed code is trusted official Marketplace code, not a sandbox for arbitrary user uploads. Process isolation limits failure and permissions, but does not promise containment of a compromised host-level package.

## Core data and integration contracts

`InstalledConnector` records stable plugin ID, installed version, source release ID, package digest, contract version, enabled/health state, timestamps, and last error. `ConnectorConfiguration` stores nonsecret settings and references to root-readable secret files; never put credentials or raw license tokens in templates, logs, course packages, or launch URLs. `ExternalAssignment` is course/chapter scoped, with title, instructions, points policy, publication and availability settings, connector ID, and a connector-owned opaque activity reference. `ExternalAttempt` or a similarly scoped result record stores student, assignment, external attempt ID, normalized score, completion/result status, update time, and audit source. Persist launch/session IDs and expiry where a timed external lab exists; keep durable cleanup work independent of the license state.

The protocol has an explicit contract version and named operations: validate configuration, health, provision or resume a student session, create a short-lived launch target, query status, and finish/cleanup. Each operation receives only a scoped course, assignment, student, and session identity, not broad database access. Operations that allocate resources require an idempotency key; retries must find the existing external project. Timeouts, bounded payloads, circuit breaking, and audit logging prevent an unhealthy connector from blocking a LabTech request. The connector runs as its own unprivileged identity and talks to core over a local authenticated socket or equivalent transport. Network destinations and required privileges are declared in the release manifest and shown to the administrator.

External grade events use a core-owned, authenticated endpoint or local protocol. LabTech validates the connector identity, installation state, assignment and enrollment scope, numeric score range, result version, and deduplication ID. Replayed events do not produce duplicate attempts or overwrite newer results. The core normalizes score to the assignment point value and then applies the existing points/weighted course policy. Manual instructor override and correction history remain LabTech-owned. A stopped or uninstalled connector does not erase stored assignments or results.

The initial External Assignment is a native LabTech content category, not an arbitrary new gradebook category supplied by plugins. Include it in course management, grade setup, chapter progress, instructor/student gradebook, CSV export, and course copy/import/export. Course packages may carry portable assignment metadata; external connector credentials, external resource IDs tied to the original site, and student attempts are excluded from ordinary clone/import. When the required connector is missing or incompatible, import preserves the assignment as unavailable with a clear instructor warning rather than attempting a launch.

LTI 1.3 launch and Assignment and Grade Services are a future connector option for compatible tools, not a requirement on GNS3. A GNS3 connector would translate the generic launch into its own per-student project workflow.

## Marketplace and administrative lifecycle

Use a dedicated official plugin catalog and release download API, distinct from `/api/marketplace/packages/`. Version its schema and include plugin ID, publisher, display text, release version, required core/API/Python/platform ranges, capabilities, declared outbound destinations, digest, signature, and release status. The exact server URL paths are finalized with the Marketplace repository; the standalone client must not infer compatibility from display strings. The Marketplace verifies the installation's licensed entitlement on catalog and download requests. A fingerprint alone is an identifier, not proof of license entitlement; the client supplies a scoped signed license credential or server-issued short-lived authorization.

Admin flow: list releases and compatibility, select a release, show capabilities and expected external access, confirm installation, download to a bounded staging area, verify transport and publisher signature against a pinned trust root and verify artifact digest, reject archive traversal and undeclared executables, check version/dependencies, install into a versioned directory and isolated runtime outside the Git checkout, apply restricted configuration, start the connector, run health check, and atomically enable the new version. Keep the previous known-good version until health is confirmed. On failure, restore it and report actionable diagnostics. Do not execute package-supplied install scripts as root or run package management inside a web request. A privileged installer helper or queued host-level operator performs the controlled install; web/Celery workers request jobs and display results.

Disabling blocks new launches while allowing existing sessions to finish and cleanup; removal requires no active sessions or a documented finish-and-cleanup workflow. Failed external cleanup stays retryable. Installer reruns preserve installed artifacts, secret files, and the plugin registry, reconcile service definitions, and report incompatible plugins after core upgrades. An update cannot silently grant new capabilities; show them to the administrator before activation.

Only superusers (or a later explicit dedicated administrator permission) can access plugin manager and mutation endpoints, and every request rechecks authorization, CSRF, and license state server-side. Instructor and student pages only expose configured activity launch controls; no core admin APIs or Marketplace credentials are sent to browsers.

## License state machine

The official licensing server adds a `plugins_marketplace_enabled` entitlement to the signed license, tied to the installation fingerprint and a server-issued expiration. Core verifies the signature, issuer/audience or equivalent scoped claims, binding, entitlement, contract end, and dates before using it. A database row, cached `expires_at` field, user role, or unverified JWT cannot grant access. The existing signing-key configuration must remain stable across normal upgrades. No superuser shortcut exists for plugin licensing.

| State | Marketplace browse/install/update | Existing plugin launches | Existing timed sessions, result, cleanup |
|---|---|---|---|
| Active verified entitlement | Allowed after current Marketplace authorization | Allowed | Allowed |
| Ordinary expiration through expiration + 30 days | Blocked | Allowed; display remaining grace | Allowed |
| After the 30-day deadline | Blocked | Blocked | Sessions launched before the deadline may finish only within their already assigned timer; results and cleanup accepted |
| Explicit central revocation or invalid signature/binding | Blocked immediately | Blocked immediately | No new work; permit bounded cleanup and recovery of already launched sessions, with operator notice |

The grace deadline is the signed `exp` (capped by any earlier binding contract end, if that is the contractual expiry) plus exactly 30 calendar days in UTC. Network failure does not create or extend an entitlement; it retains the last locally verified signed claims until their stated deadline. A successful server revocation is recorded durably and overrides cached claims. On renewal the state returns to Active. Warn the administrator before expiration and at each transition, and show students a useful launch-unavailable message after cutoff. Keep cleanup jobs and audit data operational regardless of feature state. If the licensing server wants a different policy for explicit revocation, review that as a separate policy decision before implementation.

## External assignment launch and result flow

An instructor creates an External Assignment and chooses an installed, enabled connector. A student opens the assignment in LabTech and presses Launch. Core authorizes course enrollment, publication, dates, license state, and a compatible connector. A background job provisions or resumes the student session idempotently. Once ready, the browser opens the connector's short-lived, single-use, scoped launch destination in a new tab; no site-wide API token or arbitrary administrator-provided redirect URL is exposed. Core checks destination scheme/host against the connector's approved configuration to avoid open redirects and server-side request forgery.

The student works in the external application. The connector sends authenticated completion and score events back to core, where validation and deduplication precede gradebook calculation. LabTech shows status, grade, and progress on its own pages. On finish or expiry, the connector receives cleanup work with retry and audit state. At license grace cutoff, active sessions keep their existing timeout; no extension or fresh launch is permitted. A connector outage leaves the student assignment readable with a clear retry state, and existing grades remain visible.

## Rollout, verification, and dependencies

1. Implement and test verified plugin license states independently of the current course-package Marketplace. Cover missing/invalid token, signature or machine mismatch, entitlement missing, exact expiration and 30-day boundaries, renewal, revocation, network outage, and superuser access.
2. Define manifest/protocol and implement manager, staged installation, service supervision, audit, version compatibility, rollback, and a harmless reference connector. Test malicious archives, signature/digest mismatch, dependency conflict, slow/crashed connector, interrupted install/update, disabling, reinstall, and core upgrades.
3. Implement Marketplace server catalog, publisher workflow, signed artifacts, license authorization, and downloads in its own repository. End-to-end tests require that repository and a nonproduction licensed fixture; until then the client can be tested against a contract fixture, but live Marketplace integration is unverified.
4. Add core External Assignment, new-tab launch, submission API, gradebook category/points/weights, CSV, import/export and clone behavior. Regression test existing activity types, pending/unattempted scores, student ownership, duplicate/out-of-order result events, and grade preservation on disable.
5. Build GNS3 as a separate connector after the contract works; validate project isolation, provision/resume, console link, session finish, timed expiry, cleanup retry, and concurrency before public use.

The first implementation plan should keep the core licensing/manager and the external-assignment/gradebook work as separately reviewable milestones. This design does not authorize deployment to a live instance or a Marketplace publication without the corresponding service repository and verification.
