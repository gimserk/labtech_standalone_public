from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('app', '0036_cybercity_service_recovery')]
    operations = [
        migrations.AddField(model_name='cybercitymachine', name='monitor_enabled',
            field=models.BooleanField(default=False, help_text='Automatically poll active QEMU Guest Agent monitors for this building VM.')),
        migrations.AddField(model_name='cybercitymachine', name='monitor_os_family',
            field=models.CharField(max_length=8, choices=[('linux', 'Linux'), ('windows', 'Windows')], default='linux')),
        migrations.AddField(model_name='cybercitymachine', name='monitor_poll_claimed_at',
            field=models.DateTimeField(null=True, blank=True, editable=False)),
        migrations.AddField(model_name='cybercitymachine', name='monitor_last_polled_at',
            field=models.DateTimeField(null=True, blank=True, editable=False)),
        migrations.AddField(model_name='cybercitymachine', name='monitor_last_error',
            field=models.CharField(max_length=160, blank=True, editable=False)),
        migrations.AddField(model_name='machinestatemonitor', name='last_check_error',
            field=models.CharField(max_length=160, blank=True, editable=False)),
        migrations.AlterField(
            model_name='machinestatemonitor', name='monitor_type',
            field=models.CharField(max_length=20, choices=[
                ('service', 'Service Status (e.g., sshd, apache2)'),
                ('file_hash', 'File Content Hash (SHA-256)'),
                ('file_exists', 'File Exists / Missing (QEMU Guest Agent)'),
                ('file_content', 'File Content (first 255 characters)'),
                ('db_query', 'Database Query Result'),
            ]),
        ),
    ]
