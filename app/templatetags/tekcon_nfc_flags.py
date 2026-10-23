from django import template
from app.tekcon_nfc_auth import _settings

register = template.Library()

@register.simple_tag
def tekcon_nfc_enabled():
    return _settings() is not None
