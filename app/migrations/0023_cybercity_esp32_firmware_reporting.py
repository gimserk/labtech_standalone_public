from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('app', '0022_cybercity_mqtt_tls')]

    operations = [
        migrations.AddField(model_name='cybercityesp32', name='firmware_last_seen',
                            field=models.DateTimeField(null=True, blank=True, editable=False)),
        migrations.AddField(model_name='cybercityesp32', name='firmware_reported_version',
                            field=models.PositiveIntegerField(null=True, blank=True, editable=False)),
        migrations.AddField(model_name='cybercityesp32', name='firmware_reported_status',
                            field=models.CharField(max_length=24, blank=True, default='', editable=False)),
    ]
