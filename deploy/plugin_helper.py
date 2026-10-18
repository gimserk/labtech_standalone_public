"""Root-owned, bounded connector installer. Never execute publisher code as root."""
import argparse
from datetime import timedelta
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import tempfile
import time
from zipfile import ZipFile

PLUGIN_ROOT = Path('/var/lib/labtech/plugins')
SECRET_ROOT = Path('/etc/labtech/plugins')
PUBLISHER_KEY = Path('/etc/labtech/plugin-marketplace-publisher.pem')
PYTHON = os.getenv('LABTECH_VENV_PYTHON', '/usr/bin/python3.13')


class ActivationError(ValueError):
    pass


def _run(*args):
    subprocess.run(args, check=True, timeout=180)


def restart_plugin(plugin_id):
    _run('systemctl', 'enable', f'labtech-plugin@{plugin_id}.service')
    _run('systemctl', 'restart', f'labtech-plugin@{plugin_id}.service')


def switch_release(root: Path, version: str, *, service=restart_plugin, health_check,
                   health_timeout=10.0, force_restart=False):
    """Swap only a staged release; restore and restart the old service on failure."""
    from app.plugins.transport import ConnectorUnavailable
    root = Path(root)
    if not re.fullmatch(r'[A-Za-z0-9.]{1,64}', version) or not (root / 'releases' / version).is_dir():
        raise ActivationError('Release has not been staged.')
    current = root / 'current'
    target = f'releases/{version}'
    old = os.readlink(current) if current.is_symlink() else None
    if old == target and not force_restart:
        try:
            if health_check(root.name):
                return
        except (OSError, ConnectorUnavailable):
            pass
        force_restart = True
    if current.exists() and not current.is_symlink():
        raise ActivationError('Connector current path is not a symlink.')
    temporary = root / f'.current-{os.getpid()}'
    try:
        if old != target:
            temporary.symlink_to(target)
            os.replace(temporary, current)
        service(root.name)
        deadline = time.monotonic() + health_timeout
        while True:
            try:
                if health_check(root.name):
                    break
            except (OSError, ConnectorUnavailable):
                pass
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ActivationError('Connector health check did not become ready.')
            time.sleep(min(0.25, remaining))
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        if old:
            temporary.symlink_to(old)
            os.replace(temporary, current)
            try:
                if force_restart and old == target:
                    _run('systemctl', 'stop', f'labtech-plugin@{root.name}.service')
                else:
                    service(root.name)
            except Exception:
                pass
        else:
            current.unlink(missing_ok=True)
            try:
                _run('systemctl', 'stop', f'labtech-plugin@{root.name}.service')
                _run('systemctl', 'disable', f'labtech-plugin@{root.name}.service')
            except Exception:
                pass
        raise ActivationError('Connector activation failed; previous release restored.') from exc


def _stage(root, archive_path, release):
    """Only signed wheel bytes are installed, with pip hashes and no index/source builds."""
    destination = root / 'releases' / release.version
    if destination.exists():
        if (destination / 'digest').read_text().strip() != release.digest:
            raise ActivationError('An installed version has different signed bytes.')
        return destination
    (root / 'releases').mkdir(parents=True, exist_ok=True)
    (root / 'releases').chmod(0o755)
    with tempfile.TemporaryDirectory(dir=root / 'releases', prefix='.stage-') as staging_dir:
        staging = Path(staging_dir)
        wheel_dir = staging / 'wheels'
        wheel_dir.mkdir()
        requirements = []
        with ZipFile(archive_path) as archive:
            for member in release.members:
                if not member.startswith('wheels/') or not member.endswith('.whl'):
                    continue
                wheel = wheel_dir / Path(member).name
                digest = hashlib.sha256()
                with archive.open(member) as source, wheel.open('xb') as target:
                    for chunk in iter(lambda: source.read(65536), b''):
                        digest.update(chunk)
                        target.write(chunk)
                requirements.append(f'{wheel} --hash=sha256:{digest.hexdigest()}')
        if not requirements:
            raise ActivationError('No wheels in signed release.')
        (staging / 'requirements.txt').write_text('\n'.join(requirements) + '\n')
        (staging / 'entry_point').write_text(release.entry_point + '\n')
        (staging / 'digest').write_text(release.digest + '\n')
        _run(PYTHON, '-m', 'venv', str(staging / 'venv'))
        _run(str(staging / 'venv/bin/pip'), 'install', '--no-index', '--no-deps',
             '--only-binary=:all:', '--require-hashes', '-r', str(staging / 'requirements.txt'))
        for path in staging.rglob('*'):
            if path.is_symlink():
                continue
            if path.is_dir():
                path.chmod(0o755)
            elif path.is_file():
                path.chmod(0o755 if path.stat().st_mode & 0o111 else 0o644)
        staging.chmod(0o755)
        os.replace(staging, destination)
    return destination


