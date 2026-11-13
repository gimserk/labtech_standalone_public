"""Keep all existing single-file submissions when enabling multi-file assignments."""
import os

import app.models
import app.validators
from django.db import migrations, models
import django.db.models.deletion


def migrate_legacy_files(apps, schema_editor):
    Submission = apps.get_model("app", "FileSubmission")
    Attachment = apps.get_model("app", "FileSubmissionAttachment")
    for submission in Submission.objects.exclude(file="").exclude(file__isnull=True).iterator():
        stored_path = str(submission.file)
        if not stored_path:
            continue
        Attachment.objects.create(
            submission_id=submission.pk,
            file=stored_path,
            original_filename=os.path.basename(stored_path)[:255] or "Previous upload",
            size_bytes=0,  # Original FileField did not record the byte length.
        )


class Migration(migrations.Migration):
    dependencies = [("app", "0068_cybercity_ws2811")]

    operations = [
        migrations.AlterField(
            model_name="filesubmission",
            name="file",
            field=models.FileField(
                upload_to=app.models.student_submission_upload_path,
                validators=[app.validators.validate_safe_file],
                blank=True,
            ),
        ),
        migrations.CreateModel(
            name="FileSubmissionAttachment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("file", models.FileField(
                    upload_to=app.models.student_submission_attachment_path,
                    validators=[app.validators.validate_safe_file],
                )),
                ("original_filename", models.CharField(max_length=255)),
                ("size_bytes", models.PositiveBigIntegerField(default=0)),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                ("submission", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="attachments", to="app.filesubmission",
                )),
            ],
            options={"ordering": ("uploaded_at", "pk")},
        ),
        migrations.RunPython(migrate_legacy_files, migrations.RunPython.noop),
    ]
