'use strict';
function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}
(async () => {
  const list = await (await fetch('http://127.0.0.1:9333/json/list')).json();
  const page = list.find((t) => t.type === 'page' && t.url.includes('localhost'));
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
      const d = msg.params.exceptionDetails;
      errs.push(`${d.text}: ${(d.exception && d.exception.description) || ''}`.slice(0, 300));
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
  await send('Page.enable');
  await send('Runtime.enable');
  for (const nav of ['mapa', 'relatorio', 'fontes', 'alertas', 'aparencia', 'dashboard']) {
    await ev(`document.querySelector('[data-nav="${nav}"]').click()`);
    await sleep(1200);
  }
  console.log('errors:', JSON.stringify(errs, null, 1));
  ws.close();
})().catch((e) => {
  console.error(e.message);
  process.exit(1);
});
