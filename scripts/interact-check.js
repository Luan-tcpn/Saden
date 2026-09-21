'use strict';
// P14: interações no navegador (troca de filtro + clique no mapa).
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
  await send('Page.navigate', { url: 'http://localhost:3001' });
  await sleep(2500);

  // 1) troca commodity -> Milho + Consultar -> KPI atualiza
  await ev(`document.querySelector('[data-nav="dashboard"]').click()`);
  await sleep(500);
  await ev(`document.querySelector('#sel-commodity').value = 'milho'`);
  await ev(`document.querySelector('#sel-commodity').dispatchEvent(new Event('change'))`);
  await ev(`document.querySelector('#btn-apply').click()`);
  const t0 = Date.now();
  let kpi = '';
  while (Date.now() - t0 < 120000) {
    kpi = await ev(`document.querySelector('#price-cards .card h3').textContent`);
    if (/milho/i.test(kpi || '')) break;
    await sleep(2000);
  }
  console.log('filtro commodity -> KPI:', JSON.stringify(kpi));

  // 2) mapa -> clique no centro -> popup + painel do ponto
  await ev(`document.querySelector('[data-nav="mapa"]').click()`);
  await sleep(1500);
  await ev(`document.querySelector('#map').dispatchEvent(new MouseEvent('click', {bubbles:true}))`);
  // clique real via coordenadas Leaflet: usa o centro do mapa
  await ev(`window.__sadenMapClicked = false`);
  const clicked = await ev(`(function(){ const m = document.querySelector('#map'); const r = m.getBoundingClientRect(); const x = r.left + r.width/2, y = r.top + r.height/2; const el = document.elementFromPoint(x, y); if(!el) return 'no-el'; el.dispatchEvent(new MouseEvent('click', {bubbles:true, clientX:x, clientY:y})); return 'dispatched'; })()`);
  const t1 = Date.now();
  let popup = false;
  while (Date.now() - t1 < 90000) {
    popup = await ev(`!!document.querySelector('#map .leaflet-popup-content') || !document.querySelector('#map-result').classList.contains('hidden')`);
    if (popup) break;
    await sleep(2000);
  }
  console.log('clique mapa -> dispatched:', clicked, '| resultado visível:', popup);
  const shot = await send('Page.captureScreenshot', { format: 'png' });
  require('fs').writeFileSync(require('path').join(__dirname, '..', 'tmp', 'shots', 'shot-mapa-click.png'), Buffer.from(shot.data, 'base64'));
  console.log('pageErrors:', JSON.stringify(errs));
  const ok = /milho/i.test(kpi || '') && popup && errs.length === 0;
  console.log(ok ? 'INTERACT: OK' : 'INTERACT: FALHOU');
  ws.close();
  process.exit(ok ? 0 : 1);
})().catch((e) => {
  console.error(`INTERACT-FAIL: ${e.message}`);
  process.exit(1);
});
