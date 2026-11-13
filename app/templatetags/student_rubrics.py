"""Read-only activity rubric previews for enrolled students and course instructors.

Students see only published rubric definitions and their own saved grades.
Course instructors can preview unpublished rubrics without student enrollment.
"""
from django import template
from django.contrib.contenttypes.models import ContentType

from app.gradebook_models import activity_models
from app.models import AssignmentRubric, Enrollment, RubricAssessment

register = template.Library()
SUPPORTED_MODELS = frozenset(activity_models().values())


@register.inclusion_tag("labtech/partials/student_rubric_card.html", takes_context=True)
def student_rubric_card(context, activity):
    request = context.get("request")
    if (
        request is None
        or not request.user.is_authenticated
        or activity is None
        or type(activity) not in SUPPORTED_MODELS
    ):
        return {}

    user = request.user
    is_instructor = (
        user.is_superuser
        or activity.course.instructors.filter(pk=user.pk).exists()
    )
    is_enrolled = Enrollment.objects.filter(
        course_id=activity.course_id, user=user
    ).exists()
    if not is_instructor and not is_enrolled:
        return {}

    base_context = {
        "rubric_activity": activity,
        "rubric_course": activity.course,
        "rubric_model_name": activity._meta.model_name,
        "rubric_is_instructor": is_instructor,
    }
    queryset = AssignmentRubric.objects.filter(
        course_id=activity.course_id,
        content_type=ContentType.objects.get_for_model(activity),
        object_id=activity.pk,
    )
    if not is_instructor:
        queryset = queryset.filter(published=True)
    rubric = queryset.prefetch_related("criteria__levels").first()
    if rubric is None:
        if is_instructor and activity._meta.model_name == "filesubmissionactivity":
            return {**base_context, "rubric_missing": True}
        return {}

    assessment = None
    if not is_instructor:
        assessment = RubricAssessment.objects.filter(
            rubric=rubric, student=user, released=True
        ).first()
    return {
        **base_context,
        "rubric": rubric,
        "rubric_assessment": assessment,
    }
