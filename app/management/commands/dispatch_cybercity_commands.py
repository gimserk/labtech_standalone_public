from django.core.management.base import BaseCommand
from app.cybercity_command_delivery import dispatch_pending

class Command(BaseCommand):
    help = 'Publish pending Cyber City MQTT commands. Schedule to run every minute.'

    def handle(self, *args, **options):
        count = dispatch_pending()
        self.stdout.write(f'Processed {count} Cyber City MQTT commands')
