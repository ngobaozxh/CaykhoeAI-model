/* Verify the site under a GitHub Pages style subpath.

GitHub Pages serves a repository at https://<user>.github.io/<repo>/, not at the
origin root. Every path, the service worker scope and the precache list have to
survive that prefix. This harness serves _site/ as /CayKhoeAI/ and drives a real
browser against it.

Assumes a static server is already listening on the port and serving a directory
that contains CayKhoeAI/ as a child.
*/
const fs = require('fs'), path = require('path'), { spawn } = require('child_process');
const root = path.resolve(__dirname, '..'), out = path.join(root, 'outputs');
const edge = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const port = 9251;
const base = `http://127.0.0.1:${process.env.SUBPATH_PORT || 8770}`;
const sub = '/CayKhoeAI/';
const delay = ms => new Promise(r => setTimeout(r, ms));
const report = { tests: [], exceptions: [], requests: [], base: base + sub };
const runDir = fs.mkdtempSync(path.join(out, 'subpath-run-'));
let browser, ws, id = 0; const pending = new Map();

function send(method, params = {}) {
  return new Promise((resolve, reject) => {
    const n = ++id;
    const timer = setTimeout(() => { pending.delete(n); reject(new Error('CDP timeout ' + method)); }, 90000);
    pending.set(n, { resolve, reject, timer });
    ws.send(JSON.stringify({ id: n, method, params }));
  });
}
async function evaluate(expression) {
  const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
  if (r.exceptionDetails) throw new Error(r.exceptionDetails.text + ' ' + JSON.stringify(r.exceptionDetails.exception));
  return r.result.value;
}
async function waitFor(expression, timeout = 90000) {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    try { if (await evaluate(expression)) return true; } catch (e) { }
    await delay(150);
  }
  throw new Error('Timed out: ' + expression);
}
function check(name, value, detail) {
  report.tests.push({ name, passed: !!value, ...(detail !== undefined ? { detail } : {}) });
  if (!value) throw new Error('Failed: ' + name);
}

