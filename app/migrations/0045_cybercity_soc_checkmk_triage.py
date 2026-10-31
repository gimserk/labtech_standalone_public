from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("app", "0044_cybercity_soc_checkmk_alerts"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [migrations.CreateModel(name="CyberCitySOCCheckmkTriage", fields=[
        ("id", models.BigAutoField(primary_key=True, serialize=False)),
        ("acknowledged_at", models.DateTimeField(blank=True, null=True)),
        ("alert", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="triage", to="app.cybercitysoccheckmkalert")),
        ("linked_ticket", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="checkmk_alerts", to="app.cybercitysocticket")),
        ("acknowledged_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
    ])]
