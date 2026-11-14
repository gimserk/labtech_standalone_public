# LabTech CTF regression verification

Use `bash scripts/verify_ctf_regressions.sh ctf` from a **development checkout** with the Python virtualenv activated and the project's dependencies installed. This runs:

- `manage.py check --settings=app.test_settings`
- `manage.py makemigrations --check --dry-run --settings=app.test_settings`
- The CTF Phase 2–5C, existing CTF 2.0, and QEMU collector/parser regression tests, on the in-memory SQLite test database

`bash scripts/verify_ctf_regressions.sh full` performs the same system/migration checks and runs the entire Django `app` test suite. `checks` performs only the migration and system checks.

Each step records stderr and stdout into a separate timestamped `ctf-regression-logs/<timestamp>/` directory. The command exits **nonzero** if any part fails; it does not overwrite results, suppress test failures, or edit the production database. Override the interpreter with `LABTECH_TEST_PYTHON=/opt/labtech/venv/bin/python` and optionally provide `LABTECH_TEST_OUTPUT_DIR=/some/test/log/path`.

The focused GitHub Actions workflow uses the same script and uploads the logs when the runner starts. Existing GitHub runs from 2026-11-14 have repeatedly failed within seconds with no step metadata and `BlobNotFound` on the log endpoint; that behavior cannot be diagnosed from tests and is **not** proof the application passed or failed. Check repository Actions administration, billing/spending/runner allowance and organization runner restrictions.

## Release gate

1. On **development**, run `ctf` and `full` modes, retaining failure logs.
2. Validate migration `0080_align_soc_activity_primary_keys.py` against a **restored production MariaDB backup**, not only SQLite. It touches SOC and activity primary keys and may require a maintenance window.
3. Do not roll the regression fixes into production without passing checks and reviewing failed tests.

## Diagnosing a local-only migration leaf

If Django reports `Conflicting migrations detected; multiple leaf nodes in the migration graph: (0076_merge_20261113_2215, 0080_align_soc_activity_primary_keys in app)`, inspect the development checkout:

```bash
cd /opt/labtech
git status --short app/migrations
git ls-files app/migrations/0076_merge_20261113_2215.py
cat app/migrations/0076_merge_20261113_2215.py
python manage.py showmigrations app --settings=app.test_settings
```

The `0076_merge_20261113_2215.py` file is **not part of the tracked GitHub `main` branch** as checked on November 14, 2026. It may be local/untracked or from a different branch; it should not be added as a dependency to the shared migration history without provenance checks.

**Only if it is confirmed to be untracked, purely local, and never applied to any relevant database**, move it out of the migrations directory rather than deleting it:

```bash
mkdir -p /opt/labtech/local-migration-backups
mv app/migrations/0076_merge_20261113_2215.py /opt/labtech/local-migration-backups/
bash scripts/verify_ctf_regressions.sh ctf
```

Do **not** move an applied migration or one with dependent migrations. When in doubt, keep it untouched and inspect `django_migrations` in a restored backup. If it was applied or is depended upon, reconcile it with a carefully reviewed merge migration and preserve the database history.

## Full suite test discovery

The `full` option now discovers `app/test_*.py` modules and passes their explicit `app.test_...` labels to Django's test runner. A broad `manage.py test app` discovery was importing the checkout root package as `labtech.app`, executing root `__init__.py` which expects `labtech.celery`. Explicit test labels avoid the unintended package import without altering production Celery startup. A genuine test failure still returns nonzero.

## Full-suite module discovery fix (November 14, 2026)

Earlier versions printed `Discovered 1 application test modules` because the `find -printf` escape sequence generated a single line with literal `\\n` separators. This caused Django to try importing nonsensical composite module names such as `py\\ntest_vnc_port_range`. The updated Bash runner expands each `app/test_*.py` file into a distinct argument without `find`, `sed`, or shell word-splitting. The test suite should now report many modules, not one.

The local migration conflict is **separate**. Before moving `0076_merge_20261113_2215.py`, inspect the exact file and check applied migration state against the database that was used when it was created. To check whether the extra migration was applied, use a **read-only SQL query** against the actual *development database* (or a restored backup), not the in-memory test database:

```sql
SELECT app, name, applied
FROM django_migrations
WHERE app = 'app' AND name = '0076_merge_20261113_2215';
```

If an entry exists, do not move the file or modify the migration graph before reviewing its dependencies and downstream database history. If it was never applied, and is local-only with no downstream dependency, safely back it up outside `app/migrations/` as documented above. The runner deliberately avoids changing migration files automatically.

## November 14: recurring SOC ID drift and PyJWT import failure

### Why 23 ID migrations were proposed

