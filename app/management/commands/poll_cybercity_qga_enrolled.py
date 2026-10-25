"""One scheduled pass across explicitly enrolled Cyber City building VMs.

Configure CYBERCITY_QGA_MACHINE_OS_MAP={machine_id: 'linux'|'windows'}
and CYBERCITY_QGA_MONITORING_ENABLED=True before using --apply.
"""
import logging
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from app.models import CyberCityMachine

logger = logging.getLogger(__name__)


def enrolled_machines():
    mapping = getattr(settings, "CYBERCITY_QGA_MACHINE_OS_MAP", {})
    if not isinstance(mapping, dict):
        raise CommandError("CYBERCITY_QGA_MACHINE_OS_MAP must be a dict")
    enrolled = {}
    for mid, os_family in mapping.items():
        if str(mid).isdecimal() and int(mid) > 0 and os_family in ("linux", "windows"):
            enrolled[int(mid)] = os_family
        else:
            raise CommandError("Invalid QGA machine enrollment")
    return enrolled


class Command(BaseCommand):
    help = "Poll explicitly enrolled Cyber City machines once; systemd timer schedules repeats."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        if options["apply"] and not getattr(settings, "CYBERCITY_QGA_MONITORING_ENABLED", False):
            raise CommandError("QGA monitoring apply is disabled")
        enrollment = enrolled_machines()
        running_ids = set(CyberCityMachine.objects.filter(
            pk__in=enrollment, status="running").values_list("pk", flat=True))
        successes, failures = 0, 0
        for machine_id, os_family in enrollment.items():
            if machine_id not in running_ids:
                continue
            try:
                call_command("poll_cybercity_qga", machine_id=machine_id,
                             os_family=os_family, apply=options["apply"])
                successes += 1
            except Exception:
                failures += 1
                logger.exception("QGA poll failed for enrolled machine %s", machine_id)
        self.stdout.write("polled=%s failed=%s" % (successes, failures))
        if failures:
            raise CommandError("%s enrolled machine polls failed" % failures)
