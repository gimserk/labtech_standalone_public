#!/usr/bin/env bash
# Safety test with fake Git/systemd/MariaDB: no production resources touched.
# shellcheck disable=SC1091,SC2317,SC2034
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd -P)"
TMP="$(mktemp -d)"
trap 'rm -rf -- "$TMP"' EXIT
fail_test() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
[[ -x "$ROOT/deploy/update.sh" ]] || fail_test 'updater executable bit missing'
export LABTECH_UPDATE_TESTING=1
source "$ROOT/deploy/update.sh"
declare -F labtech_validate_update_runtime >/dev/null || fail_test 'shared checks not sourced'
declare -F labtech_apply_update_schema_and_static >/dev/null || fail_test 'shared migrations not sourced'

mkdir -p "$TMP/app/.git" "$TMP/app/venv/bin" "$TMP/etc" "$TMP/bin"
printf '#!/bin/sh\nexit 0\n' > "$TMP/app/venv/bin/python"
chmod +x "$TMP/app/venv/bin/python"
touch "$TMP/app/manage.py" "$TMP/app/requirements.txt"
printf 'keep-env\n' > "$TMP/etc/labtech.env"
printf 'keep-settings\n' > "$TMP/etc/deployment_settings.py"
INSTALL_DIR="$TMP/app"
ENV_FILE="$TMP/etc/labtech.env"
SETTINGS_FILE="$TMP/etc/deployment_settings.py"
BACKUP_ROOT="$TMP/backups"
MOCK_DIRTY=no
MOCK_BRANCH=main
MOCK_UNIT_PATH="$TMP/app/venv"
MOCK_DIVERGED=no
MOCK_CHANGE=no
mkdir -p "$TMP/bin"
printf '#!/bin/sh\nexit 0\n' > "$TMP/bin/mariadb-dump"
chmod +x "$TMP/bin/mariadb-dump"
export PATH="$TMP/bin:$PATH"
id() { return 0; }
systemctl() {
  case "$1" in
    cat)
      case "$2" in
        labtech-web.service) executable=gunicorn ;;
        *) executable=celery ;;
      esac
      printf 'EnvironmentFile=%s\nEnvironment=DJANGO_SETTINGS_MODULE=deployment_settings\nExecStart=%s/%s --mock\n' \
        "$ENV_FILE" "$MOCK_UNIT_PATH/bin" "$executable"
      ;;
    is-active) return 0 ;;
    restart) printf '%s\n' "$2" >> "$TMP/restarted" ;;
    *) fail_test 'Unexpected systemctl operation' ;;
  esac
}
git_labtech() {
  case "$1" in
    remote) printf '%s\n' git@github.com:gimserk/labtech_standalone.git ;;
    branch) printf '%s\n' "$MOCK_BRANCH" ;;
    status)
      if [[ "$MOCK_DIRTY" == yes ]]; then printf ' M app/settings.py\n'; fi
      ;;
    rev-parse)
      if [[ "$2" == HEAD ]]; then printf 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n'
      else printf 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n'
      fi
      ;;
    fetch) printf 'fetch\n' >> "$TMP/git-actions" ;;
    merge-base) [[ "$MOCK_DIVERGED" != yes ]] ;;
    diff)
      if [[ "$2" == --quiet ]]; then
        [[ "$MOCK_CHANGE" != yes ]]
      fi
      ;;
    merge) printf 'merge\n' >> "$TMP/git-actions" ;;
    *) fail_test "Unexpected Git operation: $*" ;;
  esac
}

preflight || fail_test 'accepted native layout refused'
MOCK_DIRTY=yes
if preflight >/dev/null 2>&1; then fail_test 'dirty tracked files accepted'; fi
MOCK_DIRTY=no
MOCK_BRANCH=dev
if preflight >/dev/null 2>&1; then fail_test 'non-main checkout accepted'; fi
MOCK_BRANCH=main
MOCK_UNIT_PATH="$TMP/old-venv"
if preflight >/dev/null 2>&1; then fail_test 'legacy venv layout accepted'; fi
MOCK_UNIT_PATH="$TMP/app/venv"
mv "$ENV_FILE" "$TMP/etc/temp"
if preflight >/dev/null 2>&1; then fail_test 'missing env file accepted'; fi
mv "$TMP/etc/temp" "$ENV_FILE"
[[ "$(cat "$ENV_FILE")" == keep-env ]] || fail_test 'env modified during preflight'

(
  parse_args --check
  [[ "$DRY_RUN" == yes ]] || fail_test '--check ignored'
)
(
  parse_args --reapply --run-tests
  [[ "$REAPPLY:$RUN_TESTS" == yes:yes ]] || fail_test 'supported options ignored'
)
if (parse_args --unsafe >/dev/null 2>&1); then fail_test 'unknown option accepted'; fi
if (parse_args --check --reapply >/dev/null 2>&1); then fail_test 'conflicting options accepted'; fi

MOCK_DIVERGED=yes
if fetch_revision >/dev/null 2>&1; then fail_test 'diverged checkout accepted'; fi
MOCK_DIVERGED=no
fetch_revision >/dev/null || fail_test 'fetch or fast-forward validation failed'

# The real backup path must preserve current configuration and create a
# nonempty database dump before the code update can proceed.
(
  BACKUP_ROOT="$TMP/db-backups"
  as_labtech() {
    printf 'django.db.backends.mysql\nlabtech_db\n'
  }
  mariadb-dump() {
    printf '%s\n' '-- Minimal complete dump fixture'
  }
  backup_before_change || fail_test 'updater backup failed'
  [[ -s "$BACKUP_DIR/database.sql" ]] || fail_test 'missing SQL backup'
  [[ "$(cat "$BACKUP_DIR/labtech.env")" == keep-env ]] ||
    fail_test 'backup modified environment'
  [[ "$(cat "$BACKUP_DIR/deployment_settings.py")" == keep-settings ]] ||
    fail_test 'backup modified Django settings'
  [[ "$(stat -c '%a' "$BACKUP_DIR/database.sql")" == 600 ]] ||
    fail_test 'database backup must be root-only'
)

(
  BACKUP_DIR="$TMP/nonexistent"
  if apply_update >/dev/null 2>&1; then fail_test 'migrations allowed without DB backup'; fi
)
(
  BACKUP_DIR="$TMP/with-backup"
  mkdir -p "$BACKUP_DIR"
  printf 'database backup\n' > "$BACKUP_DIR/database.sql"
  calls="$TMP/apply-calls"
  run_manage() { printf '%s\n' "$1" >> "$calls"; }
  apply_update
  [[ "$(cat "$calls")" == $'migrate\nmigrate\ncollectstatic' ]] ||
    fail_test 'unexpected shared update stages'
)
(
  calls="$TMP/runtime-calls"
  run_manage() { printf '%s\n' "$1" >> "$calls"; }
  labtech_validate_update_runtime
  [[ "$(cat "$calls")" == $'check\nmakemigrations' ]] ||
    fail_test 'shared validation not used'
)
[[ "$(cat "$ENV_FILE")" == keep-env ]] || fail_test 'env modified by tests'
[[ "$(cat "$SETTINGS_FILE")" == keep-settings ]] || fail_test 'Django settings modified by tests'
printf 'PASS: updater refuses dirty/legacy installs and shares validated DB/static stages\n'
