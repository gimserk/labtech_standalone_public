#!/usr/bin/env python3
"""Create a deterministic migration-file manifest for a LabTech release.

Run in the COMPILED DEMO staging tree after packaging, before publishing to
labtech_standalone_public. Read-only against the release tree; only writes the
new manifest JSON to the explicit --output path. No Django/DB required.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
from datetime import datetime, timezone


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--release-root", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--release-id", required=True)
    args = p.parse_args()
    root = args.release_root.resolve()
    directory = root / "app" / "migrations"
    if not directory.is_dir():
        p.error(f"No app/migrations folder under {root}")
    migration_files = list(sorted(directory.glob("[0-9]*.py")))
    if not migration_files:
        p.error("Release has no numbered migration files; refusing to emit manifest")
    if args.output.exists():
        p.error("Refusing to overwrite existing release manifest")
    files = [{
        "path": "app/migrations/" + path.name,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "bytes": path.stat().st_size,
    } for path in migration_files]
    digest = hashlib.sha256(
        "\n".join(f"{item['path']}:{item['sha256']}" for item in files).encode()
    ).hexdigest()
    manifest = {
        "schema_version": 1,
        "release_id": args.release_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "migration_count": len(files),
        "migration_set_sha256": digest,
        "migration_files": files,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(args.output), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as out:
        json.dump(manifest, out, indent=2)
        out.write("\n")
    print("Release migration manifest:", args.output)
    print("Migration count:", len(files), "set SHA256:", digest)


if __name__ == "__main__":
    main()
