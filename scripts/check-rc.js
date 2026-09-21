'use strict';
function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}
(async () => {
  const created = await (await fetch('http://127.0.0.1:9333/json/new?http://localhost:3001/', { method: 'PUT' })).json();
  const ws = new WebSocket(created.webSocketDebuggerUrl);
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
  await send('Page.enable');
  await send('Runtime.enable');
  // Login rápido via API + token no localStorage (evita refazer fluxo).
  const login = await (
    await fetch('http://localhost:3001/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: 'demo@saden.local', password: 'saden123' }),
    })
  ).json();
  await ev(`localStorage.setItem('saden_token','${login.token}'); location.reload();`);
  await sleep(6000);
  const shot = async (name) => {
    const s = await send('Page.captureScreenshot', { format: 'png' });
    require('fs').writeFileSync(require('path').join(__dirname, '..', 'tmp', 'shots', name), Buffer.from(s.data, 'base64'));
  };
  const st = async (label) => {
    const d = await ev(
      `JSON.stringify({top: document.querySelector('.topbar') ? getComputedStyle(document.querySelector('.topbar')).display : 'NONE', kids: document.querySelector('.topbar') ? document.querySelector('.topbar').children.length : -1, ch: document.querySelector('.topbar') ? document.querySelector('.topbar').clientHeight : -1, parent: document.querySelector('.topbar') ? (document.querySelector('.topbar').parentElement.id || document.querySelector('.topbar').parentElement.tagName) : 'NONE', page: [...document.querySelectorAll('.page')].filter(p=>!p.classList.contains('hidden')).map(p=>p.id).join(',')})`
    );
    console.log(label, d);
  };
  await ev(`window.scrollTo(0,0)`);
  await st('dashboard:');
  await ev(`document.querySelector('[data-nav="mapa"]').click(); window.scrollTo(0,0);`);
  await sleep(1500);
  await st('mapa:     ');
  await shot('shot-rc-map.png');
  await ev(`document.querySelector('[data-nav="relatorio"]').click(); window.scrollTo(0,0);`);
  await sleep(1200);
  await st('relatorio:');
  await shot('shot-rc-rel.png');
  await ev(`document.querySelector('[data-nav="aparencia"]').click(); window.scrollTo(0,0);`);
  await sleep(800);
  await st('aparencia:');
  ws.close();
})().catch((e) => {
  console.error(e.message);
  process.exit(1);
});
