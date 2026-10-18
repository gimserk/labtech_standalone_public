/* Progressive enhancement: without JavaScript every question remains visible. */
document.addEventListener('DOMContentLoaded', () => {
  const workspace = document.querySelector('[data-pbq-workspace]');
  if (!workspace) return;
  const setText = (node, text) => { if (node && node.textContent !== text) node.textContent = text; };

  async function loadArtifact(panel) {
    const viewer = panel.querySelector('[data-pbq-text-url]');
    if (!viewer || viewer.dataset.loaded || viewer.dataset.loading) return;
    const status = viewer.querySelector('[data-pbq-text-status]');
    const content = viewer.querySelector('[data-pbq-text]');
    const retry = viewer.querySelector('[data-pbq-retry]');
    viewer.dataset.loading = 'true';
    viewer.setAttribute('aria-busy', 'true');
    status.hidden = false;
    retry.hidden = true;
    setText(status, 'Loading artifact…');
    try {
      const response = await fetch(viewer.dataset.pbqTextUrl, {credentials: 'same-origin', cache: 'no-store'});
      if (!response.ok || !(response.headers.get('Content-Type') || '').toLowerCase().startsWith('text/plain')) {
        throw new Error('Artifact unavailable');
      }
      // Never interpret evidence as markup, even if its text contains HTML.
      content.textContent = await response.text();
      content.hidden = false;
      viewer.dataset.loaded = 'true';
      status.hidden = true;
    } catch (_) {
      setText(status, 'Unable to load this artifact. Retry, or reload the page if your session has expired.');
      retry.hidden = false;
    } finally {
      delete viewer.dataset.loading;
      viewer.removeAttribute('aria-busy');
    }
  }

  const controllers = new Map();
  workspace.querySelectorAll('[data-pbq-tabs]').forEach(scope => {
    const list = scope.querySelector('[data-pbq-tablist]');
    const tabs = Array.from(list.querySelectorAll('[role="tab"]'));
    const panels = tabs.map(tab => document.getElementById(tab.getAttribute('aria-controls')));
    if (!tabs.length || panels.some(panel => !panel)) return;
    let current = 0;
    const previous = scope.querySelector('[data-pbq-previous]');
    const next = scope.querySelector('[data-pbq-next]');
    const activate = (index, focus = false) => {
      current = Math.max(0, Math.min(index, tabs.length - 1));
      tabs.forEach((tab, position) => {
        const selected = position === current;
        tab.setAttribute('aria-selected', String(selected));
        tab.tabIndex = selected ? 0 : -1;
        panels[position].hidden = !selected;
      });
      if (previous) previous.disabled = current === 0;
      if (next) next.disabled = current === tabs.length - 1;
      if (focus) tabs[current].focus();
      if (scope.dataset.pbqTabs === 'artifacts') loadArtifact(panels[current]);
    };
    tabs.forEach((tab, index) => {
      tab.addEventListener('click', () => activate(index));
      tab.addEventListener('keydown', event => {
        const moves = {ArrowRight: (index + 1) % tabs.length,
          ArrowLeft: (index + tabs.length - 1) % tabs.length, Home: 0, End: tabs.length - 1};
        if (!(event.key in moves)) return;
        event.preventDefault();
        activate(moves[event.key], true);
      });
    });
    if (previous) previous.addEventListener('click', () => activate(current - 1, true));
    if (next) next.addEventListener('click', () => activate(current + 1, true));
    panels.forEach(panel => panel.querySelector('[data-pbq-retry]')?.addEventListener('click', () => loadArtifact(panel)));
    controllers.set(scope.dataset.pbqTabs, {tabs, panels, activate});
    list.hidden = false;
    activate(0);
  });
  workspace.querySelectorAll('[data-pbq-enhanced]').forEach(element => { element.hidden = !controllers.has('questions'); });

  const questions = controllers.get('questions');
  const form = workspace.querySelector('[data-pbq-form]');
  if (!questions || !form) return;
  const submit = form.querySelector('[data-pbq-submit]');
  const readiness = form.querySelector('[data-pbq-readiness]');
  const saveState = form.querySelector('[data-pbq-save-state]');
  function answerComplete(group) {
    const radios = group.querySelectorAll('input[type="radio"]');
    if (radios.length) return Array.from(radios).some(radio => radio.checked);
    const input = group.querySelector('input, textarea, select');
    return Boolean(input && input.value.trim() && input.validity.valid &&
      (!(input.maxLength > 0) || input.value.length <= input.maxLength));
  }
  const states = () => questions.panels.map(panel => {
    const fields = Array.from(panel.querySelectorAll('[data-pbq-answer]'));
    const answered = fields.filter(answerComplete).length;
    return {complete: fields.length > 0 && answered === fields.length,
      label: answered === fields.length && fields.length ? 'Complete' : answered ? 'In progress' : 'Not started'};
  });
  function updateProgress(changed = false) {
    const progress = states();
    progress.forEach((state, index) => {
      const tab = questions.tabs[index];
      const label = questions.panels[index].querySelector('[data-pbq-question-status]');
      tab.dataset.complete = String(state.complete);
      tab.setAttribute('aria-label', `Question ${index + 1} — ${state.label}`);
      setText(tab.querySelector('[data-pbq-tab-status]'), state.complete ? '✓' : '');
      setText(label, state.label);
      label.dataset.complete = String(state.complete);
    });
    const complete = progress.filter(state => state.complete).length;
    const ready = complete === progress.length && progress.length > 0;
    const percent = ready ? 100 : Math.floor(complete / progress.length * 100);
    setText(workspace.querySelector('[data-pbq-progress]'), `${complete} of ${progress.length} questions complete · ${percent}%`);
    const bar = workspace.querySelector('[data-pbq-progress-bar]');
    bar.value = percent;
    bar.setAttribute('aria-valuetext', `${complete} of ${progress.length} questions complete`);
    setText(readiness, ready ? (workspace.hasAttribute('data-pbq-preview') ? '100% — all questions answered in this preview.' : '100% — ready to submit.') : 'Answer every question before submitting.');
    readiness.dataset.ready = String(ready);
    if (submit) submit.disabled = !ready;
    if (changed) setText(saveState, 'Unsaved changes');
    return progress;
  }
  form.addEventListener('input', () => updateProgress(true));
  form.addEventListener('change', () => updateProgress(true));
  form.addEventListener('invalid', event => {
    const index = questions.panels.findIndex(panel => panel.contains(event.target));
    if (index >= 0) questions.activate(index);
  }, true);
  // Capture first so pbq.js keeps its unsaved-work warning when submission is blocked.
  form.addEventListener('submit', event => {
    if (event.submitter?.value !== 'submit') return;
    const firstIncomplete = updateProgress().findIndex(state => !state.complete);
    if (firstIncomplete >= 0) {
      event.preventDefault();
      questions.activate(firstIncomplete, true);
    }
  }, true);
  const progress = updateProgress();
  const firstError = questions.panels.findIndex(panel => panel.querySelector('.errorlist'));
  const firstIncomplete = progress.findIndex(state => !state.complete);
  questions.activate(firstError >= 0 ? firstError : Math.max(0, firstIncomplete));
});
