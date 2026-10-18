// Real Django pages in Chromium; all network requests served locally.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require('playwright-core');
const axe = require('axe-core');
const fixture = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const output = process.argv[3] || '/tmp/pbq-workspace-results';
fs.mkdirSync(output, {recursive: true});
const root = path.resolve(__dirname, '..');

async function main() {
  const browser = await chromium.launch({executablePath: process.env.CHROMIUM_PATH || undefined,
    headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage']});
  const context = await browser.newContext({viewport: {width: 1440, height: 1050}});
  let rejectText = false;
  const requests = [];
  const serve = async route => {
    const url = new URL(route.request().url());
    if (url.pathname.startsWith('/page/')) return route.fulfill({contentType: 'text/html', body: fixture.pages[url.pathname.slice(6)]});
    const asset = fixture.assets[url.pathname + url.search];
    if (asset) {
      requests.push(url.pathname + url.search);
      if (rejectText && url.search) return route.fulfill({status: 403, body: 'Forbidden'});
      return route.fulfill({contentType: asset.contentType, headers: asset.headers, body: Buffer.from(asset.body, 'base64')});
    }
    let file;
    if (url.pathname.endsWith('/bootstrap.min.css')) file = require.resolve('bootstrap/dist/css/bootstrap.min.css');
    else if (url.pathname.endsWith('/bootstrap.bundle.min.js')) file = require.resolve('bootstrap/dist/js/bootstrap.bundle.min.js');
    else if (/jquery.*\.js$/.test(url.pathname)) file = require.resolve('jquery/dist/jquery.min.js');
    else if (url.pathname.startsWith('/static/labtech/')) file = path.join(root, 'app/static', url.pathname.slice(8));
    if (file && fs.existsSync(file)) return route.fulfill({path: file, contentType: file.endsWith('.css') ? 'text/css' : 'application/javascript'});
    return route.fulfill({status: 204, body: ''});
  };
  await context.route('**/*', serve);
  const page = await context.newPage();
  const jsErrors = [];
  page.on('pageerror', error => jsErrors.push(error.message));
  try {
    await page.goto('http://pbq.test/page/empty');
    const questionTabs = page.locator('[data-pbq-tabs="questions"] [role="tab"]');
    const artifactTabs = page.locator('[data-pbq-tabs="artifacts"] [role="tab"]');
    assert.equal(await questionTabs.count(), 5, 'Five numbered question tabs');
    assert.equal(await artifactTabs.count(), 5, 'Five numbered artifact tabs');
    assert.equal(await page.locator('[data-pbq-question]:visible').count(), 1);
    assert.equal(await page.locator('[data-pbq-submit]').isDisabled(), true);
    assert.match(await page.locator('[data-pbq-progress]').innerText(), /0.*5.*0%/);
    const evidence = await page.locator('.pbq-evidence').boundingBox();
    const answers = await page.locator('.pbq-answers').boundingBox();
    assert.ok(evidence.x < answers.x && Math.abs(evidence.width - answers.width) < 3, 'Equal left/right columns');

    // Evidence is read in place; markup must stay literal and never execute.
    await artifactTabs.nth(1).click();
    await page.waitForFunction(() => document.querySelector('[data-pbq-artifact]:not([hidden]) pre')?.textContent.includes('<script>'));
    assert.equal(await page.evaluate(() => window.unsafeEvidence), undefined);
    assert.match(await page.locator('[data-pbq-artifact]:visible pre').innerText(), /09:42:17/);
    const fetched = requests.filter(url => url.endsWith('?format=text')).length;
    await artifactTabs.nth(0).click(); await artifactTabs.nth(1).click();
    assert.equal(requests.filter(url => url.endsWith('?format=text')).length, fetched, 'Tab revisits reuse loaded text');
    await artifactTabs.nth(1).focus(); await page.keyboard.press('ArrowRight');
    assert.equal(await artifactTabs.nth(2).getAttribute('aria-selected'), 'true');
    await page.keyboard.press('Home');
    assert.equal(await artifactTabs.nth(0).getAttribute('aria-selected'), 'true');
    await page.keyboard.press('End');
    assert.equal(await artifactTabs.nth(4).getAttribute('aria-selected'), 'true');
    await questionTabs.nth(0).focus(); await page.keyboard.press('ArrowRight');
    assert.equal(await questionTabs.nth(1).getAttribute('aria-selected'), 'true');
    await page.locator('[data-pbq-previous]').click();
    assert.equal(await questionTabs.nth(0).getAttribute('aria-selected'), 'true');
    await page.locator('[data-pbq-next]').click();
    assert.equal(await questionTabs.nth(1).getAttribute('aria-selected'), 'true');

    // Complete each question, retaining all fields while switching tabs.
    for (let i = 0; i < 5; i++) {
      await questionTabs.nth(i).click();
      const panel = page.locator('[data-pbq-question]:visible');
      for (const group of await panel.locator('[data-pbq-answer]').all()) {
        const radios = group.locator('input[type="radio"]');
        if (await radios.count()) await radios.last().check();
        else if (await group.locator('select').count()) {
          const select = group.locator('select');
          await select.selectOption(await select.locator('option').last().getAttribute('value'));
        } else await group.locator('input, textarea').fill('A response based on the evidence.');
      }
      assert.match(await questionTabs.nth(i).getAttribute('aria-label'), /Complete/);
    }
    assert.match(await page.locator('[data-pbq-progress]').innerText(), /5.*5.*100%/);
    assert.match(await page.locator('[data-pbq-readiness]').innerText(), /ready to submit/i);
    assert.equal(await page.locator('[data-pbq-submit]').isEnabled(), true);
    await questionTabs.nth(0).click();
    const blank = page.locator('[data-pbq-question]:visible input[type="text"]').first();
    await blank.fill('   ');
    assert.match(await page.locator('[data-pbq-progress]').innerText(), /4.*5.*80%/);
    assert.equal(await page.locator('[data-pbq-submit]').isDisabled(), true);
    const blocked = await page.locator('[data-pbq-form]').evaluate(form => {
      const event = new SubmitEvent('submit', {bubbles:true, cancelable:true, submitter:form.querySelector('[data-pbq-submit]')});
      form.dispatchEvent(event);
      const leaving = new Event('beforeunload', {cancelable:true});
      window.dispatchEvent(leaving);
      return {submitBlocked:event.defaultPrevented, unsavedWarning:leaving.defaultPrevented};
    });
    assert.deepEqual(blocked, {submitBlocked:true, unsavedWarning:true});
    await blank.fill('restored');
    const data = await page.locator('[data-pbq-form]').evaluate(form => Object.fromEntries(new FormData(form)));
    assert.equal(Object.keys(data).filter(name => name.startsWith('answer_')).length, 8);
    assert.equal(await page.locator('[data-pbq-save-state]').innerText(), 'Unsaved changes');
    // Save and submit remain real form posts, with their original action values.
    await page.locator('[data-pbq-form]').evaluate(form => form.addEventListener('submit', event => {
      event.preventDefault(); window.testSubmitter = event.submitter.value;
    }));
    await page.locator('[data-pbq-submit]').click();
    assert.equal(await page.evaluate(() => window.testSubmitter), 'submit');
    await page.locator('[name="action"][value="save"]').click();
    assert.equal(await page.evaluate(() => window.testSubmitter), 'save');

    // All tab states in all four palettes retain readable text.
    await page.addScriptTag({content: axe.source});
    for (const theme of ['light', 'dark']) for (const contrast of ['standard', 'high']) {
      await page.evaluate(({theme, contrast}) => {
        document.documentElement.dataset.bsTheme = theme;
        document.documentElement.dataset.contrast = contrast;
      }, {theme, contrast});
      for (let index = 0; index < 5; index++) {
        await questionTabs.nth(index).click(); await artifactTabs.nth(index).click();
        await page.waitForTimeout(350);
        const result = await page.evaluate(contrast => axe.run('.pbq-workspace', {
          runOnly: [contrast === 'high' ? 'color-contrast-enhanced' : 'color-contrast', 'aria-valid-attr-value', 'aria-required-children'],
        }), contrast);
        assert.deepEqual(result.violations.map(v => ({id:v.id, nodes:v.nodes.map(n=>n.failureSummary)})), [], `${theme}/${contrast}, tab ${index+1}`);
      }
      await questionTabs.nth(0).click(); await artifactTabs.nth(1).click();
      await page.screenshot({path: path.join(output, `${theme}-${contrast}.png`), fullPage: true});
    }
    await page.setViewportSize({width: 390, height: 850});
    const left = await page.locator('.pbq-evidence').boundingBox();
    const right = await page.locator('.pbq-answers').boundingBox();
    assert.ok(right.y >= left.y + left.height, 'Panels stack on mobile');
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'No mobile horizontal overflow');
    await page.screenshot({path: path.join(output, 'mobile.png'), fullPage:true});

    await page.goto('http://pbq.test/page/saved');
    assert.match(await page.locator('[data-pbq-progress]').innerText(), /1.*5.*20%/);
    assert.equal(await page.locator('#pbq-question-tab-2').getAttribute('aria-selected'), 'true', 'Resume at first unfinished question');
    assert.equal(await page.locator('[name="revision"]').inputValue(), '1');
    await page.goto('http://pbq.test/page/errors');
    assert.equal(await page.locator('#pbq-question-tab-2').getAttribute('aria-selected'), 'true', 'Reveal first question with server errors');
    assert.equal(await page.locator('#pbq-errors').evaluate(el => el === document.activeElement), true);
    await page.goto('http://pbq.test/page/preview');
    assert.equal(await page.locator('[data-pbq-submit]').count(), 0);
    assert.equal(await page.locator('[data-pbq-question]:visible').count(), 1);
    rejectText = true;
    await page.locator('#pbq-artifact-tab-2').click();
    await page.locator('[data-pbq-artifact]:visible [data-pbq-retry]').waitFor({state:'visible'});
    rejectText = false;
    await page.locator('[data-pbq-artifact]:visible [data-pbq-retry]').click();
    await page.waitForFunction(() => document.querySelector('[data-pbq-artifact]:not([hidden]) pre')?.textContent.includes('09:42:17'));
    assert.deepEqual(jsErrors, []);
    const noJS = await browser.newContext({javaScriptEnabled:false});
    await noJS.route('**/*', serve);
    const fallback = await noJS.newPage();
    await fallback.goto('http://pbq.test/page/empty');
    assert.equal(await fallback.locator('[data-pbq-question]:visible').count(), 5, 'No-JS answers remain available');
    assert.equal(await fallback.locator('[data-pbq-submit]').isEnabled(), true);
    assert.equal(await fallback.locator('iframe.pbq-text-fallback').count(), 4);
    assert.match(await fallback.frameLocator('iframe.pbq-text-fallback').first().locator('body').innerText(), /09:42:17/);
    await noJS.close();
    console.log('PBQ tabs, inline evidence, completion, resume/errors, preview, retry, themes, mobile and submission: PASS');
  } finally { await browser.close(); }
}
main().catch(error => { console.error(error); process.exitCode=1; });
