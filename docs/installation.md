# Installing LabTech on Ubuntu 24.04 or Newer

This guide installs LabTech directly on a dedicated x86_64 server running Ubuntu 24.04 or a newer official Ubuntu release. The public package contains Linux x86_64 modules built for CPython 3.13; Python 3.12, Python 3.14, PyPy, and ARM64 cannot run this build. The installer rejects unsupported platforms and interpreters before changing the host. It manages MariaDB, Redis, Gunicorn, Celery, Nginx, and optional Let's Encrypt TLS, and it is also the supported safe-rerun and update path.

## Before you begin

Prepare:

- A dedicated x86_64 server running Ubuntu 24.04 or a newer Ubuntu release, with root or `sudo` access and at least 2 GiB of free disk space.
- CPython 3.13, including its `venv` and development packages. Keep the system's default `python3` unchanged.
- A DNS name for the server. An address record must point to the server before requesting Let's Encrypt TLS.
- Outbound access to Ubuntu package mirrors, GitHub, Python package indexes, and Let's Encrypt when TLS is selected.
- Inbound SSH (22/tcp) and HTTP (80/tcp). Allow HTTPS (443/tcp) when using TLS.
- Read access to the public `gimserk/labtech_standalone_public` repository over HTTPS. No GitHub account or deploy key is required.

The installer does not change UFW, a cloud firewall, or upstream network policy. Open only the ports your deployment requires.

## Install Python 3.13 before running the installer

