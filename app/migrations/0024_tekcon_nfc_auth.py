from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('app', '0023_cybercity_esp32_firmware_reporting'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(name='TekconNFCConfiguration', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('enabled', models.BooleanField(default=False)),
            ('server_url', models.URLField(blank=True, max_length=255,
                help_text='TEKCON HTTPS origin, DNS or IP address. No path.')),
            ('auto_create_users', models.BooleanField(default=True)),
        ]),
        migrations.CreateModel(name='TekconIdentityLink', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('participant_id', models.CharField(max_length=64, unique=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,
                related_name='tekcon_identity_link', to=settings.AUTH_USER_MODEL)),
        ]),
    ]
