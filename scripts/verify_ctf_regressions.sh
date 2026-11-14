#!/usr/bin/env bash
# Run isolated Django regressions in a checked-out LabTech development tree.
# Does NOT connect to production databases, Proxmox, Wazuh or Checkmk.
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mode="${1:-ctf}"
case "$mode" in
  ctf|full|checks) ;;
  *) echo "Usage: bash scripts/verify_ctf_regressions.sh [ctf|full|checks]" >&2; exit 2 ;;
esac

if [ ! -f manage.py ] || [ ! -f app/test_settings.py ]; then
  echo "Run from a LabTech checkout with app/test_settings.py." >&2; exit 2
fi

PYTHON="${LABTECH_TEST_PYTHON:-python3}"
if ! "$PYTHON" -c 'import django' >/dev/null 2>&1; then
  echo "Django is not installed in $PYTHON; activate the development venv first." >&2; exit 2
fi
if ! "$PYTHON" -c 'import app.test_settings as s; assert s.DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3"; assert s.DATABASES["default"]["NAME"] == ":memory:"' >/dev/null 2>&1; then
  echo "Refusing to run: isolated in-memory SQLite test database was not confirmed." >&2; exit 2
fi

# Keep a unique artifact directory, including failures and stderr.
STAMP="$(date -u +%Y%m%dT%H%M%SZ)-$$"
OUT="${LABTECH_TEST_OUTPUT_DIR:-$ROOT/ctf-regression-logs/$STAMP}"
mkdir -p "$OUT"
echo "Logging isolated $mode regressions to $OUT"
status=0

run_check() {
  local label="$1"; shift
  echo "--- $label ---"
  if "$@" > "$OUT/$label.log" 2>&1; then
    tail -n 10 "$OUT/$label.log" || true
  else
    local rc="$?"
    status=1
    echo "FAILED ($rc): $label — see $OUT/$label.log" >&2
    grep -E 'FAIL:|ERROR:|AssertionError|Traceback|SystemCheckError|Migration|Error' "$OUT/$label.log" | tail -n 30 || true
  fi
}

# Detect merge migrations that exist only on a local checkout. Never silently
# delete, modify, fake-apply, or generate migrations: production histories may
# depend on them. Print the exact files so an instructor can audit provenance.
if [ -f app/migrations/0076_merge_20261113_2215.py ]; then
  echo 'NOTICE: local app/migrations/0076_merge_20261113_2215.py detected.'
  if ! git ls-files --error-unmatch app/migrations/0076_merge_20261113_2215.py >/dev/null 2>&1; then
    echo 'This migration is not tracked by the checked-out Git branch.'
    echo 'Inspect it with: cat app/migrations/0076_merge_20261113_2215.py'
    echo 'Inspect changes with: git status --short app/migrations'
    echo 'Inspect the database with: python manage.py showmigrations app'
    echo 'Do not delete it before checking whether it was applied to a database.'
  fi
fi

run_check django-system-check "$PYTHON" manage.py check --settings=app.test_settings
run_check migration-drift "$PYTHON" manage.py makemigrations --check --dry-run --settings=app.test_settings

# The Plugin Marketplace generates RS256 test licenses via PyJWT. The
# unrelated 'jwt' distribution exports the same import name but no encode().
# Surface the venv problem directly instead of reporting ten misleading
# application regressions from the same missing dependency.
if [ "$mode" = full ]; then
  run_check pyjwt-dependency "$PYTHON" -c '
import importlib.metadata as metadata
import jwt
print("jwt module path:", getattr(jwt, "__file__", "<unknown>"))
print("jwt distributions:", metadata.packages_distributions().get("jwt", []))
try:
    print("PyJWT installed:", metadata.version("PyJWT"))
except metadata.PackageNotFoundError:
    print("PyJWT is not installed")
assert callable(getattr(jwt, "encode", None)), (
    "The imported jwt module lacks encode(). Install PyJWT in the test "
    "virtual environment and remove only the conflicting jwt package "
    "after verifying which distribution owns the jwt import."
)
'
fi

if [ "$mode" = ctf ]; then
  run_check ctf-soc-tests "$PYTHON" manage.py test \
    app.test_ctf_phase5c app.test_ctf_phase5b app.test_ctf_phase5 \
    app.test_ctf_phase4c app.test_ctf_phase4b app.test_ctf_phase4a \
    app.test_ctf_phase3b app.test_ctf_phase3 app.test_ctf_phase2 app.test_ctf2 \
    app.test_cybercity_qga_collector app.test_cybercity_qga_parser_hardening \
    --settings=app.test_settings --noinput -v 2
elif [ "$mode" = full ]; then
  # Do not use 'manage.py test app' or unscoped test discovery here:
  # Django/unittest can import the checkout directory as a top-level
  # 'labtech' package, whose root __init__.py expects labtech.celery.
  # Explicit module labels avoid that unintended project import.
  # Use Bash arrays rather than printf/sed pipelines: a literal '\\n'
  # inside find -printf joined every module into one invalid test label.
  shopt -s nullglob
  modules=()
  for file in app/test_*.py; do
    name="${file##*/}"
    modules+=("app.${name%.py}")
  done
  shopt -u nullglob
  if [ "${#modules[@]}" -eq 0 ]; then
    status=1
    echo 'No app/test_*.py modules found; refusing to report full regression success.' >&2
  else
    echo "Discovered ${#modules[@]} application test modules."
    run_check full-app-tests "$PYTHON" manage.py test "${modules[@]}" --settings=app.test_settings --noinput -v 1
  fi
fi

printf '\n'
if [ "$status" -eq 0 ]; then
  echo "PASS: All requested isolated checks completed."
else
  echo "FAIL: One or more checks failed. Full traceback logs remain in $OUT" >&2
fi
echo "Results: $OUT"
exit "$status"
