# LabTech Native Installer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one safe, idempotent Ubuntu 24.04 installer that provisions and updates a complete LabTech production host without destroying its database, uploads, or stable secrets.

**Architecture:** `deploy/install.sh` is the only operator entry point and is sourceable under a guarded test mode so its validation, rendering, and orchestration functions can be tested without root or host mutation. Runtime Python dependencies live in a reviewed production manifest, while the script generates environment-specific Django settings, systemd units, and Nginx configuration outside the checkout. Safe reruns use fast-forward-only Git updates, stable root-owned configuration, pre-migration dumps, staged validation, and health checks.

**Tech Stack:** Bash 5, Ubuntu 24.04, Python 3.12, Django 5.2 LTS, MariaDB, Redis, Gunicorn, Celery, systemd, Nginx, Certbot, ShellCheck, GitHub Actions

**Spec:** `docs/superpowers/specs/2026-09-24-labtech-native-installer-design.md`

## Global Constraints

- Support Ubuntu 24.04 LTS only; reject other distributions/releases before mutation.
- Use Python 3.12 and pin Django to `>=5.2,<5.3`.
- Expose one operator entry point: `deploy/install.sh`.
- Preserve the database, uploaded media, `DJANGO_SECRET_KEY`, and `LAB_CHECK_SECRET_KEY` on every safe rerun.
- Require a preconfigured read-only SSH deploy key for `git@github.com:gimserk/labtech.git`.
- Refuse tracked or staged Git changes; fetch and update `main` with fast-forward-only semantics; never use `git reset --hard` or `git clean`.
- Keep production secrets in `/etc/labtech/labtech.env`, owned by `root:labtech` with mode `0640`; never print them.
- Do not edit tracked `app/settings.py` during installation; generate `/etc/labtech/deployment_settings.py`.
- Treat dependency, Django check, migration-consistency, migration, static-collection, service, and HTTP-health failures as fatal.
- Record full-suite test failures as warnings and continue, ending with `completed with test warnings`.
- Never directly serve `/media/course_audio/` from Nginx.
- Do not alter UFW or cloud firewall rules.

## Review Focus

- Broad, relative, empty, or traversal-containing install paths must be rejected before any recursive ownership or directory operation; pinned by `test_validate_install_dir_rejects_dangerous_paths` in Task 2.
- Existing environment values containing spaces, `#`, quotes, dollar signs, backslashes, or Unicode must survive a read/write rerun without evaluation; pinned by `test_env_round_trip_preserves_literal_values` in Task 3.
- A dirty checkout, wrong remote, diverged branch, or non-Git nonempty directory must stop without overwriting files; pinned by four repository tests in Task 3.
- Certbot failure must retain the validated HTTP site and must not rewrite the stored public URL to HTTPS; pinned by `test_certbot_failure_keeps_http_configuration` in Task 6.
- Full-suite failure may continue, but any required check failure must stop before migration or service restart; pinned by `test_test_failure_warns_but_check_failure_stops_activation` in Task 7.

---

### Task 1: Production dependency contract and shell test harness

**Files:**
- Create: `requirements-production.txt`
- Create: `deploy/install.sh`
- Create: `deploy/tests/test_install.sh`
- Create: `.github/workflows/installer-tests.yml`

**Interfaces:**
- Consumes: the existing `requirements.txt` and imports under `app/`.
- Produces: sourceable `deploy/install.sh`; `main(args...) -> exit status`; reusable test helpers `assert_eq`, `assert_contains`, `assert_not_contains`, and `run_test`; production dependency manifest consumed by Task 4.

- [ ] **Step 1: Write the failing shell-contract tests**

Create `deploy/tests/test_install.sh` with a temporary workspace, assertion helpers, and these initial tests:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
INSTALLER="$PROJECT_ROOT/deploy/install.sh"
TEST_TMP="$(mktemp -d)"
trap 'rm -rf -- "$TEST_TMP"' EXIT

assert_eq() { [[ "$1" == "$2" ]] || { printf 'expected <%s>, got <%s>\n' "$1" "$2" >&2; return 1; }; }
assert_contains() { [[ "$1" == *"$2"* ]] || { printf 'missing <%s>\n' "$2" >&2; return 1; }; }
assert_not_contains() { [[ "$1" != *"$2"* ]] || { printf 'unexpected <%s>\n' "$2" >&2; return 1; }; }

test_source_has_no_side_effects() {
  local output
  output="$(LABTECH_INSTALL_TESTING=1 bash -c 'source "$1"; printf sourced' _ "$INSTALLER")"
  assert_eq "sourced" "$output"
}

test_help_does_not_require_root() {
  local output
  output="$(LABTECH_INSTALL_EUID=1000 "$INSTALLER" --help)"
  assert_contains "$output" "Ubuntu 24.04"
  assert_contains "$output" "safe rerun"
}

test_production_requirements_pin_django_lts() {
  grep -Fx 'Django>=5.2,<5.3' "$PROJECT_ROOT/requirements-production.txt"
  grep -Fx 'mysqlclient>=2.2,<3' "$PROJECT_ROOT/requirements-production.txt"
  grep -Fx 'celery[redis]>=5.4,<6' "$PROJECT_ROOT/requirements-production.txt"
}

run_test() {
  local name="$1"
  printf 'TEST %s\n' "$name"
  "$name"
}

for test_name in $(declare -F | awk '{print $3}' | grep '^test_' | sort); do
  run_test "$test_name"
