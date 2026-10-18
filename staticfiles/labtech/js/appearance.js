/* Rich-text documents live in iframes and cannot inherit the page's palette. */
(() => {
    'use strict';
    const root = document.documentElement;
    const attached = new WeakSet();
    let ckeditor;

    function themeDocument(editor) {
        const doc = editor.document && editor.document.$;
        if (!doc || !doc.body) return;
        const colors = getComputedStyle(root);
        let style = doc.getElementById('labtech-editor-appearance');
        if (!style) {
            style = doc.createElement('style');
            style.id = 'labtech-editor-appearance';
            doc.head.appendChild(style);
        }
        const color = role => colors.getPropertyValue(`--lt-${role}`).trim();
        doc.documentElement.style.colorScheme = root.dataset.bsTheme;
        style.textContent = `
            body { background: ${color('surface')}; color: ${color('text')}; }
            a { color: ${color('primary')}; }
            table, td, th, blockquote { border-color: ${color('border')}; }
            pre, code { background: ${color('surface-muted')}; color: ${color('text')}; }
            :focus-visible { outline: 3px solid ${color('focus')}; outline-offset: 2px; }
        `;
        // This changes only the editor document's chrome, never its saved HTML.
    }

    function attach(editor) {
        if (!attached.has(editor)) {
            attached.add(editor);
            editor.on('contentDom', () => themeDocument(editor));
        }
        themeDocument(editor);
    }

    function updateEditors() {
        if (window.CKEDITOR && ckeditor !== window.CKEDITOR) {
            ckeditor = window.CKEDITOR;
            ckeditor.on('instanceReady', event => attach(event.editor));
        }
        if (ckeditor) Object.values(ckeditor.instances).forEach(attach);
        document.querySelectorAll('.CodeMirror').forEach(element => {
            const editor = element.CodeMirror;
            const theme = root.dataset.bsTheme === 'dark' ? 'material-darker' : 'default';
            if (editor && editor.getOption('theme') !== theme) editor.setOption('theme', theme);
        });
    }

    new MutationObserver(updateEditors).observe(root, {
        attributes: true, attributeFilter: ['data-bs-theme', 'data-contrast'],
    });
    // CKEditor loads asynchronously; page-specific CodeMirror initialization
    // typically runs in DOMContentLoaded handlers registered by the template.
    document.addEventListener('load', event => {
        if (event.target.tagName === 'SCRIPT') updateEditors();
    }, true);
    document.addEventListener('DOMContentLoaded', () => requestAnimationFrame(updateEditors));
    updateEditors();
})();
