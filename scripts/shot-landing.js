'use strict';
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
  const shot = async (name) => {
    const s = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true });
    require('fs').writeFileSync(require('path').join(__dirname, '..', 'tmp', 'shots', name), Buffer.from(s.data, 'base64'));
  };
  await send('Page.enable');
  await send('Runtime.enable');
  await send('Emulation.clearDeviceMetricsOverride', {});
  await send('Emulation.setDeviceMetricsOverride', { width: 1366, height: 900, deviceScaleFactor: 1, mobile: false });
  await send('Page.navigate', { url: 'http://localhost:3001/' });
  await sleep(2500);
  await ev(`localStorage.clear(); localStorage.setItem('saden_theme','dark'); location.reload();`);
  await sleep(2500);
  await ev(`document.documentElement.style.scrollBehavior = 'auto'`);
  await ev(`(async () => { const h = document.body.scrollHeight; for (let y = 0; y < h; y += 300) { window.scrollTo(0, y); await new Promise(r => setTimeout(r, 200)); } window.scrollTo(0, document.body.scrollHeight); await new Promise(r => setTimeout(r, 1800)); window.scrollTo(0, 0); })()`);
  await sleep(1500);
  await shot('shot-landing-dark.png');
  await send('Emulation.clearDeviceMetricsOverride', {});
  await send('Emulation.setDeviceMetricsOverride', { width: 1366, height: 900, deviceScaleFactor: 1, mobile: false });
  await send('Page.navigate', { url: 'http://localhost:3001/' });
  await sleep(2500);
  await ev(`localStorage.clear(); localStorage.setItem('saden_theme','light'); location.reload();`);
  await sleep(2500);
  // Rola devagar até o fim para disparar o reveal de todas as seções antes da captura.
  // (scroll-behavior suave desligado na captura: ele impede o loop de alcançar o fim.)
  await ev(`document.documentElement.style.scrollBehavior = 'auto'`);
  await ev(`(async () => { const h = document.body.scrollHeight; for (let y = 0; y < h; y += 300) { window.scrollTo(0, y); await new Promise(r => setTimeout(r, 200)); } window.scrollTo(0, document.body.scrollHeight); await new Promise(r => setTimeout(r, 1800)); window.scrollTo(0, 0); })()`);
  await sleep(1500);
  await sleep(1200);
  await shot('shot-landing-light.png');
  await send('Emulation.clearDeviceMetricsOverride', {});
  await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: false });
  await send('Page.navigate', { url: 'http://localhost:3001/' });
  await sleep(2500);
  await ev(`document.documentElement.style.scrollBehavior = 'auto'`);
  await ev(`(async () => { const h = document.body.scrollHeight; for (let y = 0; y < h; y += 400) { window.scrollTo(0, y); await new Promise(r => setTimeout(r, 250)); } window.scrollTo(0, document.body.scrollHeight); await new Promise(r => setTimeout(r, 1800)); window.scrollTo(0, 0); })()`);
  await sleep(1500);
  await shot('shot-landing-mobile2.png');
  ws.close();
  console.log('SHOTS-OK');
})().catch((e) => {
  console.error(e.message);
  process.exit(1);
});
