from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('app', '0020_cybercity_control_vm')]

    operations = [
        migrations.AddField(
            model_name='cybercityesp32',
            name='provisioning_key_hash',
            field=models.CharField(
                max_length=128, blank=True, default='', editable=False,
                help_text="Hashed enrollment credential for the device provisioning API.",
            ),
        ),
    ]
