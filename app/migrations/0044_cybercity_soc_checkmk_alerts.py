from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("app", "0043_cybercity_soc_checkmk_samples")]
    operations = [
        migrations.CreateModel(name="CyberCitySOCCheckmkAlert", fields=[
            ("id", models.BigAutoField(primary_key=True, serialize=False)),
            ("service_name", models.CharField(max_length=160)),
            ("state", models.CharField(max_length=16, default="open", choices=[("open", "Open"), ("acknowledged", "Acknowledged"), ("resolved", "Resolved")])),
            ("last_checkmk_state", models.CharField(max_length=8)),
            ("first_seen_at", models.DateTimeField(auto_now_add=True)),
            ("last_seen_at", models.DateTimeField(auto_now=True)),
            ("occurrences", models.PositiveIntegerField(default=1)),
            ("mapping", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="alerts", to="app.cybercitysoccheckmkhost")),
        ]),
        migrations.AddConstraint(model_name="cybercitysoccheckmkalert",
            constraint=models.UniqueConstraint(fields=("mapping", "service_name"), name="soc_checkmk_alert_unique")),
    ]
