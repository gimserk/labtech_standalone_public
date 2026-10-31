from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("app", "0054_cybercity_soc_course_activity"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name="CyberCitySOCSimulation", fields=[
            ("id", models.BigAutoField(primary_key=True, serialize=False)),
            ("event_type", models.CharField(max_length=24, choices=[
                ("service_outage", "Simulated service outage"),
                ("suspicious_login", "Simulated suspicious login"),
                ("network_alert", "Simulated network alert")])),
            ("summary", models.CharField(max_length=240)),
            ("details", models.TextField(max_length=2000, blank=True)),
            ("active", models.BooleanField(default=False)),
            ("started_at", models.DateTimeField(null=True, blank=True)),
            ("ended_at", models.DateTimeField(null=True, blank=True)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("scenario", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="simulations", to="app.cybercitysocscenario")),
            ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
        ], options={"ordering": ("-created_at", "-pk")}),
    ]
