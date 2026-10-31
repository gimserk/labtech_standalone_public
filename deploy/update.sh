#!/usr/bin/env bash
# Noninteractive, conservative updates for a completed native LabTech install.
# Never calls install.sh, rewrites config, regenerates venv, or deletes media.
set -Eeuo pipefail
umask 077
INSTALL_DIR=/opt/labtech
ENV_FILE=/etc/labtech/labtech.env
SETTINGS_FILE=/etc/labtech/deployment_settings.py
BACKUP_ROOT=/var/backups/labtech/updates
LOG_FILE=/var/log/labtech/update.log
OLD_COMMIT=none
NEW_COMMIT=none
BACKUP_DIR=none
PHASE=preflight
DRY_RUN=no
REAPPLY=no
RUN_TESTS=no
# shellcheck source=lib/update_common.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)/lib/update_common.sh"
log() { printf '[labtech-update] %s\n' "$*"; }
fail() { log "ERROR: $*" >&2; return 1; }
as_labtech() { runuser -u labtech -- "$@"; }
git_labtech() { as_labtech git -C "$INSTALL_DIR" "$@"; }
run_manage() {
  as_labtech env PYTHONPATH="/etc/labtech:$INSTALL_DIR" \
    DJANGO_SETTINGS_MODULE=deployment_settings \
    "$INSTALL_DIR/venv/bin/python" "$INSTALL_DIR/manage.py" "$@"
}
usage() {
  cat <<'HELP'
Usage: sudo /opt/labtech/deploy/update.sh [--check | --reapply] [--run-tests]
  --check      Fetch/inspect target revision; change no app code, DB or services.
  --reapply    Retry migrations/static/restarts even when code is already current.
  --run-tests  Require entire Django suite to pass before migration.
No prompts or changes to env/settings, systemd units, Nginx, or uploaded media.
HELP
}
parse_args() {
  while (($#)); do
    case "$1" in
      --check) DRY_RUN=yes ;;
      --reapply) REAPPLY=yes ;;
      --run-tests) RUN_TESTS=yes ;;
      *) fail "Unknown option: $1"; return 1 ;;
    esac
    shift
  done
  if [[ "$DRY_RUN" == yes && "$REAPPLY" == yes ]]; then
    fail '--check and --reapply cannot be combined'; return 1
  fi
}
preflight() {
  [[ "$EUID" == 0 || "${LABTECH_UPDATE_TESTING:-0}" == 1 ]] || { fail 'Run with sudo'; return 1; }
  [[ -d "$INSTALL_DIR/.git" && ! -L "$INSTALL_DIR" ]] ||
    { fail 'Expected /opt/labtech Git checkout'; return 1; }
  [[ -f "$ENV_FILE" && ! -L "$ENV_FILE" &&
     -f "$SETTINGS_FILE" && ! -L "$SETTINGS_FILE" ]] ||
    { fail 'Managed config missing/symlinked; refusing changes'; return 1; }
  [[ -x "$INSTALL_DIR/venv/bin/python" && -f "$INSTALL_DIR/manage.py" ]] ||
    { fail 'Installer-managed virtual environment missing'; return 1; }
  "$INSTALL_DIR/venv/bin/python" -c 'import sys; assert (3,12) <= sys.version_info[:2] <= (3,13)' ||
    { fail 'Current Python runtime is outside supported 3.12/3.13 range'; return 1; }
  id labtech >/dev/null 2>&1 || { fail 'labtech service user missing'; return 1; }
  local binary service unit expected
  for binary in mariadb-dump flock git runuser curl; do
    command -v "$binary" >/dev/null || { fail "Missing tool $binary"; return 1; }
  done
  for service in labtech-web labtech-worker labtech-beat; do
    unit="$(systemctl cat "$service.service")" ||
      { fail "Missing service $service"; return 1; }
    [[ "$unit" == *"EnvironmentFile=$ENV_FILE"* &&
       "$unit" == *"DJANGO_SETTINGS_MODULE=deployment_settings"* ]] ||
      { fail "$service has different settings; will not rewrite them"; return 1; }
    case "$service" in
      labtech-web) expected="$INSTALL_DIR/venv/bin/gunicorn" ;;
      *) expected="$INSTALL_DIR/venv/bin/celery" ;;
    esac
    [[ "$unit" == *"ExecStart=$expected "* ]] ||
      { fail "$service uses a different Python environment"; return 1; }
    systemctl is-active --quiet "$service.service" ||
      { fail "$service inactive; refusing unattended update"; return 1; }
  done
  local origin branch status
  origin="$(git_labtech remote get-url origin)" || return 1
  [[ "$origin" == git@github.com:gimserk/labtech_standalone.git ||
     "$origin" == https://github.com/gimserk/labtech_standalone.git ]] ||
    { fail 'Unexpected Git origin'; return 1; }
  branch="$(git_labtech branch --show-current)" || return 1
  [[ "$branch" == main ]] || { fail 'Git checkout must be on main'; return 1; }
  status="$(git_labtech status --porcelain --untracked-files=no)" || return 1
  [[ -z "$status" ]] ||
    { fail 'Local tracked/staged modifications; refusing overwrite'; return 1; }
  if [[ -L "$INSTALL_DIR/.env" ]]; then
    [[ "$(readlink -- "$INSTALL_DIR/.env")" == "$ENV_FILE" ]] ||
      { fail 'Checkout .env points to an unexpected location'; return 1; }
  elif [[ -e "$INSTALL_DIR/.env" ]]; then
    fail 'Unexpected local .env; review configuration manually'; return 1
  fi
}
fetch_revision() {
  PHASE=fetch
  OLD_COMMIT="$(git_labtech rev-parse HEAD)"
  git_labtech fetch --no-tags origin main || return 1
  NEW_COMMIT="$(git_labtech rev-parse origin/main)"
  git_labtech merge-base --is-ancestor "$OLD_COMMIT" "$NEW_COMMIT" ||
    { fail 'Git history diverged; fast-forward only'; return 1; }
  log "From $OLD_COMMIT to $NEW_COMMIT"
  if [[ "$OLD_COMMIT" != "$NEW_COMMIT" ]]; then
    git_labtech diff --stat "$OLD_COMMIT" "$NEW_COMMIT" -- || return 1
  fi
}
backup_before_change() {
  PHASE=backup
  local info engine database
  info="$(as_labtech env PYTHONPATH="/etc/labtech:$INSTALL_DIR" \
    DJANGO_SETTINGS_MODULE=deployment_settings \
    "$INSTALL_DIR/venv/bin/python" -c \
    'import django; django.setup(); from django.conf import settings; d=settings.DATABASES["default"]; print(d["ENGINE"]); print(d["NAME"])')" || return 1
  engine="$(printf '%s\n' "$info" | sed -n '1p')"
  database="$(printf '%s\n' "$info" | sed -n '2p')"
  [[ "$engine" == django.db.backends.mysql &&
     "$database" =~ ^[A-Za-z][A-Za-z0-9_]{0,63}$ ]] ||
    { fail 'This updater supports the native MariaDB layout only'; return 1; }
  BACKUP_DIR="$BACKUP_ROOT/$(date -u +%Y%m%dT%H%M%SZ)-$$"
  install -d -m 0700 "$BACKUP_DIR" || return 1
  cp -p "$ENV_FILE" "$BACKUP_DIR/labtech.env" || return 1
  cp -p "$SETTINGS_FILE" "$BACKUP_DIR/deployment_settings.py" || return 1
  cp -p "$INSTALL_DIR/requirements.txt" "$BACKUP_DIR/requirements.txt" || return 1
  printf '%s\n' "$OLD_COMMIT" > "$BACKUP_DIR/pre-update-commit.txt"
  mariadb-dump --single-transaction --routines --events --triggers \
    --databases "$database" > "$BACKUP_DIR/database.sql" ||
    { rm -f "$BACKUP_DIR/database.sql"; fail 'DB backup failed'; return 1; }
  [[ -s "$BACKUP_DIR/database.sql" ]] ||
    { fail 'DB backup empty'; return 1; }
  chmod 0600 "$BACKUP_DIR"/* || return 1
  log "Backup: $BACKUP_DIR"
}
sync_code() {
  PHASE=code
  if [[ "$OLD_COMMIT" != "$NEW_COMMIT" ]]; then
    git_labtech merge --ff-only origin/main || return 1
    [[ "$(git_labtech rev-parse HEAD)" == "$NEW_COMMIT" ]] ||
      { fail 'Unexpected HEAD after fast-forward'; return 1; }
  fi
}
sync_dependencies() {
  PHASE=dependencies
  local requirements_change_status=0
  git_labtech diff --quiet "$OLD_COMMIT" "$NEW_COMMIT" -- requirements.txt ||
    requirements_change_status=$?
  [[ "$requirements_change_status" -le 1 ]] ||
    { fail 'Could not verify dependency changes'; return 1; }
  if [[ "$requirements_change_status" == 1 || "$REAPPLY" == yes ]]; then
    log 'Installing pinned dependencies after preserving current virtual environment'
    cp -a "$INSTALL_DIR/venv" "$BACKUP_DIR/venv" || return 1
    as_labtech "$INSTALL_DIR/venv/bin/python" -m pip install \
      -r "$INSTALL_DIR/requirements.txt" || return 1
  else
    log 'Requirements unchanged: keeping current virtual environment'
  fi
}
run_checks() {
  PHASE=validation
  labtech_validate_update_runtime || return 1
  if [[ "$RUN_TESTS" == yes ]]; then
    PHASE=tests
    run_manage test || return 1
  fi
}
apply_update() {
  PHASE=migrations
  [[ -s "$BACKUP_DIR/database.sql" ]] || { fail 'Missing DB backup'; return 1; }
  run_manage migrate --plan || return 1
  labtech_apply_update_schema_and_static || return 1
}
restart_services() {
  PHASE=services
  local unit
  for unit in labtech-worker labtech-beat labtech-web; do
    systemctl restart "$unit.service" || return 1
    systemctl is-active --quiet "$unit.service" ||
      { fail "Failed to start $unit"; return 1; }
  done
}
verify_health() {
  PHASE=health
  local host status maintenance
  host="$("$INSTALL_DIR/venv/bin/python" -c \
    'from dotenv import dotenv_values; print(dotenv_values("/etc/labtech/labtech.env").get("PRIMARY_HOST") or "")')" || return 1
  maintenance="$("$INSTALL_DIR/venv/bin/python" -c \
    'from dotenv import dotenv_values; print(dotenv_values("/etc/labtech/labtech.env").get("MAINTENANCE_MODE") or "False")')" || return 1
  [[ "$host" =~ ^[A-Za-z0-9.-]+$ ]] ||
    { fail 'Invalid existing PRIMARY_HOST'; return 1; }
  status="$(curl --silent --show-error --max-time 15 -o /dev/null \
    -w '%{http_code}' -H "Host: $host" http://127.0.0.1/)" || return 1
  [[ "$status" == 2?? || "$status" == 3?? ||
     ( "$status" == 503 && "$maintenance" == True ) ]] ||
    { fail "HTTP health status $status"; return 1; }
}
on_exit() {
  local rc="$1"
  if ((rc != 0)); then
    log "FAILED phase=$PHASE exit=$rc"
    log "Old=$OLD_COMMIT target=$NEW_COMMIT backup=$BACKUP_DIR log=$LOG_FILE"
    log 'No destructive Git reset or automatic database restore attempted.'
  fi
}
update_main() {
  # EXIT fires on *all* failures, even explicit "|| return 1" paths where
  # Bash's ERR trap would otherwise be skipped.
  trap 'on_exit "$?"' EXIT
  parse_args "$@" || return 1
  preflight || return 1
  [[ ! -L "$BACKUP_ROOT" && ! -L "$LOG_FILE" ]] ||
    { fail 'Backup/log location is a symlink; no changes made'; return 1; }
  install -d -m 0700 /var/log/labtech "$BACKUP_ROOT" /run/labtech || return 1
  [[ ! -L /run/labtech/update.lock ]] ||
    { fail 'Update lock path is a symlink; no changes made'; return 1; }
  exec 9>/run/labtech/update.lock
  flock -n 9 || { fail 'Another upgrade is running'; return 1; }
  touch "$LOG_FILE"; chmod 0600 "$LOG_FILE"
  exec > >(tee -a "$LOG_FILE") 2>&1
  fetch_revision || return 1
  if [[ "$DRY_RUN" == yes ]]; then
    log 'CHECK ONLY: application and data unchanged'; return 0
  fi
  if [[ "$OLD_COMMIT" == "$NEW_COMMIT" && "$REAPPLY" != yes ]]; then
    log 'Already current; use --reapply to retry interrupted upgrades'; return 0
  fi
  backup_before_change || return 1
  sync_code || return 1
  sync_dependencies || return 1
  run_checks || return 1
  apply_update || return 1
  restart_services || return 1
  verify_health || return 1
  log "SUCCESS revision=$NEW_COMMIT backup=$BACKUP_DIR"
}
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  if (($#)) && [[ "$1" == --help || "$1" == -h ]]; then usage
  else update_main "$@"
  fi
fi