done
```

- [ ] **Step 2: Run the harness and confirm the contract is absent**

Run: `bash deploy/tests/test_install.sh`

Expected: FAIL because `deploy/install.sh` and `requirements-production.txt` do not exist.

- [ ] **Step 3: Add the dependency manifest and guarded installer skeleton**

Create `requirements-production.txt` with reviewed compatible ranges for every imported third-party module:

```text
Django>=5.2,<5.3
gunicorn>=23,<24
mysqlclient>=2.2,<3
python-dotenv>=1,<2
whitenoise>=6.8,<7
celery[redis]>=5.4,<6
django-allauth>=65,<66
django-ckeditor>=6.7,<7
django-payments>=3,<4
django-crispy-forms>=2.3,<3
crispy-bootstrap5>=2024.10,<2027
django-phonenumber-field[phonenumbers]>=8,<9
Pillow>=10,<13
requests>=2.32,<3
beautifulsoup4>=4.12,<5
docker>=7,<8
proxmoxer>=2.2,<3
paramiko>=3.4,<5
PyJWT>=2.9,<3
paho-mqtt>=2.1,<3
stripe>=11,<15
squareup>=40,<50
cryptography>=42,<47
```

Before committing, build a Python 3.12 virtualenv and resolve this file. If any upper bound excludes the current compatible release or an import fails, adjust the narrowest affected bound and record the resolved version in the commit message body.

Create executable `deploy/install.sh`:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail

readonly SCRIPT_NAME="${0##*/}"
REPOSITORY_SSH="${LABTECH_REPOSITORY_SSH:-git@github.com:gimserk/labtech.git}"
TARGET_BRANCH="${LABTECH_TARGET_BRANCH:-main}"

usage() {
  cat <<'EOF'
Usage: sudo ./install.sh [--help]

Install or safely rerun LabTech on Ubuntu 24.04. Existing databases,
uploads, and stable secrets are preserved. A read-only GitHub deploy key
must already be available to root.
EOF
}

main() {
  case "${1:-}" in
    --help) usage ;;
    *) usage >&2; return 64 ;;
  esac
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
```

- [ ] **Step 4: Add continuous shell validation**

Create `.github/workflows/installer-tests.yml`:

```yaml
name: Installer tests
on:
  pull_request:
    paths:
      - 'deploy/**'
      - 'requirements-production.txt'
      - '.github/workflows/installer-tests.yml'
  push:
    branches: [main]
    paths:
      - 'deploy/**'
      - 'requirements-production.txt'
jobs:
  shell:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - name: Install ShellCheck
        run: sudo apt-get update && sudo apt-get install -y shellcheck
      - name: ShellCheck
        run: shellcheck deploy/install.sh deploy/tests/test_install.sh
      - name: Installer unit tests
        run: bash deploy/tests/test_install.sh
```

- [ ] **Step 5: Verify and commit the foundation**

Run:

```bash
chmod +x deploy/install.sh deploy/tests/test_install.sh
bash deploy/tests/test_install.sh
shellcheck deploy/install.sh deploy/tests/test_install.sh
python3.12 -m venv /tmp/labtech-requirements-check
/tmp/labtech-requirements-check/bin/pip install -r requirements.txt -r requirements-production.txt
/tmp/labtech-requirements-check/bin/pip check
```

Expected: all shell tests pass, ShellCheck reports no findings, dependency resolution succeeds, and `pip check` reports no broken requirements.

Commit:

```bash
git add requirements-production.txt deploy/install.sh deploy/tests/test_install.sh .github/workflows/installer-tests.yml
git commit -m "build: define production installer dependencies"
```

### Task 2: Preflight validation, locking, and safe paths

**Files:**
- Modify: `deploy/install.sh`
- Modify: `deploy/tests/test_install.sh`

**Interfaces:**
- Consumes: guarded installer skeleton from Task 1.
- Produces: `die(message)`, `warn(message)`, `log(message)`, `require_root()`, `require_ubuntu_2404()`, `validate_install_dir(path)`, `validate_db_identifier(value)`, `validate_hostname(value)`, `validate_http_url(value)`, `validate_origin_csv(value)`, `acquire_install_lock()`, and `run_preflight()`.

- [ ] **Step 1: Write validation and platform tests**

Add tests that source the installer with `LABTECH_INSTALL_TESTING=1` and call each function in a subshell:

```bash
test_validate_install_dir_rejects_dangerous_paths() {
  local path
  for path in '' / /opt /etc /usr /var relative ../escape /opt/../etc; do
    if (validate_install_dir "$path" >/dev/null 2>&1); then
      printf 'accepted dangerous path: %s\n' "$path" >&2
      return 1
    fi
  done
  validate_install_dir /opt/labtech
}

test_identifier_and_url_validation() {
  validate_db_identifier labtech_db
  ! validate_db_identifier 'labtech-db;DROP' >/dev/null 2>&1
  validate_hostname beta.example.com
  ! validate_hostname 'https://beta.example.com/path' >/dev/null 2>&1
  validate_http_url https://beta.example.com
  ! validate_http_url 'ftp://beta.example.com' >/dev/null 2>&1
  validate_origin_csv 'https://beta.example.com,http://127.0.0.1:8000'
  ! validate_origin_csv 'https://good.example/path' >/dev/null 2>&1
}

test_platform_and_root_are_checked_before_mutation() {
  ( EFFECTIVE_UID=1000; ! require_root >/dev/null 2>&1 )
  OS_RELEASE_FILE="$TEST_TMP/jammy"
  printf 'ID=ubuntu\nVERSION_ID="22.04"\n' >"$OS_RELEASE_FILE"
  ! require_ubuntu_2404 >/dev/null 2>&1
}
```

