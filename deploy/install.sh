#!/usr/bin/env bash
set -Eeuo pipefail
umask 027

REPOSITORY_URL='https://github.com/gimserk/labtech_standalone_public.git'
TARGET_BRANCH="${LABTECH_TARGET_BRANCH:-main}"
OS_RELEASE_FILE="${LABTECH_OS_RELEASE:-/etc/os-release}"
EFFECTIVE_UID="${LABTECH_INSTALL_EUID:-$EUID}"
VENV_PYTHON="${LABTECH_VENV_PYTHON:-python3}"
INSTALL_DIR=/opt/labtech
ENV_FILE=/etc/labtech/labtech.env
SETTINGS_FILE=/etc/labtech/deployment_settings.py
LOG_FILE=/var/log/labtech/install.log
BACKUP_ROOT=/var/backups/labtech
PHASE=preflight
TEST_WARNING=0
NGINX_WARNING=''
LATEST_DUMP=''
BACKUP_DIR=''
ENABLE_TLS=no
CREATE_ADMIN=no
declare -A CONFIG=()
ENV_KEYS=(INSTALL_DIR PRIMARY_HOST SITE_URL ALLOWED_HOSTS CSRF_TRUSTED_ORIGINS DJANGO_SECRET_KEY DJANGO_DEBUG DB_NAME DB_USER DB_PASSWORD DB_HOST DB_PORT EMAIL_HOST EMAIL_PORT EMAIL_HOST_USER EMAIL_HOST_PASSWORD EMAIL_USE_SSL EMAIL_USE_TLS DEFAULT_FROM_EMAIL STRIPE_PUBLISHABLE_KEY STRIPE_SECRET_KEY STRIPE_WEBHOOK_SECRET SQUARE_APP_ID SQUARE_ACCESS_TOKEN SQUARE_LOCATION_ID SQUARE_ENVIRONMENT GUACAMOLE_URL GUACAMOLE_ADMIN_USER GUACAMOLE_ADMIN_PASSWORD GUACAMOLE_SSO_SECRET_KEY CELERY_BROKER_URL CELERY_RESULT_BACKEND LAB_CHECK_SECRET_KEY LAB_CHECK_STEP_COOLDOWN_SECONDS LAB_CHECK_COMMAND_TIMEOUT_SECONDS LAB_CHECK_RUN_DEADLINE_SECONDS LAB_CHECK_MAX_OUTPUT_BYTES LAB_CHECK_MAX_FILE_BYTES LAB_CHECK_LEASE_SECONDS AUDIO_MAX_UPLOAD_BYTES ENABLE_TLS CERTBOT_EMAIL)
ENV_KEYS+=(MAINTENANCE_MODE ACCOUNT_ALLOW_REGISTRATION ENABLE_LDAP ENABLE_GOOGLE ENABLE_FACEBOOK ENABLE_MICROSOFT ENABLE_MAGICLINK)
ENV_KEYS+=(GOOGLE_CLIENT_ID GOOGLE_CLIENT_SECRET FACEBOOK_CLIENT_ID FACEBOOK_CLIENT_SECRET MICROSOFT_CLIENT_ID MICROSOFT_CLIENT_SECRET)
ENV_KEYS+=(LDAP_SERVER_URI LDAP_BIND_DN LDAP_BIND_PASSWORD LDAP_USER_SEARCH_BASE LDAP_GROUP_SEARCH_BASE LDAP_STAFF_GROUP LDAP_ADMIN_GROUP)
ENV_KEYS+=(LICENSE_SERVER_URL LICENSE_SERVER_PUBLIC_KEY DJANGO_SUPERUSER_USERNAME DJANGO_SUPERUSER_EMAIL DJANGO_SUPERUSER_PASSWORD)
ENV_KEYS+=(PLUGIN_MARKETPLACE_URL PLUGIN_MARKETPLACE_PUBLIC_KEY PLUGIN_MARKETPLACE_CLIENT_SECRET)
ENV_KEYS+=(LABTECH_VENV_PYTHON)
PLUGIN_ROOT="${LABTECH_PLUGIN_ROOT:-/var/lib/labtech/plugins}"
PLUGIN_SECRET_ROOT="${LABTECH_PLUGIN_SECRET_ROOT:-/etc/labtech/plugins}"
PLUGIN_SOCKET_ROOT="${LABTECH_PLUGIN_SOCKET_ROOT:-/run/labtech/plugins}"
PLUGIN_HELPER_ROOT="${LABTECH_PLUGIN_HELPER_ROOT:-/usr/local/lib/labtech}"

