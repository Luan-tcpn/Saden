'use strict';
// P14: fluxo de auth no navegador (logout -> login inválido -> login válido).
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

  // 1) logout -> tela de auth visível, token removido
  await ev(`document.querySelector('#btn-logout').click()`);
  await sleep(800);
  const authVisible = await ev(`!document.querySelector('#view-auth').classList.contains('hidden')`);
  const tokenGone = await ev(`!localStorage.getItem('saden_token')`);
  console.log('logout -> auth visível:', authVisible, '| token removido:', tokenGone);

  // 2) login inválido -> mensagem de erro, sem redirecionar
  await ev(`document.querySelector('#login-email').value = 'demo@saden.local'`);
  await ev(`document.querySelector('#login-password').value = 'senha-errada'`);
  await ev(`document.querySelector('#form-login').requestSubmit()`);
  await sleep(2500);
  const errVisible = await ev(`!document.querySelector('#login-error').classList.contains('hidden')`);
  const stillAuth = await ev(`!document.querySelector('#view-auth').classList.contains('hidden')`);
  const errText = await ev(`document.querySelector('#login-error').textContent`);
  console.log('login inválido -> erro visível:', errVisible, '| permanece no auth:', stillAuth, '| msg:', JSON.stringify(errText));

  // 3) login válido -> dashboard com dados
  await ev(`document.querySelector('#login-password').value = 'saden123'`);
  await ev(`document.querySelector('#form-login').requestSubmit()`);
  const t0 = Date.now();
  let cards = 0;
  while (Date.now() - t0 < 90000) {
    cards = await ev(`document.querySelectorAll('#price-cards .card').length`);
    if (cards >= 3) break;
    await sleep(1500);
  }
  console.log('login válido -> cards do dashboard:', cards);
  console.log('pageErrors:', JSON.stringify(errs));
  const ok = authVisible && tokenGone && errVisible && stillAuth && cards >= 3 && errs.length === 0;
  console.log(ok ? 'AUTH-FLOW: OK' : 'AUTH-FLOW: FALHOU');
  ws.close();
  process.exit(ok ? 0 : 1);
})().catch((e) => {
  console.error(`AUTH-FAIL: ${e.message}`);
  process.exit(1);
});
