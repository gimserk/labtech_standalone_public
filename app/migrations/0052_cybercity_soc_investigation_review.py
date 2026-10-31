from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("app", "0051_cybercity_soc_investigations"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.AddField(model_name="cybercitysocinvestigation", name="score", field=models.PositiveSmallIntegerField(blank=True, null=True)),
        migrations.AddField(model_name="cybercitysocinvestigation", name="instructor_feedback", field=models.TextField(blank=True, max_length=3000)),
        migrations.AddField(model_name="cybercitysocinvestigation", name="reviewed_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="cybercitysocinvestigation", name="reviewed_by", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
    ]
