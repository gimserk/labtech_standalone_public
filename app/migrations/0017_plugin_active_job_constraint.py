from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('app', '0016_plugin_registry')]
    operations = [migrations.AddConstraint(
        model_name='plugininstalljob',
        constraint=models.UniqueConstraint(fields=('plugin_id', 'release_id'),
                                           condition=models.Q(status__in=['queued', 'running']),
                                           name='unique_active_plugin_release_job'),
    )]
