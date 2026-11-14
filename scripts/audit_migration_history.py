#!/usr/bin/env python3
"""Read-only migration provenance audit for LabTech (Django 5.2).

Examples:
  python scripts/audit_migration_history.py capture --settings app.settings --output /tmp/dev-migrations.json
  python scripts/audit_migration_history.py compare /tmp/dev-migrations.json /tmp/prod-migrations.json

This tool never calls migrate, makemigrations, or writes to django_migrations.
Reports include migration filenames, names, checksums, and timestamps, not DB credentials.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "app" / "migrations"
sys.path.insert(0, str(ROOT))


def _tracked_paths() -> set[str] | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "--", "app/migrations"],
            check=True, capture_output=True, text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    return set(result.stdout.splitlines())


def _snapshot(settings: str) -> dict:
    # Configure once, using exactly the specified environment's settings.
    os.environ["DJANGO_SETTINGS_MODULE"] = settings
    import django
    django.setup()
    from django.db import connections
    from django.db.migrations.loader import MigrationLoader
    from django.db.migrations.recorder import MigrationRecorder
    from django.db.migrations.executor import MigrationExecutor

    connection = connections["default"]
    tracked = _tracked_paths()
    files = {}
    for path in sorted(MIGRATIONS.glob("[0-9]*.py")):
        relative = path.relative_to(ROOT).as_posix()
        files[path.stem] = {
            "filename": relative,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "tracked_by_git": (relative in tracked) if tracked is not None else None,
        }

    # This reads django_migrations on the actual configured database.
    recorder = MigrationRecorder(connection)
    applied_records = list(
        recorder.migration_qs.filter(app="app").order_by("applied", "name")
        .values_list("name", "applied")
    )
    applied = {
        name: timestamp.isoformat() if timestamp else None
        for name, timestamp in applied_records
    }
    loader = MigrationLoader(connection)
    disk = {
        name: migration
        for (app, name), migration in loader.disk_migrations.items()
        if app == "app"
    }
    graph_nodes = {name for (app, name) in loader.graph.nodes if app == "app"}
    disk_names = set(disk)
    applied_names = set(applied)
    executor = MigrationExecutor(connection)
    leaves = sorted(n for app, n in loader.graph.leaf_nodes("app"))
    targets = [("app", leaf) for leaf in leaves]
    plan = executor.migration_plan(targets)
    pending = [
        f"{migration.app_label}.{migration.name}"
        for migration, backwards in plan if not backwards
    ]
    # Avoid exposing settings or connection strings, including DB host and name.
    report = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "settings_module": settings,
        "app": "app",
        "git_tracking_available": tracked is not None,
        "migration_files": files,
        "graph_leaf_names": leaves,
        "graph_conflicts": {key: sorted(values)
                            for key, values in loader.detect_conflicts().items()},
        "applied": applied,
        "applied_missing_from_disk": sorted(applied_names - disk_names),
        "disk_not_recorded_as_applied": sorted(disk_names - applied_names),
        "applied_untracked_files": sorted(
            name for name in applied_names
            if name in files and files[name]["tracked_by_git"] is False
        ),
        "pending_plan": pending,
        "disk_dependencies": {
            name: sorted(f"{app}.{dep}" for app, dep in migration.dependencies)
            for name, migration in sorted(disk.items())
        },
        "graph_nodes_not_on_disk": sorted(graph_nodes - disk_names),
    }
    return report


def _compare(dev: dict, prod: dict) -> dict:
    for report in (dev, prod):
        if report.get("schema_version") != 1 or report.get("app") != "app":
            raise ValueError("Unsupported report schema/app; regenerate using this script")
    d = set(dev["applied"])
    p = set(prod["applied"])
    shared = set(dev["migration_files"]) & set(prod["migration_files"])
    hash_mismatch = sorted(
        name for name in shared
        if dev["migration_files"][name]["sha256"] != prod["migration_files"][name]["sha256"]
    )
    return {
        "dev_only_applied": sorted(d - p),
        "prod_only_applied": sorted(p - d),
        "shared_filename_hash_mismatches": hash_mismatch,
        "dev_applied_missing_from_disk": dev["applied_missing_from_disk"],
        "prod_applied_missing_from_disk": prod["applied_missing_from_disk"],
        "dev_applied_untracked_files": dev["applied_untracked_files"],
        "prod_applied_untracked_files": prod["applied_untracked_files"],
        "dev_pending_migrations": dev["pending_plan"],
        "prod_pending_migrations": prod["pending_plan"],
        "prod_graph_conflicts": prod["graph_conflicts"],
        "safe_to_migrate_automatically": False,
        "next_step": "Review graph, file hashes, applied histories, pending SQL and staging schema; no automatic migration or --fake.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    cap = sub.add_parser("capture", help="Read the configured DB's migration records; never modify DB")
    cap.add_argument("--settings", required=True, help="Actual Django settings module (not test_settings)")
    cap.add_argument("--output", required=True, type=Path, help="Where to write audit JSON")
    comp = sub.add_parser("compare", help="Compare two previously captured JSON reports offline")
    comp.add_argument("dev", type=Path)
    comp.add_argument("prod", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "capture":
            report = _snapshot(args.settings)
            if args.output.exists():
                raise ValueError(f"Refusing to overwrite existing report: {args.output}")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
            print(f"Read-only migration report: {args.output}")
            print(f"Applied: {len(report['applied'])}; graph leaves: {report['graph_leaf_names']}")
            print(f"Applied untracked files: {len(report['applied_untracked_files'])}")
            print(f"Applied records missing from disk: {len(report['applied_missing_from_disk'])}")
            print(f"Pending migration plan: {len(report['pending_plan'])}")
            if (report["graph_conflicts"] or report["applied_missing_from_disk"]
                    or report["applied_untracked_files"]):
                print("REVIEW REQUIRED: Do not apply or fake migrations until history is reconciled.")
            return 0
        dev = json.loads(args.dev.read_text())
        prod = json.loads(args.prod.read_text())
        result = _compare(dev, prod)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(f"Migration audit failed safely: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
