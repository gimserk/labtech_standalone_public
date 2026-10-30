from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ('app', '0034_lab_build_completion'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='LabNodeMigrationJob',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('instance_id_snapshot', models.PositiveIntegerField(db_index=True)),
                ('source_node', models.CharField(max_length=100)),
                ('target_node', models.CharField(max_length=100)),
                ('machine_ids', models.JSONField(default=list)),
                ('progress', models.JSONField(default=dict)),
                ('status', models.CharField(max_length=24, default='queued', db_index=True)),
                ('stage', models.CharField(max_length=60, default='queued')),
                ('last_error', models.CharField(max_length=120, blank=True)),
                ('task_upid', models.CharField(max_length=255, blank=True)),
                ('task_node', models.CharField(max_length=100, blank=True)),
                ('current_machine_id', models.PositiveIntegerField(null=True, blank=True)),
                ('started_at', models.DateTimeField(null=True, blank=True)),
                ('completed_at', models.DateTimeField(null=True, blank=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('instance', models.ForeignKey(to='app.labinstance', related_name='node_migrations', null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL)),
                ('proxmox_server', models.ForeignKey(to='app.proxmoxserver', on_delete=django.db.models.deletion.PROTECT)),
                ('requested_by', models.ForeignKey(to=settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL)),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.AddConstraint(
            model_name='labnodemigrationjob',
            constraint=models.UniqueConstraint(
                fields=['instance'],
                condition=models.Q(status__in=['queued', 'running', 'needs_attention']),
                name='one_unresolved_lab_node_migration',
            ),
        ),
    ]
