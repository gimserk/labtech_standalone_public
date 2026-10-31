from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0039_cybercity_soc_foundation"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CyberCitySOCAlert",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("state", models.CharField(max_length=16, default="open", choices=[("open", "Open"), ("acknowledged", "Acknowledged"), ("resolved", "Resolved")])),
                ("summary", models.CharField(max_length=255)),
                ("first_seen_at", models.DateTimeField(auto_now_add=True)),
                ("last_seen_at", models.DateTimeField(auto_now=True)),
                ("occurrences", models.PositiveIntegerField(default=1)),
                ("city", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="soc_alerts", to="app.cybercity")),
                ("monitor", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="soc_alert", to="app.machinestatemonitor")),
                ("acknowledged_by", models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("linked_ticket", models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL, related_name="monitoring_alerts", to="app.cybercitysocticket")),
            ],
        ),
        migrations.AddIndex(model_name="cybercitysocalert", index=models.Index(fields=("city", "state"), name="soc_alert_city_state_idx")),
    ]
