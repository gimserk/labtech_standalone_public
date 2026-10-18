# Licensed Plugin Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a licensed standalone LabTech administrator discover official connectors, install signed compatible releases, supervise isolated connector processes, and enforce a 30-day runtime grace period.

**Architecture:** LabTech verifies a plugin-specific entitlement separately from its existing course Marketplace. A versioned connector registry and local protocol keep installed code outside the Django process; a root-owned helper stages signed releases and activates versioned connector services. The official Marketplace server and External Assignment/gradebook are independent follow-on milestones.

**Tech Stack:** Django, PyJWT, `cryptography` Ed25519, Python 3.12–3.13, Celery, systemd, MariaDB, SQLite test settings, Ubuntu 24.04 or newer.

**Spec:** `docs/superpowers/specs/2026-09-28-licensed-plugin-marketplace-design.md`

## Global Constraints

- Target `gimserk/labtech_standalone`; preserve the existing `/marketplace/` course-package routes, imports, and license behavior outside the new plugin routes.
- Only superusers manage connector installation and configuration; students and instructors cannot install executable packages.
- An active, signed, machine-bound `plugins_marketplace_enabled` entitlement permits plugin catalog and installation. Ordinary expiration permits existing plugins to run for exactly 30 calendar days in UTC; it does not permit browsing/installing/updating. New plugin work stops after the deadline. Sessions launched before cutoff may finish within their original deadline, record results, and clean up.
- Explicit revocation or invalid signatures block new work immediately; cleanup remains possible. An outage never extends a verified expiration.
- A connector cannot change LabTech grading, enrollment, or database rules. Code runs in a separate restricted process; no untrusted course ZIP can become a plugin.
- Store plugin artifacts and secrets outside `/opt/labtech`'s tracked Git checkout, preserve them on installer reruns, and avoid executing downloaded install scripts as root.
- This plan delivers a working admin manager against a fixture Marketplace API and a health-only reference connector. Live discovery needs a separately implemented official Marketplace server; External Assignments and GNS3 are later plans.

## Review Focus

1. A stored License row with `expires_at=None` or an expired/forged JWT must never grant even a superuser plugin Marketplace access (Task 1 test).
2. At the precise 30-day UTC boundary, cached tokens and network outage must not authorize new launches or installs; existing session cleanup remains possible (Task 1 test).
3. A correctly signed catalog record with a replaced archive or unsafe archive path must fail before any executable is installed (Task 3 test).
4. Two simultaneous or retried install jobs for the same plugin/version must not create competing activations or lose the prior healthy release (Task 5 test).
5. A crashed or slow connector and a core installer rerun must not make Django unavailable or erase the plugin registry and secrets (Tasks 6 and 7 tests).

---

## File map and milestone boundary

| File or directory | Single responsibility |
|---|---|
| `app/plugin_license.py`, `app/migrations/0015_plugin_revocation.py`, `app/test_plugin_license.py` | Signed claims, entitlement state, revocation and deadline logic |
| `app/plugin_models.py`, `app/migrations/0016_plugin_registry.py`, `app/test_plugin_registry.py` | Installed release, configuration references, job/audit state |
| `app/plugins/package.py`, `app/test_plugin_package.py`, `docs/integrations/plugin-marketplace-api.md` | Manifest/archive verification and wire format |
| `app/plugins/marketplace.py`, `app/plugin_views.py`, `app/plugin_urls.py`, `app/templates/labtech/plugins/`, `app/test_plugin_marketplace.py` | Catalog client and admin UI |
| `deploy/plugin_helper.py`, `deploy/tests/test_plugin_helper.py`, `app/plugins/jobs.py` | Safe staging, atomic activation, rollback and privileged job handoff |
| `app/plugins/transport.py`, `examples/plugins/health_connector/`, `app/test_plugin_transport.py` | Authenticated local connector protocol and reference health connector |
| `deploy/install.sh`, `deploy/tests/test_install.sh`, `docs/operations/plugins.md` | Idempotent service/directory integration and operator recovery |

The follow-on External Assignment plan owns `app/gradebook.py`, `app/gradebook_models.py`, course import/export, student launch, grading events and GNS3-facing session integration. The separate Marketplace server plan owns official catalog publishing and license enforcement on downloads; do not assume this repository deploys that service.

### Task 1: Plugin-specific signed entitlement

**Files:** Create `app/plugin_license.py`, `app/test_plugin_license.py`, `app/migrations/0015_plugin_revocation.py`; modify `app/licensing_utils.py`, `app/models.py`.

