"""DNCC device startup orchestrator (MicroPython).

Use only on an isolated lab network until device HTTPS trust and broker
authentication/TLS are validated. Does not download or execute remote code.
"""
import time
import network
import ubinascii
import labtech_https as requests

from bootstrap_config import WIFI_SSID, WIFI_PASSWORD, LABTECH_URL, DEVICE_KEY
from mqtt_controller import BuildingController

# Configure broker credentials locally. They are NOT included in the existing
# authenticated configuration API response.
try:
    from mqtt_secrets import MQTT_USER, MQTT_PASSWORD
except ImportError:
    MQTT_USER = None
    MQTT_PASSWORD = None


def connect_wifi(timeout_seconds=25):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        for _ in range(timeout_seconds):
            if wlan.isconnected():
                break
            time.sleep(1)
    if not wlan.isconnected():
        raise OSError("Wi-Fi connection failed")
    return wlan


def read_mac(wlan):
    raw = ubinascii.hexlify(wlan.config("mac")).decode().upper()
    return ":".join(raw[i:i + 2] for i in range(0, len(raw), 2))


def fetch_config(wlan):
    if not LABTECH_URL.startswith("https://"):
        raise ValueError("LabTech must be configured with HTTPS")
    if not DEVICE_KEY or DEVICE_KEY.startswith("REPLACE"):
        raise ValueError("Device provisioning key has not been configured")
    mac = read_mac(wlan)
    url = LABTECH_URL.rstrip("/") + "/api/firmware/v2/config/?mac=" + mac
    response = requests.get(url, headers={"Authorization": "Bearer " + DEVICE_KEY})
    try:
        if response.status_code != 200:
            raise OSError("LabTech configuration request failed: HTTP %s" % response.status_code)
        config = response.json()
    finally:
        response.close()
    if config.get("mac_address", "").upper() != mac:
        raise ValueError("Configured MAC does not match this device")
    mqtt = config.get("mqtt", {})
    if not mqtt.get("host") or not mqtt.get("base_topic"):
        raise ValueError("LabTech did not configure a reachable MQTT host/topic")
    if not isinstance(config.get("pins"), list):
        raise ValueError("LabTech did not return a GPIO pin list")
    return config


# A running ESP32 periodically reloads its authenticated LabTech
# configuration. No hardware reset is required for pin/strip/topic changes.
# The value can be overridden in bootstrap_config.py (10-3600 seconds).
DEFAULT_CONFIG_REFRESH_SECONDS = 30


def effective_config(config):
    """Only settings that affect a connected controller trigger a rebuild.

    Firmware revisions are handled by the separate OTA mechanism; they
    must not cause GPIO outputs to cycle off during a config refresh.
    """
    return (
        config.get('device_id'), config.get('mac_address'),
        config.get('building'), config.get('city'),
        config.get('mqtt'), config.get('pins')
    )


