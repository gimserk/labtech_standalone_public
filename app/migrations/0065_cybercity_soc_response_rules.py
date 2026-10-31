from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("app", "0064_cybercity_soc_rehearsal_outcomes")]
    operations = [migrations.CreateModel(name="CyberCitySOCScenarioResponseRule",fields=[
        ("id",models.BigAutoField(primary_key=True,serialize=False)),
        ("action",models.CharField(max_length=24,choices=[("isolate_host","Isolate affected host"),("disable_account","Disable compromised account"),("restore_service","Restore affected service"),("verify_recovery","Verify recovery")])),
        ("outcome",models.CharField(max_length=24,choices=[("appropriate","Appropriate"),("risky","Risky"),("needs_context","Needs context")])),
        ("feedback",models.TextField(max_length=2000)),
        ("scenario",models.ForeignKey(to="app.cybercitysocscenario",on_delete=django.db.models.deletion.CASCADE,related_name="response_rules")),
    ]),migrations.AddConstraint(model_name="cybercitysocscenarioresponserule",constraint=models.UniqueConstraint(fields=("scenario","action"),name="soc_scenario_response_action_unique"))]
