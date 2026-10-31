from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("app", "0050_cybercity_soc_scenario_incidents"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [migrations.CreateModel(name="CyberCitySOCInvestigation", fields=[
        ("id", models.BigAutoField(primary_key=True, serialize=False)),
        ("findings", models.TextField(max_length=4000)),
        ("evidence", models.TextField(max_length=4000)),
        ("response_actions", models.TextField(max_length=4000)),
        ("status", models.CharField(max_length=16, choices=[("draft", "Draft"), ("submitted", "Submitted")], default="draft")),
        ("submitted_at", models.DateTimeField(null=True, blank=True)),
        ("updated_at", models.DateTimeField(auto_now=True)),
        ("scenario", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="investigations", to="app.cybercitysocscenario")),
        ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="soc_investigations", to=settings.AUTH_USER_MODEL)),
    ]), migrations.AddConstraint(model_name="cybercitysocinvestigation",
        constraint=models.UniqueConstraint(fields=("scenario", "student"), name="soc_scenario_student_unique"))]
