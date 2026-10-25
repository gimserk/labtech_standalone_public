"""Display conservative ESP32 deployment state in Cyber City templates."""
from django import template
from app.cybercity_firmware_status import firmware_deployment_status

register = template.Library()


@register.simple_tag
def esp32_firmware_status(firmware, esp32):
    return firmware_deployment_status(firmware, esp32)
