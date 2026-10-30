"""Expand the dedicated QEMU VNC port pool without changing custom ranges.

Existing AllocatedVNCPort rows are deliberately retained, so running guests
using 59xx TCP ports remain tracked until their normal cleanup completes.
"""
from django.db import migrations, models


def expand_legacy_default_vnc_range(apps, schema_editor):
    ProxmoxServer = apps.get_model('app', 'ProxmoxServer')
    db_alias = schema_editor.connection.alias
    ProxmoxServer.objects.using(db_alias).filter(
        vnc_port_start=5900, vnc_port_end=5999
    ).update(vnc_port_start=6000, vnc_port_end=6999)


class Migration(migrations.Migration):
    dependencies = [
        ('app', '0032_cybercity_reset_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='proxmoxserver',
            name='vnc_port_start',
            field=models.PositiveIntegerField(
                default=6000,
                help_text='The starting TCP port for dedicated lab VNC connections (default: 6000).',
            ),
        ),
        migrations.AlterField(
            model_name='proxmoxserver',
            name='vnc_port_end',
            field=models.PositiveIntegerField(
                default=6999,
                help_text='The ending TCP port for dedicated lab VNC connections (default: 6999).',
            ),
        ),
        migrations.RunPython(expand_legacy_default_vnc_range, migrations.RunPython.noop),
    ]
