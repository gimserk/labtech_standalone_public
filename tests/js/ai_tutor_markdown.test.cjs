/* Run with: node --test tests/js/ai_tutor_markdown.test.cjs */
'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const root = path.resolve(__dirname, '../..');
const adapter = fs.readFileSync(path.join(root, 'app/static/labtech/js/ai_tutor_markdown.js'), 'utf8');
const showdown = require(path.join(root, 'app/static/labtech/vendor/showdown-2.1.0.min.js'));

function link(href) {
    const attrs = new Map([['href', href]]);
    return {
        getAttribute: name => attrs.get(name) ?? null,
        setAttribute: (name, value) => attrs.set(name, value),
        removeAttribute: name => attrs.delete(name),
        attrs
    };
}

function container(links = []) {
    return {
        innerHTML: '',
        textContent: '',
        querySelectorAll: selector => selector === 'a[href]' ? links : []
    };
}

function setup({ withParser = true, withSanitizer = true, isSupported = true, sanitizedHtml = '<p>Sanitized</p>' } = {}) {
    const calls = [];
    const page = {
        showdown: withParser ? showdown : undefined,
        DOMPurify: withSanitizer ? {
            isSupported,
            sanitize: (input, options) => {
                calls.push({ input, options });
                return sanitizedHtml;
            }
        } : undefined
    };
    const context = { window: page, document: { baseURI: 'https://labtech.example.test/ai/' }, URL };
    vm.runInNewContext(adapter, context, { filename: 'ai_tutor_markdown.js' });
    return { render: page.LabTechTutorMarkdown.render, calls };
}

test('renders headings, emphasis, lists, fenced code, tables, and links before sanitizing', () => {
    const { render, calls } = setup();
    const markdown = [
        '## Troubleshooting',
        '**Important** and *useful*',
        '- Check the cable',
        '- Restart the port',
        '',
        '\x60\x60\x60powershell',
        'Get-NetAdapter',
        '\x60\x60\x60',
        '',
        '| Port | Status |',
        '| --- | --- |',
        '| 1 | up |',
        '',
        '[Documentation](https://example.org)'
    ].join('\n');
    const target = container();

    assert.equal(render(target, markdown), true);
    assert.equal(target.innerHTML, '<p>Sanitized</p>');
    assert.equal(calls.length, 1);
    const parsed = calls[0].input;
    assert.match(parsed, /<h2[^>]*>Troubleshooting<\/h2>/);
    assert.match(parsed, /<strong>Important<\/strong>/);
    assert.match(parsed, /<em>useful<\/em>/);
    assert.match(parsed, /<li[^>]*>Check the cable<\/li>/);
    assert.match(parsed, /<pre><code[^>]*>Get-NetAdapter/);
    assert.match(parsed, /<table>/);
    assert.match(parsed, /<a href="https:\/\/example\.org"/);
    assert.equal(Array.from(calls[0].options.ALLOWED_TAGS).includes('script'), false);
    assert.equal(Array.from(calls[0].options.ALLOWED_TAGS).includes('iframe'), false);
    assert.equal(Array.from(calls[0].options.ALLOWED_ATTR).includes('onerror'), false);
    assert.equal(Array.from(calls[0].options.ALLOWED_ATTR).includes('style'), false);
    assert.equal(calls[0].options.ALLOW_DATA_ATTR, false);
});

test('plain text fallback does not insert untrusted HTML when parser or sanitizer is unavailable', () => {
    for (const options of [
        { withParser: false }, { withSanitizer: false }, { isSupported: false }
    ]) {
        const { render } = setup(options);
        const target = container();
        const response = '<img src=x onerror=alert(1)> **raw**';
        assert.equal(render(target, response), false);
        assert.equal(target.textContent, response);
        assert.equal(target.innerHTML, '');
    }
});

test('sanitizer output is used instead of raw parser HTML', () => {
    const { render, calls } = setup({ sanitizedHtml: '<p>Allowed</p>' });
    const target = container();
    const response = '<script>bad()</script><p>Allowed</p>';
    assert.equal(render(target, response), true);
    assert.match(calls[0].input, /script/);
    assert.equal(target.innerHTML, '<p>Allowed</p>');
});

test('unsafe link protocols are blocked and safe web links are isolated', () => {
    const unsafe = link('javascript:alert(1)');
    const safe = link('https://docs.example.org/topic');
    const relative = link('../course/1');
    const malformed = link('http://[');
    const { render } = setup();
    assert.equal(render(container([unsafe, safe, relative, malformed]), 'some markdown'), true);
    assert.equal(unsafe.attrs.has('href'), false);
    assert.equal(malformed.attrs.has('href'), false);
    for (const item of [safe, relative]) {
        assert.equal(item.attrs.get('target'), '_blank');
        assert.equal(item.attrs.get('rel'), 'noopener noreferrer');
    }
});

test('render uses plain text on conversion failure', () => {
    const { render } = setup();
    const target = container();
    Object.defineProperty(target, 'innerHTML', {
        set() { throw Error('DOM insertion failed'); }
    });
    assert.equal(render(target, '## Test'), false);
    assert.equal(target.textContent, '## Test');
});
