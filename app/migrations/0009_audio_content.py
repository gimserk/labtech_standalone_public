import app.models
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('app', '0008_filesubmissionactivity_filesubmission')]

    operations = [
        migrations.CreateModel(
            name='Audio',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('available_from', models.DateTimeField(blank=True, help_text='When this item becomes available to students.', null=True)),
                ('due_date', models.DateTimeField(blank=True, help_text='Optional due date for this item.', null=True)),
                ('available_until', models.DateTimeField(blank=True, help_text='When this item is no longer available to students.', null=True)),
                ('title', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('source_type', models.CharField(choices=[('upload', 'Upload'), ('external_url', 'External HTTPS URL')], max_length=20)),
                ('audio_file', models.FileField(blank=True, upload_to=app.models.audio_upload_path)),
                ('audio_url', models.URLField(blank=True, max_length=1000)),
                ('original_filename', models.CharField(blank=True, max_length=255)),
                ('content_type', models.CharField(blank=True, max_length=100)),
                ('file_size', models.PositiveBigIntegerField(blank=True, null=True)),
                ('order', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('chapter', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='audio_items', to='app.chapter')),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='audio_items', to='app.course')),
            ],
            options={
                'ordering': ['course', 'chapter__order', 'order'],
                'constraints': [models.CheckConstraint(condition=(models.Q(source_type='upload', audio_file__gt='', audio_url='') | models.Q(source_type='external_url', audio_file='', audio_url__gt='')), name='audio_exactly_one_source')],
            },
        ),
    ]
