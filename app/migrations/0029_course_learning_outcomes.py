from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('app', '0028_merge_20261023_1546'), ('contenttypes', '0002_remove_content_type_name')]

    operations = [
        migrations.CreateModel(name='CourseLearningOutcome', fields=[
            ('id', models.BigAutoField(primary_key=True, serialize=False)),
            ('code', models.CharField(blank=True, max_length=40)),
            ('statement', models.TextField()),
            ('order', models.PositiveIntegerField(default=0)),
            ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='learning_outcomes', to='app.course')),
        ], options={'ordering': ('order', 'pk')}),
        migrations.CreateModel(name='LearningOutcomeActivity', fields=[
            ('id', models.BigAutoField(primary_key=True, serialize=False)),
            ('object_id', models.PositiveIntegerField()),
            ('content_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype')),
            ('outcome', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='activities', to='app.courselearningoutcome')),
        ], options={'constraints': [models.UniqueConstraint(fields=('outcome', 'content_type', 'object_id'), name='outcome_activity_unique')]}),
    ]
