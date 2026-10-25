from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('app', '0030_cybercity_command_outbox')]
    operations = [
        migrations.AddField(
            model_name='cybercityesp32',
            name='use_versioned_commands',
            field=models.BooleanField(
                default=False,
                help_text='Enable MQTT v1 JSON commands and correlated acknowledgments only after firmware and UTC clock validation.'),
        ),
    ]
