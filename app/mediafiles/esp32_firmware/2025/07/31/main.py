VERSION = 0

import time
import machine
import network
import ujson
import os
import ubinascii
import urequests
from umqtt.simple import MQTTClient

try:
    import config
except ImportError:
    import default_config as config

wlan = network.WLAN(network.STA_IF)
device_mac = ubinascii.hexlify(wlan.config('mac')).decode()
client_id = "esp32_" + device_mac
led = machine.Pin(2, machine.Pin.OUT)

def blink_led(times, delay=0.2):
    for _ in range(times): led.on(); time.sleep(delay); led.off(); time.sleep(delay)

def get_mac_address():
    return ':'.join(['%02x' % b for b in wlan.config('mac')]).upper()

def connect_wifi():
    print("Connecting to WiFi...", end="")
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(config.WIFI_SSID, config.WIFI_PASSWORD)
        timeout = 10
        while not wlan.isconnected() and timeout > 0:
            print(".", end=""); time.sleep(1); timeout -= 1
    if wlan.isconnected():
        print("\nWiFi Connected. IP:", wlan.ifconfig()[0]); blink_led(2); return True
    else:
        print("\nFailed to connect to WiFi."); blink_led(5, 0.5); return False

def download_file(url, save_path):
    print(f"Downloading from: {url}")
    try:
        r = urequests.get(url, stream=True)
        if r.status_code == 200:
            with open(save_path, 'wb') as f:
                while True:
                    chunk = r.raw.read(1024)
                    if not chunk: break
                    f.write(chunk)
            r.close()
            print(f"Saved to '{save_path}'")
            return True
        else:
            print(f"Failed download. Status: {r.status_code}"); r.close(); return False
    except Exception as e:
        print(f"Error during download: {e}"); return False

def ensure_dir_exists(path):
    """Checks if a directory exists, and creates it if not."""
    parts = path.split('/')
    if len(parts) > 1:
        dir_path = '/'.join(parts[:-1])
        try:
            os.stat(dir_path)
        except OSError:
            try:
                print(f"Creating directory: {dir_path}")
                os.mkdir(dir_path)
            except Exception as e:
                print(f"Failed to create directory {dir_path}: {e}")

def check_and_apply_updates():
    print(f"Firmware Version: {VERSION}. Checking for updates...")
    if not wlan.isconnected() and not connect_wifi():
        print("No WiFi, cannot check for updates."); return

    try:
        server_ip = getattr(config, 'SERVER_IP', 'your_server_ip_here') # Fallback
        check_url = f"http://{server_ip}/api/firmware/check/?mac={get_mac_address()}&version={VERSION}"
        print(f"Checking URL: {check_url}")
        
        response = urequests.get(check_url)
        if response.status_code != 200:
            print(f"Update check failed. Status: {response.status_code}"); response.close(); return
            
        data = response.json(); response.close()

        if data.get('config_url'):
            print("Syncing configuration..."); download_file(data.get('config_url'), 'config.py')
        
        if data.get('update_available'):
            print(f"New bundle version {data.get('version')} found.")
            files = data.get('files', [])
            if not files:
                print("Update available but no files listed."); return

            # Install all files from the bundle
            for file_info in files:
                path = file_info.get('path')
                url = file_info.get('url')
                ensure_dir_exists(path)
                if not download_file(url, path):
                    print(f"FATAL: Failed to download {path}. Aborting update."); return
            
            print("All files updated successfully. Rebooting..."); time.sleep(1); machine.reset()
        else:
            print("Firmware is up to date.")
    except Exception as e:
        print(f"Error checking for updates: {e}")

def mqtt_callback(topic, msg):
    topic, msg = topic.decode(), msg.decode()
    print(f"MQTT RX: {topic} -> {msg}")
    for pin_num, pin_info in config.PINS.items():
        if topic == config.MQTT_BASE_TOPIC + pin_info['subtopic'] + '/command':
            pin = machine.Pin(pin_num, machine.Pin.OUT)
            if msg.upper() == "ON": pin.on()
            elif msg.upper() == "OFF": pin.off()
            elif msg.upper() == "TOGGLE": pin.value(not pin.value())
            status = "ON" if pin.value() else "OFF"
            status_topic = config.MQTT_BASE_TOPIC + pin_info['subtopic'] + '/status'
            try:
                mqtt_client.publish(status_topic, status, retain=True)
            except Exception as e:
                print(f"MQTT TX fail: {e}")
            break

def connect_and_subscribe_mqtt():
    print("Connecting to MQTT broker...")
    try:
        client = MQTTClient(client_id, config.MQTT_BROKER, port=config.MQTT_PORT, user=config.MQTT_USER, password=config.MQTT_PASSWORD)
        client.set_callback(mqtt_callback)
        client.connect()
        for pin_info in config.PINS.values():
            client.subscribe(config.MQTT_BASE_TOPIC + pin_info['subtopic'] + '/command')
        print("MQTT Connected."); blink_led(3); return client
    except Exception as e:
        print(f"MQTT connect fail: {e}"); blink_led(8, 0.5); return None

if __name__ == "__main__":
    blink_led(1)
    check_and_apply_updates()
    
    mqtt_client = None
    if connect_wifi(): mqtt_client = connect_and_subscribe_mqtt()
    
    if mqtt_client:
        print("Starting main loop...")
        while True:
            try:
                mqtt_client.check_msg()
                time.sleep(1)
            except Exception as e:
                print(f"Loop error: {e}. Reconnecting..."); time.sleep(5)
                if not wlan.isconnected(): connect_wifi()
                mqtt_client = connect_and_subscribe_mqtt()
                if not mqtt_client: time.sleep(10)
