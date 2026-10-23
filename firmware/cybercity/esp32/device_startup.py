"""DNCC device startup orchestrator (MicroPython).

Use only on an isolated lab network until device HTTPS trust and broker
authentication/TLS are validated. Does not download or execute remote code.
"""
import time
import network
import ubinascii
try:
    import urequests as requests
except ImportError:
    import requests

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


def run():
    # Retry with bounded exponential backoff. Hardware resets are avoided.
    delay = 2
    while True:
        try:
            wlan = connect_wifi()
            config = fetch_config(wlan)
            print("DNCC city:", config["city"]["name"])
            print("DNCC building:", config["building"]["name"])
            print("Configured GPIO pins:", len(config["pins"]))
            # Best-effort firmware self-report; errors must not prevent GPIO.
            try:
                from firmware_report import report_firmware
                report_firmware()
            except (OSError, ValueError, ImportError) as exc:
                print("Firmware report unavailable:", str(exc))
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
            controller.run(on_idle=idle_callback)
            if restart_requested[0]:
                # MQTT controller has run its safe-output/disconnect cleanup.
                from machine import reset
                reset()
        except (OSError, ValueError, KeyError) as error:
            print("DNCC connection/configuration failure:", str(error))
            print("Retrying in", delay, "seconds")
            time.sleep(delay)
            delay = min(delay * 2, 60)


if __name__ == "__main__":
    run()
