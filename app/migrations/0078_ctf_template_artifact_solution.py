"""CTF Phase 5: instructor-only solution and textual evidence in reusable templates."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('app', '0077_ctf_evidence_scoring')]

    operations = [
        migrations.AddField(
            model_name='ctfchallengetemplate', name='artifact_text',
            field=models.TextField(blank=True, help_text='Optional instructor-reviewed plain-text evidence to attach as a private .txt file on deployment.'),
        ),
        migrations.AddField(
            model_name='ctfchallengetemplate', name='instructor_solution',
            field=models.TextField(blank=True, help_text='Instructor-only answer rationale; never copied into student challenges or portable exports.'),
        ),
    ]
