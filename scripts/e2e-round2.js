'use strict';
// E2E rodada 2: landing -> register -> app -> logout -> forgot/reset ->
// localização (rua, coords, my-location negada) -> tema dark -> mobile.
// Pré: Edge CDP em 127.0.0.1:9333 + backend em localhost:3001.
const fs = require('fs');
const path = require('path');
const APP = 'http://localhost:3001';
// Cache-buster: o perfil persistente do Edge + mtime do OneDrive geram 304
// falsos; a query única garante HTML fresco em cada execução.
const APPV = `${APP}/?e2e=${Date.now()}`;
const OUTBOX = path.join(__dirname, '..', 'tmp', 'mail-outbox');

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

(async () => {
  const results = [];
  const check = (name, cond, extra) => {
    results.push({ name, ok: !!cond, extra });
    console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}${extra ? ` — ${extra}` : ''}`);
  };
  // Aba dedicada e isolada: fecha páginas antigas (evita anexar a tab obsoleta)
  // e cria uma nova com URL única.
  const oldList = await (await fetch('http://127.0.0.1:9333/json/list')).json();
  for (const t of oldList.filter((x) => x.type === 'page')) {
    await fetch(`http://127.0.0.1:9333/json/close/${t.id}`).catch(() => null);
  }
  const created = await (
    await fetch(`http://127.0.0.1:9333/json/new?${encodeURIComponent(APPV)}`, { method: 'PUT' })
  ).json();
  if (!created || !created.webSocketDebuggerUrl) throw new Error('Sem aba CDP disponível');
  const ws = new WebSocket(created.webSocketDebuggerUrl);
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
      errs.push(`${d.text}: ${((d.exception && d.exception.description) || '').split('\n')[0]}`.slice(0, 220));
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
    fs.writeFileSync(path.join(__dirname, '..', 'tmp', 'shots', name), Buffer.from(s.data, 'base64'));
  };
  const waitFor = async (expr, ms = 60000) => {
    const t0 = Date.now();
    for (;;) {
      if (await ev(expr)) return true;
      if (Date.now() - t0 > ms) return false;
      await sleep(1000);
    }
  };

  await send('Page.enable');
  await send('Runtime.enable');
  await send('Emulation.clearDeviceMetricsOverride', {});
  await send('Emulation.setDeviceMetricsOverride', { width: 1366, height: 900, deviceScaleFactor: 1, mobile: false });
  // Estado limpo: sem token de sessões anteriores do mesmo perfil.
  await send('Page.navigate', { url: `${APPV}` });
  await sleep(1500);
  await send('Runtime.evaluate', { expression: `localStorage.clear()` });
  const email = `e2e${Date.now()}@saden.local`;

  // 1) landing
  await send('Page.navigate', { url: `${APPV}` });
  check('landing visível', await waitFor(`!document.querySelector('#view-landing').classList.contains('hidden')`, 15000));
  check('landing tem CTAs', await ev(`document.querySelectorAll('#view-landing [data-go]').length >= 3`));
  check('navbar com âncoras', await ev(`document.querySelectorAll('.landing-nav a').length >= 5`));
  check('logo é o satélite SVG', await ev(`(document.querySelector('.landing-top img.brand-mark')||{}).src === location.origin + '/img/logo.svg'`));
  check('foto do hero carrega', await ev(`document.querySelector('.hero-photo img').complete && document.querySelector('.hero-photo img').naturalWidth > 500`));
  check('seções narrativa', await ev(`['problema','plataforma','funcionalidades','como-funciona','dados'].every(id => !!document.getElementById(id))`));
  check('footer completo', await ev(`document.querySelectorAll('.foot-cols nav').length === 3 && !!document.querySelector('.foot-base')`));
  check('footer sem link quebrado', await ev(`[...document.querySelectorAll('.landing-foot a')].every(a => (a.getAttribute('href')||'').length > 3)`));
  await shot('shot-landing.png');

  // 2) CTA -> /register -> cadastro -> dashboard
  await ev(`document.querySelector('#view-landing [data-go="/register"]').click()`);
  check('rota /register', await waitFor(`location.pathname === '/register' && !document.querySelector('#form-register').classList.contains('hidden')`, 15000));
  await ev(`document.querySelector('#reg-name').value = 'E2E'`);
  await ev(`document.querySelector('#reg-email').value = '${email}'`);
  await ev(`document.querySelector('#reg-password').value = '123456'`);
  await ev(`document.querySelector('#form-register').requestSubmit()`);
  check('cadastro -> dashboard', await waitFor(`document.querySelectorAll('#price-cards .card').length >= 3`, 120000));

  // 3) logout -> landing
  await ev(`document.querySelector('#btn-logout').click()`);
  check('logout -> landing', await waitFor(`location.pathname === '/' && !document.querySelector('#view-landing').classList.contains('hidden')`, 15000));

  // 4) forgot -> mensagem genérica; token no outbox; reset; novo login
  await send('Page.navigate', { url: `${APP}/login?e2e=${Date.now()}` });
  await waitFor(`!document.querySelector('#form-login').classList.contains('hidden')`, 15000);
  await ev(`document.querySelector('#link-forgot').click()`);
  check('tela esqueci senha', await ev(`!document.querySelector('#form-forgot').classList.contains('hidden')`));
  await ev(`document.querySelector('#forgot-email').value = '${email}'`);
  await ev(`document.querySelector('#form-forgot').requestSubmit()`);
  check('forgot mensagem genérica', await waitFor(`!document.querySelector('#forgot-ok').classList.contains('hidden')`, 20000));
  let token = null;
  for (let i = 0; i < 10 && !token; i++) {
    await sleep(1000);
    try {
      const files = fs.readdirSync(OUTBOX).sort();
      for (let j = files.length - 1; j >= 0; j--) {
        const msg = JSON.parse(fs.readFileSync(path.join(OUTBOX, files[j]), 'utf8'));
        if (msg.to === email && msg.link) {
          token = new URL(msg.link).searchParams.get('token');
          break;
        }
      }
    } catch { /* outbox ainda não existe */ }
  }
  check('token no outbox dev', !!token);
  await send('Page.navigate', { url: `${APP}/reset?token=${token}&e2e=${Date.now()}` });
  check('tela reset', await waitFor(`!document.querySelector('#form-reset').classList.contains('hidden')`, 15000));
  await ev(`document.querySelector('#reset-password').value = 'nova-senha-9'`);
  await ev(`document.querySelector('#form-reset').requestSubmit()`);
  check('reset ok', await waitFor(`!document.querySelector('#reset-ok').classList.contains('hidden')`, 20000));
  await send('Page.navigate', { url: `${APP}/login?e2e=${Date.now()}` });
  await waitFor(`!document.querySelector('#form-login').classList.contains('hidden')`, 15000);
  await ev(`document.querySelector('#login-email').value = '${email}'`);
  await ev(`document.querySelector('#login-password').value = 'nova-senha-9'`);
  await ev(`document.querySelector('#form-login').requestSubmit()`);
  check('novo login pós-reset', await waitFor(`document.querySelectorAll('#price-cards .card').length >= 3`, 120000));

  // 5) localização: rua via autocomplete
  await ev(`document.querySelector('#inp-location').value = 'Av. Paulista, São Paulo'`);
  await ev(`document.querySelector('#inp-location').dispatchEvent(new Event('input', {bubbles:true}))`);
  check('autocomplete sugere rua', await waitFor(`document.querySelectorAll('#location-results button[data-i]').length > 0`, 30000));
  await ev(`document.querySelector('#location-results button[data-i]').click()`);
  await sleep(500);
  const coordTxt = await ev(`document.querySelector('#coord-label').textContent`);
  check('sugestão aplica coordenadas', /-23\.5/.test(coordTxt || ''), coordTxt);

  // 5b) XSS controlado: payload malicioso deve virar texto, sem executar
  await ev(`document.querySelector('#inp-location').value = '<img src=x onerror=window.__xss=1>'`);
  await ev(`document.querySelector('#inp-location').dispatchEvent(new Event('input', {bubbles:true}))`);
  await sleep(2500);
  check(
    'XSS neutralizado no autocomplete',
    await ev(`!document.querySelector('#location-results img') && window.__xss !== 1 && document.querySelector('#location-results').textContent.includes('<img')`)
  );

  // 5d) teclado no autocomplete: seta + Enter aplica a sugestão
  await ev(`document.querySelector('#inp-location').value = 'Curitiba'`);
  await ev(`document.querySelector('#inp-location').dispatchEvent(new Event('input', {bubbles:true}))`);
  check('sugestões Curitiba', await waitFor(`document.querySelectorAll('#location-results button[data-i]').length > 0`, 30000));
  await ev(`document.querySelector('#inp-location').dispatchEvent(new KeyboardEvent('keydown', {key:'ArrowDown', bubbles:true}))`);
  await ev(`document.querySelector('#inp-location').dispatchEvent(new KeyboardEvent('keydown', {key:'Enter', bubbles:true}))`);
  await sleep(800);
  const kbPlace = await ev(`document.querySelector('#place-label').textContent`);
  check('teclado aplica sugestão', /Curitiba/i.test(kbPlace || ''), kbPlace);

  // 5e) Limpar filtros restaura o padrão
  await ev(`document.querySelector('#btn-clear').click()`);
  check(
    'limpar filtros',
    await waitFor(
      `document.querySelector('#sel-commodity').value === 'soja' && document.querySelector('#inp-location').value === '' && document.querySelector('#sel-uf').value === ''`,
      15000
    )
  );
  const beforeMuni = await ev(`document.querySelector('#coord-label').textContent`);
  await ev(`document.querySelector('#sel-uf').value = 'SP'`);
  await ev(`document.querySelector('#sel-uf').dispatchEvent(new Event('change', {bubbles:true}))`);
  const muniOk = await (async () => {
    const t0 = Date.now();
    for (;;) {
      const n = await ev(`document.querySelectorAll('#sel-municipio option').length`);
      if (n > 5) break;
      if (Date.now() - t0 > 30000) return false;
      await sleep(1000);
    }
    await ev(`document.querySelector('#sel-municipio').selectedIndex = 1`);
    await ev(`document.querySelector('#sel-municipio').dispatchEvent(new Event('change', {bubbles:true}))`);
    const t1 = Date.now();
    for (;;) {
      const settled = await ev(`document.querySelector('#loc-status').classList.contains('ok')`);
      const txt = await ev(`document.querySelector('#coord-label').textContent`);
      if (settled && txt && txt !== beforeMuni) return txt;
      if (Date.now() - t1 > 90000) return false;
      await sleep(2000);
    }
  })();
  check('município atualiza coordenadas', !!muniOk, String(muniOk));
  await ev(`document.querySelector('#inp-location').value = '-21.1775, -47.8103'`);
  await ev(`document.querySelector('#btn-apply').click()`);
  check('coords viram localidade', await waitFor(`/Ribeir/.test(document.querySelector('#place-label').textContent)`, 90000));

  // 6b) período altera a série do histórico
  await ev(`document.querySelector('#sel-range').value = '3mo'`);
  await ev(`document.querySelector('#sel-range').dispatchEvent(new Event('change', {bubbles:true}))`);
  await ev(`document.querySelector('#btn-apply').click()`);
  check('período 3m aplica', await waitFor(`document.querySelector('#hist-sub').textContent.includes('2026-06')`, 90000));

  // 6b2) D39: seletor Ridge (padrão) / AR (experimental)
  check('modelo padrão é Ridge', await ev(`document.querySelector('#sel-model').value === 'ridge'`));
  await ev(`document.querySelector('#sel-model').value = 'ar'`);
  await ev(`document.querySelector('#sel-model').dispatchEvent(new Event('change', {bubbles:true}))`);
  await ev(`document.querySelector('#btn-apply').click()`);
  check('AR experimental aplica', await waitFor(`/ar \\(ordem/.test(document.querySelector('#fc-sub').textContent)`, 180000));
  check('nota experimental visível', await ev(`document.querySelector('#forecast-meta').textContent.includes('experimental')`));
  await ev(`document.querySelector('#sel-model').value = 'ridge'`);
  await ev(`document.querySelector('#sel-model').dispatchEvent(new Event('change', {bubbles:true}))`);
  await ev(`document.querySelector('#btn-apply').click()`);
  check('volta a Ridge', await waitFor(`/ridge/.test(document.querySelector('#fc-sub').textContent)`, 180000));

  // 6c) locais salvos: salvar ponto, usar, excluir
  await ev(`document.querySelector('[data-nav="mapa"]').click()`);
  check('página mapa', await waitFor(`!document.querySelector('#page-mapa').classList.contains('hidden')`, 15000));
  await ev(`document.querySelector('#inp-place-label').value = 'e2e-fazenda'`);
  await ev(`document.querySelector('#btn-place-save').click()`);
  check('local salvo', await waitFor(`document.querySelector('#places-list').textContent.includes('e2e-fazenda')`, 20000));
  await ev(`document.querySelector('#places-list [data-place-go]').click()`);
  await sleep(800);
  check('local aplicado', await ev(`document.querySelector('#place-label').textContent.includes('e2e-fazenda')`));
  await ev(`document.querySelector('#places-list [data-place-del]').click()`);
  check('local excluído', await waitFor(`!document.querySelector('#places-list').textContent.includes('e2e-fazenda')`, 20000));
  check(
    'mapa com contexto completo',
    await ev(`!document.querySelector('#page-mapa').classList.contains('hidden') && document.querySelector('.topbar') && getComputedStyle(document.querySelector('.topbar')).display !== 'none' && !!document.querySelector('#sel-commodity')`)
  );

  // 6d) referência territorial honesta no dashboard + camada Land Cover
  await ev(`document.querySelector('[data-nav="dashboard"]').click()`);
  await ev(`document.querySelector('#btn-apply').click()`);
  check(
    'nível nacional declarado',
    await waitFor(`document.querySelector('#price-cards').textContent.includes('nacional')`, 90000)
  );
  await ev(`document.querySelector('[data-nav="mapa"]').click()`);
  await ev(`document.querySelector('#btn-layer-lulc').click()`);
  check(
    'camada landcover + legenda',
    await waitFor(
      `!document.querySelector('#lulc-legend').classList.contains('hidden') && document.querySelector('#lulc-legend').textContent.includes('Crops')`,
      60000
    )
  );
  check('tiles landcover carregam', await waitFor(`document.querySelectorAll('#map img.leaflet-tile').length > 3`, 90000));
  check('swatches com cores reais', await ev(`[...document.querySelectorAll('#lulc-legend .sw:not(.none)')].every(e => getComputedStyle(e).backgroundColor !== 'rgba(0, 0, 0, 0)') && document.querySelectorAll('#lulc-legend .sw:not(.none)').length >= 8`));
  await ev(`document.querySelector('#lulc-more').click()`);
  check('legenda expansível', await waitFor(`!document.querySelector('#lulc-legend .lulc-rest').classList.contains('hidden')`, 15000));
  await ev(`document.querySelector('[data-nav="relatorio"]').click()`);
  check(
    'relatório com contexto completo',
    await ev(`!document.querySelector('#page-relatorio').classList.contains('hidden') && getComputedStyle(document.querySelector('.topbar')).display !== 'none'`)
  );
  await ev(`document.querySelector('#btn-report').click()`);
  check(
    'relatório com localidade',
    await waitFor(`/—/.test(document.querySelector('#report-body h1').textContent)`, 180000)
  );

  // 7) Minha localização (headless nega -> mensagem amigável, sem fatal)
  await ev(`document.querySelector('#btn-myloc').click()`);
  check(
    'geolocalização negada tratada',
    await waitFor(`document.querySelector('#loc-status').classList.contains('error')`, 30000)
  );

  // 8b) alertas: criar -> verificar (dispara) -> excluir
  await ev(`document.querySelector('[data-nav="alertas"]').click()`);
  check('página alertas', await waitFor(`!document.querySelector('#page-alertas').classList.contains('hidden')`, 15000));
  await ev(`document.querySelector('#al-commodity').value = 'soja'`);
  await ev(`document.querySelector('#al-kind').value = 'price_below'`);
  await ev(`document.querySelector('#al-threshold').value = '99999'`);
  await ev(`document.querySelector('#al-label').value = 'e2e-teste'`);
  await ev(`document.querySelector('#btn-al-create').click()`);
  check('alerta criado', await waitFor(`document.querySelector('#al-list').textContent.includes('e2e-teste')`, 20000));
  await ev(`document.querySelector('#btn-al-check').click()`);
  check('alerta dispara', await waitFor(`document.querySelector('#al-events').textContent.includes('DISPARADO')`, 120000));
  await ev(`document.querySelector('#al-list [data-al-del]').click()`);
  check('alerta excluído', await waitFor(`!document.querySelector('#al-list').textContent.includes('e2e-teste')`, 20000));

  // 8c) contexto por tela: sem barra global; form só no dashboard; coord-line no dashboard
  check('sem barra global', await ev(`!document.querySelector('#context-bar')`));
  await ev(`document.querySelector('[data-nav="dashboard"]').click()`);
  await sleep(500);
  check(
    'dashboard com contexto próprio',
    await ev(`!document.querySelector('#page-dashboard').classList.contains('hidden') && getComputedStyle(document.querySelector('.topbar')).display !== 'none' && !!document.querySelector('#coord-label')`)
  );
  await ev(`document.querySelector('[data-nav="aparencia"]').click()`);
  await sleep(500);
  check(
    'aparência sem form de consulta',
    await ev(`document.querySelector('#page-dashboard').classList.contains('hidden') && document.querySelector('#btn-apply').offsetParent === null`)
  );
  await ev(`document.querySelector('[data-nav="fontes"]').click()`);
  await sleep(500);
  check(
    'fontes sem form de consulta',
    await ev(`document.querySelector('#page-dashboard').classList.contains('hidden') && document.querySelector('#btn-apply').offsetParent === null`)
  );
  await ev(`document.querySelector('[data-nav="aparencia"]').click()`);
  await ev(`document.querySelector('input[name="theme"][value="dark"]').click()`);
  await sleep(1500);
  check('dark aplicado', await ev(`document.documentElement.dataset.theme === 'dark'`));
  await send('Page.navigate', { url: `${APP}/dashboard?e2e=${Date.now()}` });
  await waitFor(`document.querySelectorAll('#price-cards .card').length >= 3`, 120000);
  check('dark persiste após reload', await ev(`document.documentElement.dataset.theme === 'dark'`));
  await shot('shot-dark.png');
  // volta ao claro para não afetar outras verificações
  await ev(`document.querySelector('[data-nav="aparencia"]').click()`);
  await ev(`document.querySelector('input[name="theme"][value="light"]').click()`);
  await sleep(800);

  // 9) mobile: landing + dashboard sem overflow (dsf 1: viewport real)
  await send('Emulation.clearDeviceMetricsOverride', {});
  await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: false });
  await send('Page.navigate', { url: `${APPV}` });
  await sleep(2000);
  const ov1 = await ev(`document.documentElement.scrollWidth - document.documentElement.clientWidth`);
  check('mobile landing sem overflow', ov1 === 0, `overflow=${ov1}px`);
  check('menu mobile abre/fecha', await ev(`(function(){ const b = document.querySelector('#btn-landing-menu'); if (!b || getComputedStyle(b).display === 'none') return false; b.click(); const open = document.querySelector('#landing-nav').classList.contains('open'); b.click(); return open && !document.querySelector('#landing-nav').classList.contains('open'); })()`));
  await send('Page.navigate', { url: `${APP}/dashboard?e2e=${Date.now()}` });
  await waitFor(`document.querySelectorAll('#price-cards .card').length >= 3`, 120000);
  const ov2 = await ev(`document.documentElement.scrollWidth - document.documentElement.clientWidth`);
  check('mobile dashboard sem overflow', ov2 === 0, `overflow=${ov2}px`);
  await shot('shot-mobile2.png');

  // 10) 320px: sem overflow
  await send('Emulation.clearDeviceMetricsOverride', {});
  await send('Emulation.setDeviceMetricsOverride', { width: 320, height: 700, deviceScaleFactor: 1, mobile: false });
  await send('Page.navigate', { url: `${APP}/dashboard?e2e=${Date.now()}` });
  await waitFor(`document.querySelectorAll('#price-cards .card').length >= 3`, 120000);
  const ov3 = await ev(`document.documentElement.scrollWidth - document.documentElement.clientWidth`);
  check('320px sem overflow', ov3 === 0, `overflow=${ov3}px`);

  console.log('pageErrors:', JSON.stringify(errs));
  const failed = results.filter((r) => !r.ok);
  console.log(failed.length === 0 && errs.length === 0 ? 'E2E-R2: OK' : `E2E-R2: ${failed.length} FALHAS`);
  ws.close();
  process.exit(failed.length === 0 && errs.length === 0 ? 0 : 1);
})().catch((e) => {
  console.error(`E2E-FAIL: ${e.message}`);
  process.exit(1);
});
