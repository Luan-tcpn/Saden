'use strict';

// Integração do monitoramento automático (Release 2).
//
// O teste decisivo: o alerta dispara com o "navegador fechado", isto é, sem
// nenhuma requisição do usuário — só o ciclo do worker e o banco.
process.env.DATABASE_PATH = require('path').join(__dirname, '..', '..', 'tmp', 'test-worker-api.db');
process.env.SADEN_ADMIN_EMAILS = 'operador@saden.local';

const fs = require('fs');
const { describe, it, before, after } = require('node:test');
const assert = require('node:assert/strict');

const db = require('../../backend/src/db');

let base;
let server;
let token;
let otherToken;
const SERIES = 'yahoo:KC=F:brl:sc60';

async function api(pathname, { method = 'GET', body, token: bearer } = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (bearer) headers.Authorization = `Bearer ${bearer}`;
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

function seedObservation(price, date) {
  db.connect()
    .prepare(
      `INSERT OR REPLACE INTO price_observations(commodity_key, data_date, price_usd, fx_rate, price_brl, unit_br, provider)
       VALUES('cafe', ?, ?, 5.5, ?, 'R$/sc 60kg', 'yahoo')`
    )
    .run(date, price / 5.5, price);
}

describe('monitoramento automático — integração', () => {
  let priceService;
  let originalGetSeries;
  let scenario;

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

    priceService = require('../../backend/src/services/priceService');
    originalGetSeries = priceService.getSeries;
    // Fixture determinístico: substitui a fonte externa no ciclo do worker.
    priceService.getSeries = async (commodityKey) => {
      if (scenario && scenario.error) throw scenario.error;
      if (scenario && scenario.price != null) seedObservation(scenario.price, scenario.date);
      return { points: [], count: 0, cached: false };
    };

    const first = await api('/api/auth/register', {
      method: 'POST',
      body: { name: 'Monitor', email: 'monitor@saden.local', password: '123456' },
    });
    token = first.data.token;
    const second = await api('/api/auth/register', {
      method: 'POST',
      body: { name: 'Outro', email: 'outro-monitor@saden.local', password: '123456' },
    });
    otherToken = second.data.token;

    db.connect()
      .prepare("INSERT INTO users(name, email, password_hash) VALUES('Operador', 'operador@saden.local', 'x')")
      .run();
  });

  after(() => {
    priceService.getSeries = originalGetSeries;
    server.close();
  });

  it('dispensa o navegador: alerta dispara por ciclo do worker e fica persistido', async () => {
    const today = new Date().toISOString().slice(0, 10);
    const created = await api('/api/alerts', {
      method: 'POST',
      token,
      body: { series_id: SERIES, condition: 'price_above', threshold: 150, label: 'sem navegador' },
    });
    assert.equal(created.status, 201);

    // Antes do ciclo não há evento nenhum.
    const before = await api('/api/alerts/events', { token });
    assert.equal(before.data.events.length, 0);

    // "Navegador fechado": nenhuma chamada do usuário daqui em diante.
    scenario = { price: 200, date: today };
    const runner = require('../../backend/src/worker/runner');
    const cycle = await runner.runCycle({ owner: 'integration-test', force: true });
    assert.equal(cycle.events_created, 1);
    assert.equal(cycle.observations_new, 1);

    // Reabrir a interface = consultar o feed. O evento está lá.
    const feed = await api('/api/alerts/events', { token });
    assert.equal(feed.data.events.length, 1);
    const event = feed.data.events[0];
    assert.equal(event.observed_price, 200);
    assert.equal(event.observation_date, today);
    assert.equal(event.read, false);
    assert.equal(event.condition, 'price_above');
  });

  it('ciclo repetido não duplica evento (idempotência no banco)', async () => {
    db.connect().prepare("UPDATE alerts SET status='active', active=1, triggered_at=NULL").run();
    const runner = require('../../backend/src/worker/runner');
    const again = await runner.runCycle({ owner: 'integration-test', force: true });
    assert.equal(again.events_created, 0);
    const count = db.connect().prepare("SELECT COUNT(*) n FROM alert_events WHERE event_type='trigger'").get().n;
    assert.equal(count, 1);
  });

  it('recuperação após "queda": lease expirado é assumido, sem evento duplicado', async () => {
    const locks = require('../../backend/src/worker/locks');
    const config = require('../../backend/src/worker/config');
    // Simula worker morto no meio do ciclo: lock nosso, já vencido.
    locks.acquire(config.jobKey, 'worker-morto', -1000);
    const other = locks.acquire(config.jobKey, 'worker-novo', 60000);
    assert.equal(other.acquired, true, 'lease vencido é recuperável');
    locks.release(config.jobKey, 'worker-novo');

    db.connect().prepare("UPDATE alerts SET status='active', active=1, triggered_at=NULL").run();
    const runner = require('../../backend/src/worker/runner');
    const cycle = await runner.runCycle({ owner: 'worker-novo', force: true });
    assert.equal(cycle.events_created, 0, 'mesma observação não gera segundo evento');
    assert.equal(db.connect().prepare("SELECT COUNT(*) n FROM alert_events WHERE event_type='trigger'").get().n, 1);
  });

  it('fonte indisponível: ciclo falha sem disparar e mantém o alerta ativo', async () => {
    db.connect().prepare("UPDATE alerts SET status='active', active=1, triggered_at=NULL").run();
    db.connect().prepare('DELETE FROM series_state').run();
    scenario = { error: Object.assign(new Error('timeout na fonte'), { status: 504 }) };
    const runner = require('../../backend/src/worker/runner');
    const cycle = await runner.runCycle({ owner: 'integration-test', force: true });
    assert.equal(cycle.series_failed, 1);
    assert.equal(cycle.events_created, 0);
    const alert = db.connect().prepare('SELECT status FROM alerts').get();
    assert.equal(alert.status, 'active', 'alerta continua armado para a próxima tentativa');
    const state = db.connect().prepare("SELECT * FROM series_state WHERE series_id = ?").get(SERIES);
    assert.equal(state.last_error, 'source_unavailable');
    scenario = { price: 200, date: new Date().toISOString().slice(0, 10) };
  });

  it('duas instâncias não executam o mesmo job ao mesmo tempo', () => {
    const locks = require('../../backend/src/worker/locks');
    const config = require('../../backend/src/worker/config');
    locks.release(config.jobKey, 'a');
    const a = locks.acquire(config.jobKey, 'instancia-a', 60000);
    const b = locks.acquire(config.jobKey, 'instancia-b', 60000);
    assert.equal(a.acquired, true);
    assert.equal(b.acquired, false);
    assert.equal(b.owner, 'instancia-a');
    locks.release(config.jobKey, 'instancia-a');
  });

  it('health do worker é público e reflete o heartbeat; ops exige admin', async () => {
    const health = require('../../backend/src/worker/health');
    health.beat('worker-integration');
    const publicHealth = await api('/api/health/worker');
    assert.equal(publicHealth.status, 200);
    assert.equal(publicHealth.data.alive, true);
    assert.ok(['ok', 'degraded'].includes(publicHealth.data.status));
    assert.ok(publicHealth.data.next_run_at);

    // Depois de um ciclo bem-sucedido o estado volta a "ok".
    db.connect()
      .prepare(
        "INSERT INTO worker_runs(job_key, owner, started_at, finished_at, status, series_ok) VALUES('monitor-series','w',?,?,'ok',1)"
      )
      .run(new Date().toISOString(), new Date().toISOString());
    const healthy = await api('/api/health/worker');
    assert.equal(healthy.data.status, 'ok');

    const anonymousOps = await api('/api/ops/status');
    assert.equal(anonymousOps.status, 401);
    const userOps = await api('/api/ops/status', { token });
    assert.equal(userOps.status, 403, 'usuário comum não vê operação');
  });

  it('rate limit protege a avaliação manual por usuário', async () => {
    const rateLimit = require('../../backend/src/middleware/rateLimit');
    rateLimit._reset();
    let last = 0;
    for (let i = 0; i < 22; i++) {
      const response = await api('/api/alerts/evaluate', { method: 'POST', token: otherToken });
      last = response.status;
    }
    assert.equal(last, 429, 'excesso de avaliações é bloqueado');
    // Outro usuário não é afetado pelo limite do primeiro.
    const other = await api('/api/alerts/evaluate', { method: 'POST', token });
    assert.notEqual(other.status, 429);
    rateLimit._reset();
  });

  it('feed é isolado por usuário mesmo com worker global', async () => {
    const mine = await api('/api/alerts/events', { token });
    const theirs = await api('/api/alerts/events', { token: otherToken });
    assert.ok(mine.data.events.length >= 1);
    assert.equal(theirs.data.events.length, 0, 'worker avalia para todos, mas cada um vê só o seu');
  });

  it('worker parado é visível: status down e alerta continua "ativo"', async () => {
    const health = require('../../backend/src/worker/health');
    db.connect()
      .prepare("UPDATE worker_heartbeat SET heartbeat_at = ? WHERE id = 1")
      .run(new Date(Date.now() - 10 * 60 * 1000).toISOString());
    const response = await api('/api/health/worker');
    assert.equal(response.status, 503);
    assert.equal(response.data.status, 'down');

    const alerts = await api('/api/alerts', { token });
    const arms = alerts.data.alerts.filter((a) => a.status === 'active').length;
    assert.ok(arms >= 1, 'o alerta segue ativo — é o estado real, e a saúde denuncia o problema');
  });
});
