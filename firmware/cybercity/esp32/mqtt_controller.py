"""Cyber City ESP32 MQTT controller with WS2811 RGB status strips.

Subscribes to each LabTech-defined pin command topic and publishes retained
state. Acknowledgment reports are non-retained and correlate to JSON command IDs.
Only supported output types are initialized; all outputs start safe/off.
"""
import time
import ujson
from machine import Pin, PWM
from umqtt.simple import MQTTClient
from command_protocol import decode_command, CommandError

# Static statuses, deliberately no arbitrary effects or animations; one MQTT
# command applies a consistent mode to the entire WS2811 strip.
WS2811_MODES = {
    "OFF": (0, 0, 0),
    "NORMAL": (0, 255, 0),       # Healthy / operational
    "WARNING": (255, 180, 0),    # Degraded / attention needed
    "ERROR": (255, 0, 0),        # Failure / outage
    "INFO": (0, 0, 255),         # Informational
    "MAINTENANCE": (160, 0, 200),# Planned maintenance
    "BUSY": (255, 100, 0),       # Processing
    "RECOVERY": (0, 200, 200),   # Restoring service
    "WHITE": (255, 255, 255),    # Hardware lighting test (power intensive)
}


class BuildingController:
    def __init__(self, config, device_id, mqtt_user=None, mqtt_password=None, tls_params=None):
        self.config = config
        self.device_id = str(device_id)
        self.pins = {}
        self.topics = {}
        self.states = {}
        self.seen_commands = {}
        broker = config["mqtt"]
        self.base = broker["base_topic"].rstrip("/")
        self.state_topic = self.base + "/devices/" + self.device_id + "/status"
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
            if topic in self.pins or topic + "/command" in self.topics:
                raise ValueError("Duplicate pin topic")
            if pin_type == "LED":
                device = Pin(pin_number, Pin.OUT, value=0)
                state = 0
            elif pin_type == "DUTY_CYCLE":
                device = PWM(Pin(pin_number), freq=1000, duty_u16=0)
                state = 0
            elif pin_type == "WS2811":
                count = int(entry.get("led_count", 0))
                brightness = int(entry.get("led_brightness", 0))
                if not 1 <= count <= 300 or not 1 <= brightness <= 255:
                    raise ValueError("WS2811 requires 1-300 LEDs and brightness 1-255")
                try:
                    from neopixel import NeoPixel
                except ImportError:
                    raise ValueError("MicroPython neopixel module is required for WS2811")
                # WS2811 variants with 800 kHz signaling use the built-in
                # neopixel driver. Check actual strip timing before classroom use.
                device = NeoPixel(Pin(pin_number, Pin.OUT), count, bpp=3, timing=1)
                device.fill((0, 0, 0))
                device.write()
                state = "OFF"
            else:
                print("Unsupported pin type:", pin_type, pin_number)
                continue
            self.pins[topic] = (device, pin_type, entry)
            self.topics[topic + "/command"] = topic
            self.states[topic] = state

    def safe_outputs(self):
        """Turn all physical outputs off after a connection problem."""
        for device, kind, entry in self.pins.values():
            try:
                if kind == "LED":
                    device.value(0)
                elif kind == "DUTY_CYCLE":
                    device.duty_u16(0)
                elif kind == "WS2811":
                    device.fill((0, 0, 0))
                    device.write()
            except OSError as exc:
                print("Safe-output failure:", repr(exc))

    def _publish(self, topic, value):
        self.client.publish(topic, str(value).encode(), retain=True, qos=1)

    def _ack(self, base, command_id, status, state=None):
        packet = {'schema': 1, 'command_id': command_id, 'status': status}
        if state is not None:
            packet['state'] = state
        self.client.publish(base + '/report', ujson.dumps(packet).encode(),
                            retain=False, qos=1)
        # The legacy LabTech listener uses /ack, while the newer versioned
        # report listener uses /report. Both convey actual device execution.
        self.client.publish(base + '/ack', ujson.dumps(packet).encode(),
                            retain=False, qos=1)

    def _set_ws2811(self, device, entry, command):
        mode = command.strip().upper()
        if mode in ("ON", "1"):
            mode = "NORMAL"
        elif mode == "0":
            mode = "OFF"
        if mode not in WS2811_MODES:
            raise ValueError("WS2811 mode must be OFF/NORMAL/WARNING/ERROR/INFO/MAINTENANCE/BUSY/RECOVERY/WHITE")
        ceiling = int(entry["led_brightness"])
        color = tuple((v * ceiling) // 255 for v in WS2811_MODES[mode])
        device.fill(color)
        device.write()
        return mode

    def _on_message(self, topic, payload):
        topic = topic.decode() if isinstance(topic, bytes) else topic
        base = self.topics.get(topic)
        if base is None:
            return
        command_id = None
        try:
            if payload.lstrip().startswith(b'{'):
                command_id, command = decode_command(payload)
                if command_id in self.seen_commands:
                    prior_base, prior_state = self.seen_commands[command_id]
                    if prior_base == base:
                        self._ack(base, command_id, 'executed', prior_state)
                    return
            else:
                command = payload.decode().strip()
            device, kind, entry = self.pins[base]
            if kind == "LED":
                if command.lower() not in ('on', 'off', '1', '0'):
                    raise ValueError('Expected on/off/1/0')
                state = 1 if command.lower() in ('on', '1') else 0
                device.value(state)
            elif kind == "WS2811":
                state = self._set_ws2811(device, entry, command)
            else:
                if command.endswith('%'):
                    percentage = float(command[:-1])
                    if not 0 <= percentage <= 100:
                        raise ValueError('Percentage outside 0..100')
                    state = round(percentage * 65535 / 100)
                else:
                    state = int(command)
                    if not 0 <= state <= 65535:
                        raise ValueError('Duty outside 0..65535')
                device.duty_u16(state)
            self.states[base] = state
            self._publish(base + '/status', state)
            print("MQTT GPIO", entry['number'], kind, "=>", state)
            if command_id is not None:
                if len(self.seen_commands) >= 64:
                    self.seen_commands.pop(next(iter(self.seen_commands)))
                self.seen_commands[command_id] = (base, state)
                self._ack(base, command_id, 'executed', state)
        except (ValueError, OSError, CommandError) as exc:
            print("Rejected MQTT command for", base, repr(exc))
            if command_id is not None:
                try:
                    self._ack(base, command_id, 'failed')
                except OSError:
                    pass

    def run(self, on_idle=None, on_connected=None):
        broker = self.config["mqtt"]
        print("MQTT connecting to", broker["host"], "port", broker.get("port", 1883))
        try:
            self.client.connect()
            print("MQTT broker connected")
            for topic in self.topics:
                self.client.subscribe(topic.encode(), qos=1)
            print("MQTT subscribed to", len(self.topics), "GPIO command topics")
            self._publish(self.state_topic, "online")
            # Fresh non-retained command results and retained status values
            # both have a place; publish initial physical OFF states to avoid N/A.
            for base, state in self.states.items():
                self._publish(base + "/status", state)
            if on_connected is not None:
                try:
                    on_connected()
                except (OSError, ValueError, ImportError) as exc:
                    print("Runtime health reporting unavailable:", repr(exc))
            last_ping = time.ticks_ms()
            idle_notice = False
            while True:
                try:
                    self.client.check_msg()
                    idle_notice = False
                except OSError as exc:
                    # ESP32 socket nonblocking recv occasionally returns -1
                    # (EAGAIN). Use heartbeat ping to detect a genuine failure.
                    err = exc.args[0] if exc.args else None
                    if err not in (-1, -11, 11):
                        raise
                    if not idle_notice:
                        print("MQTT nonblocking idle read:", repr(exc))
                        idle_notice = True
                if time.ticks_diff(time.ticks_ms(), last_ping) >= 20000:
                    self.client.ping()
                    last_ping = time.ticks_ms()
                if on_idle is not None:
                    try:
                        if on_idle() is True:
                            break
                    except (OSError, ValueError, KeyError) as exc:
                        print("Optional OTA check failed:", repr(exc))
                time.sleep_ms(100)
        finally:
            self.safe_outputs()
            try:
                self._publish(self.state_topic, "offline")
                self.client.disconnect()
            except OSError:
                pass