- [ ] **Step 2: Run tests and verify failure**

Run: `bash deploy/tests/test_install.sh`

Expected: FAIL with missing validation functions.

- [ ] **Step 3: Implement preflight functions without mutation**

Add constants that allow path injection only in test mode and implement canonical-path rejection:

```bash
OS_RELEASE_FILE="${LABTECH_OS_RELEASE:-/etc/os-release}"
EFFECTIVE_UID="${LABTECH_INSTALL_EUID:-$EUID}"
LOCK_FILE="${LABTECH_LOCK_FILE:-/run/lock/labtech-install.lock}"

log() { printf '[labtech] %s\n' "$*"; }
warn() { printf '[labtech] WARNING: %s\n' "$*" >&2; }
die() { printf '[labtech] ERROR: %s\n' "$*" >&2; return 1; }

require_root() { [[ "$EFFECTIVE_UID" == 0 ]] || die "run as root with sudo"; }

validate_db_identifier() { [[ "$1" =~ ^[A-Za-z][A-Za-z0-9_]{0,63}$ ]]; }
validate_hostname() { [[ "$1" =~ ^([A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)*[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?$ ]]; }
validate_http_url() { [[ "$1" =~ ^https?://[^/[:space:]]+(:[0-9]{1,5})?$ ]]; }

validate_install_dir() {
  local raw="$1" canonical
  [[ "$raw" == /* && "$raw" != *'/../'* && "$raw" != */.. ]] || return 1
  canonical="$(realpath -m -- "$raw")"
  case "$canonical" in ''|/|/opt|/etc|/usr|/var|/home|/root) return 1;; esac
  [[ "$canonical" == /opt/* || "$canonical" == /srv/* ]]
}
```

Implement `validate_origin_csv` by splitting on commas and requiring each entry to satisfy `validate_http_url`. Implement `require_ubuntu_2404` by reading only `ID` and `VERSION_ID` from the selected os-release file. Implement `acquire_install_lock` with file descriptor 9 and nonblocking `flock -n 9`. `run_preflight` calls root, platform, lock, disk-space, and required-command checks before package or filesystem mutation.

- [ ] **Step 4: Run tests, ShellCheck, and commit**

Run:

```bash
bash deploy/tests/test_install.sh
shellcheck deploy/install.sh deploy/tests/test_install.sh
```

Expected: PASS with no ShellCheck findings.

Commit:

```bash
git add deploy/install.sh deploy/tests/test_install.sh
git commit -m "feat: validate installer preconditions"
```

### Task 3: Prompts, stable secrets, configuration, and safe Git synchronization

**Files:**
- Modify: `deploy/install.sh`
- Modify: `deploy/tests/test_install.sh`

**Interfaces:**
- Consumes: validation and logging functions from Task 2.
- Produces: associative array `CONFIG`; `load_existing_config(path)`, `prompt_value(key,prompt,default,validator)`, `prompt_secret(key,prompt)`, `ensure_generated_secrets()`, `write_env_file(path)`, `backup_managed_file(path)`, `verify_git_access()`, and `sync_repository(install_dir)`.

- [ ] **Step 1: Write literal round-trip and repository safety tests**

Use local temporary Git repositories so tests need no network:

```bash
test_env_round_trip_preserves_literal_values() {
  local env_file="$TEST_TMP/labtech.env"
  CONFIG=()
  CONFIG[EMAIL_HOST_PASSWORD]='sp ace#"$\\Unicode-✓'
  CONFIG[DJANGO_SECRET_KEY]='stable-secret'
  write_env_file "$env_file"
  CONFIG=()
  load_existing_config "$env_file"
  assert_eq 'sp ace#"$\\Unicode-✓' "${CONFIG[EMAIL_HOST_PASSWORD]}"
  assert_eq 'stable-secret' "${CONFIG[DJANGO_SECRET_KEY]}"
  [[ "$(stat -c '%a' "$env_file")" == 640 ]]
}

test_existing_secrets_are_not_rotated() {
  CONFIG=([DJANGO_SECRET_KEY]='keep-django' [DB_PASSWORD]='keep-db' [LAB_CHECK_SECRET_KEY]='keep-fernet')
  ensure_generated_secrets
  assert_eq keep-django "${CONFIG[DJANGO_SECRET_KEY]}"
  assert_eq keep-db "${CONFIG[DB_PASSWORD]}"
  assert_eq keep-fernet "${CONFIG[LAB_CHECK_SECRET_KEY]}"
}

test_dirty_checkout_is_refused() { make_git_fixture clean; printf dirty >>"$FIXTURE_WORK/README"; ! sync_repository "$FIXTURE_WORK"; }
test_wrong_remote_is_refused() { make_git_fixture wrong_remote; ! sync_repository "$FIXTURE_WORK"; }
test_diverged_checkout_is_refused() { make_git_fixture diverged; ! sync_repository "$FIXTURE_WORK"; }
test_non_git_nonempty_directory_is_refused() { mkdir -p "$TEST_TMP/not-git"; : >"$TEST_TMP/not-git/data"; ! sync_repository "$TEST_TMP/not-git"; }
```

