# Add Cyber City Control utility VM state without changing existing VM roles.
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0019_pbq_activities'),
    ]

    operations = [
        migrations.AddField(
            model_name='cybercity',
            name='control_vm_template',
            field=models.ForeignKey(
                to='app.proxmoxvmtemplate', on_delete=django.db.models.deletion.SET_NULL,
                null=True, blank=True, related_name='+',
                help_text="Proxmox template for the city's Control/MQTT VM.",
            ),
        ),
        migrations.AddField(
            model_name='cybercity',
            name='control_vmid',
            field=models.PositiveIntegerField(null=True, blank=True, unique=True),
        ),
        migrations.AddField(
            model_name='cybercity',
            name='control_vnc_port',
            field=models.PositiveIntegerField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='cybercity',
            name='control_status',
            field=models.CharField(max_length=20, default='stopped', editable=False),
        ),
    ]
