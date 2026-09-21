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
      setTimeout(() => rej(new Error(`timeout ${method}`)), 25000);
    });
  const ev = async (expression) => {
    const r = await send('Runtime.evaluate', { expression, returnByValue: true });
    return r.result && r.result.value;
  };
  const shot = async (name) => {
    const s = await send('Page.captureScreenshot', { format: 'png' });
    require('fs').writeFileSync(require('path').join(__dirname, '..', 'tmp', 'shots', name), Buffer.from(s.data, 'base64'));
  };
  await send('Page.enable');
  await send('Runtime.enable');
  await send('Emulation.clearDeviceMetricsOverride', {});
  await send('Emulation.setDeviceMetricsOverride', { width: 1366, height: 900, deviceScaleFactor: 1, mobile: false });
  await send('Page.navigate', { url: 'http://localhost:3001/dashboard' });
  await sleep(5000);
  console.log('authed:', await ev(`!document.querySelector('#view-app').classList.contains('hidden')`));
  await ev(`window.scrollTo(0,0);`);
  await sleep(600);
  await shot('shot-ctx-dash.png');
  await ev(`document.querySelector('[data-nav="aparencia"]').click(); window.scrollTo(0,0);`);
  await sleep(800);
  await shot('shot-ctx-apar.png');
  ws.close();
})().catch((e) => {
  console.error(e.message);
  process.exit(1);
});
