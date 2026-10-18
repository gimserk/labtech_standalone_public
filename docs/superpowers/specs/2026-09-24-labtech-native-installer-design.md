# LabTech Native Installer Design

**Date:** 2026-09-24  
**Status:** Approved design, pending written-spec review  
**Target repository:** `gimserk/labtech`  
**Target branch:** `codex/install-automation-design`

## Purpose

Provide one production-oriented, idempotent `install.sh` for a clean LabTech installation on Ubuntu 24.04 or newer. The same script must also repair or safely update an existing installation without deleting its database, uploaded media, or stable secrets.

The installer manages the host-level services LabTech currently needs: MariaDB, Redis, the release's default Python 3 runtime (3.12 or newer), Gunicorn, Celery worker and beat, Nginx, and optional Let's Encrypt TLS.

## Repository Constraints Confirmed on `main`

- `requirements.txt` currently contains only `cryptography>=42.0,<47`, so it does not describe the application's full runtime environment.
- `app/settings.py` hard-codes production hosts, the site URL, and trusted origins.
- The current audio model uses `CheckConstraint(condition=...)`, requiring Django 5.1 or newer. Django 5.2 LTS is the selected runtime line.
- The current Dockerfile is a minimal development base and is not an application deployment image.
- The repository contains no existing native installer, systemd units, or Nginx deployment configuration.
- Uploaded course audio is protected content and must not be exposed through a general Nginx media alias.

## Approved Decisions

| Area | Decision |
|---|---|
| Platform | Ubuntu 24.04 or newer, native packages and systemd |
| Packaging | One idempotent root-run shell script |
| Reinstall policy | Safe update; preserve database, media, and secrets |
| Git authentication | Preconfigured read-only SSH deploy key |
| HTTPS | Nginx HTTP first, optional Certbot after DNS validation |
| Integrations | Prompt for currently supported integrations |
| Administrator | Secure interactive Django superuser creation |
| Verification | Required checks are hard gates; full test failures warn and continue |
| Repository behavior | Refuse tracked/staged local changes; fast-forward only |

## Goals

1. Produce a complete first installation from an Ubuntu 24.04 or newer server.
2. Make repeated runs safe and predictable.
3. Keep live secrets outside Git.
4. Preserve the database, uploaded files, and encryption keys on reruns.
5. Configure the web process and both Celery processes.
6. serve static and ordinary media efficiently while keeping course audio private.
7. Provide useful backups, diagnostics, health checks, and operator commands.
8. Avoid default passwords and avoid placing credentials in command-line arguments.

## Non-goals

- Supporting non-Ubuntu distributions or Ubuntu releases older than 24.04.
- Docker Compose or Kubernetes deployment.
- Multi-node or high-availability deployment.
- Automatically modifying UFW or cloud-provider firewalls.
- Configuring unsupported LDAP, licensing, or authentication-toggle settings.
- Automatically rolling back arbitrary Django migrations.
- Unattended installation; prompts are required for initial administrator and integration configuration.

## Deliverable and Location

Add one executable installer at `deploy/install.sh`. It may be copied to a new server and run before the repository exists.

The script is organized into functions for:

- argument and platform validation;
- prompt handling and secret preservation;
- package installation;
- system-user and directory setup;
- Git verification and checkout;
- MariaDB and Redis provisioning;
- Python environment construction;
- generated deployment settings;
- Django validation and setup;
- systemd unit generation;
- Nginx and optional Certbot configuration;
- service activation and health checks;
- completion and recovery output.

The implementation uses `set -Eeuo pipefail`, a line-aware error trap, explicit quoting, and no shell tracing of secrets.

## Inputs

The installer prompts for:

- installation directory, default `/opt/labtech`;
- primary hostname;
- public site scheme and URL;
- additional allowed hosts;
- trusted CSRF origins;
- whether to request a Let's Encrypt certificate;
- certificate email when TLS is requested;
- database name and user, with validated safe defaults;
- SMTP host, port, user, password, SSL/TLS choice, and sender address;
- Stripe keys;
- Square application, access, location, and environment values;
- Guacamole endpoint and credentials;
- whether to create the first Django superuser.

Sensitive input uses silent prompts. On a rerun, existing values are retained when the operator accepts the default, but secret values are never displayed.

Blank credentials disable an optional integration where possible. Social-login applications remain configured through Django Admin because the current application stores those values through Django/allauth rather than environment variables.

## Safe Path and Platform Rules

Before changing the host, the script verifies:

- it is running as root;
- the OS is Ubuntu 24.04 or a newer official release, identified by a canonical `YEAR.04` or `YEAR.10` `VERSION_ID` with a release year from 24 through 9999;
- the installation path is absolute and is not `/`, `/opt`, `/etc`, `/usr`, `/var`, a home root, or another broad system path;
- the requested database/user identifiers contain only the supported identifier characters;
- hostname, URL, and origin values have valid basic forms;
- adequate disk space is available;
- required network and DNS operations are possible;
- GitHub SSH host verification and repository access succeed.

