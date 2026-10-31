from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0037_cybercity_monitors"),
    ]

    operations = [
        migrations.CreateModel(
            name="StudentActivityEvent",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("occurred_at", models.DateTimeField()),
                ("category", models.CharField(max_length=48)),
                ("action", models.CharField(max_length=80)),
                ("title_snapshot", models.CharField(max_length=255, blank=True)),
                ("outcome", models.CharField(max_length=80, blank=True)),
                ("source_model", models.CharField(max_length=100)),
                ("source_id", models.PositiveBigIntegerField()),
                ("recorded_at", models.DateTimeField(auto_now_add=True)),
                ("course_id", models.PositiveBigIntegerField(db_index=True)),
                ("student_id", models.PositiveBigIntegerField(db_index=True)),
            ],
            options={"ordering": ("-occurred_at", "-id")},
        ),
        migrations.AddConstraint(model_name="studentactivityevent", constraint=models.UniqueConstraint(fields=("source_model", "source_id", "action"), name="activity_event_source_action_once")),
        migrations.AddIndex(model_name="studentactivityevent", index=models.Index(fields=("course_id", "student_id", "-occurred_at"), name="act_event_course_student_idx")),
    ]
