from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("app", "0045_cybercity_soc_checkmk_triage")]
    operations = [
        migrations.CreateModel(name="CyberCitySOCWazuhAgent", fields=[
            ("id", models.BigAutoField(primary_key=True, serialize=False)),
            ("agent_id", models.CharField(max_length=40)),
            ("agent_name", models.CharField(blank=True, max_length=120)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("city", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="soc_wazuh_agents", to="app.cybercity")),
            ("machine", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="soc_wazuh_agent", to="app.cybercitymachine")),
        ]),
        migrations.AddConstraint(model_name="cybercitysocwazuhagent",
            constraint=models.UniqueConstraint(fields=("city", "agent_id"), name="soc_wazuh_city_agent_unique")),
    ]
