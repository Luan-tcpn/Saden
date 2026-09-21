'use strict';
// P17: checagem mobile (390x844) + acessibilidade básica via CDP.
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
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) {
      pending.get(msg.id)(msg.result);
      pending.delete(msg.id);
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
  await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 2, mobile: true });
  await send('Page.navigate', { url: 'http://localhost:3001' });
  await sleep(2500);
  // auth mobile sem token
  const authOverflow = await ev(`document.documentElement.scrollWidth - document.documentElement.clientWidth`);
  console.log('auth mobile overflow-x (px):', authOverflow);
  await ev(`localStorage.setItem('saden_token','${TOKEN}'); location.reload();`);
  const t0 = Date.now();
  let cards = 0;
  while (Date.now() - t0 < 120000) {
    cards = await ev(`document.querySelectorAll('#price-cards .card').length`);
    if (cards >= 3) break;
    await sleep(1500);
  }
  await sleep(1200);
  const dashOverflow = await ev(`document.documentElement.scrollWidth - document.documentElement.clientWidth`);
  console.log('dashboard mobile cards:', cards, '| overflow-x (px):', dashOverflow);
  const a11y = await ev(`JSON.stringify({
    inputsSemLabel: [...document.querySelectorAll('input,select')].filter(el => {
      const lbl = el.closest('label');
      const aria = el.getAttribute('aria-label');
      return !lbl && !aria;
    }).length,
    botoesSemNome: [...document.querySelectorAll('button')].filter(b => !(b.textContent||'').trim() && !b.getAttribute('aria-label')).length,
    htmlLang: document.documentElement.lang,
    canvasSemRole: [...document.querySelectorAll('canvas')].filter(c => !c.getAttribute('role') && !c.getAttribute('aria-label')).length
  })`);
  console.log('a11y:', a11y);
  const shot = await send('Page.captureScreenshot', { format: 'png' });
  require('fs').writeFileSync(require('path').join(__dirname, '..', 'tmp', 'shots', 'shot-mobile.png'), Buffer.from(shot.data, 'base64'));
  ws.close();
  // restaura viewport desktop para as próximas sessões
  console.log('MOBILE: capturado');
})().catch((e) => {
  console.error(`MOBILE-FAIL: ${e.message}`);
  process.exit(1);
});