`make_git_fixture` creates a bare expected origin plus a working clone and can add a wrong origin or divergent local commit. Set `REPOSITORY_SSH` and `TARGET_BRANCH` to the fixture values after sourcing in test mode.

- [ ] **Step 2: Run tests and verify failure**

Run: `bash deploy/tests/test_install.sh`

Expected: FAIL with missing configuration and repository functions.

- [ ] **Step 3: Implement non-evaluating environment persistence**

Declare `CONFIG` as an associative array. Write every value as a JSON-compatible double-quoted dotenv value using Python's standard library; read only `KEY=<JSON string>` records with `json.loads`, never `source` or `eval` the file:

```bash
env_quote() {
  python3 -c 'import json,sys; print(json.dumps(sys.stdin.read(), ensure_ascii=False))'
}

write_env_file() {
  local target="$1" temp key
  temp="$(mktemp "${target}.tmp.XXXXXX")"
  for key in "${ENV_KEYS[@]}"; do
    printf '%s=' "$key" >>"$temp"
    printf '%s' "${CONFIG[$key]-}" | env_quote >>"$temp"
  done
  set_managed_owner "$temp" root labtech
  chmod 0640 "$temp"
  mv -f -- "$temp" "$target"
}
```

`ENV_KEYS` is an ordered array containing `INSTALL_DIR`, `PRIMARY_HOST`, `SITE_URL`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_SSL`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `SQUARE_APP_ID`, `SQUARE_ACCESS_TOKEN`, `SQUARE_LOCATION_ID`, `SQUARE_ENVIRONMENT`, `GUACAMOLE_URL`, `GUACAMOLE_ADMIN_USER`, `GUACAMOLE_ADMIN_PASSWORD`, `GUACAMOLE_SSO_SECRET_KEY`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `LAB_CHECK_SECRET_KEY`, `LAB_CHECK_STEP_COOLDOWN_SECONDS`, `LAB_CHECK_COMMAND_TIMEOUT_SECONDS`, `LAB_CHECK_RUN_DEADLINE_SECONDS`, `LAB_CHECK_MAX_OUTPUT_BYTES`, `LAB_CHECK_MAX_FILE_BYTES`, `LAB_CHECK_LEASE_SECONDS`, `AUDIO_MAX_UPLOAD_BYTES`, `ENABLE_TLS`, and `CERTBOT_EMAIL`.

`load_existing_config` uses a short embedded Python program to validate keys against `ENV_KEYS`, decode the JSON string, reject duplicate keys and newlines, and emit NUL-delimited key/value pairs consumed with `read -r -d ''`. This keeps `$()`, backticks, and shell metacharacters literal. File ownership is applied through `set_managed_owner(path, owner, group)`, which performs `chown` in production and records/no-ops under `LABTECH_INSTALL_TESTING=1`, so the tests run as an ordinary CI user.

Generate the Django key with `secrets.token_urlsafe(50)`, the database password with `secrets.choice` over ASCII letters and digits, and the lab-check key with `cryptography.fernet.Fernet.generate_key()` after dependency installation or an equivalent URL-safe 32-byte standard-library encoding before it. Only generate a key that is absent or empty.

- [ ] **Step 4: Implement prompts, backups, and Git synchronization**

`prompt_value` retains an existing value on empty input and validates new input. `prompt_secret` prints only whether an existing value is retained. Reject newline-containing input.

`backup_managed_file` copies an existing file to `/var/backups/labtech/config/<timestamp>/` with mode `0600` before replacement.

`sync_repository` implements exactly these branches:

```bash
if [[ ! -e "$install_dir" ]]; then
  runuser -u labtech -- git clone --branch "$TARGET_BRANCH" --single-branch "$REPOSITORY_SSH" "$install_dir"
elif [[ ! -d "$install_dir/.git" ]]; then
  [[ -z "$(find "$install_dir" -mindepth 1 -maxdepth 1 -print -quit)" ]] || die "non-Git installation directory is not empty"
  rmdir -- "$install_dir"
  runuser -u labtech -- git clone --branch "$TARGET_BRANCH" --single-branch "$REPOSITORY_SSH" "$install_dir"
else
  local origin status
  origin="$(git -C "$install_dir" remote get-url origin)"
  [[ "$origin" == "$REPOSITORY_SSH" ]] || die "unexpected Git origin: $origin"
  status="$(git -C "$install_dir" status --porcelain --untracked-files=no)"
  [[ -z "$status" ]] || die "tracked or staged repository changes must be resolved"
  runuser -u labtech -- git -C "$install_dir" fetch origin "$TARGET_BRANCH"
  git -C "$install_dir" merge-base --is-ancestor HEAD "origin/$TARGET_BRANCH" \
    || die "local branch has diverged from origin/$TARGET_BRANCH"
  runuser -u labtech -- git -C "$install_dir" merge --ff-only "origin/$TARGET_BRANCH"
