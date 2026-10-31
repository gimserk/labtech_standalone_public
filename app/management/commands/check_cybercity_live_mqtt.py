"""Run real Cyber City broker and controller readiness checks from the installed host."""
import ssl
from django.core.management.base import BaseCommand, CommandError
from app.models import CyberCity, CyberCityESP32, CyberCityESP32Pin, CyberCityCommand
from app.cybercity_mqtt_tls import configure_mqtt_client_tls


class Command(BaseCommand):
    help = "Verify live broker connectivity and ESP32 report readiness for a Cyber City"

    def add_arguments(self, parser):
        parser.add_argument("--city-id", type=int, required=True)
        parser.add_argument("--timeout", type=int, default=10)

    def handle(self, *args, **opts):
        import paho.mqtt.client as mqtt
        import threading

        city = CyberCity.objects.filter(pk=opts["city_id"]).first()
        if not city or not city.mqtt_broker_address:
            raise CommandError("City or MQTT broker configuration missing")
        if not (city.mqtt_use_tls and city.mqtt_broker_username and city.mqtt_broker_password):
            raise CommandError("Live MQTT connection requires configured TLS and broker credentials")
        if not 1 <= opts["timeout"] <= 60:
            raise CommandError("Timeout must be between 1 and 60 seconds")
        esp32s = CyberCityESP32.objects.filter(building__cybercity=city)
        pins = CyberCityESP32Pin.objects.filter(esp32__building__cybercity=city).select_related("esp32__building")
        self.stdout.write("Enrolled ESP32 controllers: %d" % esp32s.count())
        self.stdout.write("Configured pins: %d" % pins.count())
        topics = [pin.get_full_topic() + "/report" for pin in pins if pin.esp32.use_versioned_commands]
        if len(set(topics)) != len(topics):
            raise CommandError("Duplicate report topics; correct pin configuration")
        self.stdout.write("Versioned report topics: %d" % len(topics))
        self.stdout.write("Recent command states:")
        for item in CyberCityCommand.objects.filter(
                machine__building__cybercity=city).order_by("-created_at")[:10]:
            self.stdout.write("  command %s: %s (attempts %s)" % (item.command_id, item.status, item.attempts))
        connected = threading.Event()
        rejected = threading.Event()

        def on_connect(client, userdata, flags, reason_code, properties=None):
            if reason_code == 0:
                connected.set()
            else:
                rejected.set()

        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        client.username_pw_set(city.mqtt_broker_username, city.mqtt_broker_password)
        configure_mqtt_client_tls(client, city)
        client.on_connect = on_connect
        try:
            client.connect(city.mqtt_broker_address, city.mqtt_broker_port, keepalive=30)
            client.loop_start()
            if not connected.wait(opts["timeout"]):
                raise CommandError("Broker did not authenticate MQTT client within timeout")
        except (OSError, ssl.SSLError) as exc:
            raise CommandError("Live MQTT connection failed: %s" % type(exc).__name__) from exc
        finally:
            client.disconnect()
            client.loop_stop()
        self.stdout.write(self.style.SUCCESS("Live MQTT broker authentication succeeded."))
        self.stdout.write("Broker authentication does not confirm an ESP32 is connected or subscribed.")
