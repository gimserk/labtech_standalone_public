"""Instructor quiz presentation controls and resumable student draft storage."""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0070_ai_course_reference_textbook"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="quiz",
            name="display_mode",
            field=models.CharField(
                max_length=8, default="all",
                choices=[("all", "All questions on one page"), ("one", "One question at a time")],
                help_text="Choose whether students see every question or progress one question at a time.",
            ),
        ),
        migrations.AddField(
            model_name="quiz",
            name="allow_backtracking",
            field=models.BooleanField(
                default=True,
                help_text="In one-question mode, allow students to revisit previously seen questions. Disable this for forward-only exams.",
            ),
        ),
        migrations.CreateModel(
            name="QuizDraft",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("answers", models.JSONField(blank=True, default=dict)),
                ("question_order", models.JSONField(blank=True, default=list)),
                ("choice_order", models.JSONField(blank=True, default=dict)),
                ("question_fingerprints", models.JSONField(blank=True, default=dict)),
                ("current_index", models.PositiveIntegerField(default=0)),
                ("max_reached", models.PositiveIntegerField(default=0)),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("quiz", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="drafts", to="app.quiz")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="quiz_drafts", to=settings.AUTH_USER_MODEL)),
            ],
            options={"constraints": [
                models.UniqueConstraint(fields=("quiz", "user"), name="quiz_one_open_draft_per_student"),
            ]},
        ),
    ]
