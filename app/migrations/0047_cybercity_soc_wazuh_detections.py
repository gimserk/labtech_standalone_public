from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("app", "0046_cybercity_soc_wazuh_agents")]
    operations = [
        migrations.CreateModel(name="CyberCitySOCWazuhDetection", fields=[
            ("id", models.BigAutoField(primary_key=True, serialize=False)),
            ("source_document_id", models.CharField(max_length=255)),
            ("source_index", models.CharField(max_length=160)),
            ("observed_at", models.DateTimeField()),
            ("rule_id", models.CharField(blank=True, max_length=64)),
            ("rule_level", models.PositiveSmallIntegerField(default=0)),
            ("description", models.CharField(blank=True, max_length=350)),
            ("collected_at", models.DateTimeField(auto_now_add=True)),
            ("mapping", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="detections", to="app.cybercitysocwazuhagent")),
        ], options={"ordering": ("-observed_at", "-pk")}),
        migrations.AddConstraint(model_name="cybercitysocwazuhdetection",
            constraint=models.UniqueConstraint(fields=("mapping", "source_index", "source_document_id"), name="soc_wazuh_event_unique")),
        migrations.AddIndex(model_name="cybercitysocwazuhdetection",
            index=models.Index(fields=("mapping", "-observed_at"), name="soc_wazuh_recent_idx")),
    ]
