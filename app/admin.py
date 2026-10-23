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


# TEKCON optional NFC authentication settings.
from .models import TekconNFCConfiguration, TekconIdentityLink
from django.contrib import admin as django_admin

@django_admin.register(TekconNFCConfiguration)
class TekconNFCConfigurationAdmin(django_admin.ModelAdmin):
    list_display = ('id', 'enabled', 'server_url', 'auto_create_users', 'target_ctf', 'target_course')
    change_form_template = 'admin/tekcon_nfc_configuration_change_form.html'

    def get_urls(self):
        from django.urls import path
        return [path('<path:object_id>/diagnostics/', self.admin_site.admin_view(self.diagnostics_view), name='app_tekconnfcconfiguration_diagnostics')] + super().get_urls()

    def diagnostics_view(self, request, object_id):
        from django.shortcuts import render
        from django.http import HttpResponseForbidden
        from .tekcon_nfc_auth import run_nfc_diagnostic
        if not self.has_change_permission(request):
            return HttpResponseForbidden()
        config = self.get_object(request, object_id)
        if config is None:
            from django.http import Http404
            raise Http404
        result = None
        if request.method == 'POST':
            result = run_nfc_diagnostic(config, request.POST.get('badge_uid', ''))
        return render(request, 'admin/tekcon_nfc_diagnostics.html', {
            **self.admin_site.each_context(request),
            'title': 'TEKCON NFC diagnostics', 'config': config, 'result': result,
            'opts': self.model._meta,
        })
    def has_add_permission(self, request):
        return super().has_add_permission(request) and not TekconNFCConfiguration.objects.exists()

@django_admin.register(TekconIdentityLink)
class TekconIdentityLinkAdmin(django_admin.ModelAdmin):
    list_display = ('participant_id', 'user', 'created_at')
    readonly_fields = ('participant_id', 'user', 'created_at')
    def has_add_permission(self, request):
        return False


# Assignment rubrics: instructor-managed definitions and criterion assessments.
# Gradebook scores are deliberately unchanged until grading integration is added.
from .models import AssignmentRubric, RubricCriterion, RubricLevel, RubricAssessment, RubricCriterionScore


class RubricCriterionInline(django_admin.TabularInline):
    model = RubricCriterion
    extra = 1
    fields = ('order', 'title', 'description', 'max_points')


@django_admin.register(AssignmentRubric)
class AssignmentRubricAdmin(django_admin.ModelAdmin):
    list_display = ('title', 'course', 'activity', 'published', 'possible_points')
    list_filter = ('course', 'published')
    search_fields = ('title', 'description')
    inlines = (RubricCriterionInline,)
    fields = ('course', 'title', 'description', 'content_type', 'object_id', 'published')

    def save_model(self, request, obj, form, change):
        obj.full_clean()
        super().save_model(request, obj, form, change)


class RubricLevelInline(django_admin.TabularInline):
    model = RubricLevel
    extra = 1


@django_admin.register(RubricCriterion)
class RubricCriterionAdmin(django_admin.ModelAdmin):
    list_display = ('title', 'rubric', 'max_points', 'order')
    list_filter = ('rubric__course',)
    inlines = (RubricLevelInline,)


class RubricCriterionScoreInline(django_admin.TabularInline):
    model = RubricCriterionScore
    extra = 0
    fields = ('criterion', 'points_awarded', 'feedback')


@django_admin.register(RubricAssessment)
class RubricAssessmentAdmin(django_admin.ModelAdmin):
    list_display = ('rubric', 'student', 'awarded_points', 'released', 'graded_by')
    list_filter = ('rubric__course', 'released')
    search_fields = ('student__username', 'rubric__title')
    inlines = (RubricCriterionScoreInline,)
    # In foundation release, prevent showing a published grade that has not
    # been synchronized to Grade, since student-facing UI isn't connected yet.
    readonly_fields = ('released', 'graded_at', 'graded_by')
    exclude = ()
    def save_model(self, request, obj, form, change):
        obj.full_clean()
        obj.graded_by = request.user
        super().save_model(request, obj, form, change)
