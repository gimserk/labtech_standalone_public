from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('app', '0033_proxmox_vnc_port_range')]

    operations = [
        migrations.CreateModel(
            name='LabCleanupSweepStatus',
            fields=[
                ('id', models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False, serialize=False)),
                ('last_run_at', models.DateTimeField(blank=True, null=True)),
            ],
        ),
        migrations.AddField(
            model_name='labinstance',
            name='build_failed',
            field=models.BooleanField(
                default=False, editable=False,
                help_text='Build worker exited in a failed or cancelled state.',
            ),
        ),
        migrations.AddField(
            model_name='labinstance',
            name='build_finished_at',
            field=models.DateTimeField(
                blank=True, null=True, editable=False,
                help_text='Set by the provisioning worker once it has exited.',
            ),
        ),
    ]
