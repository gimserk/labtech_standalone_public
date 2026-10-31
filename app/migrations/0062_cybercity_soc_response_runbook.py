from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("app", "0061_cybercity_soc_response_review"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [migrations.CreateModel(name="CyberCitySOCResponseRunbookStep", fields=[
        ("id", models.BigAutoField(primary_key=True, serialize=False)),
        ("phase", models.CharField(max_length=16, choices=[("containment","Containment"),("eradication","Eradication"),("recovery","Recovery"),("verification","Verification")])),
        ("notes", models.TextField(max_length=2000)),
        ("completed_at", models.DateTimeField(auto_now_add=True)),
        ("analyst", models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.CASCADE, related_name="+")),
        ("ticket", models.ForeignKey(to="app.cybercitysocticket", on_delete=django.db.models.deletion.CASCADE, related_name="runbook_steps")),
    ], options={"ordering": ("completed_at", "pk")}), migrations.AddConstraint(
        model_name="cybercitysocresponserunbookstep",
        constraint=models.UniqueConstraint(fields=("ticket", "analyst", "phase"), name="soc_runbook_unique_analyst_phase"),
    )]
