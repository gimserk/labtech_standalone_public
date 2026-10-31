from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("app", "0048_cybercity_soc_wazuh_evidence"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [migrations.CreateModel(name="CyberCitySOCScenario", fields=[
        ("id", models.BigAutoField(primary_key=True, serialize=False)),
        ("title", models.CharField(max_length=180)),
        ("brief", models.TextField(max_length=4000)),
        ("status", models.CharField(max_length=16, default="draft", choices=[("draft", "Draft"), ("published", "Published"), ("closed", "Closed")])),
        ("created_at", models.DateTimeField(auto_now_add=True)),
        ("city", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="soc_scenarios", to="app.cybercity")),
        ("team", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="scenarios", to="app.cybercitysocteam")),
        ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
    ], options={"ordering": ("-created_at", "-pk")})]
