# LabTech migration-history reconciliation before production deployment

**Status:** audit and deployment plan only. Nothing in this document authorizes
changing production database contents or deleting/faking migration records.
The active production database's migration ledger and schema have **not yet**
been inspected. An in-memory SQLite regression pass is not a production MariaDB
migration validation.

## Why this is necessary

On 2026-11-14, development had **applied but untracked** migration files:

- Merge-only: `0027_merge_20261023_1141`, `0030_merge_20261023_1621`,
  `0033_merge_20261025_1404`, `0036_merge_20261030_1711`,
  `0038_merge_20261031_0042`, `0039_merge_20261031_0320`,
  `0059_merge_20261031_1557`, `0063_merge_20261031_1614`,
  `0067_merge_20261031_1732`, `0068_merge_20261031_1752`,
  `0070_merge_20261111_1750`, `0071_merge_20261113_0002`,
  `0072_merge_20261113_1703`, `0073_merge_20261113_1804`,
  `0074_merge_0072_ctf_foundation_0073_merge_20261113_1804`,
  `0081_merge_20261114_0003`.
- Schema-altering (cannot treat as empty merge files):
  `0029_alter_assignmentrubric_id_alter_rubricassessment_id_and_more`,
  `0034_alter_assignmentrubric_id_alter_rubricassessment_id_and_more`,
  `0069_alter_cybercitysocalert_id_and_more`.
- State-only, applied with no SQL:
  `0082_reconcile_local_soc_pk_state`, created during the subsequent
  troubleshooting and adjusted to represent implicit BigAutoField metadata.

An earlier applied local `0076_merge_20261113_2215` was subsequently
moved outside the migration directory. Determine its provenance and applied
ledger status separately. **Do not drop its history record** merely because
the file is absent.

The tracked GitHub migration chain now ends at
`0080_align_soc_activity_primary_keys`. Development reports
`makemigrations --check --dry-run` => **No changes detected**, and
110 isolated CTF/SOC tests passed. An earlier full run passed 828 tests
(4 skipped). These are development checks, not proof of production safety.

## Non-negotiable guardrails

1. Preserve student grades, submissions, media, courses, and all database data.
2. **Never** run `migrate --fake`, `migrate --fake-initial`,
   `migrate app zero`, delete from `django_migrations`, or manually rename
   a migration on production to make the graph appear green.
3. Do not copy the entire development migrations directory to production.
4. Preserve and checksum every already-applied local migration file.
5. Validate any actual schema/PK conversion **on a restored production MariaDB
   clone** with the production code/configuration and a verified database
   backup before deploying.
6. Review the production database's current applied ledger and actual SQL
   schema before creating a *canonical* replacement or bridge migration.
   Do not treat all same-number migrations as interchangeable.

## Step A: Capture read-only migration inventories

Use a separately timestamped output file in a secured location on each host.
The script reads `django_migrations` but never writes to it. Be sure the
`--settings` module is the one that connects to that host's actual database.
Use the appropriate production settings module rather than copying a name.

**Development** (in the active LabTech Python virtual environment):

```bash
cd /opt/labtech
python scripts/audit_migration_history.py capture \
  --settings deployment_settings \
  --output /tmp/labtech-dev-migrations.json
git status --short app/migrations
git ls-files app/migrations
python manage.py migrate app --plan --settings=deployment_settings
```

Replace `deployment_settings` if development uses a different settings module.

**Production** (run only after confirming the desired settings and database):

```bash
cd /opt/labtech
python scripts/audit_migration_history.py capture \
  --settings deployment_settings \
  --output /tmp/labtech-prod-migrations.json
python manage.py migrate app --plan --settings=deployment_settings
```

`migrate --plan` **only displays** the plan. Do not run `migrate` on
production during this audit.

Safely transfer the production audit JSON to a secured staging/development
machine (it contains migration names, checksums and timestamps, not database
credentials). Compare *offline*:

```bash
python scripts/audit_migration_history.py compare \
  /tmp/labtech-dev-migrations.json /tmp/labtech-prod-migrations.json \
  > /tmp/labtech-migration-comparison.json
cat /tmp/labtech-migration-comparison.json
```

Stop and review the following:

