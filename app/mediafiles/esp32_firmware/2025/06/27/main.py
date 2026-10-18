VERSION = 0

import time
import machine
import network
import ujson
import os
import ubinascii
import urequests
from umqtt.simple import MQTTClient

# --- Dynamic Configuration Loading ---
try:
    # Try to import the server-provided config first
    import config
    print("Loaded server-provided 'config.py'.")
except ImportError:
    # If it fails, fall back to the default settings
    print("Could not find 'config.py', loading 'default_config.py'.")
    import default_config as config

# --- Global Variables ---
wlan = network.WLAN(network.STA_IF)
device_mac = ubinascii.hexlify(wlan.config('mac')).decode()
client_id = "esp32_" + device_mac
led = machine.Pin(2, machine.Pin.OUT)

# --- Helper Functions ---
def blink_led(times, delay=0.2):
    for _ in range(times):
        led.on(); time.sleep(delay); led.off(); time.sleep(delay)

def get_mac_address():
    mac_bytes = wlan.config('mac')
    return ':'.join(['%02x' % b for b in mac_bytes]).upper()

def connect_wifi():
    print("Connecting to WiFi...", end="")
    wlan.active(True)
    if not wlan.isconnected():
        # WiFi credentials now come from the loaded config
        wlan.connect(config.WIFI_SSID, config.WIFI_PASSWORD)
        timeout = 10
        while not wlan.isconnected() and timeout > 0:
            print(".", end="")
            time.sleep(1)
            timeout -= 1
    
    if wlan.isconnected():
        print("\nWiFi Connected. IP:", wlan.ifconfig()[0])
        blink_led(2)
        return True
    else:
        print("\nFailed to connect to WiFi.")
        blink_led(5, 0.5)
        return False

# --- OTA Update Logic ---
def download_file(url, save_path):
    """Generic function to download a file from a URL and save it."""
    print(f"Downloading from: {url}")
    try:
        response = urequests.get(url)
        if response.status_code == 200:
            print(f"Download successful. Saving to '{save_path}'...")
            with open(save_path, 'w') as f:
                f.write(response.text)
            response.close()
            return True
        else:
            print(f"Failed to download. Status: {response.status_code}")
            response.close()
            return False
    except Exception as e:
        print(f"Error during download: {e}")
        return False

def check_and_apply_updates():
    """Checks for both config and code updates and applies them."""
    print(f"Firmware Version: {VERSION}. Checking for updates...")
    
    if not wlan.isconnected():
        connect_wifi()
        if not wlan.isconnected():
            print("No WiFi, cannot check for updates.")
            return

    try:
        mac_for_url = get_mac_address()
        # The SERVER_IP now comes from the loaded config
        check_url = f"http://{config.SERVER_IP}/api/firmware/check/?mac={mac_for_url}&version={VERSION}"
        print(f"Checking URL: {check_url}")
        
        response = urequests.get(check_url)
        if response.status_code != 200:
            print(f"Failed to check for updates. Status: {response.status_code}")
            response.close()
            return
            
        data = response.json()
        response.close()

        # 1. Always try to sync the configuration file
        config_url = data.get('config_url')
        if config_url:
            print("Attempting to sync configuration...")
            download_file(config_url, 'config.py')
        
        # 2. Check if a code update is available and reboot if installed
        if data.get('update_available'):
            print(f"New code version {data.get('version')} available.")
            if download_file(data.get('url'), 'main_new.py'):
                os.rename('main_new.py', 'main.py')
                print("Code update installed. Rebooting...")
                time.sleep(1)
                machine.reset() # Reboot to apply code update
        else:
            print("Firmware code is up to date.")

    except Exception as e:
        print(f"Error checking for updates: {e}")

# --- MQTT Logic ---
def mqtt_callback(topic, msg):
    topic = topic.decode()
    msg = msg.decode()
    print(f"Received MQTT Message - Topic: '{topic}', Message: '{msg}'")

    for pin_num, pin_info in config.PINS.items():
        command_topic = config.MQTT_BASE_TOPIC + pin_info['subtopic'] + '/command'
        if topic == command_topic:
            target_pin = machine.Pin(pin_num, machine.Pin.OUT)
            if msg.upper() == "ON": target_pin.on()
            elif msg.upper() == "OFF": target_pin.off()
            elif msg.upper() == "TOGGLE": target_pin.value(not target_pin.value())
            
            status = "ON" if target_pin.value() else "OFF"
            status_topic = config.MQTT_BASE_TOPIC + pin_info['subtopic'] + '/status'
            try:
                mqtt_client.publish(status_topic, status, retain=True)
                print(f"Published status '{status}' to topic '{status_topic}'")
            except Exception as e:
                print(f"Failed to publish status: {e}")
            break

def connect_and_subscribe_mqtt():
    print("Connecting to MQTT broker...")
    try:
        # MQTT settings now come from the loaded config
        client = MQTTClient(client_id, config.MQTT_BROKER, port=config.MQTT_PORT, user=config.MQTT_USER, password=config.MQTT_PASSWORD)
        client.set_callback(mqtt_callback)
        client.connect()
        
        for pin_info in config.PINS.values():
            command_topic = config.MQTT_BASE_TOPIC + pin_info['subtopic'] + '/command'
            client.subscribe(command_topic)
            print(f"Subscribed to: {command_topic}")
        
        print("MQTT Connected and subscribed successfully.")
        blink_led(3)
        return client
    except Exception as e:
        print(f"Failed to connect to MQTT: {e}")
        blink_led(8, 0.5)
        return None

# --- Main Execution ---
if __name__ == "__main__":
    blink_led(1)

    # 1. Sync config and check for code updates. Reboot if new code is installed.
    check_and_apply_updates()
    
    # 2. Proceed with normal operation using the latest (or default) config
    if not wlan.isconnected(): connect_wifi()

    mqtt_client = None
    if wlan.isconnected(): mqtt_client = connect_and_subscribe_mqtt()
    
    # 3. Main loop
    if mqtt_client:
        print("Starting main loop...")
        while True:
            try:
                mqtt_client.check_msg()
                time.sleep(1)
            except Exception as e:
                print(f"Error in main loop: {e}. Reconnecting...")
                time.sleep(5)
                if not wlan.isconnected(): connect_wifi()
                mqtt_client = connect_and_subscribe_mqtt()
                if not mqtt_client:
                    print("Reconnect failed, will retry.")
                    time.sleep(10)
