/* Progressive enhancement for enrolled students' course resource popup.
   Visibility is enforced by the server, not by client-side filtering. */
document.addEventListener('DOMContentLoaded', () => {
  const modal = document.getElementById('resourcesModal');
  if (!modal) return;
  const search = modal.querySelector('#courseResourceSearch');
  const category = modal.querySelector('#courseResourceCategory');
  const clear = modal.querySelector('#courseResourceClear');
  const result = modal.querySelector('#courseResourceResultCount');
  const empty = modal.querySelector('#courseResourceNoResults');
  const sections = [...modal.querySelectorAll('[data-resource-section]')];
  const cards = [...modal.querySelectorAll('[data-resource-card]')];

  // The extension is for presentation only; never build file links from it.
  const types = {
    pdf: ['PDF', 'fa-file-pdf'],
    doc: ['Word', 'fa-file-word'], docx: ['Word', 'fa-file-word'],
    ppt: ['Slides', 'fa-file-powerpoint'], pptx: ['Slides', 'fa-file-powerpoint'],
    xls: ['Spreadsheet', 'fa-file-excel'], xlsx: ['Spreadsheet', 'fa-file-excel'],
    csv: ['CSV', 'fa-file-csv'],
    txt: ['Text', 'fa-file-alt'], md: ['Markdown', 'fa-file-alt'],
    zip: ['ZIP', 'fa-file-archive'], '7z': ['Archive', 'fa-file-archive'],
    png: ['Image', 'fa-file-image'], jpg: ['Image', 'fa-file-image'],
    jpeg: ['Image', 'fa-file-image'], gif: ['Image', 'fa-file-image'], webp: ['Image', 'fa-file-image'],
    mp3: ['Audio', 'fa-file-audio'], wav: ['Audio', 'fa-file-audio'], m4a: ['Audio', 'fa-file-audio'],
    mp4: ['Video', 'fa-file-video'], mov: ['Video', 'fa-file-video']
  };
  cards.forEach(card => {
    const filename = card.dataset.filename || '';
    const basename = filename.split('/').pop().split('\\').pop();
    const ext = basename.includes('.') ? basename.split('.').pop().toLowerCase() : '';
    const [label, icon] = types[ext] || [ext ? ext.toUpperCase().slice(0, 12) : 'File', 'fa-file-alt'];
    const typeText = card.querySelector('[data-resource-file-type]');
    const iconEl = card.querySelector('[data-resource-icon]');
    if (typeText) typeText.textContent = label;
    if (iconEl) {
      iconEl.classList.remove('fa-file-alt');
      iconEl.classList.add(icon);
    }
  });

  const update = () => {
    const term = (search?.value || '').trim().toLocaleLowerCase();
    const selected = category?.value || '';
    let visible = 0;
    for (const section of sections) {
      const matchCategory = !selected || section.dataset.resourceCategory === selected;
      let groupCount = 0;
      for (const card of section.querySelectorAll('[data-resource-card]')) {
        const label = (card.dataset.resourceSearch || card.textContent || '').toLocaleLowerCase();
        const show = matchCategory && (!term || label.includes(term));
        card.hidden = !show;
        if (show) groupCount++;
      }
      section.hidden = groupCount === 0;
      const counter = section.querySelector('[data-resource-section-count]');
      if (counter) counter.textContent = groupCount + (groupCount === 1 ? ' file' : ' files');
      visible += groupCount;
    }
    if (result) result.textContent = visible + ' of ' + cards.length + (cards.length === 1 ? ' file' : ' files') + ' shown';
    if (empty) empty.hidden = visible !== 0;
    if (clear) clear.hidden = !term && !selected;
  };
  search?.addEventListener('input', update);
  category?.addEventListener('change', update);
  clear?.addEventListener('click', () => {
    if (search) search.value = '';
    if (category) category.value = '';
    update();
    search?.focus();
  });
  update();
});
