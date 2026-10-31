from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("app", "0041_cybercity_soc_service_history")]
    operations = [
        migrations.CreateModel(name="CyberCitySOCCheckmkHost", fields=[
            ("id", models.BigAutoField(primary_key=True, serialize=False)),
            ("hostname", models.CharField(max_length=200)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("city", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="soc_checkmk_hosts", to="app.cybercity")),
            ("machine", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="soc_checkmk_host", to="app.cybercitymachine")),
        ]),
        migrations.AddConstraint(model_name="cybercitysoccheckmkhost",
            constraint=models.UniqueConstraint(fields=("city", "hostname"), name="soc_checkmk_city_host_unique")),
    ]
