from django.contrib import admin

from .forms import OpenWebUIAssistantForm
from .models import OpenWebUIAssistant


@admin.register(OpenWebUIAssistant)
class AssistantAdmin(admin.ModelAdmin):
    form = OpenWebUIAssistantForm
    list_display = ('name', 'provider', 'model_name', 'is_active',
                    'tutor_behavior', 'tutor_grounding_enabled')
    list_filter = ('provider', 'is_active', 'tutor_grounding_enabled')
    search_fields = ('name', 'model_name')