**Interfaces:** Produce `PluginEntitlement(state: Literal['active','grace','stopped','revoked'], expires_at: datetime|None, grace_until: datetime|None)` and `get_plugin_entitlement(license_obj: License|None, now: datetime) -> PluginEntitlement`. Consume the existing PEM environment variable and JWT only. Define signed claims `exp`, `fingerprint`, `plugins_marketplace_enabled`; optional `contract_end` caps the entitlement at 00:00 UTC on the following day. Require a non-null stored expiration matching the signed `exp`. `check_and_renew_license()` records explicit HTTP 403 revocation durably and clears it only after successful signed renewal.

- [ ] **Step 1: Write failing tests** in `app/test_plugin_license.py`, including `test_expiration_boundary`: `self.assertEqual(get_plugin_entitlement(license_obj, T).state, 'grace')` and `self.assertEqual(get_plugin_entitlement(license_obj, T + timedelta(days=30)).state, 'stopped')`; `test_missing_expiration_denied`: `self.assertFalse(may_manage_plugin_marketplace(superuser, get_plugin_entitlement(license_obj, now)))`. Also assert signed active permits catalog; absent row, missing flag, wrong fingerprint, forged signature, explicit HTTP 403 and network outage cannot grant new access; cleanup works in every state.
- [ ] **Step 2: Verify failure.** Run `DJANGO_SETTINGS_MODULE=app.test_settings python manage.py test app.test_plugin_license -v 2`; expect missing import or failed assertions.
- [ ] **Step 3: Implement** `get_plugin_entitlement(...)` and `may_manage_plugin_marketplace(user, entitlement) -> bool`. Verify JWT signature while handling an expired but previously valid token for grace calculation; do not trust stored `expires_at` alone. Do not alter existing 10-day non-plugin middleware grace or course-package routes. Store revocation timestamp in `License.plugin_revoked_at` with `0015_plugin_revocation.py`.
- [ ] **Step 4: Verify pass** with the Task 1 command; expect all entitlement tests to pass.
- [ ] **Step 5: Commit** `feat: verify plugin Marketplace entitlements` with the tests, code and migration.

### Task 2: Durable registry and admin audit

**Files:** Create `app/plugin_models.py`, `app/migrations/0016_plugin_registry.py`, `app/test_plugin_registry.py`; modify `app/models.py` to expose the new models in this project's existing model-loading pattern.

**Interfaces:** Define `InstalledConnector(plugin_id: str, version: str, release_id: str, digest: str, contract_version: int, enabled: bool, state: str, last_error: str)` with a unique plugin ID; `ConnectorConfiguration(installed_connector, public_config: dict, secret_path: str)`; `PluginInstallJob(requested_by, plugin_id, release_id, status, error, created_at, finished_at)`; and immutable `PluginAuditEvent(actor_id, plugin_id, action, result, occurred_at)`. A disabled/failed connector never appears as enabled.

- [ ] **Step 1: Write failing tests** such as `test_plugin_id_unique`: `self.assertRaises(IntegrityError, InstalledConnector.objects.create, plugin_id='demo', ...)` after creating `demo`, and `test_disable_keeps_audit`: `self.assertTrue(PluginAuditEvent.objects.filter(plugin_id='demo').exists())` after disabling. Assert job transitions persist and secret values never enter `public_config`.
- [ ] **Step 2: Verify failure.** Run `DJANGO_SETTINGS_MODULE=app.test_settings python manage.py test app.test_plugin_registry -v 2`; expect missing models.
- [ ] **Step 3: Implement** models, constraints, and `0016_plugin_registry.py`; use `DJANGO_SETTINGS_MODULE=app.test_settings python manage.py makemigrations --check --dry-run` after generating the checked-in migration.
- [ ] **Step 4: Verify pass** with the Task 2 tests and `DJANGO_SETTINGS_MODULE=app.test_settings python manage.py check`; expect no pending schema changes or system-check errors.
- [ ] **Step 5: Commit** `feat: persist connector registry and installation audit`.

### Task 3: Release format and trust verification

**Files:** Create `app/plugins/package.py`, `app/test_plugin_package.py`, `docs/integrations/plugin-marketplace-api.md`.

**Interfaces:** Implement `verify_release(metadata: dict, archive_path: Path, public_key_pem: bytes, core_version: str, python_version: tuple[int,int]) -> VerifiedRelease`. Metadata schema version 1 has `plugin_id`, `release_id`, `version`, `contract_version`, `core_min`, `core_max`, `python_min`, `python_max`, `archive_sha256`, `signature`, declared capabilities, outbound destinations, and archive entry point. Signature is Ed25519 over canonical JSON metadata without `signature` (sorted keys, compact separators); archive digest is SHA-256 over exact downloaded bytes. Archive is ZIP, max 128 MiB compressed, 512 MiB inflated, 1000 members, with manifest and packaged wheels. The docs fix the exact schema and distinguish plugin releases from `.coursepkg` endpoints.

