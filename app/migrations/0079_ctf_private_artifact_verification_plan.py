"""CTF Phase 5C: secure instructor binary artifact and non-operative verification notes."""
from django.db import migrations, models
import app.ctf_storage

class Migration(migrations.Migration):
    dependencies = [('app', '0078_ctf_template_artifact_solution')]
    operations = [
        migrations.AddField(
            model_name='ctfchallengetemplate', name='binary_artifact',
            field=models.FileField(
                blank=True, null=True, upload_to='ctf_bank_artifacts/',
                storage=app.ctf_storage.CTFPrivateStorage(),
                help_text='Instructor-uploaded private PNG/JPEG/PDF/PCAP evidence; one file per template.',
            ),
        ),
        migrations.AddField(
            model_name='ctfchallengetemplate', name='verification_plan',
            field=models.JSONField(
                blank=True, default=dict,
                help_text='Instructor-only AI suggested validation steps. Never applied to live labs or SOC resources automatically.',
            ),
        ),
    ]
