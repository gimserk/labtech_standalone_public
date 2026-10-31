from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("app", "0066_cybercity_soc_monitor_routing")]
    operations = [
        migrations.AddField(model_name="cybercity", name="wazuh_template", field=models.ForeignKey(to="app.proxmoxvmtemplate", on_delete=django.db.models.deletion.SET_NULL, null=True, blank=True, related_name="+")),
        migrations.AddField(model_name="cybercity", name="wazuh_vmid", field=models.PositiveIntegerField(null=True, blank=True, unique=True)),
        migrations.AddField(model_name="cybercity", name="wazuh_vnc_port", field=models.PositiveIntegerField(null=True, blank=True)),
        migrations.AddField(model_name="cybercity", name="wazuh_status", field=models.CharField(max_length=20, default='stopped', editable=False)),
        migrations.AddField(model_name="cybercity", name="wazuh_node", field=models.CharField(max_length=100, blank=True)),
        migrations.AddField(model_name="cybercity", name="wazuh_error", field=models.CharField(max_length=160, blank=True, editable=False)),
        migrations.AddField(model_name="cybercity", name="wazuh_provision_started_at", field=models.DateTimeField(null=True, blank=True, editable=False)),
        migrations.AddField(model_name="cybercity", name="wazuh_web_url", field=models.URLField(max_length=500, blank=True, help_text="Trusted HTTPS URL of the Wazuh web dashboard (students use their own accounts).")),
        migrations.AddField(model_name="cybercity", name="checkmk_template", field=models.ForeignKey(to="app.proxmoxvmtemplate", on_delete=django.db.models.deletion.SET_NULL, null=True, blank=True, related_name="+")),
        migrations.AddField(model_name="cybercity", name="checkmk_vmid", field=models.PositiveIntegerField(null=True, blank=True, unique=True)),
        migrations.AddField(model_name="cybercity", name="checkmk_vnc_port", field=models.PositiveIntegerField(null=True, blank=True)),
        migrations.AddField(model_name="cybercity", name="checkmk_status", field=models.CharField(max_length=20, default='stopped', editable=False)),
        migrations.AddField(model_name="cybercity", name="checkmk_node", field=models.CharField(max_length=100, blank=True)),
        migrations.AddField(model_name="cybercity", name="checkmk_error", field=models.CharField(max_length=160, blank=True, editable=False)),
        migrations.AddField(model_name="cybercity", name="checkmk_provision_started_at", field=models.DateTimeField(null=True, blank=True, editable=False)),
        migrations.AddField(model_name="cybercity", name="checkmk_web_url", field=models.URLField(max_length=500, blank=True, help_text="Trusted HTTPS URL of the Checkmk web UI (students use their own accounts).")),
    ]
