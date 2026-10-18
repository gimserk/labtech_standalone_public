from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('app', '0014_ai_tutor_provider')]

    operations = [
        migrations.AddField(
            model_name='license', name='plugin_revoked_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
