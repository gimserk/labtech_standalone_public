# In app/templatetags/json_extras.py
import json
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.simple_tag
def safe_json_script(data, element_id):
    """
    A custom, safe JSON script generator.
    Serializes a Python variable to JSON and wraps it in a <script> tag.
    """
    json_data = json.dumps(data)
    script_tag = f'<script id="{element_id}" type="application/json">{json_data}</script>'
    return mark_safe(script_tag)