"""Issue/rotate the shared provisioning key for an existing ESP32."""
import secrets

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError

from app.models import CyberCityESP32


class Command(BaseCommand):
    help = 'Generate and hash a provisioning key for an existing Cyber City ESP32.'

    def add_arguments(self, parser):
        parser.add_argument('mac', help='Registered ESP32 Wi-Fi MAC address')

    def handle(self, *args, **opts):
        try:
            device = CyberCityESP32.objects.get(mac_address__iexact=opts['mac'])
        except CyberCityESP32.DoesNotExist:
            raise CommandError('ESP32 MAC not registered in a building')

        key = secrets.token_urlsafe(32)
        device.provisioning_key_hash = make_password(key)
        device.save(update_fields=['provisioning_key_hash'])
        self.stdout.write('Provisioning key (shown only once):')
        self.stdout.write(key)
        self.stdout.write('Securely install it on the device; rerun command to rotate.')
