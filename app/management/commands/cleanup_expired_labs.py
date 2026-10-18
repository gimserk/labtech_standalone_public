"""Inspect, enqueue, or synchronously reconcile expired timed lab sessions."""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from app.models import LabInstance
from app.lab_services.lifecycle import request_cleanup, process, snapshot


class Command(BaseCommand):
    help = 'Reconcile expired timed labs using durable cleanup jobs.'

    def add_arguments(self, parser):
        parser.add_argument('--enqueue', action='store_true')
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--instance-id', type=int)

    def handle(self, *args, **options):
        if options['dry_run'] and options['enqueue']:
            raise CommandError('--dry-run and --enqueue cannot be combined')
        queryset = LabInstance.objects.filter(lab__lab_type='timed', expires_at__lte=timezone.now())
        if options['instance_id'] is not None:
            queryset = queryset.filter(pk=options['instance_id'])
            if not queryset.exists():
                raise CommandError('No eligible expired timed lab session with this ID')
        failed = []
        for instance in queryset.select_related('lab'):
            if options['dry_run']:
                self.stdout.write(f'Eligible session {instance.pk} lab={instance.lab_id} resources={snapshot(instance)}')
                continue
            job = request_cleanup(instance.pk, 'reconciliation', enqueue=options['enqueue'])
            self.stdout.write(f'Session {instance.pk}: job {job.pk} ({job.status})')
            if not options['enqueue']:
                status = process(job.pk)
                if status != 'completed':
                    failed.append(str(instance.pk))
        if failed:
            raise CommandError('Cleanup unresolved for session IDs: ' + ', '.join(failed))
