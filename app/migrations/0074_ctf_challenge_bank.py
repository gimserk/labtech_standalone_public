"""CTF Phase 3B persistent instructor challenge bank."""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('app', '0073_ctf_team_invitations_scoreboard_controls'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CTFChallengeCollection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120)),
                ('description', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ctf_bank_collections', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['name', 'pk']},
        ),
        migrations.AddConstraint(
            model_name='ctfchallengecollection',
            constraint=models.UniqueConstraint(fields=('owner', 'name'), name='ctf_bank_unique_owner_collection'),
        ),
        migrations.CreateModel(
            name='CTFChallengeTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('description', models.TextField()),
                ('difficulty', models.CharField(choices=[('beginner', 'Beginner'), ('intermediate', 'Intermediate'), ('advanced', 'Advanced')], default='intermediate', max_length=20)),
                ('points', models.PositiveIntegerField(default=100)),
                ('tags', models.CharField(blank=True, help_text='Comma-separated search tags', max_length=500)),
                ('flag_hash', models.CharField(blank=True, max_length=255)),
                ('hints', models.JSONField(blank=True, default=list)),
                ('external_link', models.URLField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='bank_templates', to='app.ctfcategory')),
                ('collection', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='templates', to='app.ctfchallengecollection')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ctf_bank_templates', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['name', 'pk']},
        ),
    ]
