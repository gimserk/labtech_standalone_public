#!/usr/bin/env bash
# Functions from a dynamically sourced installer are intentionally overridden in subshell tests.
# shellcheck disable=SC1091,SC2016,SC2034,SC2317
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
INSTALLER="$ROOT/deploy/install.sh"
TMP="$(mktemp -d)"
trap 'rm -rf -- "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
[[ -x "$INSTALLER" ]] || fail 'installer must exist and be executable'
export LABTECH_INSTALL_TESTING=1
# shellcheck source=../install.sh
source "$INSTALLER"
assert_contains() { [[ "$1" == *"$2"* ]] || fail "missing <$2>"; }
[[ "$REPOSITORY_URL" == 'https://github.com/gimserk/labtech_standalone_public.git' ]] || fail 'public installer must track public HTTPS repository'
assert_contains "$(usage)" 'public GitHub repository'

# A pre-cloned checkout is the documented first-install path; its presence
# must not make identity setup fail under set -e.
(
  INSTALL_DIR="$TMP/existing-checkout"
  BACKUP_ROOT="$TMP/identity-backups"
  mkdir -p "$INSTALL_DIR"
  id() { if [[ "$1" == -u ]]; then printf '1001\n'; else return 0; fi; }
  usermod() { :; }
  install() { :; }
  setup_identity_directories || fail 'identity setup failed for existing checkout'
)

(
  [[ "$VENV_PYTHON" == python3.13 ]] || fail 'public release must default to Python 3.13'
  VENV_PYTHON=python3
  if validate_python_runtime >/dev/null 2>&1; then fail 'Python 3.12 accepted for CPython 3.13 extensions'; fi
  VENV_PYTHON="$TMP/missing-python"
  if validate_python_runtime >/dev/null 2>&1; then fail 'missing Python interpreter accepted'; fi
  printf '#!/bin/sh\nexit 1\n' > "$TMP/unsupported-python"
  chmod +x "$TMP/unsupported-python"
  VENV_PYTHON="$TMP/unsupported-python"
  failure="$(validate_python_runtime 2>&1)" && fail 'unsupported Python interpreter accepted'
  assert_contains "$failure" 'Python 3.13'
)
(
  uname() { printf 'aarch64\n'; }
  if validate_public_platform >/dev/null 2>&1; then fail 'ARM64 accepted for x86_64 extensions'; fi
)
validate_public_platform || fail 'x86_64 host refused'

for path in '' / /opt /srv /etc /home relative /opt/../etc /opt/foo/../../etc /opt/foo/./bar; do
  if validate_install_dir "$path"; then fail "accepted dangerous path <$path>"; fi
done
validate_install_dir /opt/labtech || fail 'refused safe path'
validate_db_identifier labtech_db || fail 'refused DB identifier'
! validate_db_identifier 'bad;DROP' || fail 'accepted SQL injection'
validate_hostname lab.example.com || fail 'refused hostname'
! validate_hostname 'bad.example.com;reload' || fail 'accepted invalid hostname'
validate_http_url https://lab.example.com || fail 'refused valid URL'
! validate_http_url 'https://lab.example.com/path' || fail 'accepted URL path'
validate_integration_url 'https://lab.example.com/guacamole/' || fail 'refused Guacamole endpoint path'