The installer must never use an unresolved variable, wildcard, or broad directory as a recursive deletion target.

## System Packages

Install or verify the Ubuntu packages needed for:

- Git and OpenSSH client;
- the release's default Python 3 runtime (3.12 or newer), virtual environments, and headers;
- compiler/build tooling and `pkg-config`;
- MariaDB server/client and development headers;
- Redis;
- Nginx;
- Certbot and its Nginx integration;
- `curl`, CA certificates, and supporting utilities;
- image and XML development libraries required by Python dependencies.

Package installation is idempotent.

## System Identity and Directories

Create the `labtech` system user if absent. Existing compatible users are reused.

Managed locations:

| Path | Purpose | Ownership |
|---|---|---|
| `/opt/labtech` | Git checkout | `labtech:labtech` |
| `/etc/labtech/labtech.env` | Runtime configuration and secrets | `root:labtech`, mode `0640` |
| `/etc/labtech/deployment_settings.py` | Environment-specific Django overrides | `root:labtech`, mode `0640` |
| `/var/lib/labtech` | Celery beat state | `labtech:labtech` |
| `/var/log/labtech` | Installer/application operational logs if needed | restricted |
| `/var/backups/labtech` | Pre-migration database dumps and config backups | root-restricted |

The checkout's `.env` is a managed symlink to `/etc/labtech/labtech.env`, allowing Django's existing dotenv loading and systemd services to share one source without committing secrets.

## Git Checkout and Rerun Behavior

### New installation

1. Verify `ssh -T`/repository access using a preconfigured read-only deploy key.
2. Create the installation parent directory safely.
3. Clone `git@github.com:gimserk/labtech.git`.
4. Check out `main`.

### Existing Git installation

1. Verify that the checkout is the expected repository.
2. Report untracked files but leave them untouched.
3. Stop if the index or tracked working tree has modifications.
4. Fetch `main`.
5. Update using fast-forward-only semantics.
6. Never run `git reset --hard`, `git clean`, or force checkout.

### Existing non-Git installation path

Stop without overwriting it and print remediation instructions.

## Secret Lifecycle

On first install, generate:

- a cryptographically strong Django secret key;
- a strong MariaDB application password from a SQL-safe character set;
- a Fernet-compatible `LAB_CHECK_SECRET_KEY`.

On reruns, retain these values from the existing environment file. In particular, the QEMU lab-check encryption key must never be rotated implicitly, because existing encrypted guest-agent credentials depend on it.

The superuser password is accepted only by Django's interactive management command and is never written to configuration or logs.

Before replacing a managed configuration, systemd, or Nginx file, create a timestamped root-readable backup.

## Deployment Settings

Do not modify tracked `app/settings.py` during installation. Generate `/etc/labtech/deployment_settings.py`, which imports `app.settings` and overrides deployment-specific values.

The generated module controls:

- `ALLOWED_HOSTS`;
- `SITE_URL`;
- `CSRF_TRUSTED_ORIGINS`;
- secure-cookie behavior based on the active scheme;
- proxy SSL handling;
- email settings and a safe disabled/fallback behavior when SMTP is blank;
- Redis broker/result URLs;
- Django 5.2 `STORAGES`, including WhiteNoise's compressed manifest static backend.

Management commands and services receive:

- `DJANGO_SETTINGS_MODULE=deployment_settings`;
- a `PYTHONPATH` containing both `/etc/labtech` and the checkout.

## Python Environment and Dependencies

Use the release's default Python 3 runtime, require version 3.12 or newer, and pin Django to `>=5.2,<5.3`.

Install the repository's requirements and an explicit runtime compatibility set covering the packages currently imported by LabTech, including:

- Django and Gunicorn;
- MariaDB/MySQL Python support;
- python-dotenv and WhiteNoise;
- Celery with Redis;
- django-allauth;
- django-ckeditor;
- django-payments;
- django-crispy-forms and crispy-bootstrap5;
- django-phonenumber-field and phonenumbers;
- Pillow;
- requests and BeautifulSoup;
- Docker, Proxmox, Paramiko, JWT, and MQTT clients;
- Stripe and Square SDKs;
- cryptography.

The implementation plan must derive and test the exact package names/constraints against current `main`. `pip check` is a hard gate.

A rerun reinstalls/upgrades the selected constraints as needed. It does not trust the current environment merely because a virtualenv directory exists.

## Database and Redis

Start and enable MariaDB and Redis.

MariaDB provisioning:

- creates the database if absent;
- creates or reconciles the localhost application user;
- updates its password to match the preserved environment value;
- grants access only to the LabTech database;
- uses `utf8mb4` defaults where supported;
- never drops existing data.

