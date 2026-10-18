from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('app', '0017_plugin_active_job_constraint')]
    operations = [
        migrations.AddField('plugininstalljob', 'action', models.CharField(max_length=12, default='install', choices=[('install', 'Install'), ('enable', 'Enable')])),
        migrations.AddField('plugininstalljob', 'started_at', models.DateTimeField(null=True, blank=True)),
        migrations.AddField('plugininstalljob', 'previous_target', models.CharField(max_length=80, blank=True)),
        migrations.AddField('plugininstalljob', 'candidate_target', models.CharField(max_length=80, blank=True)),
    ]