fi
```

Before this branch, log `git status --porcelain --untracked-files=only` without deleting those paths. `verify_git_access` runs `git ls-remote "$REPOSITORY_SSH" "refs/heads/$TARGET_BRANCH"` with `BatchMode=yes` and a finite connection timeout.

- [ ] **Step 5: Verify and commit**

Run:

```bash
bash deploy/tests/test_install.sh
shellcheck deploy/install.sh deploy/tests/test_install.sh
```

Expected: literal values round-trip, stable keys remain unchanged, all unsafe repository states stop, and clean fixture updates fast-forward.

Commit:

```bash
git add deploy/install.sh deploy/tests/test_install.sh
git commit -m "feat: preserve installer configuration safely"
```

### Task 4: Host provisioning, database, Python environment, and deployment settings

**Files:**
- Modify: `deploy/install.sh`
- Modify: `deploy/tests/test_install.sh`

**Interfaces:**
- Consumes: `CONFIG`, safe paths, dependency manifest, and backup functions from Tasks 1-3.
- Produces: `install_system_packages()`, `ensure_service_user()`, `ensure_directories()`, `provision_mariadb()`, `provision_redis()`, `build_python_environment()`, `render_deployment_settings()`, `install_deployment_settings()`, and `run_manage(args...)`.

- [ ] **Step 1: Write rendering and command-sequencing tests**

Add a command-recorder stub directory to `PATH` and tests that assert:

```bash
test_mariadb_provisioning_never_drops_data() {
  provision_mariadb
  local sql="$(cat "$COMMAND_LOG")"
  assert_contains "$sql" 'CREATE DATABASE IF NOT EXISTS'
  assert_contains "$sql" 'GRANT ALL PRIVILEGES ON `labtech_db`.*'
  assert_not_contains "$sql" 'DROP DATABASE'
  assert_not_contains "$sql" 'DROP USER'
}

test_deployment_settings_override_hard_coded_hosts_and_storage() {
  local rendered
  rendered="$(render_deployment_settings)"
  assert_contains "$rendered" 'ALLOWED_HOSTS = csv_env("ALLOWED_HOSTS")'
  assert_contains "$rendered" 'CSRF_TRUSTED_ORIGINS = csv_env("CSRF_TRUSTED_ORIGINS")'
  assert_contains "$rendered" '"staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"}'
  assert_contains "$rendered" 'DATABASES["default"]["PASSWORD"] = env("DB_PASSWORD")'
}

test_python_environment_installs_both_manifests() {
  build_python_environment
  local commands="$(cat "$COMMAND_LOG")"
  assert_contains "$commands" 'pip install --upgrade pip setuptools wheel'
  assert_contains "$commands" 'pip install -r requirements.txt -r requirements-production.txt'
  assert_contains "$commands" 'pip check'
}
```

- [ ] **Step 2: Run tests and verify failure**

Run: `bash deploy/tests/test_install.sh`

Expected: FAIL with missing provisioning functions.

- [ ] **Step 3: Implement package, identity, directory, MariaDB, and Redis provisioning**

Install the exact Ubuntu packages through one noninteractive `apt-get install` call. Create `labtech` as a system user with `/home/labtech` and `/bin/bash` when absent; reject an existing account whose UID is 0.

Create and permission:

```text
/etc/labtech                 root:labtech 0750
/var/lib/labtech             labtech:labtech 0750
/var/log/labtech             labtech:labtech 0750
/var/backups/labtech         root:root 0700
/opt/labtech/app/mediafiles  labtech:labtech 0750
```

Provision MariaDB using SQL on standard input rather than `mysql -e` command arguments. Backtick only identifiers that already passed `validate_db_identifier`; quote the generated alphanumeric password. Use `CREATE DATABASE IF NOT EXISTS ... CHARACTER SET utf8mb4`, `CREATE USER IF NOT EXISTS`, `ALTER USER`, `GRANT`, and `FLUSH PRIVILEGES`. Enable/start `mariadb` and `redis-server` and verify both respond.

- [ ] **Step 4: Build the virtualenv and generated settings**

Create or repair `$INSTALL_DIR/venv`, then run both requirements manifests and `pip check` as `labtech`. Create the checkout `.env` symlink only after refusing any existing non-symlink path; preserve the external environment file.

`render_deployment_settings` outputs valid Python with helpers that use `os.environ` first and fall back to `dotenv_values('/etc/labtech/labtech.env')`. It overrides the database, host/origin/site URL, secure cookies, proxy header, SMTP behavior, Redis, and `STORAGES`. If `EMAIL_HOST` is empty, select `django.core.mail.backends.console.EmailBackend`; otherwise select SMTP and honor the selected SSL/TLS flags.

`run_manage` is the sole management-command interface:

```bash
run_manage() {
  runuser -u labtech -- env \
    PYTHONPATH="/etc/labtech:$INSTALL_DIR" \
    DJANGO_SETTINGS_MODULE=deployment_settings \
    "$INSTALL_DIR/venv/bin/python" "$INSTALL_DIR/manage.py" "$@"
}
```

Compile the generated settings with `python -m py_compile` before atomically installing it as `root:labtech 0640`.

- [ ] **Step 5: Verify and commit**

Run:

```bash
bash deploy/tests/test_install.sh
shellcheck deploy/install.sh deploy/tests/test_install.sh
python3 -m py_compile /tmp/rendered-deployment-settings.py
```

Expected: all tests pass, generated settings compile, and recorded SQL contains no destructive statement.

Commit:

```bash
git add deploy/install.sh deploy/tests/test_install.sh
git commit -m "feat: provision LabTech runtime dependencies"
```

### Task 5: Gunicorn and Celery systemd services

**Files:**
- Modify: `deploy/install.sh`
- Modify: `deploy/tests/test_install.sh`

**Interfaces:**
- Consumes: installation paths, service user, deployment settings, and virtualenv from Task 4.
- Produces: `render_web_unit()`, `render_worker_unit()`, `render_beat_unit()`, `verify_unit_file(path)`, `install_systemd_units()`, and `activate_application_services()`.

- [ ] **Step 1: Write exact unit-content and validation-order tests**

```bash
test_systemd_units_run_unprivileged_and_use_production_settings() {
  local web worker beat
  web="$(render_web_unit)"; worker="$(render_worker_unit)"; beat="$(render_beat_unit)"
  for unit in "$web" "$worker" "$beat"; do
    assert_contains "$unit" 'User=labtech'
    assert_contains "$unit" 'DJANGO_SETTINGS_MODULE=deployment_settings'
    assert_not_contains "$unit" 'User=root'
  done
  assert_contains "$web" '--bind 127.0.0.1:8000'
  assert_contains "$web" '--timeout 90'
  assert_contains "$worker" 'celery -A app worker'
  assert_contains "$beat" '--schedule=/var/lib/labtech/celerybeat-schedule'
}

