/* Confirm the app explains a missing model file clearly.

Loads a site whose model weights are deliberately absent and reads the status
line the user would actually see.
*/
const fs = require('fs'), path = require('path'), { spawn } = require('child_process');
const root = path.resolve(__dirname, '..'), out = path.join(root, 'outputs');
const edge = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const port = 9261;
const url = 'http://127.0.0.1:' + (process.env.MISSING_PORT || 8780) + '/_site/';
const delay = ms => new Promise(r => setTimeout(r, ms));
let browser, ws, id = 0; const pending = new Map();

function send(m, p = {}) {
  return new Promise((res, rej) => {
    const n = ++id;
    const t = setTimeout(() => { pending.delete(n); rej(new Error('CDP timeout ' + m)); }, 60000);
    pending.set(n, { res, rej, t });
    ws.send(JSON.stringify({ id: n, method: m, params: p }));
  });
}
async function ev(e) {
  const r = await send('Runtime.evaluate', { expression: e, awaitPromise: true, returnByValue: true });
  if (r.exceptionDetails) return { __err: r.exceptionDetails.text };
  return r.result.value;
}

(async () => {
  const runDir = fs.mkdtempSync(path.join(out, 'missing-run-'));
  browser = spawn(edge, ['--headless=new', '--disable-gpu', '--no-first-run', '--disable-extensions',
    '--remote-debugging-port=' + port, '--user-data-dir=' + path.join(runDir, 'p'), 'about:blank'], { stdio: 'ignore' });
  let pages;
  for (let n = 0; n < 100; n++) {
    try { pages = await (await fetch('http://127.0.0.1:' + port + '/json/list')).json(); if (pages.some(p => p.type === 'page')) break; } catch (e) { }
    await delay(100);
  }
  ws = new WebSocket(pages.find(p => p.type === 'page').webSocketDebuggerUrl);
  await new Promise((r, j) => { ws.addEventListener('open', r, { once: true }); ws.addEventListener('error', j, { once: true }); });
  ws.addEventListener('message', e => {
    const m = JSON.parse(e.data);
    if (m.id && pending.has(m.id)) { const p = pending.get(m.id); pending.delete(m.id); clearTimeout(p.t); m.error ? p.rej(new Error(JSON.stringify(m.error))) : p.res(m.result); }
  });
  await send('Page.enable'); await send('Runtime.enable');
  await send('Page.navigate', { url });

  let status = '';
  for (let i = 0; i < 40; i++) {
    await delay(700);
    status = await ev('document.getElementById("modelStatusText") ? document.getElementById("modelStatusText").textContent : ""');
    if (/Chưa tải được|sẵn sàng/.test(status || '')) break;
  }
  const cls = await ev('document.getElementById("modelStatus") ? document.getElementById("modelStatus").className : ""');
  const mentions404 = /404/.test(status || '');
  const mentionsFolder = /model\/quant/.test(status || '');
  const result = { url, status, className: cls, mentions404, mentionsFolder };
  fs.writeFileSync(path.join(out, 'missing-model-validation.json'), JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result, null, 2));
  const ok = /Chưa tải được/.test(status) && mentions404 && mentionsFolder;
  console.log('\nTHONG BAO RO RANG:', ok);
  ws.close(); browser.kill();
  setTimeout(() => process.exit(ok ? 0 : 1), 200);
})().catch(e => { console.error('FATAL', e.message); if (browser) browser.kill(); process.exit(1); });