- [ ] **Step 1: Write failing tests** including `test_tampered_archive_rejected`: `self.assertRaises(ReleaseVerificationError, verify_release, signed_metadata, tampered_zip, public_key, core_version, python_version)` and `test_valid_release`: `self.assertEqual(verify_release(...).plugin_id, 'demo')`. Cover unknown schema, incompatible versions, changed metadata, duplicate/traversal/symlink members, size limits, and undeclared executable paths before staging.
- [ ] **Step 2: Verify failure.** Run `DJANGO_SETTINGS_MODULE=app.test_settings python manage.py test app.test_plugin_package -v 2`; expect missing verifier.
- [ ] **Step 3: Implement** manifest validation, canonical signature check with `cryptography`, bounded ZIP inspection and `VerifiedRelease` return type; document endpoints `GET /api/marketplace/plugins/` and `GET /api/marketplace/plugins/{plugin_id}/releases/{release_id}/download/`, using a scoped signed entitlement rather than fingerprint alone.
- [ ] **Step 4: Verify pass** with the Task 3 tests; expect rejection before extraction for every hostile case.
- [ ] **Step 5: Commit** `feat: verify signed plugin releases`.

### Task 4: Separate admin plugin Marketplace

**Files:** Create `app/plugins/marketplace.py`, `app/plugin_views.py`, `app/plugin_urls.py`, `app/templates/labtech/plugins/index.html`, `app/test_plugin_marketplace.py`; modify `app/urls.py` to include `/admin-plugins/`, separate from `/marketplace/`.

**Interfaces:** `PluginMarketplaceClient.list_releases(entitlement: PluginEntitlement) -> list[dict]`, `.download(plugin_id: str, release_id: str, destination: Path, entitlement: PluginEntitlement) -> dict`, and `plugin_index_view(request)`; all Marketplace calls use configured HTTPS `PLUGIN_MARKETPLACE_URL` defaulting to `https://www.wyocyberrange.com`, explicit timeouts, and scoped credentials. Mutations are POST and create `PluginInstallJob` only after license and admin authorization.

- [ ] **Step 1: Write failing view/client tests** including `test_unlicensed_superuser_denied`: `self.assertNotEqual(client.get(reverse('plugin_index')).status_code, 200)` and `test_existing_course_marketplace_unchanged`: `self.assertEqual(resolve('/marketplace/').url_name, 'marketplace_list')`. Cover active superuser listing, staff/student denial, grace blocking updates, POST CSRF/method rejection and graceful network/JSON errors.
- [ ] **Step 2: Verify failure.** Run `DJANGO_SETTINGS_MODULE=app.test_settings python manage.py test app.test_plugin_marketplace -v 2`; expect missing routes/client.
- [ ] **Step 3: Implement** the client, plugin URL namespace, admin dashboard, state messages, and a queued install/disable action. Keep credentials out of rendered HTML and server logs.
- [ ] **Step 4: Verify pass** with Task 4 tests; expect all privilege and license gates to pass independently of `LicenseCheckMiddleware`'s superuser early return.
- [ ] **Step 5: Commit** `feat: add licensed admin plugin catalog`.

### Task 5: Staged host installation and rollback

**Files:** Create `deploy/plugin_helper.py`, `deploy/tests/test_plugin_helper.py`, `app/plugins/jobs.py`; extend `app/test_plugin_marketplace.py` for job handling.

**Interfaces:** `enqueue_install(plugin_id: str, release_id: str, actor_id: int) -> PluginInstallJob` records a durable request. `activate_release(job_id: int, *, health_check: Callable[[str], bool]) -> None` accepts an injected health check until Task 6 supplies the real transport. Root-owned `deploy/plugin_helper.py process --job-id N` rechecks entitlement and fetches/validates the release, takes a per-plugin lock, stages under `/var/lib/labtech/plugins/<id>/releases/<version>/`, creates a separate Python 3.12/3.13 virtual environment, installs only declared wheel artifacts with pinned hashes and no source builds, and flips the `current` symlink atomically only after service health succeeds. A root-owned systemd path/oneshot helper consumes bounded job IDs from `/var/lib/labtech/plugin-jobs/`; no arbitrary commands from web input. Package code runs as dedicated unprivileged `labtech-plugin-<id>` (or a stable restricted service identity), never as root.