CONFIG=()
CONFIG[DJANGO_SECRET_KEY]='stable-key'
CONFIG[LAB_CHECK_SECRET_KEY]='stable-fernet'
CONFIG[DB_PASSWORD]='stable-db'
CONFIG[EMAIL_HOST_PASSWORD]='space #"$\backtick` ✓ ${UNCHANGED}'
CONFIG[LICENSE_SERVER_PUBLIC_KEY]=$'-----BEGIN PUBLIC KEY-----\nMIIB...\n-----END PUBLIC KEY-----'
CONFIG[LICENSE_SERVER_URL]='https://licensing.example.com/api/licensing/'
CONFIG[PLUGIN_MARKETPLACE_URL]='https://plugins.example.com'
CONFIG[PLUGIN_MARKETPLACE_CLIENT_SECRET]='test-client-secret-1234567890-unique'
CONFIG[PLUGIN_MARKETPLACE_PUBLIC_KEY]=$'-----BEGIN PUBLIC KEY-----\nMCowBQYDK2VwAyEA...\n-----END PUBLIC KEY-----'
CONFIG[ENABLE_LDAP]=True
CONFIG[LDAP_BIND_DN]='CN=LABTECH,DC=example,DC=com'
CONFIG[GOOGLE_CLIENT_ID]='client-from-existing-env'
write_env_file "$TMP/labtech.env"
[[ "$(stat -c '%a' "$TMP/labtech.env")" == 640 ]] || fail 'env permissions'
CONFIG=()
load_existing_config "$TMP/labtech.env"
[[ "${CONFIG[EMAIL_HOST_PASSWORD]}" == 'space #"$\backtick` ✓ ${UNCHANGED}' ]] || fail 'unsafe env roundtrip'
[[ "${CONFIG[LICENSE_SERVER_PUBLIC_KEY]}" == $'-----BEGIN PUBLIC KEY-----\nMIIB...\n-----END PUBLIC KEY-----' ]] || fail 'multiline license key changed'
[[ "${CONFIG[PLUGIN_MARKETPLACE_PUBLIC_KEY]}" == $'-----BEGIN PUBLIC KEY-----\nMCowBQYDK2VwAyEA...\n-----END PUBLIC KEY-----' ]] || fail 'plugin public key changed'
[[ "${CONFIG[PLUGIN_MARKETPLACE_CLIENT_SECRET]}" == 'test-client-secret-1234567890-unique' ]] || fail 'plugin client secret changed'
validate_plugin_license_transport || fail 'HTTPS license server refused for plugin secret'
CONFIG[LICENSE_SERVER_URL]='http://licensing.example.com/api/licensing/'
if validate_plugin_license_transport; then fail 'HTTP license server accepted with plugin secret'; fi
CONFIG[LICENSE_SERVER_URL]='https://licensing.example.com/api/licensing/'
[[ "${CONFIG[LICENSE_SERVER_URL]}:${CONFIG[ENABLE_LDAP]}:${CONFIG[LDAP_BIND_DN]}:${CONFIG[GOOGLE_CLIENT_ID]}" == 'https://licensing.example.com/api/licensing/:True:CN=LABTECH,DC=example,DC=com:client-from-existing-env' ]] || fail 'integration values lost'
ensure_generated_secrets
[[ "${CONFIG[DJANGO_SECRET_KEY]}:${CONFIG[LAB_CHECK_SECRET_KEY]}:${CONFIG[DB_PASSWORD]}" == 'stable-key:stable-fernet:stable-db' ]] || fail 'secret rotated'
for key in MAINTENANCE_MODE ACCOUNT_ALLOW_REGISTRATION ENABLE_LDAP ENABLE_GOOGLE ENABLE_FACEBOOK ENABLE_MICROSOFT ENABLE_MAGICLINK GOOGLE_CLIENT_ID GOOGLE_CLIENT_SECRET FACEBOOK_CLIENT_ID FACEBOOK_CLIENT_SECRET MICROSOFT_CLIENT_ID MICROSOFT_CLIENT_SECRET LDAP_SERVER_URI LDAP_BIND_DN LDAP_BIND_PASSWORD LDAP_USER_SEARCH_BASE LDAP_GROUP_SEARCH_BASE LDAP_STAFF_GROUP LDAP_ADMIN_GROUP LICENSE_SERVER_URL LICENSE_SERVER_PUBLIC_KEY DJANGO_SUPERUSER_USERNAME DJANGO_SUPERUSER_EMAIL DJANGO_SUPERUSER_PASSWORD; do
  [[ " ${ENV_KEYS[*]} " == *" $key "* ]] || fail "unmanaged environment field $key"
done

