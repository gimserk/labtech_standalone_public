"""Read-only inspection of stalled Cyber City reset jobs.

Never delete or recreate a VM automatically from this diagnostic command:
Proxmox task state must be reconciled before any recovery action.
"""
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from app.models import CyberCityMachine

class Command(BaseCommand):
    help = 'Report Cyber City machine resets older than a specified duration.'

    def add_arguments(self, parser):
        parser.add_argument('--minutes', type=int, default=15)

    def handle(self, *args, **options):
        minutes = options['minutes']
        if minutes < 1:
            raise ValueError('--minutes must be positive')
        cutoff = timezone.now() - timedelta(minutes=minutes)
        jobs = CyberCityMachine.objects.filter(
            status__in=['reset_queued', 'resetting'],
            reset_started_at__lt=cutoff
        ).select_related('building', 'proxmox_template')
        for machine in jobs:
            self.stdout.write(
                'STALE Cyber City reset: machine=%s building=%s status=%s vmid=%s template=%s started=%s'
                % (machine.pk, machine.building_id, machine.status,
                   machine.proxmox_vmid, machine.proxmox_template.vmid,
                   machine.reset_started_at.isoformat()))
        self.stdout.write('Found %s potentially stalled reset(s). No VMs were modified.' % jobs.count())
