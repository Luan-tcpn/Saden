'use strict';

// Integração contra o app Express real com banco temporário (não toca o
// data/saden.db do servidor em execução). Inclui 2 testes "live" contra as
// fontes externas reais (Yahoo e Open-Meteo) com timeout generoso.
process.env.DATABASE_PATH = require('path').join(__dirname, '..', '..', 'tmp', 'test-saden.db');

const fs = require('fs');
const path = require('path');
const { describe, it, before, after } = require('node:test');
const assert = require('node:assert/strict');

const db = require('../../backend/src/db');

let base;
let server;

async function api(pathname, { method = 'GET', body, token } = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${base}${pathname}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  let data = null;
  try {
    data = await res.json();
  } catch {
    data = null;
  }
  return { status: res.status, data };
}

describe('API SADEN — integração', () => {
  before(async () => {
    try {
      fs.unlinkSync(process.env.DATABASE_PATH);
    } catch {
      /* primeiro run */
    }
    db.connect();
    const app = require('../../backend/src/index');
    await new Promise((resolve) => {
      server = app.listen(0, '127.0.0.1', resolve);
    });
    base = `http://127.0.0.1:${server.address().port}`;
  });

  after(() => {
    server.close();
  });

  it('health responde ok', async () => {
    const { status, data } = await api('/api/health');
    assert.equal(status, 200);
    assert.equal(data.status, 'ok');
  });

  it('registro + login + /me (fluxo auth completo)', async () => {
    const reg = await api('/api/auth/register', {
      method: 'POST',
      body: { name: 'Teste', email: 'teste@saden.local', password: '123456' },
    });
    assert.equal(reg.status, 201);
    assert.ok(reg.data.token);

    const dup = await api('/api/auth/register', {
      method: 'POST',
      body: { name: 'Teste', email: 'teste@saden.local', password: '123456' },
    });
    assert.equal(dup.status, 400);

    const bad = await api('/api/auth/login', {
      method: 'POST',
      body: { email: 'teste@saden.local', password: 'errada' },
    });
    assert.equal(bad.status, 401);

    const login = await api('/api/auth/login', {
      method: 'POST',
      body: { email: 'teste@saden.local', password: '123456' },
    });
    assert.equal(login.status, 200);

    const me = await api('/api/auth/me', { token: login.data.token });
    assert.equal(me.status, 200);
    assert.equal(me.data.user.email, 'teste@saden.local');
    process.env.SADEN_TEST_TOKEN = login.data.token;
  });

  it('rotas protegidas exigem token', async () => {
    const { status, data } = await api('/api/commodities');
    assert.equal(status, 401);
    assert.match(data.error, /login/i);
  });

  it('lista 5 commodities cadastradas', async () => {
    const { status, data } = await api('/api/commodities', { token: process.env.SADEN_TEST_TOKEN });
    assert.equal(status, 200);
    assert.equal(data.commodities.length, 5);
  });

  it('commodity desconhecida retorna 404', async () => {
    const { status } = await api('/api/commodities/xxx/latest', { token: process.env.SADEN_TEST_TOKEN });
    assert.equal(status, 404);
  });

  it('fontes documentam CEPEA/CONAB como bloqueadas (sem API)', async () => {
    const { status, data } = await api('/api/sources');
    assert.equal(status, 200);
    const byKey = Object.fromEntries(data.sources.map((s) => [s.key, s.status]));
    assert.equal(byKey['bcb-ptax'], 'active');
    assert.equal(byKey['open-meteo'], 'active');
    assert.equal(byKey.cepea, 'blocked');
    assert.equal(byKey.conab, 'blocked');
  });

  it('token expirado é rejeitado (401)', async () => {
    const path = require('path');
    const backendModules = path.join(__dirname, '..', '..', 'backend', 'node_modules');
    const jwt = require(path.join(backendModules, 'jsonwebtoken'));
    const config = require('../../backend/src/config');
    const expired = jwt.sign({ sub: 1, email: 'x@y.z' }, config.jwtSecret, { expiresIn: '-10s' });
    const { status, data } = await api('/api/auth/me', { token: expired });
    assert.equal(status, 401);
    assert.match(data.error, /expirada|inválida/i);
  });

  it('rate-limit bloqueia brute-force no login (429)', async () => {
    const rateLimit = require('../../backend/src/middleware/rateLimit');
    rateLimit._reset();
    let last = 0;
    for (let i = 0; i < 11; i++) {
      const r = await api('/api/auth/login', {
        method: 'POST',
        body: { email: 'teste@saden.local', password: 'errada' },
      });
      last = r.status;
    }
    assert.equal(last, 429);
    rateLimit._reset();
  });

  it('recuperação de senha: fluxo completo com uso único', async () => {
    const fsp = require('fs');
    const fpath = require('path');
    const outbox = fpath.join(__dirname, '..', '..', 'tmp', 'mail-outbox');
    const email = 'recovery@saden.local';
    await api('/api/auth/register', { method: 'POST', body: { name: 'Rec', email, password: '123456' } });

    const generic = 'Se houver uma conta associada';
    const r1 = await api('/api/auth/forgot', { method: 'POST', body: { email } });
    assert.equal(r1.status, 200);
    assert.match(r1.data.message, new RegExp(generic));
    // E-mail inexistente: mesma resposta (anti-enumeração).
    const r2 = await api('/api/auth/forgot', { method: 'POST', body: { email: 'ninguem@saden.local' } });
    assert.equal(r2.status, 200);
    assert.match(r2.data.message, new RegExp(generic));

    const files = fsp.readdirSync(outbox).sort();
    let token = null;
    for (let i = files.length - 1; i >= 0; i--) {
      const msg = JSON.parse(fsp.readFileSync(fpath.join(outbox, files[i]), 'utf8'));
      if (msg.to === email && msg.link) {
        token = new URL(msg.link).searchParams.get('token');
        break;
      }
    }
    assert.ok(token && token.length >= 32, 'token presente no outbox de desenvolvimento');

    const ok = await api('/api/auth/reset', { method: 'POST', body: { token, password: 'nova-senha-1' } });
    assert.equal(ok.status, 200);
    const reuse = await api('/api/auth/reset', { method: 'POST', body: { token, password: 'outra-senha-2' } });
    assert.equal(reuse.status, 400);
    const login = await api('/api/auth/login', { method: 'POST', body: { email, password: 'nova-senha-1' } });
    assert.equal(login.status, 200);
  });

  it('recuperação: token inválido e expirado são rejeitados', async () => {
    const bad = await api('/api/auth/reset', { method: 'POST', body: { token: 'x'.repeat(64), password: 'nova-senha-1' } });
    assert.equal(bad.status, 400);
    // Token expirado inserido diretamente no banco temporário.
    const crypto = require('crypto');
    const { connect } = require('../../backend/src/db');
    const u = connect().prepare('SELECT id FROM users WHERE email = ?').get('recovery@saden.local');
    const h = crypto.createHash('sha256').update('y'.repeat(64)).digest('hex');
    connect().prepare("INSERT INTO password_resets(user_id, token_hash, expires_at) VALUES(?, ?, datetime('now', '-2 hours'))").run(u.id, h);
    const exp = await api('/api/auth/reset', { method: 'POST', body: { token: 'y'.repeat(64), password: 'nova-senha-1' } });
    assert.equal(exp.status, 400);
  });

  it('LIVE: busca de rua retorna endereço Nominatim com rótulo', { timeout: 90000 }, async () => {
    const { status, data } = await api('/api/geo/search?q=Av.%20Paulista%2C%20S%C3%A3o%20Paulo', {
      token: process.env.SADEN_TEST_TOKEN,
    });
    assert.equal(status, 200);
    assert.equal(data.mode, 'text');
    const street = data.results.find((r) => r.provider === 'nominatim');
    assert.ok(street, 'esperado ao menos um resultado de rua/endereço');
    assert.ok(street.label && street.label.length > 10);
    assert.ok(Number.isFinite(street.latitude) && Number.isFinite(street.longitude));
  });

  it('LIVE: busca por coordenadas faz reverse', { timeout: 90000 }, async () => {
    const { status, data } = await api('/api/geo/search?q=-21.1775%2C%20-47.8103', {
      token: process.env.SADEN_TEST_TOKEN,
    });
    assert.equal(status, 200);
    assert.equal(data.mode, 'coordinates');
    assert.equal(data.count, 1);
    assert.match(data.results[0].label, /Ribeir.o Preto|Brasil/);
  });

  it('LIVE: reverse dedicado + coordenada inválida', { timeout: 90000 }, async () => {
    const ok = await api('/api/geo/reverse?lat=-23.55&lon=-46.63', { token: process.env.SADEN_TEST_TOKEN });
    assert.equal(ok.status, 200);
    assert.ok(ok.data.label);
    const bad = await api('/api/geo/reverse?lat=999&lon=0', { token: process.env.SADEN_TEST_TOKEN });
    assert.equal(bad.status, 400);
    const badText = await api('/api/geo/search?q=-100%2C%20-47.8', { token: process.env.SADEN_TEST_TOKEN });
    assert.equal(badText.status, 400);
  });

  it('CSV do relatório: content-type, BOM e linhas histórico+previsão', { timeout: 120000 }, async () => {
    const headers = { 'Content-Type': 'application/json', Authorization: `Bearer ${process.env.SADEN_TEST_TOKEN}` };
    const res = await fetch(`${base}/api/reports/soja/csv?horizon=7`, { headers });
    assert.equal(res.status, 200);
    assert.match(res.headers.get('content-type'), /text\/csv/);
    const buf = Buffer.from(await res.arrayBuffer());
    assert.ok(buf[0] === 0xef && buf[1] === 0xbb && buf[2] === 0xbf, 'BOM UTF-8 presente');
    const text = buf.toString('utf8');
    assert.ok(text.includes('secao;data;preco_brl;limite_inferior;limite_superior;fonte'));
    assert.ok(text.includes('\nhistorico;'));
    assert.ok(text.includes('\nprevisao;'));
  });

  it('alertas: validação, CRUD, avaliação e isolamento por usuário', { timeout: 120000 }, async () => {
    const T = process.env.SADEN_TEST_TOKEN;
    const bad1 = await api('/api/alerts', { method: 'POST', token: T, body: { commodity_key: 'soja', kind: 'preco_maluco', threshold: 10 } });
    assert.equal(bad1.status, 400);
    const bad2 = await api('/api/alerts', { method: 'POST', token: T, body: { commodity_key: 'xxx', kind: 'price_below', threshold: 10 } });
    assert.equal(bad2.status, 404);
    const bad3 = await api('/api/alerts', { method: 'POST', token: T, body: { commodity_key: 'soja', kind: 'price_below', threshold: -5 } });
    assert.equal(bad3.status, 400);
    const bad4 = await api('/api/alerts', { method: 'POST', token: T, body: { commodity_key: 'soja', kind: 'rain_above', threshold: 10 } });
    assert.equal(bad4.status, 400); // chuva exige lat/lon

    const latest = await api('/api/commodities/soja/latest', { token: T });
    const px = latest.data.price_brl;
    const a1 = await api('/api/alerts', { method: 'POST', token: T, body: { commodity_key: 'soja', kind: 'price_below', threshold: px * 2, label: 'teste' } });
    assert.equal(a1.status, 201);
    const a2 = await api('/api/alerts', { method: 'POST', token: T, body: { commodity_key: 'soja', kind: 'price_above', threshold: px * 2 } });
    assert.equal(a2.status, 201);

    const chk = await api('/api/alerts/check', { method: 'POST', token: T });
    assert.equal(chk.status, 200);
    const byId = Object.fromEntries(chk.data.results.map((r) => [r.alert.id, r.triggered]));
    assert.equal(byId[a1.data.alert.id], true);
    assert.equal(byId[a2.data.alert.id], false);

    const off = await api(`/api/alerts/${a1.data.alert.id}`, { method: 'PATCH', token: T, body: { active: false } });
    assert.equal(off.status, 200);
    assert.equal(off.data.alert.active, false);
    const chk2 = await api('/api/alerts/check', { method: 'POST', token: T });
    assert.ok(!chk2.data.results.some((r) => r.alert.id === a1.data.alert.id));

    const ev = await api(`/api/alerts/${a2.data.alert.id}/events`, { token: T });
    assert.equal(ev.status, 200);
    assert.ok(ev.data.events.length >= 1);

    const del = await api(`/api/alerts/${a1.data.alert.id}`, { method: 'DELETE', token: T });
    assert.equal(del.status, 200);
    const gone = await api(`/api/alerts/${a1.data.alert.id}/events`, { token: T });
    assert.equal(gone.status, 404);

    // Outro usuário não enxerga os alertas.
    const reg2 = await api('/api/auth/register', { method: 'POST', body: { name: 'Outro', email: 'outro@saden.local', password: '123456' } });
    const list2 = await api('/api/alerts', { token: reg2.data.token });
    assert.equal(list2.status, 200);
    assert.equal(list2.data.alerts.length, 0);
    await api(`/api/alerts/${a2.data.alert.id}`, { method: 'DELETE', token: T });
  });

  it('locais salvos: CRUD com validação e isolamento', async () => {
    const T = process.env.SADEN_TEST_TOKEN;
    const bad1 = await api('/api/places', { method: 'POST', token: T, body: { label: 'x', latitude: 999, longitude: 0 } });
    assert.equal(bad1.status, 400);
    const bad2 = await api('/api/places', { method: 'POST', token: T, body: { label: '', latitude: 0, longitude: 0 } });
    assert.equal(bad2.status, 400);
    const c = await api('/api/places', { method: 'POST', token: T, body: { label: 'Fazenda <b>Teste</b>', latitude: -21.17, longitude: -47.81 } });
    assert.equal(c.status, 201);
    assert.equal(c.data.place.label, 'Fazenda <b>Teste</b>');
    const list = await api('/api/places', { token: T });
    assert.ok(list.data.places.some((p) => p.id === c.data.place.id));
    const del = await api(`/api/places/${c.data.place.id}`, { method: 'DELETE', token: T });
    assert.equal(del.status, 200);
    const gone = await api(`/api/places/${c.data.place.id}`, { method: 'DELETE', token: T });
    assert.equal(gone.status, 404);
  });

  it('série rejeita range inválido', async () => {
    const r = await api('/api/commodities/soja/series?range=10y', { token: process.env.SADEN_TEST_TOKEN });
    assert.equal(r.status, 400);
  });

  it('price reference: nível nacional honesto com fallback declarado', { timeout: 90000 }, async () => {
    const T = process.env.SADEN_TEST_TOKEN;
    const r = await api('/api/prices/reference?commodity=soja&uf=SP&ibge_code=3543402', { token: T });
    assert.equal(r.status, 200);
    assert.equal(r.data.geographic_level, 'nacional');
    assert.equal(r.data.geographic_name, 'Brasil');
    assert.equal(r.data.currency, 'BRL');
    assert.ok(r.data.price_brl > 0);
    assert.ok(Array.isArray(r.data.fallback_chain) && r.data.fallback_chain.length >= 2);
    assert.ok(r.data.fallback_chain.every((f) => f.status === 'unavailable' && f.reason));
    assert.match(r.data.data_date, /^\d{4}-\d{2}-\d{2}$/);
    const noParam = await api('/api/prices/reference', { token: T });
    assert.equal(noParam.status, 400);
    const bad = await api('/api/prices/reference?commodity=xxx', { token: T });
    assert.equal(bad.status, 404);
  });

  it('LIVE: landcover info + tile PNG real', { timeout: 90000 }, async () => {
    const info = await api('/api/landcover/info');
    assert.equal(info.status, 200);
    assert.ok(info.data.classes.length === 9);
    assert.ok(info.data.classes.some((c) => c.name === 'Crops'));
    assert.ok(info.data.limitations.length >= 2);
    const byName = Object.fromEntries(info.data.classes.map((c) => [c.name, c.color]));
    assert.equal(byName.Crops, '#ffdb5c');
    assert.equal(byName.Trees, '#358221');
    assert.match(byName.Water, /^#[0-9a-f]{6}$/);
    const res = await fetch(`${base}/api/landcover/tile/6/20/34.png`);
    assert.equal(res.status, 200);
    assert.match(res.headers.get('content-type'), /image\/png/);
    const buf = Buffer.from(await res.arrayBuffer());
    assert.ok(buf.length > 500);
    assert.equal(buf.slice(1, 4).toString(), 'PNG');
    const bad = await fetch(`${base}/api/landcover/tile/99/0/0.png`);
    assert.equal(bad.status, 400);
  });

  it('LIVE: preço real soja (Yahoo + PTAX)', { timeout: 90000 }, async () => {
    const { status, data } = await api('/api/commodities/soja/latest', {
      token: process.env.SADEN_TEST_TOKEN,
    });
    assert.equal(status, 200);
    assert.ok(data.price_brl > 0);
    assert.ok(data.fx_venda > 0);
    assert.equal(data.provider, 'yahoo');
    assert.match(data.data_date, /^\d{4}-\d{2}-\d{2}$/);
  });

  it('LIVE: clima real Ribeirão Preto (Open-Meteo)', { timeout: 60000 }, async () => {
    const { status, data } = await api('/api/weather/forecast?lat=-21.1775&lon=-47.8103', {
      token: process.env.SADEN_TEST_TOKEN,
    });
    assert.equal(status, 200);
    assert.equal(data.daily.length, 7);
    assert.ok(Number.isFinite(data.current.temperature_2m));
  });

  it('cache kv: miss → hit → expiração/TTL → sobrescrita', async () => {
    const { cacheGet, cacheSet } = require('../../backend/src/db');
    assert.equal(cacheGet('e1:ausente'), null, 'miss retorna null');
    cacheSet('e1:obj', { a: 1, b: 'x' }, 60 * 1000);
    assert.deepEqual(cacheGet('e1:obj'), { a: 1, b: 'x' }, 'hit devolve o objeto');
    cacheSet('e1:obj', { a: 2 }, 60 * 1000);
    assert.deepEqual(cacheGet('e1:obj'), { a: 2 }, 'REPLACE sobrescreve');
    cacheSet('e1:expirada', { a: 1 }, -1000);
    assert.equal(cacheGet('e1:expirada'), null, 'TTL vencido retorna null');
    assert.equal(cacheGet('e1:expirada'), null, 'entrada expirada foi invalidada (não ressuscita)');
  });

  it('latest indica hit de cache na segunda chamada', async () => {
    const T = process.env.SADEN_TEST_TOKEN;
    const r1 = await api('/api/commodities/soja/latest', { token: T });
    assert.equal(r1.status, 200);
    assert.equal(typeof r1.data.cached, 'boolean');
    const r2 = await api('/api/commodities/soja/latest', { token: T });
    assert.equal(r2.status, 200);
    assert.equal(r2.data.cached, true, 'segunda chamada dentro do TTL usa cache');
    assert.equal(r2.data.price_brl, r1.data.price_brl);
  });

  it('forecast 422 com série curta (cache semeado, sem mock)', { timeout: 60000 }, async () => {
    const T = process.env.SADEN_TEST_TOKEN;
    const { connect, cacheSet } = require('../../backend/src/db');
    const forecastService = require('../../backend/src/services/forecastService');
    assert.ok(forecastService.MIN_POINTS >= 60, 'guarda mínima documentada');
    const points = [];
    for (let i = 0; i < 10; i++) {
      points.push({ date: `2026-01-${String(i + 1).padStart(2, '0')}`, price_brl: 100 + i });
    }
    cacheSet('prices:soja:1y', { points }, 60 * 1000);
    try {
      await assert.rejects(() => forecastService.run('soja', 7), (e) => {
        assert.equal(e.status, 422);
        assert.match(e.message, /insuficiente/i);
        return true;
      });
      const r = await api('/api/forecast/soja?horizon=7', { token: T });
      assert.equal(r.status, 422, 'rota propaga o 422 honesto');
    } finally {
      connect().prepare('DELETE FROM kv_cache WHERE key = ?').run('prices:soja:1y');
    }
  });

  it('arService.run 422 com série curta (cache semeado)', async () => {
    const { connect, cacheSet } = require('../../backend/src/db');
    const arService = require('../../backend/src/services/arService');
    const pts = [];
    for (let i = 0; i < 10; i++) pts.push({ date: `2026-01-${String(i + 1).padStart(2, '0')}`, price_brl: 100 + i });
    cacheSet('prices:soja:1y', { points: pts }, 60 * 1000);
    try {
      await assert.rejects(() => arService.run('soja', 7), (e) => {
        assert.equal(e.status, 422);
        assert.match(e.message, /insuficiente/i);
        return true;
      });
    } finally {
      connect().prepare('DELETE FROM kv_cache WHERE key = ?').run('prices:soja:1y');
    }
  });

  it('arService.run em série sintética semeada (payload completo)', { timeout: 60000 }, async () => {
    const { connect, cacheSet } = require('../../backend/src/db');
    const arService = require('../../backend/src/services/arService');
    const pts = [];
    const d0 = new Date('2026-01-01T12:00:00Z');
    for (let i = 0; i < 100; i++) {
      const d = new Date(d0);
      d.setUTCDate(d.getUTCDate() + i);
      pts.push({ date: d.toISOString().slice(0, 10), price_brl: 100 + i * 0.1 + Math.sin(i / 5) * 2 });
    }
    cacheSet('prices:soja:1y', { points: pts }, 60 * 1000);
    try {
      const out = await arService.run('soja', 14);
      assert.equal(out.model, 'ar');
      assert.ok(out.ar_order >= 1 && out.ar_order <= 8);
      assert.equal(out.horizon_days, 14);
      assert.equal(out.forecast.length, 14);
      assert.ok(['ar', 'baseline'].includes(out.model_selected));
      for (const H of ['h7', 'h14', 'h30']) assert.ok(out.recursive_eval[H].origins >= 0);
      assert.equal(out.limitations.length, 5);
      assert.ok(Number.isFinite(out.interval_sigma) && out.interval_sigma >= 0);
    } finally {
      connect().prepare('DELETE FROM kv_cache WHERE key = ?').run('prices:soja:1y');
    }
  });
});