usage() { cat <<'HELP'
Usage: sudo ./deploy/install.sh [--help]
Install LabTech on Ubuntu 24.04 or newer from the public GitHub repository.
A safe rerun preserves the database, media, and stable secrets.
HELP
}
log() { printf '[labtech] %s\n' "$*"; }
warn() { printf '[labtech] WARNING: %s\n' "$*" >&2; }
die() { printf '[labtech] ERROR: %s\n' "$*" >&2; return 1; }
require_root() { [[ "$EFFECTIVE_UID" == 0 ]] || die 'Run with sudo.'; }
require_ubuntu_2404() {
  local id version
  id="$(sed -nE 's/^ID="?([^" ]+)"?$/\1/p' "$OS_RELEASE_FILE" | head -1)"
  version="$(sed -nE 's/^VERSION_ID="?([0-9]+\.(04|10))"?$/\1/p' "$OS_RELEASE_FILE" | head -1)"
  [[ "$id" == ubuntu && "$version" =~ ^([0-9]{2,4})\.(04|10)$ && ${BASH_REMATCH[1]} -ge 24 ]] || die 'Ubuntu 24.04 or newer is required.'
}
validate_python_runtime() {
  command -v "$VENV_PYTHON" >/dev/null 2>&1 || { die 'Python 3.12 or 3.13 required; install one and set LABTECH_VENV_PYTHON.'; return 1; }
  "$VENV_PYTHON" -c 'import sys; raise SystemExit(not ((3, 12) <= sys.version_info[:2] <= (3, 13)))' || { die 'Python 3.12 or 3.13 required for pinned dependencies; set LABTECH_VENV_PYTHON.'; return 1; }
}
validate_install_dir() {
  local path="${1:-}" part
  local -a parts
  [[ "$path" == /opt/* || "$path" == /srv/* ]] || return 1
  [[ "$path" != */ && "$path" != *'//'* && "$path" != *[$'\n\r\t']* ]] || return 1
  IFS=/ read -r -a parts <<< "$path"
  for part in "${parts[@]}"; do [[ "$part" != . && "$part" != .. ]] || return 1; done
  [[ "$path" =~ ^/(opt|srv)/[A-Za-z0-9_-]+(/[A-Za-z0-9_.-]+)*$ ]] || return 1
  local parent
  parent="$(dirname -- "$path")"
  while [[ "$parent" != / ]]; do [[ ! -L "$parent" ]] || return 1; parent="$(dirname -- "$parent")"; done
  [[ ! -L "$path" ]]
}
validate_db_identifier() { [[ "${1:-}" =~ ^[A-Za-z][A-Za-z0-9_]{0,63}$ ]]; }
validate_hostname() {
  local h="${1:-}" label
  local -a labels
  [[ ${#h} -le 253 && "$h" =~ ^[A-Za-z0-9.-]+$ && "$h" != *..* ]] || return 1
  IFS=. read -r -a labels <<< "$h"
  for label in "${labels[@]}"; do
    [[ ${#label} -le 63 && "$label" =~ ^[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?$ ]] || return 1
  done
}
validate_http_url() {
  local value="${1:-}" authority host port
  [[ "$value" =~ ^https?://[^/?#[:space:]]+$ ]] || return 1
  authority="${value#*://}"; host="${authority%%:*}"
  validate_hostname "$host" || return 1
  if [[ "$authority" == *:* ]]; then
    port="${authority##*:}"
    [[ "$port" =~ ^[0-9]{1,5}$ && $((10#$port)) -gt 0 && $((10#$port)) -le 65535 ]] || return 1
  fi
}
validate_integration_url() {
  local value="${1:-}" scheme rest authority
  [[ "$value" == http://* || "$value" == https://* ]] || return 1
  [[ "$value" != *'?'* && "$value" != *'#'* && "$value" != *'@'* && "$value" != *[$'\n\r\t ']* ]] || return 1
  scheme="${value%%://*}"
  rest="${value#*://}"
  authority="${rest%%/*}"
  validate_http_url "$scheme://$authority"
}
validate_plugin_license_transport() {
  [[ -z "${CONFIG[PLUGIN_MARKETPLACE_CLIENT_SECRET]:-}" || "${CONFIG[LICENSE_SERVER_URL]:-}" == https://* ]]
}
validate_origin_csv() {
  local origin
  local -a origins
  IFS=, read -r -a origins <<< "$1"
  ((${#origins[@]})) || return 1
  for origin in "${origins[@]}"; do validate_http_url "$origin" || return 1; done
}
preflight() {
  require_root; require_ubuntu_2404; validate_python_runtime
  [[ "$TARGET_BRANCH" =~ ^[A-Za-z0-9][A-Za-z0-9_./-]*$ && "$TARGET_BRANCH" != *..* ]] || die 'Invalid branch.'
  for binary in flock git python3 curl openssl realpath runuser; do command -v "$binary" >/dev/null || die "Missing $binary"; done
  exec 9>/run/lock/labtech-install.lock
  flock -n 9 || die 'Another LabTech installation is running.'
  local free
  free="$(df -Pk /opt | awk 'NR==2 {print $4}')"
  [[ "$free" =~ ^[0-9]+$ && "$free" -ge 2097152 ]] || die 'At least 2 GiB free space is required.'
}

# The managed file contains only JSON quoted scalar values. Never execute it as shell.
load_existing_config() {
  local path="$1" key value records
  [[ -f "$path" ]] || return 0
  records="$(mktemp)"
  if ! python3 - "$path" "${ENV_KEYS[@]}" > "$records" <<'PY'
import json, re, sys
allowed = set(sys.argv[2:]); found = set()
with open(sys.argv[1], encoding='utf-8') as stream:
    for line in stream:
        key, sep, raw = line.rstrip('\n').partition('=')
        if not sep or key not in allowed or key in found:
            raise SystemExit('Invalid or duplicate managed environment key')
        value = json.loads(raw)
        if not isinstance(value, str) or '\r' in value or '\x00' in value or ('\n' in value and key not in {'LICENSE_SERVER_PUBLIC_KEY', 'PLUGIN_MARKETPLACE_PUBLIC_KEY'}):
            raise SystemExit('Invalid environment value')
        found.add(key)
        sys.stdout.buffer.write(key.encode() + b'\x00' + value.encode() + b'\x00')
PY
  then
    rm -f -- "$records"
    return 1
  fi
  while IFS= read -r -d '' key && IFS= read -r -d '' value; do CONFIG["$key"]="$value"; done < "$records"
  rm -f -- "$records"
}
write_env_file() {
  local path="$1" tmp key
  mkdir -p "$(dirname -- "$path")"
  tmp="$(mktemp "${path}.XXXXXX")"
  for key in "${ENV_KEYS[@]}"; do
    printf '%s=' "$key" >> "$tmp"
    printf %s "${CONFIG[$key]-}" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read(),ensure_ascii=False))' >> "$tmp"
  done
  chmod 0640 "$tmp"
  if [[ "${LABTECH_INSTALL_TESTING:-}" != 1 ]]; then chown root:labtech "$tmp"; fi
  backup_managed_file "$path"
  mv -f -- "$tmp" "$path"
}
ensure_generated_secrets() {
  [[ -n "${CONFIG[DJANGO_SECRET_KEY]:-}" ]] || CONFIG[DJANGO_SECRET_KEY]="$(python3 -c 'import secrets;print(secrets.token_urlsafe(50))')"
  [[ -n "${CONFIG[DB_PASSWORD]:-}" ]] || CONFIG[DB_PASSWORD]="$(python3 -c 'import secrets,string;print("".join(secrets.choice(string.ascii_letters+string.digits) for _ in range(48)))')"
  [[ -n "${CONFIG[LAB_CHECK_SECRET_KEY]:-}" ]] || CONFIG[LAB_CHECK_SECRET_KEY]="$(python3 -c 'import base64,secrets;print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())')"
}
backup_managed_file() {
  local path="$1" target
  [[ -f "$path" ]] || return 0
  BACKUP_DIR="${BACKUP_DIR:-$BACKUP_ROOT/config/$(date -u +%Y%m%dT%H%M%SZ)-$$}"
  mkdir -p "$BACKUP_DIR"
  chmod 0700 "$BACKUP_DIR"
  target="$BACKUP_DIR/$(basename -- "$path").$(date +%s%N)"
  cp -p -- "$path" "$target"; chmod 0600 "$target"
}

ask() {
  local key="$1" title="$2" default="$3" answer
  read -r -p "$title [${CONFIG[$key]:-$default}]: " answer
  if [[ "$answer" == - && -z "$default" ]]; then
    CONFIG["$key"]=''
  else
    CONFIG["$key"]="${answer:-${CONFIG[$key]:-$default}}"
  fi
}
ask_secret() {
  local key="$1" title="$2" answer
  if [[ -n "${CONFIG[$key]:-}" ]]; then
    read -r -s -p "$title [stored; Enter to keep, - to clear]: " answer
  else
    read -r -s -p "$title [optional]: " answer
  fi
  printf '\n'
  [[ "$answer" == - ]] && CONFIG["$key"]='' || CONFIG["$key"]="${answer:-${CONFIG[$key]:-}}"
}
ask_flag() {
  local key="$1" title="$2" default="$3"
  ask "$key" "$title (True/False)" "$default"
  [[ "${CONFIG[$key]}" == True || "${CONFIG[$key]}" == False ]] || die "Invalid $key toggle."
}
ask_license_key() {
  local pem_file
  read -r -p 'License public key PEM file [Enter to keep existing, blank to skip]: ' pem_file
  [[ -n "$pem_file" ]] || return 0
  if [[ "$pem_file" == - ]]; then CONFIG[LICENSE_SERVER_PUBLIC_KEY]=''; return 0; fi
  [[ -f "$pem_file" && ! -L "$pem_file" ]] || die 'License public key file not found.'
  openssl pkey -pubin -in "$pem_file" -noout >/dev/null 2>&1 || die 'Invalid public key PEM.'
  CONFIG[LICENSE_SERVER_PUBLIC_KEY]="$(cat -- "$pem_file")"
}
ask_plugin_publisher_key() {
  local pem_file
  read -r -p 'Plugin Marketplace publisher public key PEM file [Enter to keep, - to disable]: ' pem_file
  [[ -n "$pem_file" ]] || return 0
  if [[ "$pem_file" == - ]]; then CONFIG[PLUGIN_MARKETPLACE_PUBLIC_KEY]=''; return 0; fi
  [[ -f "$pem_file" && ! -L "$pem_file" ]] || die 'Plugin publisher key file not found.'
  openssl pkey -pubin -in "$pem_file" -text -noout 2>/dev/null | grep -q 'ED25519' || die 'Plugin publisher key must be Ed25519.'
  CONFIG[PLUGIN_MARKETPLACE_PUBLIC_KEY]="$(cat -- "$pem_file")"
}
yesno() {
  local answer
  read -r -p "$1 [y/N]: " answer
  case "$answer" in y|Y|yes|YES|Yes) return 0;; *) return 1;; esac
}
collect_configuration() {
  local -a hosts
  ask INSTALL_DIR 'Install directory' /opt/labtech
  INSTALL_DIR="${CONFIG[INSTALL_DIR]}"
  validate_install_dir "$INSTALL_DIR" || die 'Unsafe installation directory.'
  ask PRIMARY_HOST 'Primary hostname' ''
  validate_hostname "${CONFIG[PRIMARY_HOST]}" || die 'Invalid hostname.'
  ask SITE_URL 'Public URL' "http://${CONFIG[PRIMARY_HOST]}"
  validate_http_url "${CONFIG[SITE_URL]}" || die 'Invalid site URL.'
  [[ "${CONFIG[SITE_URL]}" == *"://${CONFIG[PRIMARY_HOST]}" ]] || die 'Site URL must match the primary hostname.'
  ask ALLOWED_HOSTS 'Additional allowed hosts (comma separated)' "${CONFIG[PRIMARY_HOST]}"
  CONFIG[ALLOWED_HOSTS]="${CONFIG[PRIMARY_HOST]},${CONFIG[ALLOWED_HOSTS]#${CONFIG[PRIMARY_HOST]}}"
  local host
  IFS=, read -r -a hosts <<< "${CONFIG[ALLOWED_HOSTS]}"
  for host in "${hosts[@]}"; do [[ -z "$host" ]] || validate_hostname "$host" || die 'Invalid allowed host.'; done
  ask CSRF_TRUSTED_ORIGINS 'CSRF trusted origins' "${CONFIG[SITE_URL]}"
  validate_origin_csv "${CONFIG[CSRF_TRUSTED_ORIGINS]}" || die 'Invalid CSRF origins.'
  ask DB_NAME 'Database name' labtech_db
  ask DB_USER 'Database user' labtech
  if ! validate_db_identifier "${CONFIG[DB_NAME]}" || ! validate_db_identifier "${CONFIG[DB_USER]}"; then
    die 'Invalid database identifier.'
    return 1
  fi
  CONFIG[DB_HOST]=localhost; CONFIG[DB_PORT]=3306; CONFIG[DJANGO_DEBUG]=False
  ask EMAIL_HOST 'SMTP host (empty disables email)' ''
  ask EMAIL_PORT 'SMTP port' 465
  [[ "${CONFIG[EMAIL_PORT]}" =~ ^[0-9]{1,5}$ ]] || die 'Invalid SMTP port.'
  ask EMAIL_HOST_USER 'SMTP user' ''
  ask_secret EMAIL_HOST_PASSWORD 'SMTP password'
  ask EMAIL_USE_SSL 'SMTP SSL (True/False)' True
  ask EMAIL_USE_TLS 'SMTP STARTTLS (True/False)' False
  [[ "${CONFIG[EMAIL_USE_SSL]}" =~ ^(True|False)$ && "${CONFIG[EMAIL_USE_TLS]}" =~ ^(True|False)$ ]] || die 'Invalid SMTP security selection.'
  [[ "${CONFIG[EMAIL_USE_SSL]}" != True || "${CONFIG[EMAIL_USE_TLS]}" != True ]] || die 'Choose SSL or STARTTLS.'
  ask DEFAULT_FROM_EMAIL 'Sender email' ''
  ask_flag MAINTENANCE_MODE 'Maintenance mode' False
  ask_flag ACCOUNT_ALLOW_REGISTRATION 'Allow registration' False
  ask_flag ENABLE_LDAP 'Enable LDAP' False
  ask_flag ENABLE_GOOGLE 'Enable Google login' False
  ask_flag ENABLE_FACEBOOK 'Enable Facebook login' False
  ask_flag ENABLE_MICROSOFT 'Enable Microsoft login' False
  if [[ "${CONFIG[ENABLE_MAGICLINK]:-False}" == True ]]; then
    warn 'Magic link is unsupported in this standalone version; disabling it.'
  fi
  CONFIG[ENABLE_MAGICLINK]=False
  ask GOOGLE_CLIENT_ID 'Google client ID' ''
  ask_secret GOOGLE_CLIENT_SECRET 'Google client secret'
  ask FACEBOOK_CLIENT_ID 'Facebook client ID' ''
  ask_secret FACEBOOK_CLIENT_SECRET 'Facebook client secret'
  ask MICROSOFT_CLIENT_ID 'Microsoft client ID' ''
  ask_secret MICROSOFT_CLIENT_SECRET 'Microsoft client secret'
  ask LDAP_SERVER_URI 'LDAP server URI (ldap:// or ldaps://)' ''
  ask LDAP_BIND_DN 'LDAP bind DN' ''
  ask_secret LDAP_BIND_PASSWORD 'LDAP bind password'
  ask LDAP_USER_SEARCH_BASE 'LDAP user search base' ''
  ask LDAP_GROUP_SEARCH_BASE 'LDAP group search base' ''
  ask LDAP_STAFF_GROUP 'LDAP staff group DN' ''
  ask LDAP_ADMIN_GROUP 'LDAP admin group DN' ''
  if [[ "${CONFIG[ENABLE_LDAP]}" == True ]]; then
    [[ "${CONFIG[LDAP_SERVER_URI]}" =~ ^ldaps?://[^[:space:]]+$ ]] || die 'LDAP server URI required when LDAP is enabled.'
    [[ -n "${CONFIG[LDAP_BIND_DN]}" && -n "${CONFIG[LDAP_BIND_PASSWORD]}" && -n "${CONFIG[LDAP_USER_SEARCH_BASE]}" && -n "${CONFIG[LDAP_GROUP_SEARCH_BASE]}" ]] || die 'LDAP bind DN/password and search bases required.'
  fi
  ask LICENSE_SERVER_URL 'License server URL (Marketplace access)' ''
  [[ -z "${CONFIG[LICENSE_SERVER_URL]}" ]] || validate_integration_url "${CONFIG[LICENSE_SERVER_URL]}" || die 'Invalid license server URL.'
  ask_license_key
  [[ -z "${CONFIG[LICENSE_SERVER_URL]}" || -n "${CONFIG[LICENSE_SERVER_PUBLIC_KEY]:-}" ]] || die 'Marketplace licensing requires a public key PEM.'
  ask PLUGIN_MARKETPLACE_URL 'Plugin Marketplace HTTPS origin' 'https://www.wyocyberrange.com'
  if [[ "${CONFIG[PLUGIN_MARKETPLACE_URL]}" != https://* ]] || ! validate_http_url "${CONFIG[PLUGIN_MARKETPLACE_URL]}"; then
    die 'Plugin Marketplace requires an HTTPS origin.'
  fi
  ask_plugin_publisher_key
  ask_secret PLUGIN_MARKETPLACE_CLIENT_SECRET 'Per-installation Marketplace client secret from the official licensing administrator'
  if [[ -n "${CONFIG[PLUGIN_MARKETPLACE_CLIENT_SECRET]:-}" ]]; then
    [[ ${#CONFIG[PLUGIN_MARKETPLACE_CLIENT_SECRET]} -ge 32 && ${#CONFIG[PLUGIN_MARKETPLACE_CLIENT_SECRET]} -le 512 ]] || die 'Plugin Marketplace client secret must be 32–512 characters.'
    validate_plugin_license_transport || die 'Plugin Marketplace client secret requires an HTTPS license server URL.'
  fi
  ask DJANGO_SUPERUSER_USERNAME 'Initial administrator username' ''
  ask DJANGO_SUPERUSER_EMAIL 'Initial administrator email' ''
  if [[ -n "${CONFIG[DJANGO_SUPERUSER_PASSWORD]:-}" ]]; then
    warn 'Legacy superuser password from .env is ignored and removed; use the interactive Django prompt.'
  fi
  CONFIG[DJANGO_SUPERUSER_PASSWORD]=''
  ask STRIPE_PUBLISHABLE_KEY 'Stripe publishable key' ''
  ask_secret STRIPE_SECRET_KEY 'Stripe secret key'
  ask_secret STRIPE_WEBHOOK_SECRET 'Stripe webhook secret'
  ask SQUARE_APP_ID 'Square application ID' ''
  ask_secret SQUARE_ACCESS_TOKEN 'Square access token'
  ask SQUARE_LOCATION_ID 'Square location ID' ''
  ask SQUARE_ENVIRONMENT 'Square environment (sandbox/production)' sandbox
  [[ "${CONFIG[SQUARE_ENVIRONMENT]}" =~ ^(sandbox|production)$ ]] || die 'Invalid Square environment.'
  ask GUACAMOLE_URL 'Guacamole URL (empty disables)' ''
  [[ -z "${CONFIG[GUACAMOLE_URL]}" ]] || validate_integration_url "${CONFIG[GUACAMOLE_URL]}" || die 'Invalid Guacamole URL.'
  ask GUACAMOLE_ADMIN_USER 'Guacamole admin user' ''
  ask_secret GUACAMOLE_ADMIN_PASSWORD 'Guacamole admin password'
  ask_secret GUACAMOLE_SSO_SECRET_KEY 'Guacamole SSO secret'
  CONFIG[CELERY_BROKER_URL]=redis://127.0.0.1:6379/0
  CONFIG[CELERY_RESULT_BACKEND]=redis://127.0.0.1:6379/0
  CONFIG[LAB_CHECK_STEP_COOLDOWN_SECONDS]="${CONFIG[LAB_CHECK_STEP_COOLDOWN_SECONDS]:-10}"
  CONFIG[LAB_CHECK_COMMAND_TIMEOUT_SECONDS]="${CONFIG[LAB_CHECK_COMMAND_TIMEOUT_SECONDS]:-15}"
  CONFIG[LAB_CHECK_RUN_DEADLINE_SECONDS]="${CONFIG[LAB_CHECK_RUN_DEADLINE_SECONDS]:-45}"
  CONFIG[LAB_CHECK_MAX_OUTPUT_BYTES]="${CONFIG[LAB_CHECK_MAX_OUTPUT_BYTES]:-16384}"
  CONFIG[LAB_CHECK_MAX_FILE_BYTES]="${CONFIG[LAB_CHECK_MAX_FILE_BYTES]:-65536}"
  CONFIG[LAB_CHECK_LEASE_SECONDS]="${CONFIG[LAB_CHECK_LEASE_SECONDS]:-120}"
  CONFIG[AUDIO_MAX_UPLOAD_BYTES]="${CONFIG[AUDIO_MAX_UPLOAD_BYTES]:-262144000}"
  CONFIG[LABTECH_VENV_PYTHON]="$VENV_PYTHON"
  CONFIG[ENABLE_TLS]="${CONFIG[ENABLE_TLS]:-no}"
  if yesno "Request or renew Let's Encrypt TLS"; then
    ENABLE_TLS=yes; CONFIG[ENABLE_TLS]=yes
    ask CERTBOT_EMAIL 'Certificate email' ''
    [[ "${CONFIG[CERTBOT_EMAIL]}" == *@*.* ]] || die 'Certificate email required.'
  fi
  # A fresh site starts on HTTP until Certbot has actually issued a certificate.
  if [[ "${CONFIG[SITE_URL]}" == https://* && ! -f /etc/nginx/sites-available/labtech ]]; then
    CONFIG[SITE_URL]="http://${CONFIG[PRIMARY_HOST]}"
    CONFIG[CSRF_TRUSTED_ORIGINS]="${CONFIG[CSRF_TRUSTED_ORIGINS]//https:\/\/${CONFIG[PRIMARY_HOST]}/http:\/\/${CONFIG[PRIMARY_HOST]}}"
    warn 'Public URL will use HTTP until a certificate is installed.'
  fi
  if yesno 'Create first superuser'; then CREATE_ADMIN=yes; fi
  ensure_generated_secrets
}

as_service_user() {
  if [[ "${LABTECH_INSTALL_TESTING:-}" == 1 ]]; then "$@"; else runuser -u labtech -- "$@"; fi
}
verify_git_access() {
  as_service_user env GIT_TERMINAL_PROMPT=0 \
    git ls-remote --exit-code "$REPOSITORY_URL" "refs/heads/$TARGET_BRANCH" >/dev/null || die 'Cannot read the public GitHub repository. Check network access and the target branch.'
}
check_existing_checkout() {
  local checkout_status
  [[ ! -e "$INSTALL_DIR" ]] && return 0
  if [[ -d "$INSTALL_DIR/.git" ]]; then
    [[ "$(git -C "$INSTALL_DIR" remote get-url origin)" == "$REPOSITORY_URL" ]] || die 'Unexpected checkout origin.'
    [[ "$(git -C "$INSTALL_DIR" branch --show-current)" == "$TARGET_BRANCH" ]] || die 'Checkout is on another branch.'
    checkout_status="$(as_service_user git -C "$INSTALL_DIR" status --porcelain --untracked-files=no)" || { die 'Cannot inspect checkout status.'; return 1; }
    [[ -z "$checkout_status" ]] || die 'Tracked checkout changes must be resolved.'
  else
    [[ -d "$INSTALL_DIR" && -z "$(find "$INSTALL_DIR" -mindepth 1 -maxdepth 1 -print -quit)" ]] || die 'Non-Git installation path contains data.'
  fi
}
sync_repository() {
  local path="$1" origin status branch
  validate_install_dir "$path" || [[ "${LABTECH_INSTALL_TESTING:-}" == 1 ]] || die 'Unsafe checkout path.'
  if [[ -d "$path/.git" ]]; then
    origin="$(git -C "$path" remote get-url origin)"
    [[ "$origin" == "$REPOSITORY_URL" ]] || { die 'Unexpected Git origin.'; return 1; }
    branch="$(git -C "$path" branch --show-current)"
    [[ "$branch" == "$TARGET_BRANCH" ]] || { die 'Checkout must be on the configured branch.'; return 1; }
    status="$(as_service_user git -C "$path" status --porcelain --untracked-files=no)" || return 1
    [[ -z "$status" ]] || { die 'Tracked/staged Git changes must be resolved.'; return 1; }
    local untracked
    untracked="$(as_service_user git -C "$path" ls-files --others --exclude-standard)" || return 1
    [[ -z "$untracked" ]] || log "Untracked checkout files retained: $untracked"
    as_service_user git -C "$path" fetch origin "$TARGET_BRANCH"
    git -C "$path" merge-base --is-ancestor HEAD "origin/$TARGET_BRANCH" || { die 'Branch has diverged.'; return 1; }
    as_service_user git -C "$path" merge --ff-only "origin/$TARGET_BRANCH"
  else
    if [[ -e "$path" ]]; then
      [[ -d "$path" && -z "$(find "$path" -mindepth 1 -maxdepth 1 -print -quit)" ]] || { die 'Non-Git installation directory is not empty.'; return 1; }
    fi
    as_service_user git clone --branch "$TARGET_BRANCH" --single-branch "$REPOSITORY_URL" "$path"
  fi
}

install_packages() {
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y git openssh-client python3 python3-venv python3-dev build-essential pkg-config \
    default-libmysqlclient-dev libldap2-dev libsasl2-dev libssl-dev libxml2-dev libxslt1-dev \
    libjpeg-dev zlib1g-dev libffi-dev mariadb-server mariadb-client redis-server nginx \
    certbot python3-certbot-nginx curl ca-certificates acl rsync
  validate_python_runtime
}
setup_identity_directories() {
  if id labtech >/dev/null 2>&1; then
    [[ "$(id -u labtech)" != 0 ]] || die 'Service account cannot be root.'
  else
    useradd --system --create-home --home-dir /home/labtech --shell /bin/bash --user-group labtech
  fi
  usermod -a -G labtech www-data
  install -d -o root -g labtech -m 0750 /etc/labtech
  install -d -o labtech -g labtech -m 0750 /var/lib/labtech /var/lib/labtech/staticfiles /var/log/labtech
  install -d -o root -g root -m 0700 "$BACKUP_ROOT" "$BACKUP_ROOT/database"
  if [[ ! -e "$INSTALL_DIR" ]]; then
    install -d -o labtech -g labtech -m 0750 "$INSTALL_DIR"
  fi
}
setup_plugin_directories() {
  if [[ "${LABTECH_INSTALL_TESTING:-}" == 1 ]]; then
    mkdir -p "$PLUGIN_ROOT" "$PLUGIN_SECRET_ROOT" "$PLUGIN_SOCKET_ROOT"
  else
    install -d -o root -g labtech-plugin -m 0750 "$PLUGIN_ROOT" "$PLUGIN_SECRET_ROOT"
    install -d -o root -g labtech-plugin -m 0770 "$PLUGIN_SOCKET_ROOT"
  fi
}
setup_plugin_identity() {
  if ! getent group labtech-plugin >/dev/null; then groupadd --system labtech-plugin; fi
  if ! id labtech-plugin >/dev/null 2>&1; then
    useradd --system --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin -g labtech-plugin labtech-plugin
  fi
  usermod -a -G labtech-plugin labtech
  # Grant only traversal; plugin code must not read the managed Django environment.
  setfacl -m u:labtech-plugin:--x /var/lib/labtech
  setfacl -m u:labtech-plugin:--x /etc/labtech
  setup_plugin_directories
}
setup_media() { install -d -o labtech -g labtech -m 0750 "$INSTALL_DIR/app/mediafiles"; }
setup_database_redis() {
  local sql_password
  systemctl enable --now mariadb redis-server
  if ! systemctl is-active --quiet mariadb || ! systemctl is-active --quiet redis-server; then
    die 'MariaDB or Redis is inactive.'
    return 1
  fi
  # Identifiers are validated and the password is escaped before interpolation into stdin SQL.
  if ! validate_db_identifier "${CONFIG[DB_NAME]}" || ! validate_db_identifier "${CONFIG[DB_USER]}"; then
    die 'Invalid database identifier.'
    return 1
  fi
  sql_password="$(printf %s "${CONFIG[DB_PASSWORD]}" | python3 -c 'import sys; s=sys.stdin.read(); print(s.replace("\\", "\\\\").replace("\x27", "\x27\x27"))')"
  mariadb <<SQL
CREATE DATABASE IF NOT EXISTS \`${CONFIG[DB_NAME]}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '${CONFIG[DB_USER]}'@'localhost' IDENTIFIED BY '$sql_password';
ALTER USER '${CONFIG[DB_USER]}'@'localhost' IDENTIFIED BY '$sql_password';
GRANT ALL PRIVILEGES ON \`${CONFIG[DB_NAME]}\`.* TO '${CONFIG[DB_USER]}'@'localhost';
FLUSH PRIVILEGES;
SQL
}
setup_python() {
  as_service_user "$VENV_PYTHON" -m venv "$INSTALL_DIR/venv"
  as_service_user "$INSTALL_DIR/venv/bin/python" -m pip install --upgrade pip setuptools wheel
  as_service_user "$INSTALL_DIR/venv/bin/python" -m pip install -r "$INSTALL_DIR/requirements.txt"
  "$INSTALL_DIR/venv/bin/python" -m pip check
  "$INSTALL_DIR/venv/bin/python" -c 'import django, ldap, celery, MySQLdb, allauth, whitenoise; assert django.VERSION[:2] == (5,2)'
}
setup_env_link() {
  local link="$INSTALL_DIR/.env" current
  if [[ -L "$link" ]]; then
    current="$(readlink -- "$link")"
    [[ "$current" == "$ENV_FILE" ]] || die 'Existing .env symlink points elsewhere.'
  elif [[ -e "$link" ]]; then
    die 'Checkout .env already exists; move it manually after reviewing its secrets.'
  else
    as_service_user ln -s "$ENV_FILE" "$link"
  fi
}
render_deployment_settings() { cat <<'PY'
"""LabTech production overrides. Managed by deploy/install.sh."""
import os
from dotenv import dotenv_values
_stored = dotenv_values('/etc/labtech/labtech.env', interpolate=False)
for _key, _value in _stored.items():
    if _value is not None:
        os.environ.setdefault(_key, _value)
if _stored.get('LICENSE_SERVER_PUBLIC_KEY'):
    # systemd may retain the literal backslash-n from a quoted EnvironmentFile.
    os.environ['LICENSE_SERVER_PUBLIC_KEY'] = _stored['LICENSE_SERVER_PUBLIC_KEY']
from app.settings import *  # noqa: F403,F401

def env(key, default=''):
    return os.environ.get(key, _stored.get(key) or default)
def csv_env(key):
    return [value.strip() for value in env(key).split(',') if value.strip()]

SECRET_KEY = env('DJANGO_SECRET_KEY')
DEBUG = False
ACCOUNT_ALLOW_REGISTRATION = env('ACCOUNT_ALLOW_REGISTRATION', 'False') == 'True'
ALLOWED_HOSTS = csv_env('ALLOWED_HOSTS')
SITE_URL = env('SITE_URL')
CSRF_TRUSTED_ORIGINS = csv_env('CSRF_TRUSTED_ORIGINS')
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = SITE_URL.startswith('https://')
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
SECURE_SSL_REDIRECT = SESSION_COOKIE_SECURE
SECURE_HSTS_SECONDS = 2592000 if SESSION_COOKIE_SECURE else 0
DATABASES['default'].update({
    'NAME': env('DB_NAME'), 'USER': env('DB_USER'),
    'PASSWORD': env('DB_PASSWORD'), 'HOST': env('DB_HOST', 'localhost'),
    'PORT': env('DB_PORT', '3306'),
})
EMAIL_HOST = env('EMAIL_HOST')
EMAIL_BACKEND = ('django.core.mail.backends.smtp.EmailBackend' if EMAIL_HOST
                 else 'django.core.mail.backends.console.EmailBackend')
EMAIL_PORT = int(env('EMAIL_PORT', '465'))
EMAIL_HOST_USER = env('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD')
EMAIL_USE_SSL = env('EMAIL_USE_SSL') == 'True' if EMAIL_HOST else False
EMAIL_USE_TLS = env('EMAIL_USE_TLS') == 'True' if EMAIL_HOST else False
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL') or EMAIL_HOST_USER
CELERY_BROKER_URL = env('CELERY_BROKER_URL', 'redis://127.0.0.1:6379/0')
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND', CELERY_BROKER_URL)
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}
STATIC_ROOT = '/var/lib/labtech/staticfiles'
PY
}
install_deployment_settings() {
  local temp
  temp="$(mktemp /etc/labtech/deployment_settings.py.XXXXXX)"
  render_deployment_settings > "$temp"
  python3 - "$temp" <<'PY'
import ast,sys
with open(sys.argv[1], encoding='utf-8') as stream:
    ast.parse(stream.read())
PY
  chown root:labtech "$temp"; chmod 0640 "$temp"
  backup_managed_file "$SETTINGS_FILE"
  mv -f -- "$temp" "$SETTINGS_FILE"
}
run_manage() {
  as_service_user env PYTHONPATH="/etc/labtech:$INSTALL_DIR" DJANGO_SETTINGS_MODULE=deployment_settings \
    "$INSTALL_DIR/venv/bin/python" "$INSTALL_DIR/manage.py" "$@"
}
render_web_unit() { cat <<UNIT
[Unit]
Description=LabTech web server
After=network-online.target mariadb.service
Wants=network-online.target
[Service]
Type=simple
User=labtech
Group=labtech
WorkingDirectory=$INSTALL_DIR
EnvironmentFile=$ENV_FILE
Environment=DJANGO_SETTINGS_MODULE=deployment_settings
Environment=PYTHONPATH=/etc/labtech:$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/gunicorn app.wsgi:application --workers 3 --bind 127.0.0.1:8000 --timeout 90
Restart=on-failure
RestartSec=5
UMask=0027
PrivateTmp=true
NoNewPrivileges=true
[Install]
WantedBy=multi-user.target
UNIT
}
render_worker_unit() { cat <<UNIT
[Unit]
Description=LabTech Celery worker
After=network-online.target mariadb.service redis-server.service
Requires=redis-server.service
[Service]
Type=simple
User=labtech
Group=labtech
WorkingDirectory=$INSTALL_DIR
EnvironmentFile=$ENV_FILE
Environment=DJANGO_SETTINGS_MODULE=deployment_settings
Environment=PYTHONPATH=/etc/labtech:$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/celery -A app worker --loglevel=INFO
Restart=on-failure
RestartSec=5
UMask=0027
PrivateTmp=true
NoNewPrivileges=true
[Install]
WantedBy=multi-user.target
UNIT
}
render_beat_unit() { cat <<UNIT
[Unit]
Description=LabTech Celery beat
After=network-online.target mariadb.service redis-server.service
Requires=redis-server.service
[Service]
Type=simple
User=labtech
Group=labtech
WorkingDirectory=$INSTALL_DIR
EnvironmentFile=$ENV_FILE
Environment=DJANGO_SETTINGS_MODULE=deployment_settings
Environment=PYTHONPATH=/etc/labtech:$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/celery -A app beat --loglevel=INFO --schedule=/var/lib/labtech/celerybeat-schedule
Restart=on-failure
RestartSec=5
UMask=0027
PrivateTmp=true
NoNewPrivileges=true
[Install]
WantedBy=multi-user.target
UNIT
}
install_systemd_units() {
  local temp unit
  temp="$(mktemp -d)"
  render_web_unit > "$temp/labtech-web.service"
  render_worker_unit > "$temp/labtech-worker.service"
  render_beat_unit > "$temp/labtech-beat.service"
  systemd-analyze verify "$temp"/*.service || return 1
  for unit in labtech-web labtech-worker labtech-beat; do
    [[ ! -L "/etc/systemd/system/$unit.service" ]] || { die 'Refusing a symlinked systemd unit.'; return 1; }
    backup_managed_file "/etc/systemd/system/$unit.service" || return 1
    install -m 0644 "$temp/$unit.service" "/etc/systemd/system/$unit.service" || return 1
  done
  rm -rf -- "$temp"
  systemctl daemon-reload
}
render_plugin_unit() { cat <<UNIT
[Unit]
Description=LabTech connector %i
After=network.target
[Service]
Type=simple
User=labtech-plugin
Group=labtech-plugin
WorkingDirectory=$PLUGIN_ROOT/%i/current
ExecStart=$PLUGIN_ROOT/%i/current/venv/bin/python $PLUGIN_HELPER_ROOT/plugin-runner.py --plugin-id %i --release-root $PLUGIN_ROOT/%i/current --socket-root $PLUGIN_SOCKET_ROOT --token-path $PLUGIN_SECRET_ROOT/%i.token
Restart=on-failure
RestartSec=5
UMask=0027
MemoryMax=512M
CPUQuota=100%
TasksMax=64
NoNewPrivileges=true
PrivateTmp=true
PrivateDevices=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$PLUGIN_SOCKET_ROOT
IPAddressDeny=any
RestrictAddressFamilies=AF_UNIX
CapabilityBoundingSet=
[Install]
WantedBy=multi-user.target
UNIT
}
render_plugin_install_service() { cat <<UNIT
[Unit]
Description=LabTech signed connector installer
After=mariadb.service network-online.target
[Service]
Type=oneshot
User=root
WorkingDirectory=$PLUGIN_HELPER_ROOT/plugin-helper-source
EnvironmentFile=$ENV_FILE
Environment=DJANGO_SETTINGS_MODULE=deployment_settings
Environment=PYTHONPATH=/etc/labtech:$PLUGIN_HELPER_ROOT/plugin-helper-source
ExecStart=$PLUGIN_HELPER_ROOT/plugin-helper-venv/bin/python $PLUGIN_HELPER_ROOT/plugin-helper-source/deploy/plugin_helper.py process-queued
TimeoutStartSec=20min
[Install]
WantedBy=multi-user.target
UNIT
}
render_plugin_install_timer() { cat <<'UNIT'
[Unit]
Description=Check queued LabTech connector installs and license grace
[Timer]
OnBootSec=2min
OnUnitActiveSec=1min
Unit=labtech-plugin-install.service
Persistent=true
[Install]
WantedBy=timers.target
UNIT
}
install_plugin_helper_snapshot() {
  local root="$PLUGIN_HELPER_ROOT/plugin-helper-source"
  local runtime="$PLUGIN_HELPER_ROOT/plugin-helper-venv"
  local -a owner_args=(--chown=root:root)
  [[ ! -L "$root" && ! -L "$runtime" ]] || die 'Refusing a symlinked plugin helper path.'
  if [[ "${LABTECH_INSTALL_TESTING:-}" == 1 ]]; then
    owner_args=()
    mkdir -p "$PLUGIN_HELPER_ROOT" "$root/app" "$root/deploy" "$runtime"
  else
    install -d -o root -g root -m 0755 "$PLUGIN_HELPER_ROOT" "$root" "$root/app" "$root/deploy" "$runtime"
  fi
  rsync -a --delete "${owner_args[@]}" --chmod=Fgo-w,Dgo-w \
    --exclude=mediafiles --exclude=__pycache__ "$INSTALL_DIR/app/" "$root/app/" || return 1
  rsync -a --delete "${owner_args[@]}" --chmod=Fgo-w,Dgo-w \
    --exclude=__pycache__ "$INSTALL_DIR/deploy/" "$root/deploy/" || return 1
  [[ -z "$(find "$root/app" "$root/deploy" -type l -print -quit)" ]] || die 'Plugin helper source contains a symlink.'
  rsync -a --delete "${owner_args[@]}" --chmod=Fgo-w,Dgo-w "$INSTALL_DIR/venv/" "$runtime/" || return 1
  while IFS= read -r -d '' link; do
    [[ "$(realpath -m "$link")" != "$INSTALL_DIR"/* ]] || die 'Plugin helper venv links into the writable checkout.'
  done < <(find "$runtime" -type l -print0)
}
install_plugin_units() {
  local temp unit
  temp="$(mktemp -d)"
  render_plugin_unit > "$temp/labtech-plugin@.service"
  render_plugin_install_service > "$temp/labtech-plugin-install.service"
  render_plugin_install_timer > "$temp/labtech-plugin-install.timer"
  install_plugin_helper_snapshot || { rm -rf -- "$temp"; return 1; }
  cat > "$temp/labtech-plugins.conf" <<'TMPFILES'
d /run/labtech 0755 root root -
d /run/labtech/plugins 0770 root labtech-plugin -
TMPFILES
  install -d -o root -g root -m 0755 "$PLUGIN_HELPER_ROOT"
  install -o root -g root -m 0644 "$INSTALL_DIR/app/plugins/runner.py" "$PLUGIN_HELPER_ROOT/plugin-runner.py"
  for unit in labtech-plugin@.service labtech-plugin-install.service labtech-plugin-install.timer; do
    [[ ! -L "/etc/systemd/system/$unit" ]] || { rm -rf -- "$temp"; die 'Refusing symlinked plugin unit.'; return 1; }
    backup_managed_file "/etc/systemd/system/$unit" || { rm -rf -- "$temp"; return 1; }
    install -o root -g root -m 0644 "$temp/$unit" "/etc/systemd/system/$unit" || { rm -rf -- "$temp"; return 1; }
  done
  install -o root -g root -m 0644 "$temp/labtech-plugins.conf" /etc/tmpfiles.d/labtech-plugins.conf
  systemd-tmpfiles --create /etc/tmpfiles.d/labtech-plugins.conf
  rm -rf -- "$temp"
  systemctl daemon-reload
  systemctl enable --now labtech-plugin-install.timer
  reconcile_plugin_services
}
reconcile_plugin_services() {
  local unit
  while IFS= read -r unit; do
    [[ "$unit" =~ ^labtech-plugin@[a-z][a-z0-9-]{0,39}\.service$ ]] || continue
    systemctl try-restart "$unit" || warn "Connector $unit did not restart; core services stay available."
  done < <(systemctl list-units 'labtech-plugin@*.service' --state=running --plain --no-legend | awk '{print $1}')
}
install_plugin_publisher_key() {
  local target=/etc/labtech/plugin-marketplace-publisher.pem
  if [[ -n "${CONFIG[PLUGIN_MARKETPLACE_PUBLIC_KEY]:-}" ]]; then
    printf '%s\n' "${CONFIG[PLUGIN_MARKETPLACE_PUBLIC_KEY]}" | install -m 0644 /dev/stdin "$target"
  else
    rm -f -- "$target"
    warn 'Plugin publisher public key missing: connector installations are disabled.'
  fi
}
render_nginx_http_site() { cat <<NGINX
server {
    listen 80;
    server_name ${CONFIG[PRIMARY_HOST]};
    client_max_body_size 260M;
    location /static/ { alias /var/lib/labtech/staticfiles/; }
    location ^~ /media/course_audio/ { return 404; }
    location /media/ { alias $INSTALL_DIR/app/mediafiles/; }
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 90s;
        proxy_read_timeout 90s;
        proxy_send_timeout 90s;
    }
}
NGINX
}
install_nginx_site() {
  local target=/etc/nginx/sites-available/labtech temp previous
  target="${LABTECH_NGINX_SITE:-$target}"
  [[ ! -L "$target" ]] || { die 'Refusing a symlinked Nginx site.'; return 1; }
  if [[ -f "$target" ]] && grep -Eq 'listen[[:space:]]+([[:digit:].]+:)?443' "$target"; then
    log 'Preserving existing HTTPS Nginx configuration.'
    nginx -t
    return
  fi
  temp="$(mktemp "${target}.XXXXXX")"
  render_nginx_http_site > "$temp"
  previous="$(mktemp)"
  if [[ -e "$target" ]]; then cp -p "$target" "$previous"; else rm -f "$previous"; fi
  backup_managed_file "$target" || return 1
  install -m 0644 "$temp" "$target" || return 1
  ln -sfn "$target" /etc/nginx/sites-enabled/labtech || return 1
  if ! nginx -t; then
    if [[ -f "$previous" ]]; then cp -p "$previous" "$target"; else rm -f "$target" /etc/nginx/sites-enabled/labtech; fi
    rm -f "$temp" "$previous"
    die 'Nginx validation failed; previous site restored.'
  fi
  rm -f "$temp" "$previous"
  systemctl enable --now nginx || return 1
  systemctl restart nginx || return 1
}

run_required_checks() {
  "$INSTALL_DIR/venv/bin/python" -m pip check || return 1
  run_manage check --deploy || return 1
  run_manage makemigrations --check --dry-run || return 1
}
run_full_tests() {
  # Test failures are an explicit warning policy, but all setup gates above remain fatal.
  if run_manage test -v 2; then
    log 'Django test suite passed.'
  else
    TEST_WARNING=1
    warn "Django tests failed; inspect $LOG_FILE before production use."
  fi
}
database_has_tables() {
  local count
  count="$(mariadb -N -s -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='${CONFIG[DB_NAME]}'")" || return 2
  [[ "$count" =~ ^[0-9]+$ ]] || return 2
  (( count > 0 ))
}
backup_database() {
  LATEST_DUMP="$BACKUP_ROOT/database/${CONFIG[DB_NAME]}-$(date -u +%Y%m%dT%H%M%SZ)-$$.sql"
  umask 077
  mariadb-dump --single-transaction --routines --events --triggers "${CONFIG[DB_NAME]}" > "$LATEST_DUMP" || return 1
  chmod 0600 "$LATEST_DUMP" || return 1
  log "Pre-migration dump created at $LATEST_DUMP"
}
create_superuser_if_requested() {
  if [[ "$CREATE_ADMIN" == yes ]]; then
    if [[ "$(run_manage shell -c 'from django.contrib.auth import get_user_model; print(int(get_user_model().objects.filter(is_superuser=True).exists()))')" == 0 ]]; then
      local -a admin_args=(createsuperuser)
      [[ -z "${CONFIG[DJANGO_SUPERUSER_USERNAME]:-}" ]] || admin_args+=(--username "${CONFIG[DJANGO_SUPERUSER_USERNAME]}")
      [[ -z "${CONFIG[DJANGO_SUPERUSER_EMAIL]:-}" ]] || admin_args+=(--email "${CONFIG[DJANGO_SUPERUSER_EMAIL]}")
      run_manage "${admin_args[@]}"
    else
      log 'Superuser already exists.'
    fi
  fi
}
activate_services() {
  local service
  for service in labtech-web labtech-worker labtech-beat; do
    systemctl enable "$service" || return 1
    systemctl restart "$service" || return 1
  done
}
configure_optional_tls() {
  [[ "$ENABLE_TLS" == yes ]] || return 0
  if [[ "${CONFIG[PRIMARY_HOST]}" != *.* || "${CONFIG[PRIMARY_HOST]}" =~ ^[0-9.]+$ ]] || ! getent ahosts "${CONFIG[PRIMARY_HOST]}" >/dev/null; then
    NGINX_WARNING='Certificate issuance skipped: public hostname or DNS unavailable.'
    warn "$NGINX_WARNING"
    return 0
  fi
  local nginx_site=/etc/nginx/sites-available/labtech saved_site
  saved_site="$(mktemp)"
  cp -p "$nginx_site" "$saved_site"
  if ! certbot --nginx --non-interactive --agree-tos --redirect \
    --email "${CONFIG[CERTBOT_EMAIL]}" -d "${CONFIG[PRIMARY_HOST]}"; then
    cp -p "$saved_site" "$nginx_site"
    nginx -t && systemctl reload nginx
    rm -f "$saved_site"
    NGINX_WARNING='Certificate issuance failed; existing Nginx configuration retained. Inspect Certbot logs.'
    warn "$NGINX_WARNING"
    return 0
  fi
  rm -f "$saved_site"
  CONFIG[SITE_URL]="https://${CONFIG[PRIMARY_HOST]}"
  CONFIG[CSRF_TRUSTED_ORIGINS]="https://${CONFIG[PRIMARY_HOST]}"
  write_env_file "$ENV_FILE"
  run_required_checks
  nginx -t
  activate_services
  systemctl enable --now certbot.timer
}
run_health_checks() {
  local service home_status
  for service in mariadb redis-server nginx labtech-web labtech-worker labtech-beat; do
    systemctl is-active --quiet "$service" || { die "$service is inactive."; return 1; }
  done
  home_status="$(curl --silent --show-error --max-time 15 -o /dev/null -w '%{http_code}' \
    -H "Host: ${CONFIG[PRIMARY_HOST]}" http://127.0.0.1/)" || { die 'Local HTTP health check failed.'; return 1; }
  if [[ "$home_status" != 2* && "$home_status" != 3* ]]; then
    if [[ "$home_status" != 503 || "${CONFIG[MAINTENANCE_MODE]:-False}" != True ]]; then
      die "Local HTTP health check returned $home_status."
      return 1
    fi
  fi
  local audio_status
  audio_status="$(curl --silent --show-error --max-time 15 -o /dev/null -w '%{http_code}' \
    -H "Host: ${CONFIG[PRIMARY_HOST]}" http://127.0.0.1/media/course_audio/probe.mp3)"
  [[ "$audio_status" == 404 ]] || die 'Course audio direct media path is not protected.'
}
run_activation_pipeline() {
  PHASE=django-validation
  run_required_checks || return 1
  PHASE=tests
  run_full_tests
  PHASE=migrations
  if database_has_tables; then
    backup_database || return 1
  else
    local inspection_status=$?
    [[ "$inspection_status" == 1 ]] || return "$inspection_status"
  fi
  run_manage migrate --noinput || return 1
  run_manage collectstatic --noinput || return 1
  create_superuser_if_requested || return 1
  PHASE=services
  install_systemd_units || return 1
  install_nginx_site || return 1
  activate_services || return 1
  if ! install_plugin_units; then warn 'Connector service setup failed; core services remain active.'; fi
}
print_summary() {
  if ((TEST_WARNING)); then
    log 'Result: completed with test warnings.'
  else
    log 'Result: healthy.'
  fi
  log "Site: ${CONFIG[SITE_URL]}"
  log "Install: $INSTALL_DIR | Config: /etc/labtech | Media: $INSTALL_DIR/app/mediafiles"
  log "Backups: $BACKUP_ROOT | Installer log: $LOG_FILE"
  log 'Services: labtech-web, labtech-worker, labtech-beat; systemctl status labtech-web labtech-worker labtech-beat'
  log 'Live logs: journalctl -fu labtech-web (also labtech-worker and labtech-beat)'
  log 'Allow inbound SSH 22 and HTTP 80; HTTPS 443 if TLS is enabled. Configure social login in Django Admin.'
  [[ -z "$NGINX_WARNING" ]] || warn "$NGINX_WARNING"
}
on_failure() {
  local line="$1" status="$2"
  trap - ERR
  warn "Installation failed in phase $PHASE at line $line (exit $status)."
  warn "Log: $LOG_FILE | Latest database dump: ${LATEST_DUMP:-none} | Configuration backups: ${BACKUP_DIR:-none}"
  warn 'Inspect: systemctl status labtech-web labtech-worker labtech-beat nginx; journalctl -u labtech-web -n 100'
  exit "$status"
}
main() {
  if [[ "${1:-}" == --help ]]; then usage; return 0; fi
  [[ $# -eq 0 ]] || { usage >&2; return 64; }
  trap 'on_failure "$LINENO" "$?"' ERR
  preflight
  PHASE=configuration
  if [[ -f "$ENV_FILE" ]]; then load_existing_config "$ENV_FILE"; fi
  collect_configuration
  check_existing_checkout
  install -d -m 0700 /var/log/labtech
  touch "$LOG_FILE"
  chmod 0600 "$LOG_FILE"
  exec > >(tee -a "$LOG_FILE") 2>&1
  PHASE=packages
  install_packages
  PHASE=identity
  setup_identity_directories
  setup_plugin_identity
  # Git access may need the service account created on the first run.
  PHASE=checkout
  verify_git_access
  sync_repository "$INSTALL_DIR"
  setup_media
  PHASE=python
  setup_python
  PHASE=environment
  write_env_file "$ENV_FILE"
  install_plugin_publisher_key
  setup_env_link
  install_deployment_settings
  PHASE=database
  setup_database_redis
  run_activation_pipeline
  PHASE=tls
  configure_optional_tls
  PHASE=health
  run_health_checks
  print_summary
}
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