Before migrations on an existing database, write a timestamped `mariadb-dump` to `/var/backups/labtech`. The installer prints the dump path on later failure.

## Required Validation and Django Setup

Run in this order:

1. `pip check`;
2. `python manage.py check --deploy`;
3. `python manage.py makemigrations --check --dry-run`;
4. the full test suite with `--settings=test_settings`;
5. a pre-migration database dump when the database already contains tables;
6. `python manage.py migrate --noinput`;
7. `python manage.py collectstatic --noinput`;
8. secure interactive superuser creation when requested.

Dependency, import, Django configuration, migration-consistency, migration, and static-collection failures are hard stops.

Per the approved policy, test-suite failures are captured and clearly reported but do not stop the installation. A run with test failures ends as "completed with test warnings," never as fully healthy.

## systemd Services

Generate and enable:

### `labtech-web.service`

- runs Gunicorn as `labtech`;
- binds only to `127.0.0.1:8000`;
- uses three workers by default;
- uses a timeout safely above the 45-second lab-check deadline;
- restarts on unexpected failure;
- starts after networking and MariaDB.

### `labtech-worker.service`

- runs `celery -A app worker`;
- uses the production deployment settings;
- starts after Redis and MariaDB;
- restarts on unexpected failure.

### `labtech-beat.service`

- runs `celery -A app beat`;
- stores schedule state under `/var/lib/labtech`;
- starts after Redis and MariaDB;
- restarts on unexpected failure.

All services use the shared environment file and run without root privileges. Unit files receive appropriate systemd hardening that is compatible with the application's filesystem and networking needs.

## Nginx

Generate one Nginx site configuration that:

- listens on port 80 initially;
- proxies application requests to `127.0.0.1:8000`;
- forwards host, client address, and protocol headers;
- sets `client_max_body_size` slightly above 250 MiB;
- uses proxy timeouts long enough for lab-check requests;
- serves collected static files directly;
- may serve ordinary media directly;
- explicitly denies `/media/course_audio/`;
- leaves authenticated course audio streaming/downloading to Django routes;
- is validated with `nginx -t` before reload.

The installer does not alter UFW. It reports that inbound SSH, HTTP, and optionally HTTPS must be allowed.

## Optional TLS

HTTP configuration is installed and validated first.

When TLS is requested:

1. verify the hostname resolves appropriately enough to attempt issuance;
2. collect a certificate email;
3. run Certbot's Nginx integration;
4. enable renewal through the distribution's timer;
5. update the stored site URL and trusted origin to HTTPS;
6. re-run relevant Django and Nginx validation.

A certificate issuance failure leaves the validated HTTP site in place and reports remediation steps.

## Activation and Health Checks

Only after hard-gate validation, migrations, and static collection succeed:

1. install validated unit files;
2. run `systemctl daemon-reload`;
3. enable and restart web, worker, and beat;
4. install/validate/reload Nginx;
5. verify MariaDB and Redis;
6. verify all three LabTech services;
7. perform a local HTTP request with the configured Host header.

A failed required service or HTTP health check causes a nonzero installer exit.

## Failure and Recovery

The error trap reports:

- the failed phase and command location;
- the installer log;
- relevant `systemctl status` and `journalctl` commands;
- the latest database dump when one exists;
- any configuration backups made during the run.

The installer does not automatically restore a database after a failed migration. Django migrations are not universally reversible, and an automatic restore could discard legitimate concurrent data. It prints an exact administrator-invoked restore procedure instead.

The script avoids activating unvalidated service or Nginx files. Where feasible, the prior live configuration remains in place until replacement configuration has passed syntax checks.

## Completion Output

The final summary includes:

- installation result: healthy or completed with test warnings;
- site URL and TLS status;
- install, configuration, media, and backup locations;
- service names;
- commands for service status and live logs;
- required firewall ports;
- remaining social-login configuration in Django Admin;
- any failed tests;
- database restore guidance location.

It never prints database, SMTP, payment, Guacamole, Django, or lab-check secrets.

## Acceptance Criteria

1. A fresh Ubuntu 24.04 or newer host with a working read-only GitHub deploy key can install LabTech using one script.
2. The application starts under Gunicorn and returns a local response through Nginx.
3. Celery worker and beat are enabled and running.
4. MariaDB and Redis are enabled and usable by the application.
5. Django 5.2 is installed and `python manage.py check` succeeds with the audio model.
6. A second run preserves the database, media, Django secret, and lab-check key.
7. A dirty tracked checkout causes a safe stop without overwriting files.
8. A non-Git nonempty installation directory causes a safe stop.
9. Nginx cannot directly serve files under `/media/course_audio/`.
10. No default password or live secret is committed or printed.
11. Hard-gate failures prevent service activation.
12. Full-test failures are warned and recorded according to the approved policy.
13. Existing databases receive a pre-migration dump.
14. Optional Certbot failure does not destroy the working HTTP configuration.