def validate_runtime_config(config):
    """Check a prospective layout before stopping a working MQTT controller."""
    mqtt = config.get('mqtt')
    pins = config.get('pins')
    if not isinstance(mqtt, dict) or not isinstance(pins, list):
        raise ValueError('Invalid MQTT or pin configuration')
    base = mqtt.get('base_topic', '').rstrip('/')
    if not mqtt.get('host') or not base or '+' in base or '#' in base:
        raise ValueError('Invalid MQTT host/base topic')
    port = int(mqtt.get('port', 1883))
    if not 1 <= port <= 65535:
        raise ValueError('Invalid MQTT port')
    if port == 8883:
        # Reject a new TLS broker configuration before taking an existing
        # plaintext controller offline when this device lacks TLS trust data.
        try:
            from mqtt_tls_config import MQTT_TLS_ENABLED, MQTT_TLS_PARAMS
        except ImportError:
            MQTT_TLS_ENABLED = False
            MQTT_TLS_PARAMS = None
        if not MQTT_TLS_ENABLED or not isinstance(MQTT_TLS_PARAMS, dict):
            raise ValueError('Broker TLS requires installed verified TLS settings')
        if MQTT_TLS_PARAMS.get('server_hostname') != mqtt['host']:
            raise ValueError('Broker TLS hostname does not match device certificate settings')
    numbers = set()
    topics = set()
    for entry in pins:
        if not isinstance(entry, dict):
            raise ValueError('Invalid pin entry')
        kind = entry.get('type')
        # I2C types are still only supported by custom firmware; preserve
        # the existing behavior of skipping them in BuildingController.
        if kind not in ('LED', 'DUTY_CYCLE', 'WS2811', 'I2C_LED', 'I2C_SCREEN'):
            raise ValueError('Unsupported pin type')
        number = int(entry['number'])
        topic = entry['topic']
        if number < 0 or number in numbers:
            raise ValueError('Invalid or duplicate GPIO number')
        if (not isinstance(topic, str) or not topic.startswith(base + '/')
                or topic in topics):
            raise ValueError('Invalid or duplicate pin MQTT topic')
        numbers.add(number)
        topics.add(topic)
        if kind == 'WS2811':
            count = int(entry.get('led_count', 0))
            brightness = int(entry.get('led_brightness', 0))
            if not 1 <= count <= 300 or not 1 <= brightness <= 255:
                raise ValueError('Invalid WS2811 strip count/brightness')
            import neopixel  # Fail before disconnecting if the driver is absent.
    return True


class ConfigRefresher:
    """Fetch new pin layout while retaining the live MQTT session on errors."""

    def __init__(self, wlan, config, interval_seconds=DEFAULT_CONFIG_REFRESH_SECONDS):
        self.wlan = wlan
        self.config = config
        self.pending_config = None
        try:
            seconds = int(interval_seconds)
        except (TypeError, ValueError):
            seconds = DEFAULT_CONFIG_REFRESH_SECONDS
        if not 10 <= seconds <= 3600:
            seconds = DEFAULT_CONFIG_REFRESH_SECONDS
        self.interval_ms = seconds * 1000
        self.last_poll_ms = time.ticks_ms()

    def poll(self):
        if time.ticks_diff(time.ticks_ms(), self.last_poll_ms) < self.interval_ms:
            return False
        self.last_poll_ms = time.ticks_ms()
        try:
            updated = fetch_config(self.wlan)
            if effective_config(updated) == effective_config(self.config):
                return False
            validate_runtime_config(updated)
            self.pending_config = updated
            print('DNCC pin/controller configuration changed in LabTech')
            return True
        except (OSError, ValueError, KeyError, TypeError, ImportError) as error:
            # Never stop a working controller because the API was temporarily
            # unavailable or a new layout cannot be applied.
            print('DNCC configuration refresh skipped:', str(error))
            return False


