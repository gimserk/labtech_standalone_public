"""Scenario assessments kept separate from the existing quiz schema."""

import uuid
from pathlib import Path

from ckeditor.fields import RichTextField
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum
from django.utils.deconstruct import deconstructible

from .models import ContentTiming


@deconstructible
class PBQStorage(FileSystemStorage):
    @property
    def base_location(self):
        return str(
            getattr(settings, "PBQ_PRIVATE_ROOT", settings.BASE_DIR / "private_pbq")
        )

    @property
    def location(self):
        root = Path(self.base_location).resolve()
        for value in (settings.MEDIA_ROOT, getattr(settings, "STATIC_ROOT", None)):
            if value:
                public = Path(value).resolve()
                if root == public or public in root.parents:
                    raise ValidationError(
                        "PBQ_PRIVATE_ROOT must be outside public media/static roots."
                    )
        return str(root)

    def url(self, name):
        raise ValueError("PBQ artifacts require authenticated delivery.")


def artifact_path(instance, filename):
    return f"{instance.activity_id}/{uuid.uuid4().hex}{Path(filename).suffix.lower()}"


class PBQActivity(ContentTiming):
    course = models.ForeignKey(
        "Course", on_delete=models.CASCADE, related_name="pbq_activities"
    )
    chapter = models.ForeignKey(
        "Chapter",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="pbq_activities",
    )
    title = models.CharField(max_length=255)
    scenario = RichTextField(blank=True, config_name="pbq")
    order = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=False)
    max_attempts = models.PositiveIntegerField(default=1)
    show_answers_after = models.CharField(
        max_length=16,
        default="never",
        choices=[
            ("never", "Never"),
            ("graded", "After grading"),
            ("due_date", "After due date"),
            ("until_date", "After availability ends"),
        ],
    )
    content_locked_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["chapter__order", "order", "pk"]

    def clean(self):
        super().clean()
        if self.chapter_id and self.chapter.course_id != self.course_id:
            raise ValidationError({"chapter": "Choose a chapter in this course."})
        if (
            self.available_from
            and self.available_until
            and self.available_from > self.available_until
        ):
            raise ValidationError("Availability end must follow the start.")

    @property
    def max_score(self):
        return (
            PBQAnswerField.objects.filter(question__activity=self).aggregate(
                total=Sum("points")
            )["total"]
            or 0
        )

    def __str__(self):
        return self.title


class PBQArtifact(models.Model):
    activity = models.ForeignKey(
        PBQActivity, on_delete=models.CASCADE, related_name="artifacts"
    )
    file = models.FileField(storage=PBQStorage(), upload_to=artifact_path)
    title = models.CharField(max_length=255)
    caption = models.TextField(blank=True)
    alt_text = models.CharField(max_length=500, blank=True)
    original_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    file_size = models.PositiveIntegerField()
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "pk"]

    @property
    def is_image(self):
        return self.content_type.startswith("image/")


class PBQQuestion(models.Model):
    activity = models.ForeignKey(
        PBQActivity, on_delete=models.CASCADE, related_name="questions"
    )
    prompt = RichTextField(config_name="pbq")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "pk"]


class PBQAnswerField(models.Model):
    TYPES = [
        ("mcq", "Multiple Choice"),
        ("fill_blank", "Fill in the Blank"),
        ("short_answer", "Short Answer"),
        ("dropdown", "Dropdown"),
    ]
    question = models.ForeignKey(
        PBQQuestion, on_delete=models.CASCADE, related_name="answer_fields"
    )
    label = models.CharField(max_length=500)
    answer_type = models.CharField(max_length=16, choices=TYPES)
    order = models.PositiveIntegerField(default=0)
    points = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    case_sensitive = models.BooleanField(default=False)
    marking_guidance = models.TextField(blank=True)

    class Meta:
        ordering = ["order", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(points__gt=0), name="pbq_field_positive_points"
            )
        ]


