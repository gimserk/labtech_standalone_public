document.addEventListener('DOMContentLoaded', () => {
  const buttons = document.querySelectorAll('.lab-check-work');
  const csrf = document.querySelector('input[name="csrfmiddlewaretoken"]');
  function cooldown(button, seconds) {
    let remaining = Math.max(1, Math.min(Number(seconds) || 10, 60));
    button.disabled = true;
    const original = button.textContent;
    button.textContent = `Retry in ${remaining}s`;
    const timer = setInterval(() => {
      remaining -= 1;
      if (remaining <= 0) {
        clearInterval(timer);
        button.disabled = false;
        button.textContent = original;
      } else button.textContent = `Retry in ${remaining}s`;
    }, 1000);
  }
  for (const button of buttons) {
    button.addEventListener('click', async () => {
      button.disabled = true;
      const panel = button.closest('section');
      const feedback = panel.querySelector('.check-feedback');
      feedback.textContent = 'Checking your work…';
      try {
        const response = await fetch(button.dataset.url, {
          method: 'POST', credentials: 'same-origin', headers: { 'X-CSRFToken': csrf?.value || '' }
        });
        const payload = await response.json();
        if (response.status === 409) {
          feedback.textContent = 'A check is in progress. Please retry shortly.';
          cooldown(button, payload.retry_after_seconds);
          return;
        }
        if (!response.ok) throw new Error('request_failed');
        for (const item of payload.checks || []) {
          const row = Array.from(panel.querySelectorAll('[data-check-id]')).find(el => el.dataset.checkId === String(item.id));
          if (!row) continue;
          row.querySelector('.check-outcome').textContent = item.outcome;
          let hint = row.querySelector('.check-hint');
          if (!hint) {
            hint = document.createElement('span');
            hint.className = 'check-hint';
            row.appendChild(hint);
          }
          hint.textContent = item.hint || '';
        }
        feedback.textContent = payload.outcome === 'pass' ? 'All checks passed.' :
          payload.outcome === 'fail' ? 'Review the hints and retry.' : 'Validation is temporarily unavailable. Please retry later.';
        document.dispatchEvent(new Event('labchecks:updated'));
        cooldown(button, payload.retry_after_seconds);
      } catch (_error) {
        feedback.textContent = 'Validation is temporarily unavailable. Please retry later.';
        button.disabled = false;
      }
    });
  }
});
