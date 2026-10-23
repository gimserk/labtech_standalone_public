from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('app', '0021_cybercity_esp32_provisioning_key')]

    operations = [
        migrations.AddField(
            model_name='cybercity',
            name='mqtt_use_tls',
            field=models.BooleanField(default=False, help_text='Use verified TLS for the city MQTT broker.'),
        ),
        migrations.AddField(
            model_name='cybercity',
            name='mqtt_ca_certificate_path',
            field=models.CharField(max_length=500, blank=True, help_text='Server-local trusted CA bundle path when MQTT TLS is enabled.'),
        ),
    ]
