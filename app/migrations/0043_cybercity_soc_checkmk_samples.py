from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("app", "0042_cybercity_soc_checkmk_hosts")]
    operations = [
        migrations.CreateModel(name="CyberCitySOCCheckmkSample", fields=[
            ("id", models.BigAutoField(primary_key=True, serialize=False)),
            ("service_name", models.CharField(max_length=160)),
            ("state", models.CharField(max_length=8, choices=[("OK", "OK"), ("WARN", "Warning"), ("CRIT", "Critical"), ("UNKNOWN", "Unknown")])),
            ("observed_at", models.DateTimeField(db_index=True)),
            ("mapping", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="samples", to="app.cybercitysoccheckmkhost")),
        ], options={"ordering": ("-observed_at", "-id")}),
        migrations.AddIndex(model_name="cybercitysoccheckmksample",
            index=models.Index(fields=("mapping", "service_name", "-observed_at"), name="soc_checkmk_sample_idx")),
    ]
