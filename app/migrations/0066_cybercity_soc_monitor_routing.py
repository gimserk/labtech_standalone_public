from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("app", "0065_cybercity_soc_response_rules")]
    operations = [migrations.CreateModel(name="CyberCitySOCMonitorRoute",fields=[
        ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
        ("monitor",models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,related_name="soc_route",to="app.machinestatemonitor")),
        ("team",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="monitor_routes",to="app.cybercitysocteam")),
    ],options={"verbose_name":"Cyber City SOC monitor route"})]