Check whether your configured package sources provide Python 3.13. On Ubuntu 24.04 it may require an additional package source; the [deadsnakes PPA](https://launchpad.net/~deadsnakes/+archive/ubuntu/ppa) publishes Python 3.13 for that release. Review the source before adding it to a production server. For example, on Ubuntu 24.04:

```bash
sudo apt-get install -y software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt-get update
sudo apt-get install -y python3.13 python3.13-venv python3.13-dev
python3.13 --version
```

On a release whose configured sources already provide these packages, install the three `python3.13` packages without adding the PPA. The installer selects `python3.13` by default. If it is installed under another path, set `LABTECH_VENV_PYTHON` to that CPython 3.13 executable for installation and future reruns. If a previous run created an incomplete virtual environment under another Python version, remove only `/opt/labtech/venv` before rerunning.

The default managed locations are:

| Location | Purpose |
|---|---|
| `/opt/labtech` | Git checkout and Python virtual environment |
| `/etc/labtech/labtech.env` | Root-owned runtime configuration and secrets |
| `/etc/labtech/deployment_settings.py` | Generated production Django settings |
| `/opt/labtech/app/mediafiles` | Uploaded media |
| `/var/lib/labtech` | Celery scheduler state and collected static files |
| `/var/log/labtech/install.log` | Installer and test output |
| `/var/backups/labtech` | Configuration and pre-migration database backups |

## Create the service account and check repository access

Git operations run as the `labtech` service account. Create that account before the first clone if it does not exist:

```bash
id labtech >/dev/null 2>&1 || \
  sudo useradd --system --create-home --home-dir /home/labtech \
    --shell /bin/bash --user-group labtech
sudo -u labtech env GIT_TERMINAL_PROMPT=0 \
  git ls-remote https://github.com/gimserk/labtech_standalone_public.git refs/heads/main
```

The command must print the `main` reference. It uses GitHub's public HTTPS endpoint without storing credentials.

## Run a clean installation

Clone the repository as the service account, then run the installer from the checkout:

```bash
sudo install -d -m 0750 -o labtech -g labtech /opt/labtech
sudo -u labtech git clone https://github.com/gimserk/labtech_standalone_public.git /opt/labtech
sudo /opt/labtech/deploy/install.sh
```

Alternatively, copy the reviewed public repository—including `deploy/install.sh`—to a temporary location and run `sudo ./deploy/install.sh`; the installer will create and synchronize `/opt/labtech` itself.

The production installer tracks `main`. A maintainer testing an implementation branch on a disposable host may explicitly override it:

```bash
sudo env LABTECH_TARGET_BRANCH=codex/native-installer ./deploy/install.sh
```

Do not use a development branch override on a production host.

## Answer the configuration prompts

Press Enter to accept the displayed default or retain the existing value on a rerun. Existing secret values are never displayed. For optional integration values, enter a single `-` to clear an existing value. These are the prompts in order:

| Prompt | Guidance and blank behavior |
|---|---|
| Installation directory | Defaults to `/opt/labtech`; only a safe path under `/opt` or `/srv` is accepted. |
| Primary hostname | DNS hostname or IP used by Nginx and the local health check. |
| Public site URL | Full `http://` or `https://` origin with no path. |
| Allowed hosts | Comma-separated Django hosts; the primary hostname is always included. |
| CSRF trusted origins | Comma-separated HTTP/HTTPS origins. |
| Request Let's Encrypt TLS | Answer yes only for a public DNS hostname that resolves to this server. |
| Certificate email | Required and shown only when Let's Encrypt TLS is selected. |
| MariaDB database name | Defaults to `labtech_db`; letters, digits, and underscores only. |
| MariaDB application user | Defaults to `labtech`; letters, digits, and underscores only. |
| MariaDB host and port | Fixed to the locally managed MariaDB service at `localhost:3306`. |
| SMTP host | Leave blank to use Django's console email backend. |
| SMTP port and user | Port defaults to 465; the user may be blank when SMTP is disabled. |
| SMTP password | Silent optional prompt; blank disables/retains according to whether a value exists. |
| Use SMTP SSL / STARTTLS | Select at most one. Defaults are SSL yes, STARTTLS no. |
| Default sender address | May be blank; normally the SMTP sender address. |
| Maintenance mode and account registration | Explicit `True` or `False`; both default to `False`. |
| LDAP, Google, Facebook, Microsoft login | Explicit `True` or `False`; all default to `False`. Magic link is forced `False` because it is unsupported. |
| Google, Facebook, and Microsoft OAuth IDs and secrets | Prompts cover each provider. Secret prompts are silent; empty values keep existing values. |
| LDAP server URI, bind DN/password, search bases, staff/admin groups | LDAP URI and the bind/search settings are required when LDAP is enabled. The bind password prompt is silent. |
| License server URL and public key | Optional for an install without Marketplace access. When a URL is set, provide a valid public key PEM file path; Enter retains the stored key, and `-` clears it. A PEM with multiple lines is preserved. |
| First administrator username and email | Optional prefilled inputs to Django's interactive superuser command. Its password is never stored. |
| Stripe publishable key | Leave blank to disable Stripe. |
| Stripe secret and webhook secret | Silent optional prompts. |
| Square application ID | Leave blank to disable Square. |
| Square access token | Silent optional prompt. |
| Square location ID | Optional when Square is disabled. |
| Square environment | `sandbox` or `production`; defaults to `sandbox`. |
| Guacamole URL | Leave blank to disable Guacamole integration. |
| Guacamole admin user | Optional when Guacamole is disabled. |
| Guacamole admin password and SSO secret | Silent optional prompts. |
| Create the first Django superuser | If selected and no superuser exists, Django securely prompts for the account and password. |

On a fresh installation, HTTPS is activated only after Certbot succeeds; the site uses HTTP until then. The installer generates the Django secret, MariaDB application password, and QEMU lab-check encryption key on the first run. It preserves them on every rerun. It never writes a superuser password to disk. An old `DJANGO_SUPERUSER_PASSWORD` value is discarded; Django asks for the password interactively. `DJANGO_DEBUG` remains `False`, and `ENABLE_MAGICLINK` remains `False`. The managed environment covers the authentication, OAuth, LDAP, licensing, SMTP, payment, Guacamole, Celery, and lab-check fields as well as the core settings. Do not paste credentials or the PEM into a command-line argument. If you already have a checkout `.env` file, move it out of the checkout after reviewing its contents; the installer refuses to overwrite it. Enter its values at the installer prompts.

## Safely rerun or update the installation

Run the same command again:

```bash
sudo /opt/labtech/deploy/install.sh
```

The installer preserves the database, uploaded media, stable secrets, and untracked files. It collects static assets under `/var/lib/labtech/staticfiles`, outside the Git checkout. It reinstalls required packages, reconciles the virtual environment, and updates the expected branch with a fast-forward-only merge. It stops without changing the checkout when it finds:

- modified or staged tracked files;
- a Git remote other than `https://github.com/gimserk/labtech_standalone_public.git`;
- a branch that has diverged from its remote;
- a non-Git, nonempty installation directory.

Resolve those conditions manually. The installer never runs `git reset --hard`, `git clean`, or a forced checkout. Before applying migrations to a database that already has tables, it creates a timestamped dump under `/var/backups/labtech/database`.

## Configure DNS and optional HTTPS

Nginx is installed and validated over HTTP first. For built-in TLS, point the primary hostname to the server, allow inbound 80/tcp and 443/tcp, answer yes to the TLS prompt, and provide a certificate email. Certbot uses the Nginx plugin, configures redirects, and enables its renewal timer.

On a first TLS attempt, DNS or certificate failure retains the validated HTTP site and leaves the public URL configured for HTTP. On a rerun of an already-working HTTPS installation, the installer preserves the existing HTTPS site and settings if DNS lookup or Certbot reconfiguration fails. Correct DNS/firewall issues and safely rerun the installer. The installer never changes firewall rules.

## Verify services and inspect logs

Check all required services and the local proxy path:

```bash
sudo systemctl is-active mariadb redis-server nginx \
  labtech-web labtech-worker labtech-beat
curl -I -H 'Host: your.labtech.example' http://127.0.0.1/
```

Inspect status and live logs:

```bash
sudo systemctl status labtech-web labtech-worker labtech-beat nginx
sudo journalctl -fu labtech-web
sudo journalctl -fu labtech-worker
sudo journalctl -fu labtech-beat
sudo journalctl -fu nginx
sudo less /var/log/labtech/install.log
```

The local site request must return a 2xx or 3xx response, or 503 when maintenance mode is explicitly enabled. The installer treats inactive services or any other failed HTTP health check as fatal.

## Configure social login in Django Admin

Google, Facebook, Microsoft, and other django-allauth application credentials remain database-backed. After installation, sign in to Django Admin and configure the required **Social applications**, provider client IDs/secrets, site assignment, and callback URLs. They are intentionally not collected by the installer.

## Understand protected course audio

Uploaded course audio is protected content. Nginx must never serve `/media/course_audio/` directly; that path is explicitly denied before the general media alias. Verify the protection:

```bash
curl -I -H 'Host: your.labtech.example' \
  http://127.0.0.1/media/course_audio/probe.mp3
```

The response must be `404`. Student playback and download use authenticated Django course routes such as `/courses/.../audio/.../stream/` and `/courses/.../audio/.../download/`, where enrollment and availability checks are enforced.

## Back up and restore MariaDB

The installer creates a mode-0600, single-transaction dump before migrations whenever the database already contains tables. List available dumps without guessing a filename:

```bash
sudo find /var/backups/labtech/database -maxdepth 1 -type f \
  -name 'labtech_db-*.sql' -printf '%TY-%Tm-%Td %TH:%TM %p\n' | sort
```

A restore can destroy newer data. Schedule downtime and verify the selected file. The guarded procedure stops application writers first, takes an additional safety dump, and starts services only after a successful restore. The operator must enter the exact backup path:

```bash
read -r -p 'Exact backup file to restore: ' BACKUP_FILE
case "$BACKUP_FILE" in
  /var/backups/labtech/database/*.sql) ;;
  *) echo 'Refusing path outside the LabTech database backup directory' >&2; exit 1 ;;
esac
sudo test -f "$BACKUP_FILE" || { echo 'Backup file not found' >&2; exit 1; }

sudo bash -s -- "$BACKUP_FILE" <<'RESTORE'
set -Eeuo pipefail
backup_file="$1"
safety_dump="/var/backups/labtech/database/pre-restore-$(date -u +%Y%m%dT%H%M%SZ).sql"
systemctl stop labtech-web labtech-worker labtech-beat
umask 077
mariadb-dump --single-transaction --routines --events --triggers labtech_db > "$safety_dump"
mariadb labtech_db < "$backup_file"
systemctl start labtech-web labtech-worker labtech-beat
RESTORE
sudo systemctl is-active labtech-web labtech-worker labtech-beat
```

Review the dump and migration history before restoring. Do not automatically restore a dump after a migration failure; a restore may discard legitimate writes or require application-specific migration recovery.

## Course audio storage

Course audio uploads require writable persistent media storage. The default upload limit is 250 MiB; set `AUDIO_MAX_UPLOAD_BYTES` to a smaller byte value if needed. Configure the reverse proxy to accept requests above this limit, and back up uploaded media alongside the database. Uploaded audio is served through enrolled-user endpoints that require readable, seekable storage. External audio URLs are linked directly over HTTPS; the server does not fetch them. Course content backup snapshots store uploaded audio in the database JSON field, so large recordings can increase database backup size and may require a larger database packet setting. Exported course packages include the uploaded media separately.

If a web server serves `/media/` directly from disk, deny public requests to `/media/course_audio/` before the general media rule. Django also excludes this prefix from its media route; private playback and downloads must pass through the authenticated course audio URLs.

## Diagnose an installation with test warnings


Required dependency checks, Django deployment checks, migration consistency, migrations, static collection, service activation, and health checks are hard gates. The full Django test suite is different: under the approved installation policy, a test failure allows setup to continue but the final result is **completed with test warnings**, never healthy.

Before production use, inspect the captured failure and rerun it from the managed virtual environment:

```bash
sudo less /var/log/labtech/install.log
cd /opt/labtech
sudo -u labtech env \
  PYTHONPATH=/etc/labtech:/opt/labtech \
  DJANGO_SETTINGS_MODULE=deployment_settings \
  /opt/labtech/venv/bin/python manage.py test -v 2
```

For a hard failure, the installer prints the failed phase, log path, latest database dump, configuration-backup location, and `systemctl`/`journalctl` diagnostics. Correct the underlying problem and rerun the same installer; do not delete the database, media directory, or `/etc/labtech/labtech.env`.
