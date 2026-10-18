// Exercise the shipped CKEditor filter in a DOM, without external network access.
// npm install --prefix /tmp/pbq-dom jsdom@26.1.0 --ignore-scripts
// NODE_PATH=/tmp/pbq-dom/node_modules PYTHON_BIN=venv/bin/python node scripts/test_pbq_editor.cjs
const assert = require('node:assert/strict');
const {execFileSync} = require('node:child_process');
const {pathToFileURL} = require('node:url');
const {JSDOM, ResourceLoader, VirtualConsole} = require('jsdom');
const config = JSON.parse(execFileSync(process.env.PYTHON_BIN || 'python', ['-c',
  "import os,json,pathlib;os.environ['DJANGO_SETTINGS_MODULE']='app.test_settings';import django;django.setup();import ckeditor;from django.conf import settings;print(json.dumps({'root':str(pathlib.Path(ckeditor.__file__).parent/'static'/'ckeditor'/'ckeditor'),'config':settings.CKEDITOR_CONFIGS['pbq']}))"
], {encoding:'utf8'}));
const base = pathToFileURL(config.root + '/').href;
class LocalAssets extends ResourceLoader {
  fetch(url, options) { return url.startsWith(base) ? super.fetch(url, options) : null; }
}
const virtualConsole = new VirtualConsole();
if (process.env.PBQ_EDITOR_DEBUG) virtualConsole.sendTo(console);
const dom = new JSDOM('<div id="story" contenteditable="true"></div>', {
  url:base + 'test.html', runScripts:'dangerously', resources:new LocalAssets(),
  pretendToBeVisual:true, virtualConsole,
  beforeParse(window) {
    Object.defineProperty(window.navigator, 'userAgent', {value:'Mozilla/5.0 AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'});
  },
});
const window = dom.window;
window.CKEDITOR_BASEPATH = base;
const source = window.document.createElement('script');
source.src = base + 'ckeditor.js';
window.document.head.appendChild(source);
let timeout;
new Promise((resolve,reject) => {
  timeout=setTimeout(() => reject(new Error('Editor did not become ready')),15000);
  source.onload = () => {
    window.CKEDITOR.disableAutoInline = true;
    const editor=window.CKEDITOR.inline('story', {...config.config, versionCheck:false});
    editor.on('uiReady', () => {
      try {
        // Use the real editor's toolbar-configured filter without requiring a
        // browser selection/layout engine. Test two load/save filter passes.
        const CKEDITOR=window.CKEDITOR;
        const filter = html => {
          const fragment=CKEDITOR.htmlParser.fragment.fromHtml(html);
          editor.filter.applyTo(fragment);
          const writer=new CKEDITOR.htmlParser.basicWriter();
          fragment.writeHtml(writer);
          return writer.getHtml();
        };
        const saved=filter('<p>Evidence</p><img src="/courses/1/pbq/1/artifacts/1/" alt="Network evidence">');
        assert.match(saved, /<img\b/, 'The first filter pass must retain the picker image');
        const reopened=filter(saved);
        assert.match(reopened, /<img\b/, 'Reopening must retain the image');
        assert.match(reopened, /Network evidence/, 'Alternative text must survive');
        assert.doesNotMatch(filter('<p onclick="alert(1)">Text</p>'), /onclick/);
        resolve();
      } catch(error) { reject(error); }
    }, null, null, 9999);
  };
  source.onerror=() => reject(new Error('CKEditor could not load'));
}).then(() => console.log('PBQ toolbar content filter, two passes: PASS'))
  .catch(error => { console.error(error.message); process.exitCode=1; })
  .finally(() => { clearTimeout(timeout); window.close(); });
