from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("app", "0057_cybercity_soc_simulation_history")]
    operations = [migrations.CreateModel(name="CyberCitySOCInvestigationEvidence", fields=[
        ("id", models.BigAutoField(primary_key=True, serialize=False)),
        ("added_at", models.DateTimeField(auto_now_add=True)),
        ("investigation", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="event_evidence", to="app.cybercitysocinvestigation")),
        ("simulation", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="student_evidence", to="app.cybercitysocsimulation")),
    ]), migrations.AddConstraint(
        model_name="cybercitysocinvestigationevidence",
        constraint=models.UniqueConstraint(fields=("investigation", "simulation"), name="soc_investigation_event_evidence_unique"),
    )]
