'use strict';
// Validação visual P14: pilota Edge headless via CDP (WebSocket global do Node 22,
// sem dependências), injeta JWT, captura telas e coleta erros de console/rede.
// Uso: $env:SADEN_VISUAL_TOKEN="<jwt>"; node scripts/visual-check.js
// Pré-requisito: Edge com --remote-debugging-port=9333 aberto.
const fs = require('fs');
const path = require('path');

const APP = 'http://localhost:3001';
const TOKEN = process.env.SADEN_VISUAL_TOKEN;
const SHOTS = path.join(__dirname, '..', 'tmp', 'shots');
if (!TOKEN) {
  console.error('SADEN_VISUAL_TOKEN ausente');
  process.exit(1);
}
fs.mkdirSync(SHOTS, { recursive: true });

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function cdpConnect() {
  const list = await (await fetch('http://127.0.0.1:9333/json/list')).json();
  const page = list.find((t) => t.type === 'page');
  if (!page) throw new Error('Sem aba page no Edge headless');
  const ws = new WebSocket(page.webSocketDebuggerUrl, [], { maxPayload: 256 * 1024 * 1024 });
  await new Promise((res, rej) => {
    ws.onopen = res;
    ws.onerror = rej;
  });
  let id = 0;
  const pending = new Map();
  const events = { console: [], errors: [], failed: [] };
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) {
      const { res, rej } = pending.get(msg.id);
      pending.delete(msg.id);
      if (msg.error) rej(new Error(msg.error.message));
      else res(msg.result);
    } else if (msg.method) {
      if (msg.method === 'Runtime.consoleAPICalled' && msg.params.type === 'error') {
        events.console.push(msg.params.args.map((a) => a.value ?? a.description).join(' '));
      }
      if (msg.method === 'Runtime.exceptionThrown') {
        events.errors.push(msg.params.exceptionDetails.text);
      }
      if (msg.method === 'Log.entryAdded' && ['error'].includes(msg.params.entry.level)) {
        events.errors.push(msg.params.entry.text);
      }
      if (msg.method === 'Network.loadingFailed') {
        events.failed.push(msg.params.errorText);
      }
    }
  };
  const send = (method, params = {}) =>
    new Promise((res, rej) => {
      const cur = ++id;
      pending.set(cur, { res, rej });
      ws.send(JSON.stringify({ id: cur, method, params }));
      setTimeout(() => {
        if (pending.has(cur)) {
          pending.delete(cur);
          rej(new Error(`CDP timeout: ${method}`));
        }
      }, 20000);
    });
  return { send, events, close: () => ws.close() };
}

async function waitFor(send, expr, timeoutMs = 60000) {
  const t0 = Date.now();
  for (;;) {
    const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true });
    if (r.result && r.result.value) return true;
    if (Date.now() - t0 > timeoutMs) throw new Error(`waitFor expirou: ${expr}`);
    await sleep(1000);
  }
}

(async () => {
  const { send, events, close } = await cdpConnect();
  await send('Page.enable');
  await send('Runtime.enable');
  await send('Log.enable');
  await send('Network.enable');
  await send('Emulation.setDeviceMetricsOverride', {
    width: 1366,
    height: 900,
    deviceScaleFactor: 1,
    mobile: false,
  });

  // 1) tela de auth
  await send('Page.navigate', { url: APP });
  await waitFor(send, `!!document.querySelector('#form-login')`);
  await sleep(1000);
  const auth = await send('Page.captureScreenshot', { format: 'png' });
  fs.writeFileSync(path.join(SHOTS, 'shot-auth.png'), Buffer.from(auth.data, 'base64'));

  // 2) login via token + dashboard
  await send('Runtime.evaluate', {
    expression: `localStorage.setItem('saden_token','${TOKEN}'); location.reload();`,
  });
  await waitFor(send, `document.querySelectorAll('#price-cards .card').length >= 3`, 120000);
  await sleep(1500);
  const dash = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true });
  fs.writeFileSync(path.join(SHOTS, 'shot-dashboard.png'), Buffer.from(dash.data, 'base64'));
  const dashState = await send('Runtime.evaluate', {
    expression: `JSON.stringify({status: document.querySelector('#dash-status').textContent, cards: document.querySelectorAll('#price-cards .card').length})`,
    returnByValue: true,
  });

  // 3) mapa
  await send('Runtime.evaluate', { expression: `document.querySelector('[data-nav="mapa"]').click()` });
  await waitFor(send, `!!document.querySelector('#map.leaflet-container')`);
  await sleep(2500);
  const mapa = await send('Page.captureScreenshot', { format: 'png' });
  fs.writeFileSync(path.join(SHOTS, 'shot-mapa.png'), Buffer.from(mapa.data, 'base64'));

  // 4) relatório (gera via backend; pode levar ~1-2min sem cache)
  await send('Runtime.evaluate', { expression: `document.querySelector('[data-nav="relatorio"]').click(); document.querySelector('#btn-report').click();` });
  await waitFor(send, `!!document.querySelector('#report-body h1')`, 180000);
  await sleep(800);
  const rep = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true });
  fs.writeFileSync(path.join(SHOTS, 'shot-relatorio.png'), Buffer.from(rep.data, 'base64'));

  close();
  console.log(JSON.stringify({ dashboard: JSON.parse(dashState.result.value), consoleErrors: events.console, pageErrors: events.errors, netFailed: events.failed }, null, 1));
})().catch((e) => {
  console.error(`VISUAL-FAIL: ${e.message}`);
  process.exit(1);
});
