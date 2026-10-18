"""Durable metadata for isolated, administrator-installed connectors."""
from pathlib import PurePosixPath
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


PLUGIN_ID = re.compile(r'^[a-z][a-z0-9-]{0,39}$')
SECRET_NAMES = {'secret', 'token', 'api_key', 'password', 'credential', 'private_key'}


def _contains_secret(value):
    if isinstance(value, dict):
        return any(any(name in str(key).lower() for name in SECRET_NAMES) or _contains_secret(item)
                   for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_secret(item) for item in value)
    return False


class InstalledConnector(models.Model):
    STATES = [('installing', 'Installing'), ('enabled', 'Enabled'),
              ('disabled', 'Disabled'), ('failed', 'Failed')]
    plugin_id = models.CharField(max_length=40, unique=True)
    version = models.CharField(max_length=64)
    release_id = models.CharField(max_length=120)
    digest = models.CharField(max_length=64)
    contract_version = models.PositiveIntegerField()
    enabled = models.BooleanField(default=False)
    state = models.CharField(max_length=16, choices=STATES, default='installing')
    last_error = models.TextField(blank=True)
    installed_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.CheckConstraint(
            condition=models.Q(enabled=False) | models.Q(state='enabled'), name='connector_enabled_state',
        )]

    def clean(self):
        if not PLUGIN_ID.fullmatch(self.plugin_id or ''):
            raise ValidationError({'plugin_id': 'Use lowercase letters, numbers, and hyphens.'})
        if self.enabled and self.state != 'enabled':
            raise ValidationError({'enabled': 'Only a healthy enabled connector may be active.'})

    def save(self, *args, **kwargs):
        self.clean()
        return super().save(*args, **kwargs)


class ConnectorConfiguration(models.Model):
    installed_connector = models.OneToOneField(InstalledConnector, on_delete=models.CASCADE,
                                               related_name='configuration')
    public_config = models.JSONField(default=dict)
    secret_path = models.CharField(max_length=512, blank=True)

    def clean(self):
        if not isinstance(self.public_config, dict) or _contains_secret(self.public_config):
            raise ValidationError({'public_config': 'Keep credentials in a separate secret file.'})
        if self.secret_path:
            path = PurePosixPath(self.secret_path)
            if (not path.is_absolute() or '..' in path.parts
                    or not self.secret_path.startswith('/etc/labtech/plugins/')
                    or self.secret_path.endswith('/')):
                raise ValidationError({'secret_path': 'Use a file under /etc/labtech/plugins/.'})

    def save(self, *args, **kwargs):
        self.clean()
        return super().save(*args, **kwargs)


class PluginInstallJob(models.Model):
    STATUS = [('queued', 'Queued'), ('running', 'Running'),
              ('succeeded', 'Succeeded'), ('failed', 'Failed')]
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    plugin_id = models.CharField(max_length=40)
    release_id = models.CharField(max_length=120)
    status = models.CharField(max_length=12, choices=STATUS, default='queued')
    action = models.CharField(max_length=12, default='install', choices=[('install', 'Install'), ('enable', 'Enable')])
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    previous_target = models.CharField(max_length=80, blank=True)
    candidate_target = models.CharField(max_length=80, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['plugin_id', 'release_id'],
                                                condition=models.Q(status__in=['queued', 'running']),
                                                name='unique_active_plugin_release_job')]


class PluginAuditEvent(models.Model):
    actor_id = models.PositiveIntegerField(null=True, blank=True)
    plugin_id = models.CharField(max_length=40)
    action = models.CharField(max_length=50)
    result = models.CharField(max_length=200)
    occurred_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError('Audit events cannot be edited.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Audit events cannot be deleted.')
