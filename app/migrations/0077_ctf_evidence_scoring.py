"""CTF Phase 4C: opt-in flagless evidence awards and immutable award origin."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('app', '0076_ctf_soc_ticket_evidence')]

    operations = [
        migrations.AddField(
            model_name='ctfchallenge', name='scoring_method',
            field=models.CharField(
                choices=[('flag', 'Submit a flag'), ('evidence', 'Verify live evidence (no flag)')],
                default='flag', max_length=12,
                help_text='Evidence mode awards points only when the submitting student passes all configured live lab/SOC requirements.',
            ),
        ),
        migrations.AddField(
            model_name='ctfsubmission', name='scoring_source',
            field=models.CharField(
                choices=[('flag', 'Flag submission'), ('evidence', 'Verified evidence')],
                default='flag', max_length=12,
                help_text='Immutable award origin for scoreboard and auditing.',
            ),
        ),
    ]
