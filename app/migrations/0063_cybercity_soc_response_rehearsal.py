from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("app", "0062_cybercity_soc_response_runbook"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [migrations.CreateModel(name="CyberCitySOCResponseRehearsal", fields=[
        ("id", models.BigAutoField(primary_key=True, serialize=False)),
        ("action", models.CharField(max_length=24, choices=[("isolate_host","Isolate affected host"),("disable_account","Disable compromised account"),("restore_service","Restore affected service"),("verify_recovery","Verify recovery")])),
        ("expected_result", models.TextField(max_length=2000)),
        ("observed_result", models.CharField(max_length=200, default="Dry run only — no infrastructure commands executed")),
        ("created_at", models.DateTimeField(auto_now_add=True)),
        ("analyst", models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.SET_NULL, null=True, related_name="+")),
        ("ticket", models.ForeignKey(to="app.cybercitysocticket", on_delete=django.db.models.deletion.CASCADE, related_name="response_rehearsals")),
    ], options={"ordering": ("-created_at", "-pk")})]
