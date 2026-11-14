"""CTF Phase 4A: optional lab-verified flag prerequisite."""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('app', '0074_ctf_challenge_bank')]

    operations = [
        migrations.AddField(
            model_name='ctfchallenge',
            name='verification_step',
            field=models.ForeignKey(
                to='app.step', on_delete=django.db.models.deletion.PROTECT,
                null=True, blank=True, related_name='ctf_verified_challenges',
                help_text='Optional: require successful, current QEMU guest-agent checks for this linked lab step before accepting a flag.',
            ),
        ),
    ]
