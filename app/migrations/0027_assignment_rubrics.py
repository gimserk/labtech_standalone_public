from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('app', '0026_tekcon_nfc_target_course'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.CreateModel(name='AssignmentRubric', fields=[
            ('id', models.BigAutoField(primary_key=True, serialize=False)),
            ('title', models.CharField(max_length=255)),
            ('description', models.TextField(blank=True)),
            ('object_id', models.PositiveIntegerField()),
            ('published', models.BooleanField(default=False, help_text='Display rubric to students.')),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('content_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype')),
            ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assignment_rubrics', to='app.course')),
        ], options={'constraints': [
            models.UniqueConstraint(fields=('content_type', 'object_id'), name='assignment_rubric_one_per_activity')]}),
        migrations.CreateModel(name='RubricCriterion', fields=[
            ('id', models.BigAutoField(primary_key=True, serialize=False)),
            ('title', models.CharField(max_length=255)),
            ('description', models.TextField(blank=True)),
            ('max_points', models.DecimalField(max_digits=8, decimal_places=2)),
            ('order', models.PositiveIntegerField(default=0)),
            ('rubric', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='criteria', to='app.assignmentrubric')),
        ], options={'ordering': ('order', 'pk')}),
        migrations.CreateModel(name='RubricLevel', fields=[
            ('id', models.BigAutoField(primary_key=True, serialize=False)),
            ('label', models.CharField(max_length=100)),
            ('description', models.TextField(blank=True)),
            ('points', models.DecimalField(max_digits=8, decimal_places=2)),
            ('order', models.PositiveIntegerField(default=0)),
            ('criterion', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='levels', to='app.rubriccriterion')),
        ], options={'ordering': ('order', 'pk')}),
        migrations.CreateModel(name='RubricAssessment', fields=[
            ('id', models.BigAutoField(primary_key=True, serialize=False)),
            ('feedback', models.TextField(blank=True)),
            ('released', models.BooleanField(default=False)),
            ('graded_at', models.DateTimeField(blank=True, null=True)),
            ('graded_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='rubric_assessments_graded', to=settings.AUTH_USER_MODEL)),
            ('rubric', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assessments', to='app.assignmentrubric')),
            ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
        ], options={'constraints': [
            models.UniqueConstraint(fields=('rubric', 'student'), name='rubric_one_assessment_per_student')]}),
        migrations.CreateModel(name='RubricCriterionScore', fields=[
            ('id', models.BigAutoField(primary_key=True, serialize=False)),
            ('points_awarded', models.DecimalField(max_digits=8, decimal_places=2)),
            ('feedback', models.TextField(blank=True)),
            ('assessment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='scores', to='app.rubricassessment')),
            ('criterion', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app.rubriccriterion')),
        ], options={'constraints': [
            models.UniqueConstraint(fields=('assessment', 'criterion'), name='rubric_one_score_per_criterion')]}),
    ]
