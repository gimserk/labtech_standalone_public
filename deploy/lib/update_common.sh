#!/usr/bin/env bash
# Shared application update logic. Callers provide INSTALL_DIR and run_manage().
labtech_validate_update_runtime() {
  "$INSTALL_DIR/venv/bin/python" -m pip check || return 1
  run_manage check --deploy || return 1
  run_manage makemigrations --check --dry-run || return 1
}
labtech_apply_update_schema_and_static() {
  run_manage migrate --noinput || return 1
  run_manage collectstatic --noinput || return 1
}