- **Production applied migration missing from disk**: do not delete or fake
  ledger entries; recover its exact original file and inspect dependencies.
- **Same migration filename but different SHA256 across hosts**:
  provenance conflict. Preserve both copies; do not overwrite one with
  another simply to match filenames.
- **Local-only applied migration with real operations**:
  assess its effect on the actual schema and any downstream dependency.
- **Different graph leaves, pending plans, or absent dependencies**:
  derive a canonical graph preserving both histories. Never invent a
  no-op bridge for missing schema effects.
- `0080` changes primary-key definitions and merits schema verification on
  restored production MariaDB, even when model state is now consistent.

## Step B: Produce an immutable migration evidence bundle

Back up the **exact original** untracked development migration files
(outside `app/migrations`) as an archive. Do not move, edit, or remove
the live originals while collecting evidence.

```bash
cd /opt/labtech
mkdir -p /tmp/labtech-migration-audit
git status --short app/migrations > /tmp/labtech-migration-audit/dev-git-status.txt
python - <<'PY'
from pathlib import Path
import subprocess, tarfile
root = Path.cwd()
tracked = set(subprocess.check_output(
    ["git", "ls-files", "--", "app/migrations"], text=True
).splitlines())
untracked = [
    p for p in sorted((root / "app/migrations").glob("[0-9]*.py"))
    if p.relative_to(root).as_posix() not in tracked
]
with tarfile.open("/tmp/labtech-migration-audit/dev-untracked-migrations.tar.gz", "w:gz") as tar:
    for path in untracked:
        tar.add(path, arcname=path.relative_to(root).as_posix())
print("Archived", len(untracked), "untracked migration files without modifying originals")
PY
sha256sum /tmp/labtech-migration-audit/dev-untracked-migrations.tar.gz
```

Record any earlier moved `0076_merge_20261113_2215.py` separately
if present in a local backups folder.

## Step C: Review schema against a restored production MariaDB backup

Before any write on production, verify the database backup can be restored,
then restore into an isolated staging host. Review:

- The physical column data type and AUTO_INCREMENT for each of the 23
  SOC/activity primary keys affected by migration `0080`.
- Primary-key/foreign-key compatibility and referenced indexes.
- The effects and ordering of local `0029`, `0034`, and `0069` on
  the *current* production schema and the tracked migration chain.
- The SQL generated by all unapplied tracked migrations:
  `python manage.py sqlmigrate app <migration_name> --settings=deployment_settings`, and the full
  `python manage.py migrate app --plan --settings=deployment_settings` result.
- Constraints on MariaDB: Django conditional unique constraints are not
  created there (including CTFSubmission and CTFTeamInvitation); this is
  a **separate data-integrity release gate**.

Choose one of these resolutions **only after** comparing production evidence:

1. **Production only uses tracked migrations, and staging applies them
   cleanly.** Keep its tracked chain; do not add local dev-only migrations to
   production. Preserve dev-only applied files on development and document
   that difference.
2. **Production has applied extra local migrations.** Recover those exact
   original files before migrating. Build a reviewed canonical graph or
   environment-specific bridge with dependencies that account for the actual
   applied schema. Test the full plan on the restored production clone.
3. **Schemas diverge across environments.** Develop an explicit
   forward-only, data-preserving schema reconciliation and a rollback/recovery
   plan, rather than applying a no-op or fake migration.

## Step D: Production gate and rollback

- Require a working, tested backup of MariaDB **and** LabTech media files.
- Capture current app Git commit, migration inventory, schema snapshot and
  systemd service configuration.
- Confirm the restored-clone migration plan is fully rehearsed, has no
  destructive unreviewed schema operations, and ends with
  `makemigrations --check --dry-run` returning no changes.
- Run the application regression suite using `app.test_settings` (in-memory
  database); additionally run production-like integration checks on the
  restored MariaDB clone.
- Stage a maintenance/rollback window for any real primary-key DDL.
- After production deployment, rerun read-only migration inventory and
  `showmigrations app` to confirm the expected ledger.

**Current decision:** production migration rollout is **blocked pending
production audit evidence**; no production schema changes or applied
migration ledger modifications should be attempted yet.