def run():
    # Retry with bounded exponential backoff. Hardware resets are avoided.
    delay = 2
    pending_config = None
    while True:
        try:
            wlan = connect_wifi()
            config = pending_config if pending_config is not None else fetch_config(wlan)
            pending_config = None
            print("DNCC city:", config["city"]["name"])
            print("DNCC building:", config["building"]["name"])
            print("Configured GPIO pins:", len(config["pins"]))
            # Do not print enrollment or broker credentials.
            user = MQTT_USER.encode() if MQTT_USER else None
            password = MQTT_PASSWORD.encode() if MQTT_PASSWORD else None
            # TLS can only be switched on with a board-verified SSL stack.
            # Broker TLS is independently configured from LabTech HTTPS.
            tls_params = None
            try:
                from mqtt_tls_config import MQTT_TLS_ENABLED, MQTT_TLS_PARAMS
            except ImportError:
                MQTT_TLS_ENABLED = False
                MQTT_TLS_PARAMS = None
            if MQTT_TLS_ENABLED:
                if not isinstance(MQTT_TLS_PARAMS, dict) or not MQTT_TLS_PARAMS:
                    raise ValueError("MQTT TLS enabled but no verified parameters configured")
                tls_params = MQTT_TLS_PARAMS
            elif int(config["mqtt"].get("port", 1883)) == 8883:
                raise ValueError("Broker TLS port requires verified TLS parameters")
            controller = BuildingController(
                config, "dncc-esp32-" + read_mac(wlan).replace(":", "").lower(),
                mqtt_user=user, mqtt_password=password, tls_params=tls_params
            )
            delay = 2
            idle_callback = None
            try:
                import ota_runtime_config
            except ImportError:
                ota_runtime_config = None
            OTA_CHECK_ENABLED = bool(getattr(ota_runtime_config, 'OTA_CHECK_ENABLED', False))
            OTA_INTERVAL_SECONDS = getattr(ota_runtime_config, 'OTA_INTERVAL_SECONDS', 3600)
            OTA_AUTO_INSTALL_ENABLED = getattr(ota_runtime_config, 'OTA_AUTO_INSTALL_ENABLED', False) is True
            restart_requested = [False]
            if OTA_CHECK_ENABLED:
                from ota_polling import OTAPoller
                poller = OTAPoller(interval_seconds=int(OTA_INTERVAL_SECONDS),
                                   allow_install=OTA_AUTO_INSTALL_ENABLED is True)
                def report_update():
                    result = poller.poll()
                    if result.get('status') == 'update_available':
                        print('Cyber City firmware update available:', result['result'].get('version'))
                    if (result.get('status') == 'restart_required' and
                            isinstance(result.get('result'), dict) and
                            type(result['result'].get('installed')) is int and
                            result['result'].get('restart_required') is True):
                        restart_requested[0] = True
                        return True
                idle_callback = report_update
            def report_connected_runtime():
                # Reaching here proves the MQTT connection and subscriptions
                # were established and 'online' publish returned; it does NOT
                # prove long-term operation or independent boot health.
                from firmware_report import report_firmware
                report_firmware(status='running')
            def report_firmware_safe(status='running'):
                from firmware_report import report_firmware
                return report_firmware(status=status)
            # Periodic self-check-ins are opt-in; they do not certify boot health.
            HEALTH_OBSERVATION_ENABLED = getattr(ota_runtime_config, 'HEALTH_OBSERVATION_ENABLED', False) is True
            if HEALTH_OBSERVATION_ENABLED:
                from health_observer import HealthObserver
                observer = HealthObserver(report_firmware_safe)
                prior_idle = idle_callback
                def health_idle():
                    if prior_idle is not None and prior_idle() is True:
                        return True
                    observer.poll(connected=True)
                idle_callback = health_idle
            import bootstrap_config
            refresh_seconds = getattr(
                bootstrap_config, 'CONFIG_REFRESH_INTERVAL_SECONDS',
                DEFAULT_CONFIG_REFRESH_SECONDS
            )
            refresher = ConfigRefresher(wlan, config, refresh_seconds)
            def live_config_idle():
                # Preserve existing OTA/health behavior while adding a
                # periodic authenticated configuration refresh.
                if idle_callback is not None and idle_callback() is True:
                    return True
                return refresher.poll()
            controller.run(on_idle=live_config_idle,
                           on_connected=report_connected_runtime)
            if restart_requested[0]:
                # Firmware activation (not pin changes) may require reset.
                from machine import reset
                reset()
            if refresher.pending_config is not None:
                # BuildingController safely disables old GPIO outputs and
                # disconnects MQTT before returning. Rebuild from the freshly
                # verified settings without any ESP32 power cycle/reset.
                pending_config = refresher.pending_config
                print('DNCC applying updated pin layout without reboot')
                continue
        except (OSError, ValueError, KeyError) as error:
            print("DNCC connection/configuration failure:", str(error))
            print("Retrying in", delay, "seconds")
            time.sleep(delay)
            delay = min(delay * 2, 60)


if __name__ == "__main__":
    run()
