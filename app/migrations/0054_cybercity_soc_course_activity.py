from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("app", "0053_cybercity_soc_rubric_scores")]
    operations = [
        migrations.AddField(model_name="cybercitysocscenario", name="course_activity",
            field=models.ForeignKey(to="app.filesubmissionactivity", null=True, blank=True,
                on_delete=django.db.models.deletion.SET_NULL, related_name="soc_scenarios")),
    ]
