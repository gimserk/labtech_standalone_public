"""DNCC ESP32 MQTT controller for existing Cyber City pin conventions.

Load a trusted configuration dictionary supplied by an authenticated setup
flow. This module does not download or execute code.
Requires MicroPython umqtt.simple (plus its normal dependencies).
"""
import time
import ujson
from machine import Pin, PWM
from umqtt.simple import MQTTClient


class BuildingController:
    def __init__(self, config, device_id, mqtt_user=None, mqtt_password=None, tls_params=None):
        self.config = config
        self.device_id = str(device_id)
        self.pins = {}
        self.topics = {}
        broker = config["mqtt"]
        self.base = broker["base_topic"].rstrip("/")
        self.state_topic = self.base + "/devices/" + self.device_id + "/status"
        # Only enable TLS when a board-validated SSL configuration is supplied.
        # A secure port number alone must never imply verified TLS.
        if tls_params is not None:
            if not isinstance(tls_params, dict) or not tls_params:
                raise ValueError("TLS parameters must be a validated nonempty dictionary")
            if tls_params.get("server_hostname") != broker["host"]:
                raise ValueError("TLS server hostname must match configured MQTT host")
            try:
                import ssl
                required = ssl.CERT_REQUIRED
            except (ImportError, AttributeError):
                raise ValueError("This MicroPython SSL build cannot enforce CA verification")
            if tls_params.get("cert_reqs") != required:
                raise ValueError("TLS must require server certificate validation")
        self.client = MQTTClient(
            self.device_id, broker["host"], port=int(broker.get("port", 1883)),
            user=mqtt_user, password=mqtt_password, keepalive=60,
            ssl=tls_params is not None, ssl_params=tls_params or {},
        )
        self.client.set_callback(self._on_message)
        self.client.set_last_will(self.state_topic, b"offline", retain=True, qos=1)
        for entry in config["pins"]:
            pin_number = int(entry["number"])
            pin_type = entry["type"]
            topic = entry["topic"]
            if not topic.startswith(self.base + "/"):
                raise ValueError("Pin topic outside building namespace")
            if pin_type == "LED":
                device = Pin(pin_number, Pin.OUT, value=0)
            elif pin_type == "DUTY_CYCLE":
                device = PWM(Pin(pin_number), freq=1000, duty_u16=0)
            else:
                # I2C devices require peripheral-specific configuration.
                # Do not drive an unimplemented I2C pin as an ordinary GPIO.
                print("Unsupported pin type:", pin_type, pin_number)
                continue
            self.pins[topic] = (device, pin_type)
            self.topics[topic + "/command"] = topic

    def safe_outputs(self):
        """Set controlled outputs to off/zero after a connection failure."""
        for device, kind in self.pins.values():
            if kind == "LED":
                device.value(0)
            elif kind == "DUTY_CYCLE":
                device.duty_u16(0)

    def _publish(self, topic, value):
        self.client.publish(topic, str(value).encode(), retain=True, qos=1)

    def _on_message(self, topic, payload):
        topic = topic.decode() if isinstance(topic, bytes) else topic
        base = self.topics.get(topic)
        if base is None:
            return
        command = payload.decode().strip().lower()
        device, kind = self.pins[base]
        try:
            if kind == "LED":
                if command not in ("on", "off", "1", "0"):
                    raise ValueError("Expected on/off/1/0")
                state = 1 if command in ("on", "1") else 0
                device.value(state)
            else:
                # PWM accepts decimal duty (0..65535) or 0..100% string.
                if command.endswith("%"):
                    percentage = float(command[:-1])
                    if not 0 <= percentage <= 100:
                        raise ValueError("Percentage outside 0..100")
                    state = round(percentage * 65535 / 100)
                else:
                    state = int(command)
                    if not 0 <= state <= 65535:
                        raise ValueError("Duty outside 0..65535")
                device.duty_u16(state)
            self._publish(base + "/status", state)
        except (ValueError, OSError) as exc:
            # Do not echo arbitrary untrusted commands to display screens.
            print("Rejected MQTT command for", base, str(exc))

    def run(self, on_idle=None):
        self.client.connect()
        try:
            for topic in self.topics:
                self.client.subscribe(topic.encode(), qos=1)
            self._publish(self.state_topic, "online")
            while True:
                self.client.check_msg()
                if on_idle is not None:
                    try:
                        if on_idle() is True:
                            # Exit cleanly before a caller-controlled reset.
                            break
                    except (OSError, ValueError, KeyError) as exc:
                        print('Optional OTA check failed:', str(exc))
                time.sleep_ms(100)
        finally:
            self.safe_outputs()
            try:
                self._publish(self.state_topic, "offline")
                self.client.disconnect()
            except OSError:
                pass
