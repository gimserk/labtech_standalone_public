from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("app", "0060_cybercity_soc_response_plans"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.AddField(model_name="cybercitysocresponseplan", name="review_status",
            field=models.CharField(max_length=16, choices=[("pending","Pending"),("approved","Approved"),("changes","Changes requested")], default="pending")),
        migrations.AddField(model_name="cybercitysocresponseplan", name="instructor_feedback",
            field=models.TextField(max_length=2000, blank=True)),
        migrations.AddField(model_name="cybercitysocresponseplan", name="reviewed_at",
            field=models.DateTimeField(null=True, blank=True)),
        migrations.AddField(model_name="cybercitysocresponseplan", name="reviewed_by",
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL, null=True, blank=True,
                on_delete=django.db.models.deletion.SET_NULL, related_name="+")),
    ]
