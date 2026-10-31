"""Explicitly bind a real Cyber City machine monitor to a SOC team."""
from django.core.management.base import BaseCommand, CommandError
from app.models import MachineStateMonitor, CyberCitySOCTeam, CyberCitySOCMonitorRoute

class Command(BaseCommand):
    help = "Route one real QEMU monitor to an assigned SOC team (within the same city)"

    def add_arguments(self, parser):
        parser.add_argument("--monitor-id", type=int, required=True)
        parser.add_argument("--team-id", type=int, required=True)

    def handle(self, *args, **opts):
        monitor = MachineStateMonitor.objects.select_related("machine__building").filter(
            pk=opts["monitor_id"]).first()
        team = CyberCitySOCTeam.objects.filter(pk=opts["team_id"]).first()
        if monitor is None or team is None:
            raise CommandError("Monitor or SOC team not found.")
        if monitor.machine.building.cybercity_id != team.city_id:
            raise CommandError("Monitor and SOC team must belong to the same Cyber City.")
        route, created = CyberCitySOCMonitorRoute.objects.update_or_create(
            monitor=monitor, defaults={"team": team})
        self.stdout.write(self.style.SUCCESS(
            f"Monitor {monitor.pk} now routes real alerts to SOC team {team.pk}."))
