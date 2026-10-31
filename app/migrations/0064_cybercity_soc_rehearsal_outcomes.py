from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("app", "0063_cybercity_soc_response_rehearsal"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.AddField(model_name="cybercitysocresponserehearsal", name="scenario_outcome",
            field=models.CharField(max_length=24, choices=[("not_evaluated","Not evaluated"),("appropriate","Appropriate"),("risky","Risky"),("needs_context","Needs context")], default="not_evaluated")),
        migrations.AddField(model_name="cybercitysocresponserehearsal", name="scenario_feedback",
            field=models.TextField(max_length=2000, blank=True)),
        migrations.AddField(model_name="cybercitysocresponserehearsal", name="evaluated_at",
            field=models.DateTimeField(null=True, blank=True)),
        migrations.AddField(model_name="cybercitysocresponserehearsal", name="evaluated_by",
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+")),
    ]
