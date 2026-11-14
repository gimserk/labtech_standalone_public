"""CTF Phase 4B: scoped SOC ticket evidence requirements."""
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [('app', '0075_ctf_verified_lab_step')]
    operations = [
        migrations.AddField(
            model_name='ctfchallenge', name='soc_ticket',
            field=models.ForeignKey(
                to='app.cybercitysocticket', on_delete=django.db.models.deletion.PROTECT,
                null=True, blank=True, related_name='ctf_challenges',
                help_text='Optional: a specific real SOC ticket that must be resolved by an authorized SOC team.',
            ),
        ),
        migrations.AddField(
            model_name='ctfchallenge', name='soc_evidence_type',
            field=models.CharField(max_length=12, blank=True,
                choices=[('wazuh', 'Wazuh detection'), ('checkmk', 'Checkmk service alert')],
                help_text='Require real mapped SOC evidence linked to the selected ticket.'),
        ),
    ]