class PBQChoice(models.Model):
    answer_field = models.ForeignKey(
        PBQAnswerField, on_delete=models.CASCADE, related_name="choices"
    )
    text = models.CharField(max_length=500)
    order = models.PositiveIntegerField(default=0)
    is_correct = models.BooleanField(default=False)

    class Meta:
        ordering = ["order", "pk"]


class PBQAcceptedAnswer(models.Model):
    answer_field = models.ForeignKey(
        PBQAnswerField, on_delete=models.CASCADE, related_name="accepted_answers"
    )
    text = models.CharField(max_length=1000)


class PBQAttempt(models.Model):
    activity = models.ForeignKey(
        PBQActivity, on_delete=models.CASCADE, related_name="attempts"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="pbq_attempts"
    )
    attempt_number = models.PositiveIntegerField()
    state = models.CharField(
        max_length=16,
        default="draft",
        choices=[
            ("draft", "Draft"),
            ("submitted", "Pending grading"),
            ("graded", "Graded"),
        ],
    )
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    graded_at = models.DateTimeField(null=True, blank=True)
    maximum = models.PositiveIntegerField()
    earned = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    revision = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["activity", "user", "attempt_number"],
                name="pbq_attempt_number_unique",
            )
        ]
        ordering = ["-submitted_at", "-pk"]


class PBQResponse(models.Model):
    attempt = models.ForeignKey(
        PBQAttempt, on_delete=models.CASCADE, related_name="responses"
    )
    answer_field = models.ForeignKey(
        PBQAnswerField, on_delete=models.CASCADE, related_name="responses"
    )
    selected_choice = models.ForeignKey(
        PBQChoice, null=True, blank=True, on_delete=models.SET_NULL
    )
    text = models.TextField(blank=True)
    automatic_score = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    awarded_points = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    feedback = models.TextField(blank=True)
    grader = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    graded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["attempt", "answer_field"], name="pbq_response_unique"
            )
        ]


class PBQGradeEvent(models.Model):
    response = models.ForeignKey(
        PBQResponse, on_delete=models.CASCADE, related_name="grade_events"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)
    previous_score = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    new_score = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    previous_feedback = models.TextField(blank=True)
    new_feedback = models.TextField(blank=True)
    reason = models.TextField(blank=True)


def protect_pbq_definition(sender, instance, origin=None, **kwargs):
    """Cascades must not erase assessment history, except explicit course deletion."""
    from .models import Course
    from django.db import transaction

    if isinstance(origin, Course) or getattr(origin, "model", None) is Course:
        return
    if isinstance(instance, PBQActivity):
        activity_id = instance.pk
    elif isinstance(instance, (PBQArtifact, PBQQuestion)):
        activity_id = instance.activity_id
    elif isinstance(instance, PBQAnswerField):
        activity_id = instance.question.activity_id
    else:
        activity_id = instance.answer_field.question.activity_id
    with transaction.atomic():
        activity = PBQActivity.objects.select_for_update().get(pk=activity_id)
        if activity.attempts.exists():
            raise ValidationError(
                "PBQ attempts exist. Move or duplicate the PBQ instead of deleting its content."
            )


def remove_pbq_artifact(sender, instance, **kwargs):
    from django.db import transaction

    storage, name = instance.file.storage, instance.file.name

    def remove():
        if name and not PBQArtifact.objects.filter(file=name).exists():
            storage.delete(name)

    transaction.on_commit(remove)


from django.db.models.signals import pre_delete, post_delete

for _model in (
    PBQActivity,
    PBQArtifact,
    PBQQuestion,
    PBQAnswerField,
    PBQChoice,
    PBQAcceptedAnswer,
):
    pre_delete.connect(
        protect_pbq_definition,
        sender=_model,
        weak=False,
        dispatch_uid="protect_" + _model.__name__,
    )
post_delete.connect(
    remove_pbq_artifact,
    sender=PBQArtifact,
    weak=False,
    dispatch_uid="pbq_artifact_cleanup",
)
