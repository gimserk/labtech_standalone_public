"""Run one bounded QEMU Guest Agent monitor pass for existing Cyber City VMs."""
import logging

from django.core.management.base import BaseCommand, CommandError
from django.core.cache import cache
from django.conf import settings
from proxmoxer import ProxmoxAPI

from app.models import CyberCityMachine
from app.cybercity_qga_collector import collect_qga_observation, QGACollectionError
from app.cybercity_qga_monitoring import (
    normalize_observations, GuestAgentObservationError,
)
from app.cybercity_monitor_evaluator import evaluate_monitor_observations

logger = logging.getLogger(__name__)


def connect_proxmox(server):
    settings = {"host": server.host, "port": server.port, "verify_ssl": server.verify_ssl}
    if server.api_token_id:
        settings.update(user=server.user, token_name=server.api_token_id.split("!")[-1],
                        token_value=server.password_or_token_secret)
    else:
        settings.update(user=server.user, password=server.password_or_token_secret)
    return ProxmoxAPI(**settings)


def poll_machine(machine, api, os_family, apply=False):
    observations = {}
    failures = []
    monitors = list(machine.state_monitors.filter(
        is_active=True, monitor_type__in=("service", "file_hash", "file_exists", "file_content")).order_by("pk"))
    for monitor in monitors:
        try:
            observations[monitor.pk] = collect_qga_observation(
                machine, monitor, api, os_family)
        except (QGACollectionError, GuestAgentObservationError) as exc:
            failures.append((monitor.pk, str(exc)))
    if not observations:
        return {"observed": 0, "queued": [], "failures": failures}
    states = normalize_observations(machine, observations)
    queued = evaluate_monitor_observations(machine, states) if apply else []
    return {"observed": len(states), "queued": queued, "failures": failures}


class Command(BaseCommand):
    help = "Poll Cyber City QEMU Guest Agent monitors once (dry run unless --apply)."

    def add_arguments(self, parser):
        parser.add_argument("--machine-id", type=int, required=True)
        parser.add_argument("--os-family", choices=("linux", "windows"), required=True)
        parser.add_argument("--apply", action="store_true",
                            help="Persist observations and queue MQTT commands")

    def handle(self, *args, **options):
        if options["apply"] and not getattr(settings, "CYBERCITY_QGA_MONITORING_ENABLED", False):
            raise CommandError("QGA monitoring apply is disabled in settings")
        machine = CyberCityMachine.objects.select_related(
            "proxmox_template__proxmox_server", "building").filter(
            pk=options["machine_id"], status="running").first()
        if machine is None:
            raise CommandError("Running Cyber City building machine not found")
        from app.cybercity_qga_monitoring import validate_guest_agent_target
        try:
            server, _, _ = validate_guest_agent_target(machine)
            lock_key = "cybercity:qga:poll:%s" % machine.pk
            if not cache.add(lock_key, "busy", timeout=120):
                raise CommandError("A monitor poll is already in progress")
            try:
                result = poll_machine(machine, connect_proxmox(server),
                                      options["os_family"], apply=options["apply"])
            finally:
                cache.delete(lock_key)
        except (GuestAgentObservationError, QGACollectionError) as exc:
            raise CommandError(str(exc)) from exc
        for monitor_id, reason in result["failures"]:
            logger.warning("QGA monitor %s unavailable for machine %s: %s",
                           monitor_id, machine.pk, reason)
        self.stdout.write(
            "machine=%s mode=%s observed=%s failures=%s queued=%s" % (
                machine.pk, "apply" if options["apply"] else "dry-run",
                result["observed"], len(result["failures"]), len(result["queued"])))
