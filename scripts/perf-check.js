'use strict';
// P16: medição de latência cold vs warm + contagem de chamadas por fluxo.
// Uso: node scripts/perf-check.js  (servidor em execução)
// Não otimiza nada — apenas mede (medir antes de otimizar).
const BASE = 'http://localhost:3001';

async function timed(label, fn) {
  const t = Date.now();
  const r = await fn();
  const ms = Date.now() - t;
  console.log(`${label}: ${ms}ms (http ${r.status})`);
  return { ms, ...r };
}

(async () => {
  const email = `perf${Date.now()}@saden.local`;
  const reg = await (
    await fetch(`${BASE}/api/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: 'Perf', email, password: '123456' }),
    })
  ).json();
  const H = { Authorization: `Bearer ${reg.token}` };
  const get = (p) => fetch(`${BASE}${p}`, { headers: H }).then(async (r) => ({ status: r.status, data: await r.json().catch(() => null) }));

  console.log('--- COLD (primeira chamada; upstream real) ---');
  await timed('latest soja (cold)', () => get('/api/commodities/soja/latest'));
  await timed('series soja 1y (cold)', () => get('/api/commodities/soja/series?range=1y'));
  await timed('forecast soja 14d (cold)', () => get('/api/forecast/soja?horizon=14'));
  await timed('weather (cold)', () => get('/api/weather/forecast?lat=-21.1775&lon=-47.8103'));

  console.log('--- WARM (cache) ---');
  await timed('latest soja (warm)', () => get('/api/commodities/soja/latest'));
  await timed('series soja 1y (warm)', () => get('/api/commodities/soja/series?range=1y'));
  await timed('forecast soja 14d (warm-ish)', () => get('/api/forecast/soja?horizon=14'));
  await timed('weather (warm)', () => get('/api/weather/forecast?lat=-21.1775&lon=-47.8103'));

  console.log('--- FLUXO DASHBOARD (contagem de chamadas) ---');
  // dashboard faz: latest + series + forecast + weather + N latest (comparação)
  const t0 = Date.now();
  const calls = [
    '/api/commodities/soja/latest',
    '/api/commodities/soja/series?range=1y',
    '/api/forecast/soja?horizon=14',
    '/api/weather/forecast?lat=-21.1775&lon=-47.8103',
    '/api/commodities/soja/latest',
    '/api/commodities/milho/latest',
    '/api/commodities/cafe/latest',
    '/api/commodities/trigo/latest',
    '/api/commodities/algodao/latest',
  ];
  await Promise.all(calls.map((c) => get(c)));
  console.log(`dashboard: ${calls.length} chamadas em ${Date.now() - t0}ms (warm)`);
})().catch((e) => {
  console.error(`PERF-FAIL: ${e.message}`);
  process.exit(1);
});
