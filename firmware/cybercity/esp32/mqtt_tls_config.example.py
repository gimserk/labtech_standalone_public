# COPY to mqtt_tls_config.py only after validating the exact ESP32 build.
# The default remains disabled so existing test installations still work.
#
# TLS params supported by umqtt.simple vary across MicroPython releases.
# Merely setting ssl=True does not prove that certificates are verified.
MQTT_TLS_ENABLED = False
MQTT_TLS_PARAMS = None

# For a build that supports full certificate verification, investigate:
# import ssl
# MQTT_TLS_ENABLED = True
# MQTT_TLS_PARAMS = {
#     "server_hostname": "mqtt.city.example.edu",
#     "cert_reqs": ssl.CERT_REQUIRED,
#     # Your build must securely load a trusted CA.
# }
#
# Do not turn this on until certificate-chain AND hostname rejection have
# been tested on the actual board. Unsupported builds fail closed.
