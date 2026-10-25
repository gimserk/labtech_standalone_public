from django.db import migrations, models
import django.db.models.deletion
import uuid

class Migration(migrations.Migration):
    dependencies = [('app', '0029_course_learning_outcomes')]
    operations = [
        migrations.CreateModel(
            name='CyberCityCommand',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('command_id', models.UUIDField(default=uuid.uuid4, unique=True, editable=False)),
                ('payload', models.CharField(max_length=255)),
                ('status', models.CharField(max_length=16, default='pending', db_index=True)),
                ('attempts', models.PositiveSmallIntegerField(default=0)),
                ('last_error', models.TextField(blank=True)),
                ('next_attempt_at', models.DateTimeField(null=True, blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('published_at', models.DateTimeField(null=True, blank=True)),
                ('machine', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='commands', to='app.cybercitymachine')),
                ('pin', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='commands', to='app.cybercityesp32pin')),
            ],
        ),
    ]
