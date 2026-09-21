'use strict';
// Recheck pós-ajuste P17: dashboard renderiza, canvas com rótulo, zero erros.
const TOKEN = process.env.SADEN_VISUAL_TOKEN;
if (!TOKEN) {
  console.error('SADEN_VISUAL_TOKEN ausente');
  process.exit(1);
}
function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}
(async () => {
  const list = await (await fetch('http://127.0.0.1:9333/json/list')).json();
  const page = list.find((t) => t.type === 'page');
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((res, rej) => {
    ws.onopen = res;
    ws.onerror = rej;
  });
  let id = 0;
  const pending = new Map();
  const errs = [];
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) {
      pending.get(msg.id)(msg.result);
      pending.delete(msg.id);
    } else if (msg.method === 'Runtime.exceptionThrown') {
      errs.push(msg.params.exceptionDetails.text);
    }
  };
  const send = (method, params = {}) =>
    new Promise((res, rej) => {
      const cur = ++id;
      pending.set(cur, res);
      ws.send(JSON.stringify({ id: cur, method, params }));
      setTimeout(() => rej(new Error(`timeout ${method}`)), 20000);
    });
  const ev = async (expression) => {
    const r = await send('Runtime.evaluate', { expression, returnByValue: true });
    return r.result && r.result.value;
  };
  await send('Page.enable');
  await send('Runtime.enable');
  await send('Emulation.setDeviceMetricsOverride', { width: 1366, height: 900, deviceScaleFactor: 1, mobile: false });
  await send('Page.navigate', { url: 'http://localhost:3001' });
  await sleep(2000);
  await ev(`localStorage.setItem('saden_token','${TOKEN}'); location.reload();`);
  const t0 = Date.now();
  let cards = 0;
  while (Date.now() - t0 < 120000) {
    cards = await ev(`document.querySelectorAll('#price-cards .card').length`);
    if (cards >= 3) break;
    await sleep(1500);
  }
  const labelled = await ev(`[...document.querySelectorAll('canvas')].filter(c=>c.getAttribute('aria-label')).length`);
  const legend = await ev(`!!document.querySelector('.legend')`);
  console.log('cards:', cards, '| canvas com aria-label:', labelled, '| legenda mapa no DOM:', legend);
  console.log('pageErrors:', JSON.stringify(errs));
  const ok = cards >= 3 && labelled === 3 && errs.length === 0;
  console.log(ok ? 'RECHECK: OK' : 'RECHECK: FALHOU');
  ws.close();
  process.exit(ok ? 0 : 1);
})().catch((e) => {
  console.error(`RECHECK-FAIL: ${e.message}`);
  process.exit(1);
});
