from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0038_student_activity_event"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(name="CyberCitySOCTeam", fields=[
            ("id", models.BigAutoField(primary_key=True, serialize=False)),
            ("name", models.CharField(max_length=120)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("city", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="soc_teams", to="app.cybercity")),
            ("members", models.ManyToManyField(blank=True, related_name="cybercity_soc_teams", to=settings.AUTH_USER_MODEL)),
        ]),
        migrations.AddConstraint(model_name="cybercitysocteam", constraint=models.UniqueConstraint(fields=("city", "name"), name="soc_unique_team_name")),
        migrations.CreateModel(name="CyberCitySOCTicket", fields=[
            ("id", models.BigAutoField(primary_key=True, serialize=False)),
            ("kind", models.CharField(max_length=16, choices=[("incident", "Security incident"), ("helpdesk", "Help desk"), ("change", "Change control")])),
            ("title", models.CharField(max_length=200)),
            ("description", models.TextField(blank=True)),
            ("priority", models.CharField(max_length=12, default="medium", choices=[("low", "Low"), ("medium", "Medium"), ("high", "High"), ("critical", "Critical")])),
            ("status", models.CharField(max_length=16, default="new", choices=[("new", "New"), ("triage", "Triage"), ("in_progress", "In progress"), ("pending", "Pending approval"), ("resolved", "Resolved"), ("closed", "Closed")])),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("resolved_at", models.DateTimeField(null=True, blank=True)),
            ("city", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="soc_tickets", to="app.cybercity")),
            ("team", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="tickets", to="app.cybercitysocteam")),
            ("building", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="app.cybercitybuilding")),
            ("machine", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="app.cybercitymachine")),
            ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
            ("assigned_to", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
        ], options={"ordering": ("-created_at", "-pk")}),
        migrations.AddIndex(model_name="cybercitysocticket", index=models.Index(fields=("city", "kind", "status"), name="soc_city_type_status_idx")),
        migrations.CreateModel(name="CyberCitySOCEvent", fields=[
            ("id", models.BigAutoField(primary_key=True, serialize=False)),
            ("action", models.CharField(max_length=80)),
            ("detail", models.CharField(max_length=500, blank=True)),
            ("recorded_at", models.DateTimeField(auto_now_add=True)),
            ("city", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="soc_events", to="app.cybercity")),
            ("team", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="app.cybercitysocteam")),
            ("ticket", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="events", to="app.cybercitysocticket")),
            ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
        ], options={"ordering": ("-recorded_at", "-pk")}),
        migrations.AddIndex(model_name="cybercitysocevent", index=models.Index(fields=("city", "-recorded_at"), name="soc_city_event_time_idx")),
    ]
