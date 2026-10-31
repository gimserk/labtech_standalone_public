from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("app", "0052_cybercity_soc_investigation_review")]
    operations = [
        migrations.AddField(model_name="cybercitysocinvestigation", name=field,
            field=models.PositiveSmallIntegerField(blank=True, null=True))
        for field in ("findings_score", "evidence_score", "response_score", "documentation_score")
    ]