After applying `0080_align_soc_activity_primary_keys`, Django detected a new `0082` alteration for the same 23 SOC/activity `id` fields. Those Python models *explicitly* declare `models.BigAutoField(primary_key=True)`, but the original `0080` serialized the equivalent underlying SQL field as *auto-created*, with `auto_created=True`, `serialize=False`, and `verbose_name='ID'`. Django's migration autodetector compares the deconstructed field states, not just SQL types, so it continued to propose changes.

The corrected `0080` serializes the **same BigAutoField primary-key SQL type** with the metadata of the actual explicit model definitions. This changes historical migration state metadata but does **not** add a new migration or require reapplying `0080`; it must still be reviewed against a staging MariaDB schema before a production rollout. Avoid creating an `0082` migration solely to flip this field metadata back and forth.

A local untracked `0081_merge_20261114_0003.py` is a separate graph reconciliation created on development. Preserve that migration on the development instance if recorded applied. Before promoting code to production, review all untracked local migration dependencies and do not assume production has the same history.

### Why ten Plugin Marketplace tests failed with `jwt.encode`

`requirements.txt` pins `PyJWT==2.10.1`. Its correct `import jwt` module exposes `encode()`. Another distribution named `jwt` also imports as `jwt` but does not provide the PyJWT API.

Diagnose the *active development virtualenv*:

```bash
cd /opt/labtech
python -c 'import jwt, importlib.metadata as md; print(jwt.__file__); print(md.packages_distributions().get("jwt")); print(getattr(jwt, "encode", None))'
python -m pip show PyJWT jwt
```

If the conflicting `jwt` package is installed, remove that **distribution** from the development venv and reinstall the required PyJWT package; do not change application code or mask these tests:

```bash
python -m pip uninstall jwt
python -m pip install --force-reinstall 'PyJWT==2.10.1'
python -c 'import jwt; assert callable(jwt.encode); print(jwt.__file__)'
```

Run these commands only after confirming `python` points to the intended venv; do not execute indiscriminately on production. The full regression runner now checks for the correct JWT import separately, saving a `pyjwt-dependency.log` file when it fails. Then rerun:

```bash
bash scripts/verify_ctf_regressions.sh ctf
bash scripts/verify_ctf_regressions.sh full
```

## November 14 follow-up: definitive SOC PK state fix (implicit IDs)

The earlier fix to `0080` did not stop drift because the development machine has applied legacy parallel migrations that serialize the same 23 IDs as Django **auto-created** fields. A new local state-only `0082_reconcile_local_soc_pk_state.py` was successfully applied with **no SQL**, but the migration autodetector still proposed `0083` for the same fields. The issue is not column type; it is explicit-versus-implicit ID metadata.

**Repository correction:** the 23 SOC/activity model `id = models.BigAutoField(primary_key=True)` declarations have been removed. `app.apps.AppConfig.default_auto_field = 'django.db.models.BigAutoField'` generates *the same* primary key type and schema automatically. Historical `0080` now keeps the auto-created metadata, so it matches the upstream historical and local legacy branches. This is a model/migration *state consistency* fix, not a database migration.

**Special local development follow-up:** Do not delete the applied local `0082_reconcile_local_soc_pk_state.py` or its `django_migrations` record. It was written as a state-only reconciliation in the previous troubleshooting step and its 23 operations still declare explicit IDs. After `git pull --ff-only`, inspect and back up that untracked file, then update only the **state-only** field declarations so it preserves implicit IDs:

```bash
cd /opt/labtech
cp -p app/migrations/0082_reconcile_local_soc_pk_state.py \
  app/migrations/0082_reconcile_local_soc_pk_state.py.backup
python - <<'PY'
from pathlib import Path
p = Path("app/migrations/0082_reconcile_local_soc_pk_state.py")
s = p.read_text()
old = "field=models.BigAutoField(primary_key=True)"
new = "field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')"
assert s.count(old) == 23, f"Unexpected migration field count: {s.count(old)}"
assert "database_operations=[]" in s, "Not the expected state-only migration"
p.write_text(s.replace(old,new))
print("Aligned 23 state-only SOC/activity IDs to auto-created metadata")
PY
python manage.py makemigrations --check --dry-run
```

The backup has a `.backup` extension, so it will not be interpreted as a migration module. The local 0082 migration has no database operations, and reloading its file updates Django's *in-memory* migration state on subsequent commands without changing schema or replaying migrations. Preserve and separately reconcile all locally applied, untracked migrations before deploying to another environment.

**Do not use `makemigrations --merge`, generate another `0083`, delete the local `0082`, or change migration records.** The fix remains unverified until local drift check and full regression run pass. Production migration-history reconciliation is still required.
