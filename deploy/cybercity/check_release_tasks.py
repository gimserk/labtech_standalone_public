#!/usr/bin/env python3
"""Fail closed if a compiled public LabTech release omits Cyber City tasks.

Usage:
    python deploy/cybercity/check_release_tasks.py /path/to/public-build
    python deploy/cybercity/check_release_tasks.py /opt/labtech --runtime

The --runtime check initializes Django and verifies Celery's task registry.
It does not connect to Proxmox, allocate VMs, or mutate the database.
"""
import argparse
import os
from pathlib import Path
import sys

REQUIRED_MODULES = (
    'tasks',
    'views',
    'cybercity_building_tasks',
    'cybercity_utility_tasks',
    'cybercity_reset_tasks',
)
REQUIRED_TASKS = (
    'app.cybercity_building_tasks.provision_cybercity_building_task',
    'app.cybercity_utility_tasks.provision_cybercity_utility_task',
    'app.cybercity_reset_tasks.reset_cybercity_machine_task',
)


def verify_build(root):
    app_dir = root / 'app'
    missing = []
    for module in REQUIRED_MODULES:
        # This check is for the Python 3.13 **compiled public** release.
        hits = list(app_dir.glob(f'{module}.cpython-313-*.so'))
        if not hits:
            missing.append(module)
        else:
            print(f'OK compiled {module}: {hits[0].name}')
    if missing:
        raise RuntimeError(
            'Incomplete Python 3.13 public release: missing compiled modules: '
            + ', '.join(missing)
        )


def verify_runtime(root):
    sys.path.insert(0, str(root))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
    import django
    django.setup()
    import app.tasks  # noqa: F401; loads task registration
    from app.celery import app as celery_app

    registered = set(celery_app.tasks)
    missing = [name for name in REQUIRED_TASKS if name not in registered]
    if missing:
        raise RuntimeError('Missing Celery registrations: ' + ', '.join(missing))
    print('OK: all Cyber City provisioning/reset tasks registered')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('release_dir', type=Path)
    parser.add_argument('--runtime', action='store_true')
    args = parser.parse_args()
    root = args.release_dir.resolve()
    verify_build(root)
    if args.runtime:
        verify_runtime(root)
    print('Cyber City compiled release gate passed')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'RELEASE BLOCKED: {exc}', file=sys.stderr)
        sys.exit(1)
