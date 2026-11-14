"""Student quiz status helpers for course content cards."""
from django import template

from app.models import QuizDraft

register = template.Library()


@register.simple_tag
def quiz_has_draft(quiz, user):
    """Only the current authenticated user's unfinished quiz state is relevant."""
    if not getattr(user, 'is_authenticated', False):
        return False
    return QuizDraft.objects.filter(quiz=quiz, user=user).exists()
