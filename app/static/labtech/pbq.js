document.addEventListener('DOMContentLoaded', () => {
  const type = document.getElementById('id_answer_type');
  if (type) {
    const configure = () => {
      const visible = {
        options: ['mcq', 'dropdown'], correct_option: ['mcq', 'dropdown'],
        accepted: ['fill_blank'], case_sensitive: ['fill_blank'],
        marking_guidance: ['short_answer']
      };
      Object.entries(visible).forEach(([name, types]) => {
        const input = document.getElementById('id_' + name);
        if (input) input.closest('p').hidden = !types.includes(type.value);
      });
    };
    type.addEventListener('change', configure);
    configure();
  }
  let dirty = false;
  document.querySelectorAll('[data-pbq-form]').forEach(form => {
    form.addEventListener('input', () => { dirty = true; });
    form.addEventListener('submit', event => { if (!event.defaultPrevented) dirty = false; });
  });
  window.addEventListener('beforeunload', event => {
    if (dirty) { event.preventDefault(); event.returnValue = ''; }
  });
  const error = document.getElementById('pbq-errors');
  if (error) error.focus();
  document.querySelectorAll('[data-pbq-image]').forEach(button => {
    button.addEventListener('click', () => {
      if (!window.CKEDITOR) return;
      const editor = CKEDITOR.currentInstance || Object.values(CKEDITOR.instances)[0];
      if (!editor) return;
      const image = new CKEDITOR.dom.element('img');
      image.setAttributes({src: button.dataset.pbqImage, alt: button.dataset.alt});
      editor.insertElement(image);
      dirty = true;
    });
  });
  if (window.CKEDITOR) {
    CKEDITOR.on('instanceReady', event => event.editor.on('change', () => { dirty = true; }));
  }
});
