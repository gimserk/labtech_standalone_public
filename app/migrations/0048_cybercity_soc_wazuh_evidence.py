from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("app", "0047_cybercity_soc_wazuh_detections")]
    operations = [
        migrations.CreateModel(name="CyberCitySOCWazuhEvidence", fields=[
            ("id", models.BigAutoField(primary_key=True, serialize=False)),
            ("attached_at", models.DateTimeField(auto_now_add=True)),
            ("detection", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="soc_evidence", to="app.cybercitysocwazuhdetection")),
            ("ticket", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="wazuh_evidence", to="app.cybercitysocticket")),
        ]),
    ]