def _ensure_token(plugin_id):
    """Create a scoped credential once; rotating it is an operator action."""
    import grp
    SECRET_ROOT.mkdir(parents=True, exist_ok=True)
    token_path = SECRET_ROOT / f'{plugin_id}.token'
    try:
        descriptor = os.open(token_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o640)
    except FileExistsError:
        if not token_path.is_file() or token_path.is_symlink():
            raise ActivationError('Unsafe connector token path.')
        return
    with os.fdopen(descriptor, 'w') as secret:
        secret.write(secrets.token_hex(32) + '\n')
    os.chown(token_path, 0, grp.getgrnam('labtech-plugin').gr_gid)
    token_path.chmod(0o640)


def activate_release(job_id: int, *, health_check=None, root=PLUGIN_ROOT):
    """Revalidate entitlement and signed metadata inside the privileged process."""
    from django.utils import timezone
    from django.conf import settings
    from app.models import License
    from app.plugin_license import get_plugin_entitlement
    from app.plugin_models import InstalledConnector, PluginAuditEvent, PluginInstallJob
    from app.plugins.marketplace import PluginMarketplaceClient
    from app.plugins.package import verify_release
    if type(job_id) is not int or job_id < 1 or job_id > 2147483647:
        raise ActivationError('Invalid job identifier.')
    job = PluginInstallJob.objects.get(pk=job_id)
    if job.status == 'succeeded':
        return
    if job.status != 'queued':
        raise ActivationError('Job is not queued.')
    root = Path(root)
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,39}', job.plugin_id):
        raise ActivationError('Invalid plugin identifier.')
    plugin_root = root / job.plugin_id
    plugin_root.mkdir(parents=True, exist_ok=True)
    plugin_root.chmod(0o755)
    with (plugin_root / '.install.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        job.refresh_from_db()
        if job.status == 'succeeded':
            return
        if job.status != 'queued':
            raise ActivationError('Job is not queued.')
        job.status = 'running'
        job.started_at = timezone.now()
        job.save(update_fields=['status', 'started_at'])
        try:
            if job.action != 'enable' and InstalledConnector.objects.filter(plugin_id=job.plugin_id, state='disabled').exists():
                raise ActivationError('Connector was disabled after installation was requested.')
            if job.action == 'enable' and not InstalledConnector.objects.filter(plugin_id=job.plugin_id, state='disabled').exists():
                raise ActivationError('Only a disabled connector can be re-enabled.')
            entitlement = get_plugin_entitlement(License.objects.filter(pk=1).first(), timezone.now())
            if entitlement.state != 'active':
                raise ActivationError('An active plugin entitlement is required.')
            if not PUBLISHER_KEY.is_file():
                raise ActivationError('Marketplace publisher public key is missing.')
            with tempfile.TemporaryDirectory(dir=plugin_root, prefix='.download-') as temp:
                archive = Path(temp) / 'release.zip'
                metadata = PluginMarketplaceClient().download(job.plugin_id, job.release_id, archive, entitlement)
                release = verify_release(metadata, archive, PUBLISHER_KEY.read_bytes(),
                                         settings.LABTECH_PLUGIN_CORE_VERSION, sys.version_info[:2])
                _stage(plugin_root, archive, release)
            _ensure_token(job.plugin_id)
            current = plugin_root / 'current'
            job.previous_target = os.readlink(current) if current.is_symlink() else ''
            job.candidate_target = f'releases/{release.version}'
            job.save(update_fields=['previous_target', 'candidate_target'])
            if health_check is None:
                from app.plugins.transport import ConnectorClient
                health_check = lambda identifier: ConnectorClient(enforce_entitlement=False).call(identifier, 'health', {})['healthy']
            switch_release(plugin_root, release.version, health_check=health_check,
                           force_restart=job.action == 'enable')
            if job.action != 'enable' and InstalledConnector.objects.filter(plugin_id=job.plugin_id, state='disabled').exists():
                _restore_previous(plugin_root, job.previous_target, restart=False)
                raise ActivationError('Connector was disabled during activation.')
            InstalledConnector.objects.update_or_create(plugin_id=release.plugin_id, defaults={
                'version': release.version, 'release_id': release.release_id, 'digest': release.digest,
                'contract_version': 1, 'enabled': True, 'state': 'enabled', 'last_error': '',
            })
            job.status, job.error, job.finished_at = 'succeeded', '', timezone.now()
            job.save(update_fields=['status', 'error', 'finished_at'])
            PluginAuditEvent.objects.create(actor_id=job.requested_by_id, plugin_id=job.plugin_id,
                                            action='install', result='succeeded')
        except Exception as exc:
            job.status, job.error, job.finished_at = 'failed', str(exc)[:500], timezone.now()
            job.save(update_fields=['status', 'error', 'finished_at'])
            PluginAuditEvent.objects.create(actor_id=job.requested_by_id, plugin_id=job.plugin_id,
                                            action='install', result='failed')
            raise ActivationError('Plugin install failed; see job status.') from exc


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['process', 'process-queued'])
    parser.add_argument('--job-id', type=int)
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error('Plugin helper requires root.')
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
    import django
    django.setup()
    if args.command == 'process':
        if args.job_id is None:
            parser.error('--job-id required')
        activate_release(args.job_id)
    else:
        from app.plugin_models import PluginInstallJob
        recover_interrupted_jobs()
        reconcile_runtime()
        for job_id in PluginInstallJob.objects.filter(status='queued').order_by('pk').values_list('pk', flat=True)[:10]:
            try:
                activate_release(job_id)
            except ActivationError:
                continue


