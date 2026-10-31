from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("app", "0040_cybercity_soc_alerts")]

    operations = [
        migrations.CreateModel(
            name="CyberCitySOCServiceSample",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("observed_at", models.DateTimeField(db_index=True)),
                ("service_up", models.BooleanField()),
                ("service_state", models.CharField(max_length=32)),
                ("city", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="soc_service_samples", to="app.cybercity")),
                ("monitor", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="soc_service_samples", to="app.machinestatemonitor")),
            ],
            options={"ordering": ("-observed_at", "-id")},
        ),
        migrations.AddIndex(
            model_name="cybercitysocservicesample",
            index=models.Index(fields=("city", "monitor", "-observed_at"), name="soc_service_history_idx"),
        ),
    ]
