'use strict';
// Smoke test E2E contra servidor em execução (padrão http://localhost:3001).
// Uso: node scripts/smoke-test.js [baseUrl]
// Retorna exit 1 em qualquer falha. Não bloqueia: timeouts curtos por etapa.
const BASE = process.argv[2] || 'http://localhost:3001';

async function req(path, { method = 'GET', body, token, timeoutMs = 90000 } = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(`${BASE}${path}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
      signal: ctrl.signal,
    });
    const data = await res.json().catch(() => null);
    return { status: res.status, data };
  } finally {
    clearTimeout(t);
  }
}

function check(name, cond, extra) {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}${extra ? ` — ${extra}` : ''}`);
  if (!cond) process.exitCode = 1;
}

(async () => {
  const email = `smoke${Date.now()}@saden.local`;
  const reg = await req('/api/auth/register', {
    method: 'POST',
    body: { name: 'Smoke', email, password: '123456' },
    timeoutMs: 15000,
  });
  check('register', reg.status === 201 && reg.data.token, `http ${reg.status}`);
  const token = reg.data.token;

  const login = await req('/api/auth/login', {
    method: 'POST',
    body: { email, password: '123456' },
    timeoutMs: 15000,
  });
  check('login', login.status === 200, `http ${login.status}`);

  const noAuth = await req('/api/commodities', { timeoutMs: 15000 });
  check('proteção sem token (401)', noAuth.status === 401, `http ${noAuth.status}`);

  const latest = await req('/api/commodities/soja/latest', { token });
  check('preço real soja', latest.status === 200 && latest.data.price_brl > 0, `http ${latest.status} R$ ${latest.data && latest.data.price_brl}`);

  const wx = await req('/api/weather/forecast?lat=-21.1775&lon=-47.8103', { token, timeoutMs: 60000 });
  check('clima real', wx.status === 200 && wx.data.daily.length === 7, `http ${wx.status}`);

  const geo = await req('/api/geo/search?q=Ribeirao%20Preto', { token, timeoutMs: 60000 });
  check('geocodificação', geo.status === 200 && geo.data.count > 0, `http ${geo.status}`);

  const fc = await req('/api/forecast/soja?horizon=7', { token, timeoutMs: 120000 });
  check('previsão', fc.status === 200 && fc.data.forecast.length === 7, `http ${fc.status} modelo=${fc.data && fc.data.model}`);

  const rep = await req('/api/reports/soja?lat=-21.17&lon=-47.81&horizon=7', { token, timeoutMs: 120000 });
  check('relatório', rep.status === 200 && rep.data.forecast.points.length === 7, `http ${rep.status}`);

  console.log(process.exitCode ? 'SMOKE: FALHAS DETECTADAS' : 'SMOKE: OK ponta a ponta');
})();
