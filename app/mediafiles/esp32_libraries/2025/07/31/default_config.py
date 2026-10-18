# INSTRUCTIONS:
# 1. Create this file named 'default_config.py' on your ESP32.
# 2. This file provides essential FALLBACK settings if the device cannot reach
#    the Django server on first boot.
# 3. The WiFi credentials here are REQUIRED, as the device needs them to get online.

# -- WiFi Configuration (Required) --
WIFI_SSID = "YOUR_WIFI_SSID"
WIFI_PASSWORD = "YOUR_WIFI_PASSWORD"

# -- Fallback MQTT Broker Configuration --
# These are only used if the device cannot download a config from the server.
MQTT_BROKER = "YOUR_MQTT_BROKER_IP" # e.g., "192.168.0.88"
MQTT_PORT = 1883
MQTT_USER = "" #Optional
MQTT_PASSWORD = "" #Optional

# -- Fallback Device Configuration --
MQTT_BASE_TOPIC = "cybercity/fallback/" 
PINS = {
    # GPIO Pin Number: { 'name': 'Friendly Name', 'subtopic': 'mqtt_sub_topic' }
    2: {'name': 'Onboard LED', 'subtopic': 'fallback/led'},
}
