from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("app", "0059_cybercity_soc_analyst_triage"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [migrations.CreateModel(name="CyberCitySOCResponsePlan", fields=[
        ("id", models.BigAutoField(primary_key=True, serialize=False)),
        ("containment", models.TextField(max_length=2000)),
        ("eradication", models.TextField(max_length=2000)),
        ("recovery", models.TextField(max_length=2000)),
        ("validation", models.TextField(max_length=2000)),
        ("status", models.CharField(max_length=16, choices=[("draft", "Draft"), ("submitted", "Submitted")], default="draft")),
        ("submitted_at", models.DateTimeField(null=True, blank=True)),
        ("created_at", models.DateTimeField(auto_now_add=True)),
        ("analyst", models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.SET_NULL, null=True, related_name="+")),
        ("ticket", models.ForeignKey(to="app.cybercitysocticket", on_delete=django.db.models.deletion.CASCADE, related_name="response_plans")),
    ], options={"ordering": ("-created_at", "-pk")})]
