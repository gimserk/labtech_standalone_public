"""CTF scoring consistency, hashed flags, and immutable duplicate submission audit."""
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db import migrations, models
import django.db.models.deletion
from pathlib import Path
from django.core.files import File
import app.ctf_storage


def harden_ctf_history(apps, schema_editor):
    Challenge = apps.get_model('app', 'CTFChallenge')
    Submission = apps.get_model('app', 'CTFSubmission')
    Duplicate = apps.get_model('app', 'CTFSubmissionDuplicate')
    # Preserve the first legitimate credited solve for every solo participant or
    # team. Historical duplicate solves are archived with their original IDs and
    # points rather than silently deleted.
    seen = set()
    for solve in Submission.objects.order_by('submitted_at', 'pk').iterator():
        identity = (
            solve.challenge_id,
            ('team', solve.team_id) if solve.team_id else ('solo', solve.user_id),
        )
        if identity in seen:
            Duplicate.objects.create(
                original_submission_id=solve.pk, challenge_id_snapshot=solve.challenge_id,
                user_id_snapshot=solve.user_id, team_id_snapshot=solve.team_id,
                points_awarded=solve.points_awarded, submitted_at=solve.submitted_at,
            )
            Submission.objects.filter(pk=solve.pk).delete()
        else:
            seen.add(identity)

    for challenge in Challenge.objects.all().iterator():
        if challenge.flag:
            challenge.flag_hash = make_password(challenge.flag)
            challenge.flag = ''
            challenge.save(update_fields=['flag', 'flag_hash'])


def privatize_ctf_evidence(apps, schema_editor):
    from django.conf import settings
    Challenge = apps.get_model('app', 'CTFChallenge')
    storage = app.ctf_storage.CTFPrivateStorage()
    old_root = Path(settings.MEDIA_ROOT).resolve()
    verified_sources = []
    # First pass: copy and verify EVERY available legacy file before deleting
    # ANY public file. A failed migration cannot strand a partial subset.
    for challenge in Challenge.objects.exclude(attached_file='').exclude(attached_file__isnull=True).iterator():
        name = str(challenge.attached_file)
        source = (old_root / name).resolve()
        if source != old_root and old_root not in source.parents:
            continue
        if not source.is_file():
            # Missing legacy files are reported by the readiness checker.
            continue
        if not storage.exists(name):
            with source.open('rb') as source_file:
                written = storage.save(name, File(source_file))
            if written != name:
                raise RuntimeError('CTF evidence destination name changed: ' + name)
        if storage.size(name) != source.stat().st_size:
            raise RuntimeError('Unable to verify migrated CTF evidence: ' + name)
        verified_sources.append(source)
    # Second pass: only after verification, remove the old publicly served
    # copies. A deletion failure leaves a public duplicate for the operator to
    # remove rather than invalidating the verified private copy.
    for source in verified_sources:
        try:
            source.unlink()
        except OSError:
            pass


def reverse_noop(apps, schema_editor):
    # Raw flags cannot and must not be reconstructed from one-way hashes.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('app', '0071_quiz_draft_and_navigation_options'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='ctfchallenge',
            name='difficulty',
            field=models.CharField(max_length=20, default='intermediate',
                choices=[('beginner', 'Beginner'), ('intermediate', 'Intermediate'), ('advanced', 'Advanced')]),
        ),
        migrations.AddField(
            model_name='ctfchallenge',
            name='flag_hash',
            field=models.CharField(max_length=255, blank=True, default='', help_text='One-way salted hash of the challenge flag.'),
        ),
        migrations.AlterField(
            model_name='ctfchallenge',
            name='flag',
            field=models.CharField(max_length=255, blank=True, default='',
                help_text='Legacy flag field; flags are now stored as one-way password hashes.'),
        ),
        migrations.CreateModel(
            name='CTFSubmissionDuplicate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('challenge_id_snapshot', models.PositiveIntegerField()),
                ('user_id_snapshot', models.PositiveIntegerField()),
                ('team_id_snapshot', models.PositiveIntegerField(blank=True, null=True)),
                ('points_awarded', models.IntegerField(default=0)),
                ('submitted_at', models.DateTimeField()),
                ('original_submission_id', models.PositiveIntegerField(unique=True)),
            ],
            options={'ordering': ['original_submission_id']},
        ),
        migrations.CreateModel(
            name='CTFInvalidFlagAttempt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('attempted_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('challenge', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                    related_name='invalid_attempts', to='app.ctfchallenge')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                    related_name='ctf_invalid_attempts', to=settings.AUTH_USER_MODEL)),
            ],
            options={'indexes': [
                models.Index(fields=['user', 'challenge', 'attempted_at'], name='ctf_wrong_flag_window'),
            ]},
        ),
        migrations.AlterField(
            model_name='ctfchallenge',
            name='attached_file',
            field=models.FileField(
                blank=True, null=True,
                storage=app.ctf_storage.CTFPrivateStorage(),
                upload_to='ctf_files/',
                help_text='Private evidence delivered only to eligible participants (e.g. PCAP or forensic image).',
            ),
        ),
        migrations.AlterUniqueTogether(
            name='ctfsubmission',
            unique_together=set(),
        ),
        migrations.RunPython(harden_ctf_history, reverse_code=reverse_noop),
        migrations.AddConstraint(
            model_name='ctfsubmission',
            constraint=models.UniqueConstraint(
                fields=['challenge', 'team'], condition=models.Q(team__isnull=False),
                name='ctf_unique_team_solve',
            ),
        ),
        migrations.AddConstraint(
            model_name='ctfsubmission',
            constraint=models.UniqueConstraint(
                fields=['challenge', 'user'], condition=models.Q(team__isnull=True),
                name='ctf_unique_solo_solve',
            ),
        ),
        migrations.RunPython(privatize_ctf_evidence, reverse_code=reverse_noop),
    ]
