"""Example manual test with the authenticated v2 configuration response.

Before importing, save an approved configuration as local_config.py and
install umqtt.simple on the ESP32. Do not run this on production actuators.
"""
from local_config import CONFIG, DEVICE_ID, MQTT_USER, MQTT_PASSWORD
from mqtt_controller import BuildingController

controller = BuildingController(
    CONFIG, DEVICE_ID,
    mqtt_user=MQTT_USER.encode() if MQTT_USER else None,
    mqtt_password=MQTT_PASSWORD.encode() if MQTT_PASSWORD else None,
)
controller.run()