def reconcile_runtime():
    """Grace expiry blocks new calls and stops connector services; core stays up."""
    from django.utils import timezone
    from app.models import License
    from app.plugin_license import get_plugin_entitlement
    from app.plugin_models import InstalledConnector
    runtime_allowed = get_plugin_entitlement(License.objects.filter(pk=1).first(), timezone.now()).allows_launch
    queryset = InstalledConnector.objects.all() if not runtime_allowed else InstalledConnector.objects.filter(enabled=False)
    for plugin_id in queryset.values_list('plugin_id', flat=True):
        try:
            _run('systemctl', 'stop', f'labtech-plugin@{plugin_id}.service')
        except Exception:
            continue


def _restore_previous(plugin_root, previous_target, *, restart=True):
    current = plugin_root / 'current'
    if previous_target and re.fullmatch(r'releases/[A-Za-z0-9.]{1,64}', previous_target) and (plugin_root / previous_target).is_dir():
        replacement = plugin_root / f'.restore-{os.getpid()}'
        replacement.symlink_to(previous_target)
        os.replace(replacement, current)
        if restart:
            restart_plugin(plugin_root.name)
        else:
            _run('systemctl', 'stop', f'labtech-plugin@{plugin_root.name}.service')
    else:
        current.unlink(missing_ok=True)
        _run('systemctl', 'stop', f'labtech-plugin@{plugin_root.name}.service')
        _run('systemctl', 'disable', f'labtech-plugin@{plugin_root.name}.service')


def recover_interrupted_jobs(*, root=PLUGIN_ROOT, now=None):
    """A timed-out root helper releases its lock; reconcile only its recorded target."""
    from django.db.models import Q
    from django.utils import timezone
    from app.plugin_models import PluginAuditEvent, PluginInstallJob
    now = now or timezone.now()
    stale = PluginInstallJob.objects.filter(status='running').filter(
        Q(started_at__lt=now - timedelta(minutes=21)) |
        Q(started_at__isnull=True, created_at__lt=now - timedelta(minutes=21))
    ).order_by('pk')[:10]
    for job in stale:
        if not re.fullmatch(r'[a-z][a-z0-9-]{0,39}', job.plugin_id):
            continue
        plugin_root = Path(root) / job.plugin_id
        if not plugin_root.is_dir():
            job.status = 'failed'
            job.error = 'Installation interrupted; connector storage is missing.'
            job.finished_at = now
            job.save(update_fields=['status', 'error', 'finished_at'])
            PluginAuditEvent.objects.create(actor_id=job.requested_by_id, plugin_id=job.plugin_id,
                                            action='install_recovered', result='failed')
            continue
        with (plugin_root / '.install.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            job.refresh_from_db()
            if job.status != 'running':
                continue
            current = plugin_root / 'current'
            recovery_error = ''
            if (job.candidate_target and current.is_symlink()
                    and os.readlink(current) == job.candidate_target):
                try:
                    _restore_previous(plugin_root, job.previous_target, restart=job.action != 'enable')
                except Exception:
                    recovery_error = ' Service restart/stop needs operator attention.'
            job.status = 'failed'
            job.error = 'Installation interrupted; prior release restored when applicable.' + recovery_error
            job.finished_at = now
            job.save(update_fields=['status', 'error', 'finished_at'])
            PluginAuditEvent.objects.create(actor_id=job.requested_by_id, plugin_id=job.plugin_id,
                                            action='install_recovered', result='failed')


if __name__ == '__main__':
    main()
