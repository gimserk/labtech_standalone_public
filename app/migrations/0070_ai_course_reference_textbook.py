from django.db import migrations, models
import app.ai_course_book


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0069_file_submission_multiple_attachments"),
    ]
    operations = [
        migrations.AddField(
            model_name="aigeneratedcourse",
            name="source_book",
            field=models.FileField(
                blank=True, storage=app.ai_course_book.AITextbookStorage(),
                upload_to=app.ai_course_book.textbook_upload_path,
                help_text="Private reference book used to create this course.",
            ),
        ),
        migrations.AddField(
            model_name="aigeneratedcourse",
            name="source_book_name",
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