REPOSITORY_URL="file://$TMP/origin.git"
TARGET_BRANCH=main
git -c init.defaultBranch=main init --bare "$TMP/origin.git" >/dev/null
git -c init.defaultBranch=main init "$TMP/source" >/dev/null
git -C "$TMP/source" config user.email test@example.com
git -C "$TMP/source" config user.name test
git -C "$TMP/source" commit --allow-empty -qm initial
printf baseline > "$TMP/source/readme"
git -C "$TMP/source" add readme
git -C "$TMP/source" commit -qm 'tracked fixture'
git -C "$TMP/source" remote add origin "$REPOSITORY_URL"
git -C "$TMP/source" push -q -u origin main
verify_git_access || fail 'could not read fixture repository'
git clone -q --branch main "$REPOSITORY_URL" "$TMP/permissions"
printf modified > "$TMP/permissions/readme"
(
  INSTALL_DIR="$TMP/permissions"
  # A root Git status can fail when its index is owned by the service user.
  # The service-user wrapper can still inspect and reject the tracked edit.
  git() {
    if [[ " $* " == *' status '* ]]; then
      printf 'fatal: .git/index: Permission denied\n' >&2
      return 128
    fi
    command git "$@"
  }
  as_service_user() { command "$@"; }
  if check_existing_checkout >/dev/null 2>&1; then fail 'preflight accepted dirty checkout after root status failed'; fi
  if sync_repository "$INSTALL_DIR" >/dev/null 2>&1; then fail 'sync accepted dirty checkout after root status failed'; fi
)
mkdir -p "$TMP/precreated"
sync_repository "$TMP/precreated" || fail 'could not clone into precreated empty install directory'
sync_repository "$TMP/work" || fail 'could not clone'
printf kept > "$TMP/work/untracked.txt"
sync_output="$(sync_repository "$TMP/work" 2>&1)" || fail 'could not sync an existing checkout with untracked files'
assert_contains "$sync_output" 'Untracked checkout files retained: untracked.txt'
[[ "$(cat "$TMP/work/untracked.txt")" == kept ]] || fail 'untracked file was lost'
printf dirty > "$TMP/work/readme"
git -C "$TMP/work" add readme
if sync_repository "$TMP/work" >/dev/null 2>&1; then fail 'staged changes overwritten'; fi
git -C "$TMP/work" reset -q --hard HEAD
git -C "$TMP/work" remote set-url origin file:///tmp/wrong.git
if sync_repository "$TMP/work" >/dev/null 2>&1; then fail 'wrong origin accepted'; fi
mkdir -p "$TMP/non-git"
printf data > "$TMP/non-git/data"
if sync_repository "$TMP/non-git" >/dev/null 2>&1; then fail 'non-git data overwritten'; fi

INSTALL_DIR=/opt/labtech
CONFIG[PRIMARY_HOST]=lab.example.com
config="$(render_nginx_http_site)"
assert_contains "$config" 'location ^~ /media/course_audio/'
assert_contains "$config" 'return 404;'
assert_contains "$config" 'proxy_pass http://127.0.0.1:8000;'
assert_contains "$(render_web_unit)" 'User=labtech'
assert_contains "$(render_beat_unit)" '--schedule=/var/lib/labtech/celerybeat-schedule'
assert_contains "$(render_deployment_settings)" 'CompressedManifestStaticFilesStorage'
assert_contains "$(render_deployment_settings)" 'interpolate=False'

# Plugin state is external to the tracked checkout and preserved across reruns.
(
  PLUGIN_ROOT="$TMP/plugins"
  PLUGIN_SECRET_ROOT="$TMP/secrets"
  PLUGIN_SOCKET_ROOT="$TMP/sockets"
  setup_plugin_directories
  mkdir -p "$PLUGIN_ROOT/demo/releases/1.0.0"
  ln -s releases/1.0.0 "$PLUGIN_ROOT/demo/current"
  printf stable > "$PLUGIN_SECRET_ROOT/demo.token"
  setup_plugin_directories
  [[ "$(readlink "$PLUGIN_ROOT/demo/current")" == releases/1.0.0 ]] || fail 'rerun changed plugin release'
  [[ "$(cat "$PLUGIN_SECRET_ROOT/demo.token")" == stable ]] || fail 'rerun changed plugin secret'
)
assert_contains "$(render_plugin_unit)" 'User=labtech-plugin'
assert_contains "$(render_plugin_unit)" 'MemoryMax=512M'
assert_contains "$(render_plugin_install_timer)" 'OnUnitActiveSec=1min'
assert_contains "$(render_plugin_install_service)" 'ExecStart=/usr/local/lib/labtech/plugin-helper-venv/bin/python'
[[ "$(render_plugin_install_service)" != *"$INSTALL_DIR/venv/bin/python"* ]] || fail 'root helper runs writable venv'
[[ " ${ENV_KEYS[*]} " == *' PLUGIN_MARKETPLACE_PUBLIC_KEY '* ]] || fail 'plugin publisher key unmanaged'
[[ " ${ENV_KEYS[*]} " == *' PLUGIN_MARKETPLACE_CLIENT_SECRET '* ]] || fail 'plugin client secret unmanaged'
(
  INSTALL_DIR="$TMP/helper-source"
  PLUGIN_HELPER_ROOT="$TMP/helper-owned"
  mkdir -p "$INSTALL_DIR/app" "$INSTALL_DIR/deploy" "$INSTALL_DIR/venv/bin"
  printf 'trusted\n' > "$INSTALL_DIR/app/settings.py"
  printf 'trusted\n' > "$INSTALL_DIR/deploy/plugin_helper.py"
  ln -s /usr/bin/python3 "$INSTALL_DIR/venv/bin/python"
  install_plugin_helper_snapshot || fail 'could not stage root-owned helper'
  printf 'changed\n' > "$INSTALL_DIR/deploy/plugin_helper.py"
  [[ "$(cat "$PLUGIN_HELPER_ROOT/plugin-helper-source/deploy/plugin_helper.py")" == trusted ]] || fail 'helper still reads writable checkout'
  [[ "$(stat -c '%U:%a' "$PLUGIN_HELPER_ROOT/plugin-helper-source/deploy/plugin_helper.py")" == "$(id -un):640" ]] || fail 'helper snapshot is writable by other users'
)

