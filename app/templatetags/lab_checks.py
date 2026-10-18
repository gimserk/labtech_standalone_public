"""One bulk query for required checks on a lab page."""
from django import template

from app.models import LabInstance, StepCheck
from app.lab_checks.selectors import current_check_state

register = template.Library()


@register.simple_tag
def lab_check_context(instance, lab):
    active = list(StepCheck.objects.filter(step__lab=lab, is_active=True, removed_at__isnull=True)
                  .select_related('step', 'lab_machine').order_by('step__order', 'order', 'pk'))
    states = current_check_state(instance) if instance and instance.status == LabInstance.STATUS_ACTIVE else {}
    by_step = {}
    for check in active:
        state = states.get(check.pk)
        by_step.setdefault(check.step_id, []).append({'check': check, 'outcome': state.outcome if state else None,
                                                      'passed': state.passed if state else False})
    return {'has_checks': bool(active), 'ready': bool(instance) and bool(states) and all(s.passed for s in states.values()),
            'total_count': len(active), 'passed_count': sum(1 for state in states.values() if state.passed),
            'by_step': by_step}
