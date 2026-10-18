# In app/context_processors.py

from .models import Course, Enrollment
from django.conf import settings

def session_expiry_context(request):
    """
    Makes the session expiry timestamp available to all templates.
    """
    if request.user.is_authenticated:
        # get_expiry_date() returns a timezone-aware datetime object
        expiry_datetime = request.session.get_expiry_date()
        # Convert to ISO 8601 format, which JavaScript can easily parse
        return {'SESSION_EXPIRY_TIMESTAMP': expiry_datetime.isoformat()}
    return {}

def role_context(request):
    """
    Makes simplified user roles available in all templates.
    """
    if not request.user.is_authenticated:
        return {}

    user = request.user
    
    # Check for each role based on the simplified structure.
    is_site_admin = user.is_superuser
    
    # An instructor is ONLY someone who is explicitly assigned to teach a course.
    is_instructor = Course.objects.filter(instructors=user).exists()
    
    # The student role is now considered the default for any authenticated user.
    is_student = True

    return {
        'is_student_role': is_student,
        'is_instructor_role': is_instructor,
        'is_site_admin_role': is_site_admin,
    }

def registration_context(request):
    """Exposes the registration toggle to the templates."""
    return {
        'ACCOUNT_ALLOW_REGISTRATION': getattr(settings, 'ACCOUNT_ALLOW_REGISTRATION', True)
    }
