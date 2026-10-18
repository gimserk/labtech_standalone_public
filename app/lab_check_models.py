"""Persistent guest-agent check definitions and sanitized attempt history."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction


class StepCheck(models.Model):
    step = models.ForeignKey('Step', on_delete=models.CASCADE, related_name='vm_checks')
    lab_machine = models.ForeignKey('LabMachine', on_delete=models.CASCADE, related_name='step_checks')
    check_type = models.CharField(max_length=64)
    public_config = models.JSONField(default=dict)
    secret_config_encrypted = models.TextField(blank=True)
    student_label = models.CharField(max_length=160)
    failure_hint = models.CharField(max_length=500)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    removed_at = models.DateTimeField(null=True, blank=True)
    definition_revision = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('step_id', 'order', 'id')

    def clean(self):
        super().clean()
        if self.step_id and self.lab_machine_id and self.step.lab_id != self.lab_machine.lab_id:
            raise ValidationError('Machine and step must belong to the same lab.')
        if self.is_active and not self.removed_at and self.lab_machine_id and not self.lab_machine.guest_os:
            raise ValidationError('Guest OS must be classified before adding checks.')
        if self.is_active and not self.removed_at and self.lab_machine_id and self.check_type:
            from .lab_checks.registry import get_validator, RegistryError
            from .lab_checks.types import ConfigError
            from .lab_checks.secrets import decrypt_secret_config, SecretConfigError
            try:
                secret = decrypt_secret_config(self.secret_config_encrypted) if self.secret_config_encrypted else {}
                get_validator(self.check_type).normalize(self.lab_machine.guest_os, self.public_config, secret)
            except (RegistryError, ConfigError, SecretConfigError) as exc:
                raise ValidationError('Check configuration is invalid for the selected guest OS.') from exc

    def bump_revision_if_execution_changed(self, previous):
        fields = ('step_id', 'lab_machine_id', 'check_type', 'public_config', 'secret_config_encrypted')
        if any(getattr(self, field) != getattr(previous, field) for field in fields):
            self.definition_revision = previous.definition_revision + 1

    def save(self, *args, **kwargs):
        from app.models import Lab
        with transaction.atomic():
            # Shared lab lock serializes definition edits with the final finish gate.
            previous_lab_id = type(self).objects.filter(pk=self.pk).values_list('step__lab_id', flat=True).first() if self.pk else None
            lab_ids = sorted({lab_id for lab_id in (self.step.lab_id, previous_lab_id) if lab_id is not None})
            list(Lab.objects.select_for_update().filter(pk__in=lab_ids).order_by('pk').values_list('pk', flat=True))
            if self.pk:
                previous = type(self).objects.select_for_update().get(pk=self.pk)
                self.bump_revision_if_execution_changed(previous)
                if kwargs.get('update_fields'):
                    kwargs['update_fields'] = set(kwargs['update_fields']) | {'definition_revision'}
            self.full_clean()
            return super().save(*args, **kwargs)


class ValidationRun(models.Model):
    CONTEXTS = [('student_step', 'Student step'), ('finish', 'Finish'), ('instructor_preview', 'Instructor preview')]
    OUTCOMES = [(value, value) for value in ('pass', 'fail', 'infrastructure_error', 'configuration_error', 'abandoned')]
    lab_instance = models.ForeignKey('LabInstance', on_delete=models.CASCADE, related_name='validation_runs')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='lab_validation_runs')
    step = models.ForeignKey('Step', null=True, blank=True, on_delete=models.SET_NULL)
    context = models.CharField(max_length=24, choices=CONTEXTS)
    status = models.CharField(max_length=16, default='running')
    outcome = models.CharField(max_length=32, blank=True, choices=OUTCOMES)
    started_at = models.DateTimeField(auto_now_add=True)
    deadline_at = models.DateTimeField()
    finished_at = models.DateTimeField(null=True, blank=True)
    pass_count = models.PositiveIntegerField(default=0)
    fail_count = models.PositiveIntegerField(default=0)
    error_count = models.PositiveIntegerField(default=0)

    class Meta:
        indexes = [models.Index(fields=('lab_instance', '-started_at')), models.Index(fields=('actor', '-started_at'))]


class ValidationLease(models.Model):
    lab_instance = models.OneToOneField('LabInstance', on_delete=models.CASCADE, related_name='validation_lease')
    run = models.OneToOneField(ValidationRun, on_delete=models.CASCADE, related_name='lease')
    expires_at = models.DateTimeField(db_index=True)


class ValidationResult(models.Model):
    run = models.ForeignKey(ValidationRun, on_delete=models.CASCADE, related_name='results')
    check_definition = models.ForeignKey(StepCheck, on_delete=models.PROTECT, related_name='results')
    check_type_snapshot = models.CharField(max_length=64)
    definition_revision = models.PositiveIntegerField()
    public_label_snapshot = models.CharField(max_length=160)
    step_snapshot = models.ForeignKey('Step', null=True, on_delete=models.SET_NULL, related_name='+')
    machine_snapshot = models.ForeignKey('LabMachine', null=True, on_delete=models.SET_NULL, related_name='+')
    outcome = models.CharField(max_length=32, choices=ValidationRun.OUTCOMES)
    code = models.CharField(max_length=64)
    duration_ms = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=('run', 'check_definition'), name='unique_run_check_result')]
        indexes = [models.Index(fields=('check_definition', 'definition_revision'))]

    def save(self, *args, **kwargs):
        if self._state.adding:
            self.check_type_snapshot = self.check_definition.check_type
            self.definition_revision = self.check_definition.definition_revision
            self.public_label_snapshot = self.check_definition.student_label
            self.step_snapshot = self.check_definition.step
            self.machine_snapshot = self.check_definition.lab_machine
        super().save(*args, **kwargs)
