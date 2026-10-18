// Exercise actual media decoding and error/retry behavior on rendered Django pages.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require('playwright-core');
const axe = require('axe-core');
const fixture = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const output = process.argv[3] || '/tmp/audio-player-results';
fs.mkdirSync(output, {recursive:true});
const root = path.resolve(__dirname, '..');

async function main() {
  const browser = await chromium.launch({executablePath:process.env.CHROMIUM_PATH || undefined,
    headless:true, args:['--no-sandbox', '--disable-dev-shm-usage']});
  const context = await browser.newContext({viewport:{width:1440,height:1050}});
  let broken = false;
  let mediaRequests = 0;
  await context.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (url.pathname.startsWith('/page/')) return route.fulfill({contentType:'text/html', body:fixture.pages[url.pathname.slice(6)]});
    if (url.href === fixture.external_url || url.pathname === fixture.stream_url) {
      mediaRequests++;
      if (broken) return route.fulfill({contentType:'text/html', body:'<html>A sharing page, not an audio stream</html>'});
      return route.fulfill({contentType:'audio/wav', headers:{'Accept-Ranges':'bytes'}, body:Buffer.from(fixture.wav, 'base64')});
    }
    let file;
    if (url.pathname.endsWith('/bootstrap.min.css')) file = require.resolve('bootstrap/dist/css/bootstrap.min.css');
    else if (url.pathname.endsWith('/bootstrap.bundle.min.js')) file = require.resolve('bootstrap/dist/js/bootstrap.bundle.min.js');
    else if (/jquery.*\.js$/.test(url.pathname)) file = require.resolve('jquery/dist/jquery.min.js');
    else if (url.pathname.startsWith('/static/labtech/')) file = path.join(root, 'app/static', url.pathname.slice(8));
    if (file && fs.existsSync(file)) return route.fulfill({path:file, contentType:file.endsWith('.css')?'text/css':'application/javascript'});
    return route.fulfill({status:204, body:''});
  });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  try {
    for (const kind of ['external', 'upload']) {
      await page.goto('https://labtech.test/page/'+kind);
      assert.equal(await page.locator('[data-audio-player]').count(), 1, 'Audio uses a shared player card');
      const audio = page.locator('audio');
      await page.waitForFunction(() => document.querySelector('audio').readyState >= 1);
      assert.equal(await audio.getAttribute('crossorigin'), null, 'Do not impose a new CORS requirement');
      const playerWidth = (await audio.boundingBox()).width;
      const cardWidth = (await page.locator('[data-audio-player]').boundingBox()).width;
      assert.ok(playerWidth > cardWidth * 0.8, 'Both sources use full-width controls');
      await audio.evaluate(a => a.play());
      await page.waitForFunction(() => document.querySelector('audio').currentTime > 0.1);
      assert.match(await page.locator('[data-audio-status]').innerText(), /Playing/);
      await audio.evaluate(a => {a.pause(); a.currentTime=1;});
      assert.match(await page.locator('[data-audio-status]').innerText(), /Paused/);
      assert.ok(await audio.evaluate(a => a.currentTime >= 1));
      await page.waitForFunction(() => document.querySelector('audio').readyState >= 3);
      await audio.evaluate(a => a.dispatchEvent(new Event('stalled')));
      assert.match(await page.locator('[data-audio-status]').innerText(), /Paused/, 'Buffered audio should not show a stalled warning');
      assert.equal(await page.locator('.mark-complete-btn').count(), 1, 'Completion remains available');
    }
    broken = true;
    await page.goto('https://labtech.test/page/external');
    await page.waitForFunction(() => document.querySelector('audio').error !== null);
    assert.match(await page.locator('[data-audio-status]').innerText(), /Unable to play/);
    const source = page.getByRole('link', {name:'Open audio source'});
    assert.equal(await source.getAttribute('href'), fixture.external_url);
    assert.equal(await source.getAttribute('target'), '_blank');
    assert.equal(await page.getByRole('button', {name:'Retry loading'}).isVisible(), true);
    const count = mediaRequests;
    broken = false;
    await page.getByRole('button', {name:'Retry loading'}).click();
    await page.waitForFunction(() => document.querySelector('audio').readyState >= 1 && !document.querySelector('audio').error);
    assert.ok(mediaRequests > count, 'Retry requests the media again');
    await page.locator('audio').evaluate(a => a.play());
    await page.waitForFunction(() => document.querySelector('audio').currentTime > 0.1);
    await page.locator('audio').evaluate(a => a.pause());

    for (const theme of ['light', 'dark']) for (const contrast of ['standard', 'high']) {
      await page.evaluate(({theme,contrast}) => {
        document.documentElement.dataset.bsTheme=theme;
        document.documentElement.dataset.contrast=contrast;
      }, {theme,contrast});
      await page.evaluate(async () => {
        await new Promise(requestAnimationFrame);
        await Promise.all(document.getAnimations().map(animation => animation.finished.catch(() => {})));
      });
      await page.addScriptTag({path:require.resolve('axe-core/axe.min.js')});
      const results = await page.evaluate(async contrast => axe.run('[data-audio-player]', {
        rules:{'color-contrast-enhanced':{enabled:contrast === 'high'}},
      }), contrast);
      assert.deepEqual(results.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))})), [], theme+'/'+contrast);
      await page.screenshot({path:path.join(output, theme+'-'+contrast+'.png'), fullPage:true});
    }
    await page.setViewportSize({width:390,height:844});
    if (await page.locator('.course-sidebar.is-open').count()) await page.locator('#panel-toggle-btn').click();
    await page.evaluate(async () => {
      await new Promise(requestAnimationFrame);
      await Promise.all(document.getAnimations().map(animation => animation.finished.catch(() => {})));
    });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true, 'No mobile overflow');
    const audio = await page.locator('audio').boundingBox();
    await page.screenshot({path:path.join(output,'mobile.png'), fullPage:true});
    assert.ok(audio.width > 250 && audio.x + audio.width <= 390, 'Usable mobile player: '+JSON.stringify(audio));
    broken = true;
    await page.goto('https://labtech.test/page/external');
    await page.waitForFunction(() => document.querySelector('audio').error !== null);
    await page.addScriptTag({path:require.resolve('axe-core/axe.min.js')});
    for (const theme of ['light', 'dark']) for (const contrast of ['standard', 'high']) {
      await page.evaluate(async ({theme,contrast}) => {
        document.documentElement.dataset.bsTheme=theme;
        document.documentElement.dataset.contrast=contrast;
        await new Promise(requestAnimationFrame);
        await Promise.all(document.getAnimations().map(animation => animation.finished.catch(() => {})));
      }, {theme,contrast});
      const result = await page.evaluate(async contrast => axe.run('[data-audio-player]', {
        rules:{'color-contrast-enhanced':{enabled:contrast === 'high'}},
      }), contrast);
      assert.deepEqual(result.violations.map(v=>v.id), [], 'Error state '+theme+'/'+contrast);
    }
    assert.deepEqual(errors, []);
    console.log('Audio playback, seeking, external failure/retry, links, completion, themes and mobile: PASS');
  } finally {await browser.close();}
}
main().catch(error => {console.error(error); process.exitCode=1;});
