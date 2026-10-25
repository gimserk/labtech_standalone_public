from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('app', '0031_cybercity_versioned_commands')]
    operations = [
        migrations.AddField(
            model_name='cybercitymachine', name='reset_started_at',
            field=models.DateTimeField(null=True, blank=True, editable=False)),
        migrations.AddField(
            model_name='cybercitymachine', name='reset_error',
            field=models.TextField(blank=True, default='', editable=False)),
    ]