test_units_are_verified_before_daemon_reload() {
  install_systemd_units
  assert_command_order 'systemd-analyze verify' 'systemctl daemon-reload'
}
```

- [ ] **Step 2: Run tests and verify failure**

Run: `bash deploy/tests/test_install.sh`

Expected: FAIL with missing unit renderers.

- [ ] **Step 3: Render, validate, and install all three units**

Each unit sets `WorkingDirectory=$INSTALL_DIR`, rendered `Environment=PYTHONPATH=/etc/labtech:$INSTALL_DIR`, fixed `Environment=DJANGO_SETTINGS_MODULE=deployment_settings`, an explicit `$INSTALL_DIR/venv` executable, `Restart=on-failure`, `RestartSec=5`, `UMask=0027`, `PrivateTmp=true`, `NoNewPrivileges=true`, and a writable-path allowance only where required.

Write candidate units to a root-only temporary directory, run `systemd-analyze verify` on all three, back up existing units, atomically install mode `0644`, then call `systemctl daemon-reload`. `activate_application_services` enables and restarts `labtech-web`, `labtech-worker`, and `labtech-beat` only after Task 7's Django activation gates succeed.

- [ ] **Step 4: Verify and commit**

Run:

```bash
bash deploy/tests/test_install.sh
shellcheck deploy/install.sh deploy/tests/test_install.sh
```

Expected: unit tests pass and verification precedes daemon reload in the command log.

Commit:

```bash
git add deploy/install.sh deploy/tests/test_install.sh
git commit -m "feat: configure LabTech systemd services"
```

### Task 6: Nginx, protected media, and optional TLS

**Files:**
- Modify: `deploy/install.sh`
- Modify: `deploy/tests/test_install.sh`

**Interfaces:**
- Consumes: configured hostname/site URL, static/media paths, and web service address.
- Produces: `render_nginx_http_site()`, `install_nginx_site()`, `configure_optional_tls()`, and `NGINX_WARNING`.

- [ ] **Step 1: Write proxy, media-security, validation, and Certbot failure tests**

```bash
test_nginx_denies_course_audio_before_general_media() {
  local config deny_line media_line
  config="$(render_nginx_http_site)"
  assert_contains "$config" 'client_max_body_size 260M;'
  assert_contains "$config" 'proxy_pass http://127.0.0.1:8000;'
  assert_contains "$config" 'proxy_set_header X-Forwarded-Proto $scheme;'
  deny_line="$(grep -n 'location ^~ /media/course_audio/' <<<"$config" | cut -d: -f1)"
  media_line="$(grep -n 'location /media/' <<<"$config" | cut -d: -f1)"
  (( deny_line < media_line ))
  assert_contains "$config" 'return 404;'
}

test_nginx_is_validated_before_reload() {
  install_nginx_site
  assert_command_order 'nginx -t' 'systemctl reload nginx'
}

test_certbot_failure_keeps_http_configuration() {
  CONFIG[SITE_URL]='http://beta.example.com'
  CERTBOT_RC=1
  configure_optional_tls || true
  assert_eq 'http://beta.example.com' "${CONFIG[SITE_URL]}"
  assert_contains "$NGINX_WARNING" 'certificate issuance failed'
  grep -q 'listen 80' "$FAKE_NGINX_SITE"
}
```

- [ ] **Step 2: Run tests and verify failure**

Run: `bash deploy/tests/test_install.sh`

Expected: FAIL with missing Nginx/TLS functions.

- [ ] **Step 3: Implement HTTP Nginx configuration and protected media rule**

Render an HTTP server block with the primary `server_name`, 260 MiB request limit, 90-second proxy timeouts, forwarded headers, static alias, and media locations. The protected location must be:

```nginx
location ^~ /media/course_audio/ {
    return 404;
}
```

Place it before the ordinary `/media/` alias and leave authenticated `/courses/.../audio/.../stream/` and `/download/` routes proxied to Django.

Install with backup/restore safety: write a candidate, back up the current site, atomically replace it, run `nginx -t`, restore the prior file if validation fails, and reload only after success. Enable Nginx but do not change firewall rules.

- [ ] **Step 4: Implement optional Certbot without sacrificing HTTP**

When selected, require a public hostname and certificate email, confirm DNS resolution, then call Certbot's Nginx plugin noninteractively with agreement and redirect flags. Only after success set `SITE_URL=https://...`, update trusted origins, rewrite the environment file, re-run Django/Nginx checks, and restart the three application services so they load the HTTPS settings. On failure, keep the HTTP values and configuration, set `NGINX_WARNING`, and continue to a warning summary.