- [ ] **Step 1: Write failing tests** using temporary paths and mocked package download/systemd, including `test_failed_health_restores_current`: `self.assertEqual(current.resolve(), old_release)` after `activate_release(job_id, health_check=lambda _: False)`, and `test_repeat_job_idempotent`: `self.assertEqual(activated_versions, ['1.0.0'])` after two identical jobs. Cover concurrency, bad signatures, interrupted stage, and disabled connector races.
- [ ] **Step 2: Verify failure.** Run `python -m unittest discover -s deploy/tests -p 'test_plugin_helper.py' -v` and `DJANGO_SETTINGS_MODULE=app.test_settings python manage.py test app.test_plugin_marketplace -v 2`; expect missing helper/job flow.
- [ ] **Step 3: Implement** installer helper, spool job handoff, atomic release activation, rollback and audit updates. The helper trusts only server-signed release metadata and a numeric queued job ID, and never executes a package-supplied root script.
- [ ] **Step 4: Verify pass** with Task 5 tests; expect stable prior release after all simulated failures.
- [ ] **Step 5: Commit** `feat: stage and roll back isolated connector releases`.

### Task 6: Connector protocol and harmless reference

**Files:** Create `app/plugins/transport.py`, `app/test_plugin_transport.py`, `examples/plugins/health_connector/manifest.json`, `examples/plugins/health_connector/connector.py` and its packaging fixture.

**Interfaces:** `ConnectorClient.call(plugin_id: str, operation: Literal['health','validate_configuration','provision','launch','status','finish'], payload: dict, *, timeout: float=5.0) -> dict` uses a per-plugin local Unix socket with a scoped rotating secret and protocol version 1. Unsupported operations produce a typed error. This milestone exercises `health` and `validate_configuration`; other methods are reserved for the External Assignment/GNS3 milestones. Each call bounds message size and elapsed time. Task 5 passes `lambda plugin_id: ConnectorClient().call(plugin_id, 'health', {})['healthy']` as its activation health check.

- [ ] **Step 1: Write failing tests** including `test_health_response`: `self.assertTrue(client.call('demo', 'health', {})['healthy'])` and `test_timeout_is_typed`: `self.assertRaises(ConnectorUnavailable, client.call, 'slow', 'health', {}, timeout=0.01)`. Cover invalid token, protocol mismatch, oversized messages, duplicate plugin ID, and a crashing connector without a Django HTTP 500.
- [ ] **Step 2: Verify failure.** Run `DJANGO_SETTINGS_MODULE=app.test_settings python manage.py test app.test_plugin_transport -v 2`; expect missing client.
- [ ] **Step 3: Implement** the local request/response schema, timeout and circuit behavior, plus a health-only reference connector that holds no student or grade data.
- [ ] **Step 4: Verify pass** with Task 6 tests and the reference connector's local health check; expect typed failure with no unhandled HTTP 500.
- [ ] **Step 5: Commit** `feat: add versioned isolated connector protocol`.

### Task 7: Native installer reconciliation and operator recovery

**Files:** Modify `deploy/install.sh`, `deploy/tests/test_install.sh`, `.env.template`; create `docs/operations/plugins.md`.

**Interfaces:** Native installer creates restricted plugin artifact, spool, and secret directories outside the tracked checkout, installs root-owned helper service/path templates, reloads systemd, and reconciles existing connector services without uninstalling their data. `PLUGIN_MARKETPLACE_URL` and `PLUGIN_MARKETPLACE_PUBLIC_KEY` are preserved in the managed environment, and missing key disables installs with a clear admin message. Provide operator commands to check install jobs, inspect state, retry failed cleanup/activation, roll back, and rotate keys safely.

- [ ] **Step 1: Extend shell fixture tests** such as `test_rerun_preserves_plugin_state`: `[[ "$(readlink "$plugin_root/current")" == 'releases/1.0.0' ]]` and `[[ -f "$secret_root/demo.env" ]]` after two installer invocations. Assert incompatible version warning, missing trust key blocks new install, and connector service failure leaves `labtech-web` active.
- [ ] **Step 2: Verify failure.** Run `bash deploy/tests/test_install.sh`; expect the new fixture assertions to fail.
- [ ] **Step 3: Implement** directory/service setup, environment keys, reconciliation and operator documentation; keep `deploy/install.sh` safe rerun and Python-version checks intact.
- [ ] **Step 4: Verify pass.** Run `bash deploy/tests/test_install.sh`, `DJANGO_SETTINGS_MODULE=app.test_settings python manage.py check`, and the Task 1–6 targeted suites; expect all pass. Run `git diff --check` and inspect that only new plugin URLs were added.
- [ ] **Step 5: Commit** `docs: integrate plugin services with native installer` with code, tests and operations guide.

## Handoff to later milestones

After the reference connector is installable and its health is visible, write a separate plan for the official Marketplace server using its actual repository and deployment contract. Write another for core External Assignment, new-tab launch, result ingestion, gradebook/CSV and course package/clone integration, then build GNS3 as an independent connector. Do not label this foundation as complete end-to-end Marketplace availability until the official service exposes the tested catalog and download endpoints.
