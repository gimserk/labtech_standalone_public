"""CTF Phase 2: opt-in team invitations, live scoreboard controls and audit."""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('app', '0072_ctf_foundation'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='ctf', name='submissions_paused',
            field=models.BooleanField(default=False, help_text='Temporarily stop flag submissions and hint purchases without ending the event.'),
        ),
        migrations.AddField(
            model_name='ctf', name='scoreboard_frozen',
            field=models.BooleanField(default=False, help_text='Show the captured standings until the instructor unfreezes the scoreboard.'),
        ),
        migrations.AddField(
            model_name='ctf', name='scoreboard_snapshot',
            field=models.JSONField(default=list, blank=True, help_text='Standings captured when the public leaderboard was frozen.'),
        ),
        migrations.AddField(
            model_name='ctf', name='scoreboard_recent_snapshot',
            field=models.JSONField(default=list, blank=True, help_text='Recent solves captured when the public leaderboard was frozen.'),
        ),
        migrations.AddField(
            model_name='ctf', name='scoreboard_frozen_at',
            field=models.DateTimeField(null=True, blank=True),
        ),
        migrations.CreateModel(
            name='CTFTeamInvitation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(max_length=12, default='pending', choices=[
                    ('pending', 'Pending'), ('accepted', 'Accepted'), ('declined', 'Declined'), ('canceled', 'Canceled'),
                ])),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField()),
                ('responded_at', models.DateTimeField(null=True, blank=True)),
                ('ctf', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='team_invitations', to='app.ctf')),
                ('team', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='invitations', to='app.ctfteam')),
                ('recipient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ctf_team_invitations', to=settings.AUTH_USER_MODEL)),
                ('invited_by', models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, null=True, related_name='ctf_team_invites_sent', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.AddConstraint(
            model_name='ctfteaminvitation',
            constraint=models.UniqueConstraint(fields=['ctf', 'recipient'],
                condition=models.Q(status='pending'), name='ctf_one_pending_invite_per_event_user'),
        ),
        migrations.CreateModel(
            name='CTFScoreAdjustment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('delta', models.IntegerField()),
                ('reason', models.CharField(max_length=500)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('ctf', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='score_adjustments', to='app.ctf')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, null=True, blank=True, related_name='ctf_score_adjustments', to=settings.AUTH_USER_MODEL)),
                ('team', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, null=True, blank=True, related_name='score_adjustments', to='app.ctfteam')),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, null=True, related_name='ctf_adjustments_created', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.AddConstraint(
            model_name='ctfscoreadjustment',
            constraint=models.CheckConstraint(
                condition=(models.Q(user__isnull=False, team__isnull=True) |
                           models.Q(user__isnull=True, team__isnull=False)),
                name='ctf_adjustment_solo_or_team'),
        ),
        migrations.CreateModel(
            name='CTFControlLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(max_length=80)),
                ('details', models.JSONField(default=dict, blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('ctf', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='control_log', to='app.ctf')),
                ('actor', models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, null=True, to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
