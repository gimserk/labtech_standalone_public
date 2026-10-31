"""Live per-city ESP32 MQTT report subscriber.

Requires broker ACLs restricting each controller to its own /report topics and
a read-only listener credential. Do not use public or unrestricted MQTT brokers.
"""
import logging

from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections
from app.models import CyberCity, CyberCityESP32Pin
from app.cybercity_mqtt_tls import configure_mqtt_client_tls
from app.cybercity_live_mqtt_reports import process_pin_report

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Subscribe to authenticated Cyber City ESP32 v1 reports for one city"

    def add_arguments(self, parser):
        parser.add_argument("--city-id", type=int, required=True)

    def handle(self, *args, **options):
        import paho.mqtt.client as mqtt

        city = CyberCity.objects.filter(pk=options["city_id"]).first()
        if city is None or not city.mqtt_broker_address:
            raise CommandError("City or configured MQTT broker not found")
        if not city.mqtt_use_tls or not city.mqtt_broker_username or not city.mqtt_broker_password:
            raise CommandError("Live report listener requires TLS and a scoped MQTT listener account")
        pins = list(CyberCityESP32Pin.objects.filter(
            esp32__building__cybercity=city,
            esp32__use_versioned_commands=True,
        ).select_related("esp32__building"))
        topics = [pin.get_full_topic() + "/report" for pin in pins]
        if len(topics) != len(set(topics)):
            raise CommandError("Ambiguous MQTT report topics; fix pin configuration")
        if not topics:
            raise CommandError("No versioned ESP32 pins enrolled in this city")

        def on_connect(client, userdata, flags, reason_code, properties=None):
            if reason_code != 0:
                logger.error("MQTT listener connection rejected")
                return
            for topic in topics:
                client.subscribe(topic, qos=1)
            logger.info("Subscribed to %d scoped Cyber City report topics", len(topics))

        def on_message(client, userdata, msg):
            close_old_connections()
            try:
                process_pin_report(city_id=city.pk, topic=msg.topic, payload=msg.payload)
            except Exception:
                logger.exception("Rejected or failed Cyber City ESP32 device report")
            finally:
                close_old_connections()

        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        client.username_pw_set(city.mqtt_broker_username, city.mqtt_broker_password)
        configure_mqtt_client_tls(client, city)
        client.on_connect = on_connect
        client.on_message = on_message
        self.stdout.write("Starting live MQTT report listener for city %s" % city.pk)
        # connect_async allows loop_forever to retry even if the broker is down at startup.
        client.reconnect_delay_set(min_delay=2, max_delay=120)
        client.connect_async(city.mqtt_broker_address, city.mqtt_broker_port, keepalive=60)
        client.loop_forever(retry_first_connection=True)
