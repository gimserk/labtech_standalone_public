from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0081_merge_20261114_0003"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
            migrations.AlterField(
                model_name='cybercitysocalert',
                name='id',
                field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
            ),
            migrations.AlterField(
                model_name='cybercitysoccheckmkalert',
                name='id',
                field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
            ),
            migrations.AlterField(
                model_name='cybercitysoccheckmkhost',
                name='id',
                field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
            ),
            migrations.AlterField(
                model_name='cybercitysoccheckmksample',
                name='id',
                field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
            ),
            migrations.AlterField(
                model_name='cybercitysoccheckmktriage',
                name='id',
                field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
            ),
            migrations.AlterField(
                model_name='cybercitysocevent',
                name='id',
                field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
            ),
            migrations.AlterField(
                model_name='cybercitysocinvestigation',
                name='id',
                field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
            ),
            migrations.AlterField(
                model_name='cybercitysocinvestigationevidence',
                name='id',
                field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
            ),
            migrations.AlterField(
                model_name='cybercitysocresponseplan',
                name='id',
                field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
            ),
            migrations.AlterField(
                model_name='cybercitysocresponserehearsal',
                name='id',
                field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
            ),
            migrations.AlterField(
                model_name='cybercitysocresponserunbookstep',
                name='id',
                field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
            ),
            migrations.AlterField(
                model_name='cybercitysocscenario',
                name='id',
                field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
            ),
            migrations.AlterField(
                model_name='cybercitysocscenarioresponserule',
                name='id',
                field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
            ),
            migrations.AlterField(
                model_name='cybercitysocservicesample',
                name='id',
                field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
            ),
            migrations.AlterField(
                model_name='cybercitysocsimulation',
                name='id',
                field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
            ),
            migrations.AlterField(
                model_name='cybercitysocsimulationtransition',
                name='id',
                field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
            ),
            migrations.AlterField(
                model_name='cybercitysocteam',
                name='id',
                field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
            ),
            migrations.AlterField(
                model_name='cybercitysocticket',
                name='id',
                field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
            ),
            migrations.AlterField(
                model_name='cybercitysoctriagedecision',
                name='id',
                field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
            ),
            migrations.AlterField(
                model_name='cybercitysocwazuhagent',
                name='id',
                field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
            ),
            migrations.AlterField(
                model_name='cybercitysocwazuhdetection',
                name='id',
                field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
            ),
            migrations.AlterField(
                model_name='cybercitysocwazuhevidence',
                name='id',
                field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
            ),
            migrations.AlterField(
                model_name='studentactivityevent',
                name='id',
                field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
            ),
            ],
        ),
    ]
