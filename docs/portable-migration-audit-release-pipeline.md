# Migration audits without a PROD release

LabTech deployment path:

`ChatGPT → GitHub private labtech_standalone → DEV → BETA → compiled DEMO → GitHub labtech_standalone_public → PROD`

Do **not** deploy a new LabTech release to production merely to run a migration
audit. This is a read-only inventory tool and release manifest process.

## Option A: portable, standalone PROD audit

`scripts/audit_migrations_portable.py` is a single-file script that may be
transferred separately to a secured existing PROD host (e.g. via an approved
administrative file-transfer mechanism). It uses the **existing** production
Python environment, settings and installed MariaDB driver, but does **not**
import Django models, migrations or invoke Django's migration executor.

On each machine, confirm settings path, app directory, and venv first.
Example (replace these if your environment differs):

```bash
cd /opt/labtech
/opt/labtech/venv/bin/python /tmp/audit_migrations_portable.py \
  --settings deployment_settings \
  --settings-dir /etc/labtech \
  --app-dir /opt/labtech/app \
  --output /tmp/labtech-prod-migrations.json
```

This requires `/etc/labtech/deployment_settings.py` to be importable by that
Python interpreter, and uses database credentials configured in that existing
settings module. The script reads only `django_migrations` and hashes local
`app/migrations/*.py`. It does **not** execute migrations, restart services,
or write to application databases.

For DEV and BETA, run the same script under the *respective environment* to
obtain comparable files:

```bash
/opt/labtech/venv/bin/python /tmp/audit_migrations_portable.py \
  --settings deployment_settings --settings-dir /etc/labtech \
  --app-dir /opt/labtech/app --output /tmp/labtech-dev-migrations.json
```

Move report JSON files securely to one comparison host. The script
`scripts/audit_migration_history.py compare` can compare the files:

```bash
python scripts/audit_migration_history.py compare \
  /tmp/labtech-dev-migrations.json /tmp/labtech-prod-migrations.json
```

**Limitation:** Standalone mode intentionally does **not** compute Django
migration graph leaves, conflict detection, or pending SQL. Those fields are
`null`, meaning **unknown**, not passing. Use the Django-aware audit on
DEV/BETA and validate the actual production migration plan on a restored
production MariaDB clone before deployment.

**Security:** The reports contain migration names, timestamps, and checksums
but not DB credentials or connection targets. Protect the reports nonetheless;
the standalone writer creates them with `0600` permissions and refuses to
overwrite existing output. Importing existing deployment settings may execute
module-level initialization; review the settings module before using. This tool
does not bypass any production access policy.

## Option B: compiled DEMO migration manifest

In the compiled DEMO stage, run:

```bash
python scripts/create_release_migration_manifest.py \
  --release-root /path/to/compiled/labtech \
  --release-id your-release-version-or-commit \
  --output /path/to/release-artifacts/labtech-migrations.json
```

Include `labtech-migrations.json` with the published release artifacts,
after verifying that the generated list includes the intended migration set.
It records file names and SHA-256 fingerprints, and provides a single
migration-set fingerprint. It needs no running Django app and no database
connection.

**Do not** assume the manifest creates missing migrations, reconciles
different applied histories, or verifies actual DB schema. It is only a
package-integrity/provenance artifact. Until the build process is explicitly
integrated, generating and bundling this file is a manual release step.

## Release gate

Before promoting BETA → compiled DEMO → public GitHub → PROD:

1. Compare DEV, BETA, PROD applied migration ledgers and file hashes.
2. Preserve applied untracked migrations, including DEV-specific `0081` and
   state-only `0082`; do not delete ledger entries or use `migrate --fake`.
3. Review every schema-changing local migration against a **restored PROD
   MariaDB backup**. Determine whether PROD uses the tracked linear chain or
   has independent historical applied migrations.
4. Only then author a forward-only reconciliation (if necessary), test
   migration SQL and data-preserving rollback, and release via the existing
   staged process.

The CKEditor replacement project remains deferred. This audit makes **no**
changes to existing course content or editor storage.
