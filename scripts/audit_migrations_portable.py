#!/usr/bin/env python3
"""Portable, read-only LabTech migration audit.

Copy this SINGLE script to an existing DEV/BETA/PROD host. It does not need
updated LabTech source files or a new package build. It imports only the
host's existing deployment settings and MariaDB/MySQL driver, never Django
models, migration executor, or management commands.

Example (host already has /etc/labtech/deployment_settings.py):
  /opt/labtech/venv/bin/python audit_migrations_portable.py \\
    --settings deployment_settings --settings-dir /etc/labtech \\
    --app-dir /opt/labtech/app --output /tmp/labtech-prod-migrations.json

Use a credentials-protected output location. Reports do NOT include passwords,
database hostnames, usernames, or database names. No production writes.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone


def tracked_names(app_dir: Path) -> set[str] | None:
    # Git metadata may not exist in the compiled production release.
    base = app_dir.parent
    try:
        result = subprocess.run(
            ["git", "-C", str(base), "ls-files", "--", "app/migrations"],
            check=True, capture_output=True, text=True,
        )
        if not (base / ".git").exists():
            return None
        return set(result.stdout.splitlines())
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None


def applied_migrations(settings_module: str, settings_dir: Path) -> dict[str, str | None]:
    # Use the installed settings and DB driver. No django.setup() or application
    # imports, so existing PROD code does not need a release merely to audit.
    sys.path.insert(0, str(settings_dir))
    importlib.invalidate_caches()
    config = importlib.import_module(settings_module)
    db = config.DATABASES["default"]
    engine = db["ENGINE"]
    options = dict(db.get("OPTIONS") or {})
    if engine == "django.db.backends.mysql":
        import MySQLdb
        values = {
            "db": db.get("NAME"), "user": db.get("USER"),
            "passwd": db.get("PASSWORD"), "host": db.get("HOST") or "localhost",
        }
        if db.get("PORT"):
            values["port"] = int(db["PORT"])
        if options.get("read_default_file"):
            values["read_default_file"] = options["read_default_file"]
        if options.get("unix_socket"):
            values["unix_socket"] = options["unix_socket"]
        conn = MySQLdb.connect(**values)
    elif engine == "django.db.backends.sqlite3":
        import sqlite3
        conn = sqlite3.connect(db["NAME"])
    else:
        raise ValueError("Unsupported database engine for portable audit")
    try:
        cur = conn.cursor()
        try:
            cur.execute("SELECT name, applied FROM django_migrations WHERE app = %s" if engine.endswith("mysql") else
                        "SELECT name, applied FROM django_migrations WHERE app = ?", ("app",))
            return {name: str(applied) if applied is not None else None
                    for name, applied in cur.fetchall()}
        finally:
            cur.close()
    finally:
        conn.close()


def capture(settings: str, settings_dir: Path, app_dir: Path) -> dict:
    migrations = app_dir / "migrations"
    if not migrations.is_dir():
        raise ValueError("Migration directory not found at specified --app-dir")
    tracked = tracked_names(app_dir)
    files = {}
    for path in sorted(migrations.glob("[0-9]*.py")):
        relative = "app/migrations/" + path.name
        files[path.stem] = {
            "filename": relative,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "tracked_by_git": relative in tracked if tracked is not None else None,
        }
    applied = applied_migrations(settings, settings_dir)
    return {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "settings_module": settings,
        "app": "app",
        "capture_mode": "portable_sql_read_only",
        "git_tracking_available": tracked is not None,
        "migration_files": files,
        "applied": applied,
        "applied_missing_from_disk": sorted(set(applied) - set(files)),
        "disk_not_recorded_as_applied": sorted(set(files) - set(applied)),
        "applied_untracked_files": sorted(
            n for n in applied if n in files and files[n]["tracked_by_git"] is False
        ),
        # Unlike the Django-aware audit, this script cannot safely infer the
        # migration graph or future SQL, especially from a compiled release.
        "graph_leaf_names": None,
        "graph_conflicts": None,
        "pending_plan": None,
        "disk_dependencies": None,
        "graph_nodes_not_on_disk": None,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--settings", required=True)
    p.add_argument("--settings-dir", required=True, type=Path)
    p.add_argument("--app-dir", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    try:
        if args.output.exists():
            raise ValueError("Output file already exists; choose a new report path")
        report = capture(args.settings, args.settings_dir, args.app_dir)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        # Restrict freshly-created audit reports to the current user.
        fd = os.open(str(args.output), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, sort_keys=True)
            stream.write("\n")
        print("Read-only audit written:", args.output)
        print("Applied app migrations:", len(report["applied"]))
        print("Applied records missing from disk:", len(report["applied_missing_from_disk"]))
        print("Applied files untracked in git:", len(report["applied_untracked_files"]))
        print("Graph and migration plan: not evaluated (portable audit)")
        return 0
    except Exception as exc:
        # Avoid printing DB exception details: they may contain connection info.
        print(f"Audit failed safely: {type(exc).__name__}. Check settings, permissions and driver.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
