import sys
from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model
from app.models import (
    Badge, UserBadge, Certificate, ContentCompletion,
    Course, Lab, Quiz
)

User = get_user_model()

class Command(BaseCommand):
    help = 'Retroactively awards badges to users who have met the requirements.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("--- Starting Retroactive Badge Audit ---"))

        all_users = User.objects.filter(is_active=True)
        all_badges = Badge.objects.all()
        badges_awarded = 0
        
        self.stdout.write(f"Checking {all_users.count()} users against {all_badges.count()} badges...")

        # Get all relevant completion data once to reduce database hits
        all_completions = ContentCompletion.objects.all()
        all_course_completions = Certificate.objects.all() # Using Certificates as a proxy for course completion

        for user in all_users:
            # Get badges the user has already earned to avoid re-checking
            earned_badge_ids = set(UserBadge.objects.filter(user=user).values_list('badge_id', flat=True))
            
            # Filter to check only unearned badges
            unearned_badges = all_badges.exclude(id__in=earned_badge_ids)

            if not unearned_badges:
                continue

            # Get this user's completions once
            user_completions = all_completions.filter(user=user)
            user_course_completions = all_course_completions.filter(user=user)

            for badge in unearned_badges:
                requirements_met = True

                # Check course requirements
                required_courses_ids = set(badge.required_courses.values_list('id', flat=True))
                if required_courses_ids:
                    completed_courses_ids = set(user_course_completions.filter(course_id__in=required_courses_ids).values_list('course_id', flat=True))
                    if not required_courses_ids.issubset(completed_courses_ids):
                        requirements_met = False
                
                # Check lab requirements
                if requirements_met:
                    required_labs_ids = set(badge.required_labs.values_list('id', flat=True))
                    if required_labs_ids:
                        lab_ct = ContentType.objects.get_for_model(Lab)
                        completed_labs_ids = set(user_completions.filter(content_type=lab_ct, object_id__in=required_labs_ids).values_list('object_id', flat=True))
                        if not required_labs_ids.issubset(completed_labs_ids):
                            requirements_met = False

                # Check quiz requirements
                if requirements_met:
                    required_quizzes_ids = set(badge.required_quizzes.values_list('id', flat=True))
                    if required_quizzes_ids:
                        quiz_ct = ContentType.objects.get_for_model(Quiz)
                        completed_quizzes_ids = set(user_completions.filter(content_type=quiz_ct, object_id__in=required_quizzes_ids).values_list('object_id', flat=True))
                        if not required_quizzes_ids.issubset(completed_quizzes_ids):
                            requirements_met = False
                
                # If all checks passed, award the badge
                if requirements_met:
                    UserBadge.objects.create(user=user, badge=badge)
                    badges_awarded += 1
                    self.stdout.write(f"  -> Awarded badge '{badge.name}' to '{user.username}'")

        self.stdout.write(self.style.SUCCESS(f"\n--- Audit Complete ---"))
        self.stdout.write(self.style.SUCCESS(f"✅ Awarded {badges_awarded} new badges."))