(
  calls="$TMP/calls"
  run_required_checks() { printf 'checks\n' >> "$calls"; return 1; }
  run_full_tests() { printf 'tests\n' >> "$calls"; }
  run_manage() { printf 'manage %s\n' "$*" >> "$calls"; }
  if run_activation_pipeline >/dev/null 2>&1; then fail 'required check failure continued'; fi
  [[ "$(cat "$calls")" == checks ]] || fail 'service activation passed failed checks'
)
(
  INSTALL_DIR="$TMP/fake-install"
  mkdir -p "$INSTALL_DIR/venv/bin"
  printf '#!/bin/sh\nexit 1\n' > "$INSTALL_DIR/venv/bin/python"
  chmod +x "$INSTALL_DIR/venv/bin/python"
  run_manage() { fail 'Django check ran after pip check failed'; }
  if run_required_checks >/dev/null 2>&1; then fail 'pip check failure was ignored'; fi
)
(
  calls="$TMP/activation"
  run_required_checks() { printf 'checks\n' >> "$calls"; }
  run_full_tests() { printf 'tests\n' >> "$calls"; TEST_WARNING=1; }
  database_has_tables() { return 0; }
  backup_database() { printf 'backup\n' >> "$calls"; }
  run_manage() { printf '%s\n' "$1" >> "$calls"; }
  create_superuser_if_requested() { :; }
  install_systemd_units() { printf 'units\n' >> "$calls"; }
  install_plugin_units() { :; }
  install_nginx_site() { printf 'nginx\n' >> "$calls"; }
  activate_services() { printf 'services\n' >> "$calls"; }
  run_activation_pipeline
  [[ "$TEST_WARNING" == 1 ]] || fail 'test warning was lost'
  [[ "$(cat "$calls")" == $'checks\ntests\nbackup\nmigrate\ncollectstatic\nunits\nnginx\nservices' ]] || fail 'activation order or backup gate changed'
)
(
  calls="$TMP/database-error"
  run_required_checks() { :; }
  run_full_tests() { :; }
  database_has_tables() { return 2; }
  run_manage() { printf '%s\n' "$1" >> "$calls"; }
  if run_activation_pipeline >/dev/null 2>&1; then fail 'database inspection failure was ignored'; fi
  [[ ! -e "$calls" ]] || fail 'migration ran after database inspection failed'
)
(
  calls="$TMP/plugin-service-error"
  run_required_checks() { :; }
  run_full_tests() { :; }
  database_has_tables() { return 1; }
  run_manage() { :; }
  create_superuser_if_requested() { :; }
  install_systemd_units() { :; }
  install_nginx_site() { :; }
  activate_services() { printf 'core active\n' > "$calls"; }
  install_plugin_units() { return 1; }
  run_activation_pipeline >/dev/null 2>&1 || fail 'connector setup failure interrupted core activation'
  [[ "$(cat "$calls")" == 'core active' ]] || fail 'core was not activated'
)
(
  CONFIG[MAINTENANCE_MODE]=True
  systemctl() { return 0; }
  curl() {
    if [[ "$*" == *course_audio* ]]; then printf '404'; else printf '503'; fi
  }
  run_health_checks || fail 'maintenance mode health response refused'
  CONFIG[MAINTENANCE_MODE]=False
  if run_health_checks >/dev/null 2>&1; then fail 'unexpected 503 accepted'; fi
)

printf 'PASS: installer path, input, secret, repository, and config tests\n'