(async () => {
  browser = spawn(edge, ['--headless=new', '--disable-gpu', '--no-first-run', '--disable-extensions',
    '--remote-debugging-port=' + port, '--user-data-dir=' + path.join(runDir, 'profile'), 'about:blank'], { stdio: 'ignore' });
  let pages;
  for (let n = 0; n < 100; n++) {
    try { pages = await (await fetch('http://127.0.0.1:' + port + '/json/list')).json(); if (pages.some(p => p.type === 'page')) break; } catch (e) { }
    await delay(100);
  }
  if (!pages) throw new Error('Browser CDP unavailable');
  ws = new WebSocket(pages.find(p => p.type === 'page').webSocketDebuggerUrl);
  await new Promise((r, j) => { ws.addEventListener('open', r, { once: true }); ws.addEventListener('error', j, { once: true }); });
  ws.addEventListener('message', e => {
    const m = JSON.parse(e.data);
    if (m.id && pending.has(m.id)) {
      const p = pending.get(m.id); pending.delete(m.id); clearTimeout(p.timer);
      m.error ? p.reject(new Error(JSON.stringify(m.error))) : p.resolve(m.result);
    }
    if (m.method === 'Runtime.exceptionThrown') report.exceptions.push(m.params.exceptionDetails);
    if (m.method === 'Network.responseReceived') {
      const r = m.params.response;
      if (r.url.startsWith(base)) report.requests.push({ url: r.url.replace(base, ''), status: r.status });
    }
    if (m.method === 'Network.loadingFailed') {
      report.requests.push({ url: (m.params.requestId || '') + ' FAILED', status: 0, error: m.params.errorText });
    }
  });
  await send('Page.enable'); await send('Runtime.enable'); await send('Network.enable');
  await send('Emulation.setDeviceMetricsOverride', { width: 1280, height: 900, deviceScaleFactor: 1, mobile: false });

  // --- load at the subpath -------------------------------------------------
  await send('Page.navigate', { url: base + sub });
  await waitFor('window.__cayKhoeAI && window.__cayKhoeAI.ready()');
  check('site loads and the model initializes at a subpath', true);
  report.runtime = await evaluate('({tf:tf.version.tfjs,backend:tf.getBackend(),status:document.getElementById("modelStatusText").textContent})');

  // Visual proof that the published tree renders from the subpath.
  {
    const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
    fs.writeFileSync(path.join(out, 'subpath-preview.png'), Buffer.from(shot.data, 'base64'));
  }

  const bad = report.requests.filter(r => r.status >= 400 || r.error);
  check('no request under the subpath returns an error', bad.length === 0,
    bad.length ? JSON.stringify(bad.slice(0, 8)) : `${report.requests.length} requests, all 2xx`);
  report.badRequests = bad;

  // --- the model actually ran ---------------------------------------------
  const inferred = await evaluate(`(async()=>{const p=await window.__cayKhoeAI.predictAsync(new Float32Array(224*224*3).fill(.5));return {classes:p.length,sum:p.reduce((a,b)=>a+b,0)};})()`);
  check('model produces 14 valid probabilities at a subpath',
    inferred.classes === 14 && Math.abs(inferred.sum - 1) < .001, JSON.stringify(inferred));
  report.inference = inferred;

  // --- fonts ---------------------------------------------------------------
  const fonts = await evaluate(`(()=>{const cs=getComputedStyle(document.getElementById('heroTitle'));return {family:cs.fontFamily.split(',')[0],loaded:document.fonts.check('500 58px Fraunces'),faces:document.fonts.size};})()`);
  check('hero font is Fraunces and reports loaded', fonts.loaded && /Fraunces/.test(fonts.family), JSON.stringify(fonts));
  report.fonts = fonts;

  // --- service worker scope ------------------------------------------------
  const sw = await evaluate(`(async()=>{const r=await navigator.serviceWorker.getRegistration();if(!r)return {registered:false};return {registered:true,scope:new URL(r.scope).pathname,active:!!r.active};})()`);
  check('service worker registers', sw.registered, JSON.stringify(sw));
  check('service worker scope is the subpath', sw.scope === sub, JSON.stringify(sw));
  report.serviceWorker = sw;

  // --- precache ------------------------------------------------------------
  await waitFor('document.getElementById("offlineStatus").textContent.includes("Đã lưu đủ")');
  check('precache reports complete at the subpath', true);
  const cache = await evaluate(`(async()=>{const k=await caches.keys();const c=await caches.open(k.find(x=>x.startsWith('caykhoeai-')));const m=await c.keys();return {caches:k.length,entries:m.length,sample:m.slice(0,3).map(r=>new URL(r.url).pathname)};})()`);
  check('every precached entry sits under the subpath',
    cache.sample.every(p => p.startsWith(sub)), JSON.stringify(cache));
  report.cache = cache;

  // --- offline reload ------------------------------------------------------
  await send('Network.emulateNetworkConditions', { offline: true, latency: 0, downloadThroughput: 0, uploadThroughput: 0 });
  await send('Page.reload');
  await waitFor('window.__cayKhoeAI && window.__cayKhoeAI.ready()');
  check('reload while offline still initializes at the subpath', true);
  const off = await evaluate(`(async()=>{const p=await __cayKhoeAI.predictAsync(new Float32Array(224*224*3).fill(.5));return p.length===14;})()`);
  check('offline inference works at the subpath', off);

  check('no uncaught JS exceptions', report.exceptions.length === 0,
    report.exceptions.length ? JSON.stringify(report.exceptions[0]).slice(0, 300) : 'none');
  report.ok = true;
})().catch(e => { report.ok = false; report.error = e.stack; console.error(e); }).finally(() => {
  fs.writeFileSync(path.join(out, 'subpath-validation.json'), JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report, null, 2));
  if (ws) ws.close(); if (browser) browser.kill();
  setTimeout(() => process.exit(report.ok ? 0 : 1), 200);
});
