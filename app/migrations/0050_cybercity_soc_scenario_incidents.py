from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("app", "0049_cybercity_soc_scenarios")]
    operations = [
        migrations.AddField(
            model_name="cybercitysocscenario", name="incident",
            field=models.ForeignKey(
                to="app.cybercitysocticket", null=True, blank=True,
                related_name="soc_scenarios", on_delete=django.db.models.deletion.SET_NULL,
            ),
        ),
    ]