- [ ] **Step 5: Verify and commit**

Run:

```bash
bash deploy/tests/test_install.sh
shellcheck deploy/install.sh deploy/tests/test_install.sh
```

Expected: protected audio is denied, Nginx reload follows validation, and simulated Certbot failure preserves HTTP.

Commit:

```bash
git add deploy/install.sh deploy/tests/test_install.sh
git commit -m "feat: configure Nginx and optional TLS"
```

### Task 7: Activation gates, database backups, health checks, and end-to-end orchestration

**Files:**
- Modify: `deploy/install.sh`
- Modify: `deploy/tests/test_install.sh`

**Interfaces:**
- Consumes: all functions from Tasks 1-6.
- Produces: `run_required_checks()`, `run_full_tests()`, `database_has_tables()`, `backup_database()`, `apply_django_changes()`, `create_superuser_if_requested()`, `run_activation_pipeline()`, `run_health_checks()`, `print_summary()`, and completed `main()`.

- [ ] **Step 1: Write failure-boundary and orchestration-order tests**

```bash
test_test_failure_warns_but_check_failure_stops_activation() {
  MANAGE_CHECK_RC=0; MANAGE_TEST_RC=1
  run_activation_pipeline
  assert_contains "$INSTALL_RESULT" 'completed with test warnings'
  assert_command_order 'manage.py test --settings=test_settings -v 2' 'manage.py migrate --noinput'

  reset_command_log
  MANAGE_CHECK_RC=1; MANAGE_TEST_RC=0
  ! run_activation_pipeline
  assert_not_contains "$(cat "$COMMAND_LOG")" 'manage.py migrate'
  assert_not_contains "$(cat "$COMMAND_LOG")" 'systemctl restart labtech-web'
}

test_existing_database_is_dumped_before_migration() {
  DATABASE_HAS_TABLES=1
  run_activation_pipeline
  assert_command_order 'mariadb-dump' 'manage.py migrate --noinput'
}

test_services_start_only_after_migrate_and_collectstatic() {
  run_activation_pipeline
  assert_command_order 'manage.py migrate --noinput' 'manage.py collectstatic --noinput'
  assert_command_order 'manage.py collectstatic --noinput' 'systemctl restart labtech-web'
}

test_health_failure_returns_nonzero() {
  CURL_RC=7
  ! run_health_checks
}
```

- [ ] **Step 2: Run tests and verify failure**

Run: `bash deploy/tests/test_install.sh`

Expected: FAIL with missing activation functions.

- [ ] **Step 3: Implement checks, warning-only tests, backup, and Django changes**

`run_required_checks` runs, as hard gates:

```bash
"$INSTALL_DIR/venv/bin/pip" check
run_manage check --deploy
run_manage makemigrations --check --dry-run
```

`run_full_tests` executes `run_manage test --settings=test_settings -v 2`, tees output to the installer log, captures `PIPESTATUS[0]`, and sets `TEST_WARNING=1` without returning failure when tests fail.

`database_has_tables` queries `information_schema.tables`. If true, `backup_database` writes a timestamped single-transaction dump with `--defaults-extra-file` pointing to a mode-0600 temporary client file, avoiding passwords in argv. It removes that temporary file via a function-local trap.

Then run `migrate --noinput` and `collectstatic --noinput`. If requested and no matching superuser exists, call `run_manage createsuperuser` with no password environment variable.

- [ ] **Step 4: Complete main orchestration, health checks, and summary**

Use this phase order in `main`:

```text
parse arguments -> preflight/lock -> load existing config -> prompts
-> OS packages -> user/directories -> Git sync -> Python environment
-> generated settings/env symlink -> MariaDB/Redis -> required checks
-> full tests (warning-only) -> database dump -> migrate -> collectstatic
-> optional superuser -> validated systemd units -> validated HTTP Nginx
-> service activation -> optional TLS -> health checks -> summary
```

Install an `ERR` trap that reports the phase, line, log path, latest dump, and diagnostic commands without expanding secret values.

`run_health_checks` requires active MariaDB, Redis, web, worker, beat, and Nginx units; then uses `curl --fail --silent --show-error --max-time 15 -o /dev/null -H "Host: ${CONFIG[PRIMARY_HOST]}" http://127.0.0.1/`. Curl treats the application's local 2xx/3xx response as success without following a redirect off-host. Any required health failure exits nonzero.

`print_summary` reports healthy versus completed-with-test-warnings, the URL, TLS state, managed locations, firewall ports, service/log commands, remaining allauth admin setup, and warning strings. It prints no `CONFIG` secret values.

- [ ] **Step 5: Run the full shell verification**

Run:

```bash
bash deploy/tests/test_install.sh
shellcheck deploy/install.sh deploy/tests/test_install.sh
bash -n deploy/install.sh deploy/tests/test_install.sh
```

Expected: all tests pass, ShellCheck and Bash syntax checks are clean, failure-boundary tests prove activation ordering.

- [ ] **Step 6: Commit orchestration**

```bash
git add deploy/install.sh deploy/tests/test_install.sh
git commit -m "feat: orchestrate safe LabTech installation"
```

### Task 8: Operator documentation and final verification

