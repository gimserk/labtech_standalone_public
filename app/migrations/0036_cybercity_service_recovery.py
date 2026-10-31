from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('app', '0035_lab_node_migration')]
    operations = [
        migrations.AddField(model_name='cybercity', name='pfsense_node', field=models.CharField(max_length=100, blank=True, help_text='Actual Proxmox node of the City Service clone, not the template node.')),
        migrations.AddField(model_name='cybercity', name='pfsense_error', field=models.CharField(max_length=160, blank=True, editable=False)),
        migrations.AddField(model_name='cybercity', name='pfsense_provision_started_at', field=models.DateTimeField(null=True, blank=True, editable=False)),
        migrations.AddField(model_name='cybercity', name='control_node', field=models.CharField(max_length=100, blank=True, help_text='Actual Proxmox node of the City Service clone, not the template node.')),
        migrations.AddField(model_name='cybercity', name='control_error', field=models.CharField(max_length=160, blank=True, editable=False)),
        migrations.AddField(model_name='cybercity', name='control_provision_started_at', field=models.DateTimeField(null=True, blank=True, editable=False)),
        migrations.AddField(model_name='cybercity', name='management_node', field=models.CharField(max_length=100, blank=True, help_text='Actual Proxmox node of the City Service clone, not the template node.')),
        migrations.AddField(model_name='cybercity', name='management_error', field=models.CharField(max_length=160, blank=True, editable=False)),
        migrations.AddField(model_name='cybercity', name='management_provision_started_at', field=models.DateTimeField(null=True, blank=True, editable=False)),
    ]
