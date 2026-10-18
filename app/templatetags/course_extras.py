from django import template
from django.urls import reverse
from django.urls.exceptions import NoReverseMatch
import random
import re

# Note: This is an absolute import, which is more robust
from app.models import ContentCompletion

register = template.Library()


@register.simple_tag
def active_ai_assistant_available():
    from app.models import OpenWebUIAssistant
    return OpenWebUIAssistant.objects.filter(is_active=True).exclude(host='').exclude(model_name='').exists()

@register.filter(name='class_name')
def class_name(value):
    """A template filter that returns the name of an object's class."""
    return value.__class__.__name__

@register.simple_tag
def is_completed(completed_items, content_type_id, object_id):
    """
    A template tag to check if a specific content item is in the set of completed items.
    Usage: {% is_completed completed_items content_type.id item.id as item_is_completed %}
    """
    return (content_type_id, object_id) in completed_items

@register.filter
def get_item(dictionary, key):
    """
    A template filter to allow accessing a dictionary item with a variable key.
    Usage: {{ my_dictionary|get_item:my_variable }}
    """
    return dictionary.get(key)


@register.filter(name='gradebook_label')
def gradebook_label(key):
    from app.gradebook import CATEGORY_LABELS
    return CATEGORY_LABELS.get(key, key)

@register.filter(name='get_score')
def get_score(grade_string):
    """
    Extracts a numerical percentage from a grade string.
    Handles formats like "85%", "4 / 5", "✓", or returns 0 for "—".
    """
    if not isinstance(grade_string, str):
        return 0
    
    if '✓' in grade_string:
        return 100

    # NEW: Check for fractional format like "4 / 5"
    if '/' in grade_string:
        parts = [p.strip() for p in grade_string.split('/')]
        try:
            numerator = float(parts[0])
            denominator = float(parts[1])
            if denominator == 0:
                return 0
            return (numerator / denominator) * 100
        except (ValueError, IndexError):
            return 0 # In case of malformed fraction

    # Existing logic for percentages like "85%"
    numbers = re.findall(r"[-+]?\d*\.\d+|\d+", grade_string)
    if numbers:
        try:
            return float(numbers[0])
        except (ValueError, IndexError):
            return 0
    
    return 0

@register.filter
def shuffle(arg):
    """
    Takes a list or queryset and returns it in a randomized order.
    """
    try:
        tmp = list(arg)
        random.shuffle(tmp)
        return tmp
    except (TypeError, ValueError):
        return arg
    
@register.simple_tag
def get_content_url(item, action):
    """
    Returns the correct edit or delete URL for any course content item.
    action must be 'edit' or 'delete'.
    """
    model_name = item.__class__.__name__.lower()
    
    url_name_map = {
        'textpage': 'labtech_edit_text_page',
        'video': 'labtech_edit_video',
        'quiz': 'labtech_edit_quiz',
        'lab': 'labtech_edit_lab',
        'hotspotactivity': 'labtech_edit_hotspot',
        'draganddropactivity': 'labtech_edit_drag_and_drop',
        'codingactivity': 'labtech_edit_coding_activity',
    }
    
    if action == 'delete':
        url_name_map = {
            'textpage': 'labtech_delete_text_page',
            'video': 'labtech_delete_video',
            'quiz': 'labtech_delete_quiz',
            'lab': 'labtech_delete_lab',
            'hotspotactivity': 'labtech_delete_hotspot',
            'draganddropactivity': 'labtech_delete_drag_and_drop',
            'codingactivity': 'labtech_delete_coding_activity',
        }

    url_name = url_name_map.get(model_name)
    
    if not url_name:
        return ""

    try:
        return reverse(url_name, args=[item.course.id, item.id])
    except NoReverseMatch:
        return ""
    except Exception:
        return ""
