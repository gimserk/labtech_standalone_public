import sys
from itertools import chain
from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.contenttypes.models import ContentType
from app.models import (
    Enrollment, Certificate, CertificateTemplate, ContentCompletion,
    Course, TextPage, Video, Audio, Quiz, Lab, HotspotActivity, DragAndDropActivity, CodingActivity
)

class Command(BaseCommand):
    help = 'Retroactively awards certificates for fully completed courses.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("--- Starting Retroactive Certificate Audit ---"))

        # First, ensure a default certificate template exists to award.
        default_template = CertificateTemplate.objects.filter(course__isnull=True).first()
        if not default_template:
            self.stdout.write(self.style.ERROR("\nERROR: No default certificate template found. Please create one in the admin panel before running this script."))
            sys.exit(1)

        enrollments_to_check = Enrollment.objects.select_related('user', 'course').all()
        certificates_awarded = 0
        
        self.stdout.write(f"Checking {enrollments_to_check.count()} total course enrollments...")

        # Use a transaction to make the process more efficient
        with transaction.atomic():
            for enrollment in enrollments_to_check:
                user = enrollment.user
                course = enrollment.course

                # 1. Skip if the user already has a certificate for this course
                if Certificate.objects.filter(user=user, course=course).exists():
                    continue

                # 2. Get all content items that belong to this specific course
                all_content = list(chain(
                    course.text_pages.all(), course.videos.all(), course.audio_items.all(), course.quizzes.all(),
                    course.labs.all(), course.hotspot_activities.all(),
                    course.drag_and_drop_activities.all(), course.coding_activities.all(), course.pbq_activities.all()
                ))
                total_items = len(all_content)

                if total_items == 0:
                    continue

                # 3. Count how many of THIS course's items the user has completed
                content_ids = [item.id for item in all_content]
                content_type_ids = [ContentType.objects.get_for_model(item).id for item in all_content]
                
                completed_pairs = set(ContentCompletion.objects.filter(
                    user=user, 
                    content_type_id__in=set(content_type_ids),
                    object_id__in=content_ids
                ).values_list('content_type_id', 'object_id'))
                completed_count = sum(
                    (ContentType.objects.get_for_model(item).id, item.id) in completed_pairs
                    for item in all_content
                )

                # 4. If the course is 100% complete, award the certificate
                if completed_count >= total_items:
                    course_template = CertificateTemplate.objects.filter(course=course).first()
                    template_to_use = course_template or default_template
                    
                    Certificate.objects.create(
                        user=user,
                        course=course,
                        template=template_to_use
                    )
                    certificates_awarded += 1
                    self.stdout.write(f"  -> Awarded certificate to '{user.username}' for completing '{course.title}'")

        self.stdout.write(self.style.SUCCESS(f"\n--- Audit Complete ---"))
        self.stdout.write(self.style.SUCCESS(f"✅ Awarded {certificates_awarded} new certificates."))
