// Real rendered Django pages, Bootstrap and browser-computed contrast.
// See docs/operations/appearance.md for setup and commands.
const fs = require('node:fs');
const path = require('node:path');
const {execFileSync} = require('node:child_process');
const {chromium} = require('playwright-core');
const axe = require('axe-core');

const pages = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const output = process.argv[3] || '/tmp/labtech-theme-results';
fs.mkdirSync(output, {recursive: true});
const root = path.resolve(__dirname, '..');
const ckeditorRoot = execFileSync(process.env.PYTHON_BIN || 'python', ['-c',
  'import ckeditor,pathlib;print(pathlib.Path(ckeditor.__file__).parent/"static")'
], {encoding: 'utf8'}).trim();

async function main() {
  const browser = await chromium.launch({
    executablePath: process.env.CHROMIUM_PATH || undefined,
    headless: true,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });
  const context = await browser.newContext({viewport: {width: Number(process.env.THEME_WIDTH || 1365), height: 1000}});
  await context.route('**/*', async route => {
    const url = new URL(route.request().url());
    let file;
    if (url.hostname === 'theme.test' && url.pathname.startsWith('/page/')) {
      return route.fulfill({contentType: 'text/html', body: pages[url.pathname.slice(6)]});
    }
    if (/^\/api\/cybercity\/\d+\/status\/$/.test(url.pathname)) {
      return route.fulfill({json: {buildings: [{id: 1, name: 'Hospital', pos_x: 40, pos_y: 40,
        pins: [{name: 'Power', status: 'on'}, {name: 'Network', status: 'off'}]}]}});
    }
    if (url.pathname.endsWith('/bootstrap.min.css')) file = require.resolve('bootstrap/dist/css/bootstrap.min.css');
    else if (url.pathname.endsWith('/bootstrap.bundle.min.js')) file = require.resolve('bootstrap/dist/js/bootstrap.bundle.min.js');
    else if (/jquery.*\.js$/.test(url.pathname)) file = require.resolve('jquery/dist/jquery.min.js');
    else if (url.pathname.includes('/codemirror/5.65.15/')) {
      let relative = url.pathname.split('/codemirror/5.65.15/')[1].replace('.min.', '.');
      if (/^codemirror\./.test(relative)) relative = 'lib/' + relative;
      file = path.join(path.dirname(require.resolve('codemirror/package.json')), relative);
    } else if (url.pathname.startsWith('/static/ckeditor/')) file = path.join(ckeditorRoot, url.pathname.slice(8));
    else if (url.pathname.startsWith('/static/labtech/')) file = path.join(root, 'app/static', url.pathname.slice(8));
    if (file && fs.existsSync(file)) {
      const ext = path.extname(file);
      const types = {'.css':'text/css', '.js':'application/javascript', '.png':'image/png', '.svg':'image/svg+xml', '.gif':'image/gif'};
      return route.fulfill({path: file, contentType: types[ext] || 'application/octet-stream'});
    }
    // No external network, live mutations, images, or services in this check.
    return route.fulfill({status: 204, body: ''});
  });
  const page = await context.newPage();
  const failures = [];
  let checked = 0;
  try {
    for (const name of Object.keys(pages).filter(name => !process.env.THEME_ONLY || process.env.THEME_ONLY.split(',').includes(name))) {
      await page.goto('http://theme.test/page/' + name);
      if (name === 'take_hotspot_activity') await page.locator('#take-again-btn').evaluate(button => { button.style.display = 'inline-block'; });
      if (name === 'pbq_edit') await page.waitForFunction(() => Object.values(window.CKEDITOR?.instances || {}).some(editor => editor.status === 'ready'));
      if (name === 'home') {
        const search = page.locator('[data-workspace-tool-search]');
        if (await search.count()) {
          await search.fill('VMID');
          const matched = await page.locator('[data-workspace-tool]:visible').allTextContents();
          if (matched.length !== 1 || !matched[0].includes('VMID pools')) {
            failures.push({page: name, target: ['[data-workspace-tool-search]'], summary: 'Admin tool search did not narrow to VMID pools'});
          }
          await search.fill('');
          if (await page.locator('[data-workspace-tool-group]:visible').count() !== 4) {
            failures.push({page: name, target: ['[data-workspace-tool-group]'], summary: 'Clearing tool search did not restore all groups'});
          }
        }
      }
      if (name === 'home_instructor') {
        if (await page.locator('#instructor-workspace').count() !== 1 || await page.locator('.course-table').count() !== 0) {
          failures.push({page: name, target: ['#instructor-workspace'], summary: 'Teaching overview duplicated the full management table'});
        }
      }
      if (name === 'instructor_my_courses') {
        const status = page.locator('[data-course-index-status]');
        const search = page.locator('[data-course-index-search]');
        if (await status.count() && await search.count()) {
          await status.selectOption('archived');
          if (await page.locator('tr[data-course-row]:not([hidden]):not([data-course-status="archived"])').count() !== 0) {
            failures.push({page: name, target: ['[data-course-index-status]'], summary: 'Archived filter left current courses displayed'});
          }
          await status.selectOption('all');
          await search.fill('unlikely-unique-course-name-999');
          if (await page.locator('tr[data-course-row]:not([hidden])').count() !== 0) {
            failures.push({page: name, target: ['[data-course-index-search]'], summary: 'Course directory search did not filter nonmatching rows'});
          }
          await search.fill('');
        }
      }
      if (name === 'cybercity_dashboard') {
        const citySearch = page.locator('#cc-city-search');
        await citySearch.fill('nothing-matches-this-city');
        if (await page.locator('.cc-city-card:visible').count() !== 0 ||
            !(await page.locator('[data-cc-no-results]').isVisible())) {
          failures.push({page: name, target: ['#cc-city-search'], summary: 'City search did not hide unmatched cards'});
        }
        await citySearch.fill('');
        if (await page.locator('.cc-city-card:visible').count() === 0) {
          failures.push({page: name, target: ['#cc-city-search'], summary: 'Clearing city search did not restore cards'});
        }
      }
      if (name === 'cybercity_detail') {
        const buildingSearch = page.locator('#cc-building-search');
        await buildingSearch.fill('nothing-matches-this-building');
        if (await page.locator('.cc-building-card:visible').count() !== 0) {
          failures.push({page: name, target: ['#cc-building-search'], summary: 'Building search did not filter cards'});
        }
        await buildingSearch.fill('');
        if (await page.locator('.cc-building-card:visible').count() === 0) {
          failures.push({page: name, target: ['#cc-building-search'], summary: 'Clearing building search did not restore buildings'});
        }
        const advanced = page.locator('#cc-services details.cc-secondary-actions').first();
        if (await advanced.count()) {
          await advanced.locator('summary').press('Enter');
          if (!(await advanced.evaluate(el => el.open))) {
            failures.push({page: name, target: ['#cc-services details'], summary: 'Service actions were not keyboard-expandable'});
          }
          await advanced.locator('summary').press('Enter');
        }
      }
      if (name === 'cybercity_soc_dashboard') {
        if (!(await page.locator('#cc-soc-queue').evaluate(el => el.open))) {
          failures.push({page: name, target: ['#cc-soc-queue'], summary: 'Operational ticket queue should be visible by default'});
        }
        const assets = page.locator('#cc-soc-assets');
        await assets.locator('summary').press('Enter');
        if (!(await assets.evaluate(el => el.open))) {
          failures.push({page: name, target: ['#cc-soc-assets'], summary: 'SOC inventory could not be keyboard-expanded'});
        }
      }
      if (name === 'cybercity_building_detail' || name === 'cybercity_esp32_detail' || name === 'cybercity_visualizer') {
        if (!await page.locator('nav.cc-breadcrumbs').count()) {
          failures.push({page: name, target: ['nav.cc-breadcrumbs'], summary: 'CyberCity navigation breadcrumb missing'});
        }
      }
      if (name === 'cybercity_visualizer') {
        const scroll = await page.evaluate(() => getComputedStyle(document.body).overflow);
        if (scroll === 'hidden') failures.push({page: name, target: ['body'], summary: 'Visualizer blocks document scrolling'});
        if (!await page.getByRole('link', {name:'Back to city'}).count()) {
          failures.push({page: name, target: ['.visualizer-header'], summary: 'Visualizer missing return path to the city'});
        }
      }
      if (name === 'course_detail') {
        const header = page.locator('.course-sidebar .chapter-header').first();
        if (await header.count()) {
          const initial = await header.getAttribute('aria-expanded');
          if (initial !== 'true') failures.push({page: name, target: ['.chapter-header'], summary: 'First/active chapter did not open automatically'});
          const panelId = await header.getAttribute('aria-controls');
          const lessons = page.locator('#' + panelId);
          await header.press('Enter');
          if ((await header.getAttribute('aria-expanded')) !== 'false' || !(await lessons.evaluate(el => el.hidden))) {
            failures.push({page: name, target: ['.chapter-header'], summary: 'Enter did not collapse chapter and update ARIA'});
          }
          await header.press('Space');
          if ((await header.getAttribute('aria-expanded')) !== 'true' || (await lessons.evaluate(el => el.hidden))) {
            failures.push({page: name, target: ['.chapter-header'], summary: 'Space did not expand chapter and update ARIA'});
          }
        }
      }
      if (name === 'course_detail' && await page.locator('#resourcesModal').count()) {
        // Exercise the actual resource modal search without mutating any files.
        const result = await page.evaluate(() => {
          const search = document.getElementById('courseResourceSearch');
          const filter = document.getElementById('courseResourceCategory');
          const clear = document.getElementById('courseResourceClear');
          const cards = [...document.querySelectorAll('#resourcesModal [data-resource-card]')];
          const visible = () => cards.filter(item => !item.hidden).length;
          const groups = () => [...document.querySelectorAll('#resourcesModal [data-resource-section]')].filter(el => !el.hidden).length;
          const initial = {cards: visible(), groups: groups(), hasFileTypes: cards.every(card =>
            card.querySelector('[data-resource-file-type]').textContent !== 'File')};
          search.value = 'wireshark';
          search.dispatchEvent(new Event('input', {bubbles: true}));
          const searchResult = {cards: visible(), groups: groups()};
          filter.value = 'Syllabus';
          filter.dispatchEvent(new Event('change', {bubbles: true}));
          const noResults = {cards: visible(), emptyShown: !document.getElementById('courseResourceNoResults').hidden};
          clear.click();
          const restored = {cards: visible(), groups: groups()};
          return {initial, searchResult, noResults, restored};
        });
        if (result.initial.cards !== 2 || result.initial.groups !== 2 || !result.initial.hasFileTypes ||
            result.searchResult.cards !== 1 || result.searchResult.groups !== 1 ||
            result.noResults.cards !== 0 || !result.noResults.emptyShown ||
            result.restored.cards !== 2 || result.restored.groups !== 2) {
          failures.push({page: name, target: ['#resourcesModal'], summary: 'Class resource search, category filtering, file types or reset failed: ' + JSON.stringify(result)});
        }
      }
      const originalEditorContent = await page.evaluate(() => Object.values(window.CKEDITOR?.instances || {}).map(editor => editor.getData()));
      await page.addScriptTag({content: axe.source});
      for (const theme of ['light', 'dark']) {
        for (const contrast of ['standard', 'high']) {
          await page.evaluate(({theme, contrast}) => {
            document.documentElement.dataset.bsTheme = theme;
            document.documentElement.dataset.contrast = contrast;
          }, {theme, contrast});
          // Wait for existing CSS color transitions before measuring contrast.
          await page.waitForTimeout(500);
          const editorFailures = await page.evaluate(() => {
            const probe = document.createElement('div');
            probe.style.backgroundColor = 'var(--lt-surface)';
            document.body.append(probe);
            const expected = getComputedStyle(probe).backgroundColor;
            probe.remove();
            const failures = [];
            for (const element of document.querySelectorAll('.CodeMirror')) {
              if (getComputedStyle(element).backgroundColor !== expected) failures.push('CodeMirror surface does not follow theme');
            }
            for (const editor of Object.values(window.CKEDITOR?.instances || {})) {
              const body = editor.document?.$?.body;
              if (body && body.ownerDocument.defaultView.getComputedStyle(body).backgroundColor !== expected) failures.push('CKEditor document does not follow theme');
            }
            const canvas = document.getElementById('cityCanvas');
            if (canvas) {
              const pixel = Array.from(canvas.getContext('2d').getImageData(50, 140, 1, 1).data).slice(0, 3);
              const expectedPixel = expected.match(/\d+/g).slice(0, 3).map(Number);
              if (pixel.some((channel, index) => Math.abs(channel - expectedPixel[index]) > 2)) failures.push(`Canvas building surface does not follow theme: ${pixel} expected ${expectedPixel}`);
            }
            return failures;
          });
          for (const summary of editorFailures) failures.push({page: name, theme, contrast, target: ['editor'], summary});
          if (name === 'course_detail') {
            const surfaceColors = await page.evaluate(() => {
              const chapter = document.querySelector('.course-sidebar .chapter-header');
              const lessons = document.querySelector('.course-sidebar .chapter-body');
              return chapter && lessons ? [getComputedStyle(chapter).backgroundColor, getComputedStyle(lessons).backgroundColor] : null;
            });
            if (!surfaceColors || surfaceColors[0] === surfaceColors[1]) {
              failures.push({page: name, theme, contrast, target: ['.chapter-section'], summary: 'Chapter and lessons do not have distinct background surfaces'});
            }
          }
          const results = await page.evaluate(async contrast => axe.run({
            include: [['#main-content'], ['.navbar'], ['.labtech-footer']],
          }, {runOnly: [contrast === 'high' ? 'color-contrast-enhanced' : 'color-contrast'], resultTypes: ['violations']}), contrast);
          for (const violation of results.violations) {
            for (const node of violation.nodes) {
              failures.push({page: name, theme, contrast, target: node.target, summary: node.failureSummary});
            }
          }
          if (name === 'shared_controls') {
            for (const button of await page.locator('#main-content .btn').all()) {
              await button.hover();
              await page.waitForTimeout(250);
              const issues = await button.evaluate(async element => axe.run(element, {
                runOnly: [document.documentElement.dataset.contrast === 'high' ? 'color-contrast-enhanced' : 'color-contrast'],
                resultTypes: ['violations'],
              }));
              for (const violation of issues.violations) for (const node of violation.nodes) failures.push({page: name, theme, contrast, target: node.target, summary: 'Hover: ' + node.failureSummary});
            }
            await page.keyboard.press('Tab');
            await page.locator('#sample-input').focus();
            const outline = await page.locator('#sample-input').evaluate(element => getComputedStyle(element).outlineWidth);
            if (parseFloat(outline) < 2) failures.push({page: name, theme, contrast, target: ['#sample-input'], summary: 'Keyboard focus outline is missing'});
          }
          checked++;
          if (process.env.THEME_SCREENSHOTS && ['learn_flashcard_deck','pbq_edit','course_detail','instructor_gradebook'].includes(name)) {
            await page.screenshot({path: path.join(output, `${name}-${theme}-${contrast}.png`), fullPage: true});
          }
        }
      }
      const finalEditorContent = await page.evaluate(() => Object.values(window.CKEDITOR?.instances || {}).map(editor => editor.getData()));
      if (JSON.stringify(originalEditorContent) !== JSON.stringify(finalEditorContent)) failures.push({page: name, summary: 'Theme switching changed saved rich-text content'});
      console.log(`${name}: checked four theme combinations`);
    }
    // The existing Follow device setting must continue to react while open.
    if (!process.env.THEME_ONLY) {
      pages.system_preference = pages.profile_edit.replace('data-theme-choice="light"', 'data-theme-choice="system"');
      await page.emulateMedia({colorScheme: 'light'});
      await page.goto('http://theme.test/page/system_preference');
      await page.emulateMedia({colorScheme: 'dark'});
      await page.waitForFunction(() => document.documentElement.dataset.bsTheme === 'dark');
      await page.emulateMedia({colorScheme: 'light'});
      await page.waitForFunction(() => document.documentElement.dataset.bsTheme === 'light');
      console.log('Follow device: live light/dark changes passed');
    }
  } finally {
    await browser.close();
  }
  fs.writeFileSync(path.join(output, 'contrast.json'), JSON.stringify({checked, failures}, null, 2));
  console.log(`${checked} page/theme combinations; ${failures.length} contrast failures`);
  if (failures.length) process.exitCode = 1;
}
main().catch(error => { console.error(error); process.exitCode = 1; });
