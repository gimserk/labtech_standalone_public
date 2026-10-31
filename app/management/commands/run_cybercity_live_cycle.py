"""Operator-triggered real QEMU -> MQTT live cycle for a single Cyber City VM.

This can enact physical ESP32 behavior. Only run against an authorized test building.
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from app.models import CyberCityMachine
from app.management.commands.poll_cybercity_qga import connect_proxmox, poll_machine
from app.cybercity_qga_monitoring import validate_guest_agent_target
from app.cybercity_command_delivery import dispatch_pending


class Command(BaseCommand):
    help = "Execute one authorized, live QEMU monitor and city-scoped MQTT dispatch cycle"

    def add_arguments(self, parser):
        parser.add_argument("--machine-id", type=int, required=True)
        parser.add_argument("--execute", action="store_true", help="I authorize real VM monitoring and physical MQTT pin actions")
        parser.add_argument("--dispatch-limit", type=int, default=25)

    def handle(self, *args, **opts):
        machine = CyberCityMachine.objects.select_related(
            "building", "proxmox_template__proxmox_server").filter(pk=opts["machine_id"]).first()
        if machine is None or machine.status != "running" or not machine.monitor_enabled:
            raise CommandError("A running, monitoring-enabled Cyber City building VM is required")
        if not 1 <= opts["dispatch_limit"] <= 25:
            raise CommandError("Dispatch limit must be between 1 and 25")
        if not getattr(settings, "CYBERCITY_QGA_MONITORING_ENABLED", False):
            raise CommandError("Live QEMU monitoring must be explicitly enabled in settings")
        city = machine.building.cybercity
        if not city.mqtt_broker_address:
            raise CommandError("The city's MQTT broker is not configured")
        if not opts["execute"]:
            raise CommandError("No action taken. Pass --execute only for an authorized physical test; pending commands for this city may also be dispatched.")
        server, _, _ = validate_guest_agent_target(machine)
        self.stdout.write(f"Polling real QEMU Guest Agent for VM {machine.pk} in Cyber City {city.pk}")
        result = poll_machine(machine, connect_proxmox(server), machine.monitor_os_family, apply=True)
        self.stdout.write(f"Observations: {result['observed']}; failures: {len(result['failures'])}; triggers queued: {len(result['queued'])}")
        if result["failures"]:
            raise CommandError("Monitor failures occurred; queued commands were not dispatched by this command")
        sent = dispatch_pending(limit=opts["dispatch_limit"], city_id=city.pk)
        self.stdout.write(self.style.SUCCESS(
            f"Attempted delivery for {sent} existing or newly queued commands for Cyber City {city.pk}. Check ESP32 execution reports in SOC."))
