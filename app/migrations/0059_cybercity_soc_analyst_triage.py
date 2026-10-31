from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("app", "0058_cybercity_soc_event_evidence"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [migrations.CreateModel(name="CyberCitySOCTriageDecision", fields=[
        ("id", models.BigAutoField(primary_key=True, serialize=False)),
        ("disposition", models.CharField(max_length=24, choices=[
            ("needs_investigation", "Needs investigation"), ("likely_benign", "Likely benign"),
            ("suspected_incident", "Suspected incident"), ("insufficient_evidence", "Insufficient evidence")])),
        ("rationale", models.TextField(max_length=2000)),
        ("evidence_reference", models.CharField(max_length=500, blank=True)),
        ("created_at", models.DateTimeField(auto_now_add=True)),
        ("analyst", models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.SET_NULL, null=True, related_name="+")),
        ("ticket", models.ForeignKey(to="app.cybercitysocticket", on_delete=django.db.models.deletion.CASCADE, related_name="triage_decisions")),
    ], options={"ordering": ("-created_at", "-pk")})]
