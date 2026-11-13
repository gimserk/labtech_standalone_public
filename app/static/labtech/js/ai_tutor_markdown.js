/* Markdown is parsed locally and sanitized before display in the student AI Tutor.
   Third-party dependencies are pinned in labtech/vendor, not loaded from a CDN. */
(function (root) {
    'use strict';

    const ALLOWED_TAGS = [
        'p', 'br', 'hr', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'strong', 'b', 'em', 'i', 'del', 's', 'a', 'code', 'pre',
        'blockquote', 'ul', 'ol', 'li', 'table', 'thead', 'tbody',
        'tfoot', 'tr', 'th', 'td', 'sup', 'sub'
    ];
    const ALLOWED_ATTR = ['href', 'title', 'colspan', 'rowspan'];
    const converter = root.showdown ? new root.showdown.Converter({
        tables: true,
        ghCodeBlocks: true,
        strikethrough: true,
        simplifiedAutoLink: true,
        literalMidWordUnderscores: true,
        smoothLivePreview: true,
        noHeaderId: true
    }) : null;

    function render(container, markdown) {
        const source = String(markdown == null ? '' : markdown);
        if (!container) return false;

        // No untrusted HTML is inserted if a dependency fails to load.
        if (!converter || !root.DOMPurify || root.DOMPurify.isSupported === false) {
            container.textContent = source;
            return false;
        }

        try {
            const html = converter.makeHtml(source);
            const safeHtml = root.DOMPurify.sanitize(html, {
                ALLOWED_TAGS: ALLOWED_TAGS,
                ALLOWED_ATTR: ALLOWED_ATTR,
                ALLOW_DATA_ATTR: false
            });
            container.innerHTML = safeHtml;

            // Links are optional in tutor answers. Only navigation protocols are allowed.
            container.querySelectorAll('a[href]').forEach(link => {
                try {
                    const url = new URL(link.getAttribute('href'), document.baseURI);
                    if (!['http:', 'https:', 'mailto:'].includes(url.protocol)) {
                        link.removeAttribute('href');
                        return;
                    }
                    if (url.protocol === 'http:' || url.protocol === 'https:') {
                        link.setAttribute('target', '_blank');
                        link.setAttribute('rel', 'noopener noreferrer');
                    }
                } catch (_error) {
                    link.removeAttribute('href');
                }
            });
            return true;
        } catch (_error) {
            container.textContent = source;
            return false;
        }
    }

    root.LabTechTutorMarkdown = { render };
})(window);
