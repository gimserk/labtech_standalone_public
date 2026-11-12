from django.core.management.base import BaseCommand, CommandError
from app.models import CyberCity
from app.cybercity_status_consumer import listen_city_status
from app.cybercity_status_daemon import run_all_city_status_listeners


class Command(BaseCommand):
    help = 'Receive real ESP32 MQTT pin statuses; --all-cities supervises every city.'

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument('--city-id', type=int)
        group.add_argument('--all-cities', action='store_true',
                           help='Run continuously, discover cities and refresh pin subscriptions')
        parser.add_argument('--seconds', type=int, default=30)
        parser.add_argument('--forever', action='store_true',
                            help='Keep a city-scoped connection open with reconnect')
        parser.add_argument('--refresh-seconds', type=int, default=15,
                            help='City and pin discovery interval (all-cities mode)')

    def handle(self, *args, **options):
        if options['all_cities']:
            if not 5 <= options['refresh_seconds'] <= 300:
                raise CommandError('refresh-seconds must be 5 through 300')
            self.stdout.write('Starting automatic Cyber City MQTT status listener')
            run_all_city_status_listeners(refresh_seconds=options['refresh_seconds'])
            return
        city = CyberCity.objects.get(pk=options['city_id'])
        count = listen_city_status(city, options['seconds'], forever=options['forever'])
        self.stdout.write(f'Ingested {count} pin status messages')
