/* LabTech Course Builder: accessible metadata editing, readiness navigation and bulk actions.
   All mutations are server-validated and course-scoped. Student data is never edited here. */
(function () {
  'use strict';

  function init() {
    const root = document.getElementById('courseBuilder');
    if (!root) return;
    const select = (id) => document.getElementById(id);
    const rows = () => Array.from(root.querySelectorAll('tr[data-type]'));
    const csrf = root.dataset.csrf || document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
    const status = select('builderStatus');

    function message(text, isError) {
      if (!status) return;
      status.textContent = text;
      status.className = 'small mb-3 ' + (isError ? 'text-danger' : 'text-success');
    }

    async function postJSON(url, body) {
      const response = await fetch(url, {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf, 'X-Requested-With': 'XMLHttpRequest' },
        body: JSON.stringify(body),
      });
      const data = await response.json().catch(() => ({ error: 'The server did not return a valid response.' }));
      if (!response.ok || data.ok === false || data.status === 'error') {
        throw new Error(data.error || data.message || 'The operation could not be saved.');
      }
      return data;
    }

    function setExpanded(chapter, expanded) {
      const header = chapter?.querySelector('.builder-chapter-header');
      if (!header) return;
      header.classList.toggle('is-open', expanded);
      const toggle = header.querySelector('.chapter-toggle');
      if (toggle) toggle.setAttribute('aria-expanded', String(expanded));
    }

    root.querySelectorAll('.chapter-toggle').forEach((toggle) => {
      toggle.addEventListener('click', () => {
        const chapter = toggle.closest('.builder-chapter');
        setExpanded(chapter, !chapter.querySelector('.builder-chapter-header').classList.contains('is-open'));
      });
    });

    function filterRows(shouldOpen) {
      const term = (select('builderSearch')?.value || '').trim().toLowerCase();
      const kind = select('builderTypeFilter')?.value || '';
      const state = select('builderStatusFilter')?.value || '';
      let count = 0;
      rows().forEach((row) => {
        const matches = (!term || (row.dataset.title + ' ' + row.dataset.chapterName).toLowerCase().includes(term))
          && (!kind || row.dataset.type === kind)
          && (!state || row.dataset.readiness === state || (state === 'review' && row.dataset.readiness === 'blocked'));
        row.hidden = !matches;
        if (matches) count += 1;
      });
      root.querySelectorAll('.builder-chapter').forEach((chapter) => {
        const visible = Array.from(chapter.querySelectorAll('tr[data-type]')).some((row) => !row.hidden);
        chapter.hidden = !visible && Boolean(term || kind || state);
        if (shouldOpen && visible && (term || kind || state)) setExpanded(chapter, true);
      });
      const unassigned = select('builderUnassigned');
      if (unassigned) {
        unassigned.hidden = !Array.from(unassigned.querySelectorAll('tr[data-type]')).some(row => !row.hidden);
      }
      if (select('builderVisibleCount')) select('builderVisibleCount').textContent = count + ' activities match the current filters.';
      updateSelection();
    }

    ['builderSearch', 'builderTypeFilter', 'builderStatusFilter'].forEach((id) => {
      select(id)?.addEventListener(id === 'builderSearch' ? 'input' : 'change', () => filterRows(true));
    });
    filterRows(false);

    root.querySelectorAll('.builder-issue-link').forEach((link) => {
      link.addEventListener('click', (event) => {
        const target = document.getElementById(link.getAttribute('href').slice(1));
        if (!target) return;
        event.preventDefault();
        ['builderSearch', 'builderTypeFilter', 'builderStatusFilter'].forEach((id) => {
          if (select(id)) select(id).value = '';
        });
        filterRows(false);
        setExpanded(target.closest('.builder-chapter'), true);
        target.scrollIntoView({ behavior: 'smooth', block: 'center' });
        const focusTarget = target.querySelector('.builder-quick-edit, .item-title');
        if (focusTarget) {
          if (!focusTarget.hasAttribute('tabindex')) focusTarget.setAttribute('tabindex', '-1');
          focusTarget.focus({ preventScroll: true });
        }
      });
    });

    function selectedItems() {
      return rows().filter((row) => row.querySelector('.builder-select')?.checked).map((row) => ({
        type: row.dataset.type, id: Number(row.dataset.id),
      }));
    }

    function updateSelection() {
      const count = selectedItems().length;
      if (select('builderSelectionCount')) select('builderSelectionCount').textContent = count + ' selected';
      const visible = rows().filter(row => !row.hidden);
      const checkAll = select('builderSelectVisible');
      if (checkAll) {
        checkAll.checked = visible.length > 0 && visible.every(row => row.querySelector('.builder-select')?.checked);
        checkAll.indeterminate = visible.some(row => row.querySelector('.builder-select')?.checked) && !checkAll.checked;
      }
    }

    root.querySelectorAll('.builder-select').forEach(box => box.addEventListener('change', updateSelection));
    select('builderSelectVisible')?.addEventListener('change', (event) => {
      rows().filter(row => !row.hidden).forEach((row) => {
        const box = row.querySelector('.builder-select');
        if (box) box.checked = event.target.checked;
      });
      updateSelection();
    });

    function bulkChoices() {
      const action = select('builderBulkAction')?.value;
      const visibility = {
        builderBulkChapterWrap: action === 'move_chapter',
        builderBulkDatesWrap: action === 'set_dates',
        builderBulkPointsWrap: action === 'set_points',
      };
      Object.entries(visibility).forEach(([id, visible]) => {
        const target = select(id);
        if (target) target.hidden = !visible;
      });
    }
    select('builderBulkAction')?.addEventListener('change', bulkChoices);
    bulkChoices();

    select('builderBulkApply')?.addEventListener('click', async () => {
      const action = select('builderBulkAction').value;
      const items = selectedItems();
      if (!action || !items.length) return message('Choose a bulk action and at least one activity.', true);
      if (items.length > 200) return message('Select no more than 200 activities.', true);
      const payload = { action, items };
      if (action === 'move_chapter') payload.chapter_id = select('builderBulkChapter').value;
      if (action === 'set_points') payload.points = select('builderBulkPoints').value;
      if (action === 'set_dates') {
        payload.dates = {};
        [['builderSetStart', 'available_from', 'builderBulkStart'], ['builderSetDue', 'due_date', 'builderBulkDue'], ['builderSetEnd', 'available_until', 'builderBulkEnd']].forEach(([box, key, field]) => {
          if (select(box).checked) payload.dates[key] = select(field).value;
        });
      }
      if (['publish', 'unpublish', 'exclude_grade'].includes(action) &&
          !window.confirm('Apply this change to ' + items.length + ' selected activities?')) return;
      const button = select('builderBulkApply');
      button.disabled = true;
      message('Saving ' + items.length + ' activities…', false);
      try {
        const result = await postJSON(root.dataset.bulkUrl, payload);
        message((result.updated || items.length) + ' activities updated.', false);
        window.location.reload(); // Stay in the course builder and refresh all readiness checks.
      } catch (err) {
        message(err.message, true);
        button.disabled = false;
      }
    });

    const panel = select('builderEditPanel');
    const form = select('builderEditForm');
    root.querySelectorAll('.builder-quick-edit').forEach(button => {
      button.addEventListener('click', () => {
        if (!panel || !form || !window.bootstrap?.Offcanvas) return message('The quick editor is unavailable. Use the Actions menu.', true);
        const row = button.closest('tr[data-type]');
        form.action = row.dataset.editUrl;
        select('builderEditName').value = row.dataset.title;
        select('builderEditChapter').value = row.dataset.chapterId || '';
        select('builderEditStart').value = row.dataset.start || '';
        select('builderEditDue').value = row.dataset.due || '';
        select('builderEditEnd').value = row.dataset.end || '';
        const publishable = row.dataset.published !== 'unsupported';
        select('builderPublishWrap').hidden = !publishable;
        select('builderEditPublish').checked = row.dataset.published === 'true';
        select('builderGradeWrap').hidden = row.dataset.gradeable === 'false';
        select('builderEditIncluded').checked = row.dataset.graded === 'true';
        select('builderEditPoints').value = row.dataset.points || '0';
        const full = row.querySelector('.dropdown-menu a[href]:not(.text-danger)');
        select('builderFullEditor').hidden = !full;
        if (full) select('builderFullEditor').href = full.href;
        select('builderEditTitle').textContent = 'Quick edit: ' + row.dataset.title;
        select('builderEditError').hidden = true;
        select('builderEditError').textContent = '';
        window.bootstrap.Offcanvas.getOrCreateInstance(panel).show();
      });
    });

    form?.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (!form.reportValidity()) return;
      const data = new FormData(form);
      if (!select('builderPublishWrap').hidden) data.append('published', String(select('builderEditPublish').checked));
      if (!select('builderGradeWrap').hidden) {
        data.append('included', String(select('builderEditIncluded').checked));
        data.append('points', select('builderEditPoints').value);
      }
      const button = select('builderEditSave');
      const errorBox = select('builderEditError');
      button.disabled = true;
      errorBox.hidden = true;
      try {
        const response = await fetch(form.action, {
          method: 'POST', body: data, credentials: 'same-origin',
          headers: { 'X-CSRFToken': csrf, 'X-Requested-With': 'XMLHttpRequest' },
        });
        const result = await response.json().catch(() => ({ error: 'Invalid server response.' }));
        if (!response.ok || !result.ok) throw new Error(result.error || 'Unable to save changes.');
        window.location.reload();
      } catch (err) {
        errorBox.textContent = err.message;
        errorBox.hidden = false;
        button.disabled = false;
      }
    });

    root.querySelectorAll('.builder-move').forEach(button => {
      button.addEventListener('click', async () => {
        button.disabled = true;
        try {
          await postJSON(root.dataset.moveUrl, {
            type: button.dataset.moveType, id: Number(button.dataset.moveId),
            direction: button.dataset.direction,
          });
          window.location.reload();
        } catch (err) {
          message(err.message, true);
          button.disabled = false;
        }
      });
    });

    function sendOrder(url, payload) {
      postJSON(url, payload).catch((err) => {
        message(err.message + ' Reloading the previous order.', true);
        window.location.reload();
      });
    }
    // Drag-and-drop is progressive enhancement. Accessible movement buttons always work.
    if (window.Sortable && root.querySelector('.chapter-drag-handle')) {
      const chapters = select('chapter-list');
      if (chapters) new window.Sortable(chapters, {
        animation: 150, draggable: '.builder-chapter', handle: '.chapter-drag-handle',
        ghostClass: 'sortable-ghost',
        onEnd: () => sendOrder(root.dataset.chapterOrderUrl, {
          new_order: Array.from(chapters.querySelectorAll(':scope > .builder-chapter')).map(ch => ch.dataset.id),
        }),
      });
      root.querySelectorAll('.sortable-content-tbody').forEach(tbody => {
        new window.Sortable(tbody, {
          animation: 150, draggable: 'tr[data-type]', handle: '.drag-handle',
          ghostClass: 'sortable-ghost',
          onEnd: () => sendOrder(root.dataset.contentOrderUrl, {
            new_order: rows().map(row => ({ type: row.dataset.type, id: row.dataset.id })),
          }),
        });
      });
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
}());
