from django.core.management.base import BaseCommand
from app.models import CyberCity
from app.cybercity_status_consumer import listen_city_status


class Command(BaseCommand):
    help = 'Listen to configured Cyber City ESP32 status topics for a bounded interval.'

    def add_arguments(self, parser):
        parser.add_argument('--city-id', type=int, required=True)
        parser.add_argument('--seconds', type=int, default=30)
        parser.add_argument('--forever', action='store_true', help='Keep a persistent MQTT connection, reconnecting if disconnected')

    def handle(self, *args, **options):
        city = CyberCity.objects.get(pk=options['city_id'])
        count = listen_city_status(city, options['seconds'], forever=options['forever'])
        self.stdout.write(f'Ingested {count} pin status messages')