**Files:**
- Create: `docs/installation.md`
- Modify: `README.md`
- Verify: `deploy/install.sh`
- Verify: `deploy/tests/test_install.sh`
- Verify: `requirements-production.txt`

**Interfaces:**
- Consumes: the complete installer from Tasks 1-7.
- Produces: documented deploy-key preparation, clean-install/rerun procedure, integration prompts, firewall/TLS steps, diagnostics, backup/restore commands, and final evidence against the design acceptance criteria.

- [ ] **Step 1: Write documentation assertions before the guide**

Add to `deploy/tests/test_install.sh`:

```bash
test_installation_guide_covers_required_operations() {
  local guide="$PROJECT_ROOT/docs/installation.md"
  grep -Fq 'read-only SSH deploy key' "$guide"
  grep -Fq 'sudo ./deploy/install.sh' "$guide"
  grep -Fq 'journalctl -fu labtech-web' "$guide"
  grep -Fq '/var/backups/labtech' "$guide"
  grep -Fq 'course_audio' "$guide"
  grep -Fq 'completed with test warnings' "$guide"
}
```

- [ ] **Step 2: Run the documentation test and verify failure**

Run: `bash deploy/tests/test_install.sh`

Expected: FAIL because `docs/installation.md` does not exist.

- [ ] **Step 3: Write the installation and recovery guide**

Use this exact guide structure, filling each section with the commands and behavior already fixed by the spec and prior tasks:

```markdown
# Installing LabTech on Ubuntu 24.04
## Before you begin
## Configure a read-only SSH deploy key
## Run a clean installation
## Answer the configuration prompts
## Safely rerun or update the installation
## Configure DNS and optional HTTPS
## Verify services and inspect logs
## Configure social login in Django Admin
## Understand protected course audio
## Back up and restore MariaDB
## Diagnose an installation with test warnings
```

The guide must include:

- Ubuntu 24.04 prerequisites and DNS;
- creating and registering a read-only GitHub deploy key without placing private material in the repository;
- downloading/copying the installer and running `sudo ./deploy/install.sh`;
- every prompt and which values may be blank;
- clean-install and safe-rerun behavior;
- service status/log commands;
- ports 22/80/443 and the explicit no-firewall-change policy;
- optional Certbot behavior;
- configuration, media, and backup locations;
- how to inspect a test-warning installation;
- a guarded MariaDB restore procedure that stops services, takes an additional safety dump, and requires the operator to name the exact backup file;
- confirmation that `/media/course_audio/` must return 404 while authenticated course routes handle playback/download;
- social-login application configuration through Django Admin.

Replace the one-line README with the existing title plus a concise project note and link to `docs/installation.md`; do not invent broader product documentation.

- [ ] **Step 4: Run repository and Django verification**

Run in a clean Python 3.12 environment:

```bash
bash deploy/tests/test_install.sh
shellcheck deploy/install.sh deploy/tests/test_install.sh
bash -n deploy/install.sh deploy/tests/test_install.sh
python3.12 -m venv /tmp/labtech-final-venv
/tmp/labtech-final-venv/bin/pip install -r requirements.txt -r requirements-production.txt
/tmp/labtech-final-venv/bin/pip check
DJANGO_SETTINGS_MODULE=test_settings /tmp/labtech-final-venv/bin/python manage.py check
DJANGO_SETTINGS_MODULE=test_settings /tmp/labtech-final-venv/bin/python manage.py makemigrations --check --dry-run
DJANGO_SETTINGS_MODULE=test_settings /tmp/labtech-final-venv/bin/python manage.py test --settings=test_settings -v 2
git diff --check
git status --short
```

Expected: shell/Django checks and tests pass, no pending migrations, no whitespace errors, and only intended files are modified.

- [ ] **Step 5: Perform a disposable Ubuntu 24.04 smoke install**

On a fresh disposable Ubuntu 24.04 VM with a read-only deploy key and DNS-independent HTTP hostname, run the implementation branch twice using the explicit development-only branch override (the production default remains `main`):

```bash
sudo env LABTECH_TARGET_BRANCH=codex/install-automation-implementation ./deploy/install.sh
sudo env LABTECH_TARGET_BRANCH=codex/install-automation-implementation ./deploy/install.sh
sudo systemctl is-active mariadb redis-server nginx labtech-web labtech-worker labtech-beat
curl -I -H 'Host: beta.example.com' http://127.0.0.1/
curl -I -H 'Host: beta.example.com' http://127.0.0.1/media/course_audio/probe.mp3
sudo sha256sum /etc/labtech/labtech.env
```

Expected: both runs succeed; all services are active; the site returns 2xx/3xx; the direct audio path returns 404; the second run preserves the environment-file hash when no prompt values change; Git remains clean. Record VM image/release and command results in the PR description rather than committing machine-specific output.

- [ ] **Step 6: Commit documentation**

```bash
git add docs/installation.md README.md deploy/tests/test_install.sh
git commit -m "docs: add LabTech installation guide"
```

- [ ] **Step 7: Request whole-branch review**

Compare the implementation branch with `main` and request review focused on destructive shell operations, secret leakage, SQL quoting, environment round-tripping, Git refusal paths, activation ordering, Nginx audio protection, and rerun idempotence. Resolve every finding, rerun Step 4, and repeat the disposable two-run smoke test for any change to orchestration, configuration rendering, services, database handling, or Nginx.
