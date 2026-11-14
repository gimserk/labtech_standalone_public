/* Progressive enhancement for CyberCity directories. No server actions are changed. */
document.addEventListener('DOMContentLoaded', () => {
  for (const root of document.querySelectorAll('[data-cc-filter]')) {
    const search = root.querySelector('[data-cc-search]');
    const status = root.querySelector('[data-cc-status]');
    const count = root.querySelector('[data-cc-count]');
    const empty = root.querySelector('[data-cc-no-results]');
    const items = [...root.querySelectorAll('[data-cc-item]')];
    const update = () => {
      const term = (search?.value || '').trim().toLocaleLowerCase();
      const category = status?.value || 'all';
      let visible = 0;
      for (const item of items) {
        const haystack = (item.getAttribute('data-cc-search-text') || item.textContent).toLocaleLowerCase();
        const matches = (!term || haystack.includes(term)) &&
          (category === 'all' || item.dataset.ccCategory === category);
        item.hidden = !matches;
        if (matches) visible += 1;
      }
      if (count) count.textContent = visible + ' of ' + items.length + ' shown';
      if (empty) empty.hidden = visible !== 0 || items.length === 0;
    };
    search?.addEventListener('input', update);
    status?.addEventListener('change', update);
    update();
  }
});
