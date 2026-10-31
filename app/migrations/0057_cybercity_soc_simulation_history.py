from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("app", "0056_cybercity_soc_simulation_timeline"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [migrations.CreateModel(name="CyberCitySOCSimulationTransition", fields=[
        ("id", models.BigAutoField(primary_key=True, serialize=False)),
        ("action", models.CharField(max_length=12, choices=[("activated", "Activated"), ("ended", "Ended")])),
        ("occurred_at", models.DateTimeField(auto_now_add=True)),
        ("simulation", models.ForeignKey(to="app.cybercitysocsimulation", related_name="transitions", on_delete=django.db.models.deletion.CASCADE)),
        ("actor", models.ForeignKey(to=settings.AUTH_USER_MODEL, related_name="+", null=True, on_delete=django.db.models.deletion.SET_NULL)),
    ], options={"ordering": ("occurred_at", "pk")})]
