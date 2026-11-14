'use strict';

// Testes do worker (Release 2): agenda, locks, saúde, ciclo e idempotência.
// Banco temporário; nenhuma chamada de rede (priceService é substituído).
process.env.DATABASE_PATH = require('path').join(__dirname, '..', '..', 'tmp', 'test-worker.db');
process.env.SADEN_WORKER_RUN_ON_START = '0';

const fs = require('fs');
const { describe, it, before, beforeEach } = require('node:test');
const assert = require('node:assert/strict');

const db = require('../../backend/src/db');

function iso(offsetMs) {
  return new Date(Date.now() + offsetMs).toISOString();
}
function today(offsetDays = 0) {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() + offsetDays);
  return d.toISOString().slice(0, 10);
}
function makeUser(email) {
  return Number(
    db
      .connect()
      .prepare("INSERT INTO users(name, email, password_hash) VALUES('T', ?, 'x')")
      .run(email).lastInsertRowid
  );
}
function makeAlert(userId, seriesId, condition, threshold) {
  return Number(
    db
      .connect()
      .prepare(
        `INSERT INTO alerts(user_id, commodity_key, kind, condition, series_id, threshold, currency, unit, status, active, updated_at)
         VALUES(?, 'cafe', ?, ?, ?, ?, 'BRL', 'R$/sc 60kg', 'active', 1, datetime('now'))`
      )
      .run(userId, condition, condition, seriesId, threshold).lastInsertRowid
  );
}
function seedObservation(commodityKey, price, date) {
  db.connect()
    .prepare(
      `INSERT OR REPLACE INTO price_observations(commodity_key, data_date, price_usd, fx_rate, price_brl, unit_br, provider)
       VALUES(?, ?, ?, 5.5, ?, 'R$/sc 60kg', 'yahoo')`
    )
    .run(commodityKey, date, price / 5.5, price);
}

describe('agenda do worker', () => {
  const scheduler = require('../../backend/src/worker/scheduler');

  it('dia útil antes do horário preferencial executa hoje', () => {
    // 2026-11-16 é segunda-feira. 10h local (13h UTC em SP, UTC-3).
    const from = new Date('2026-11-16T13:00:00Z');
    const next = scheduler.nextRun(from, { preferredHourLocal: 18, timezone: 'America/Sao_Paulo' });
    assert.equal(next.toISOString(), '2026-11-16T21:00:00.000Z');
  });

  it('depois do horário preferencial vai para o próximo dia útil', () => {
    const from = new Date('2026-11-16T22:00:00Z'); // segunda 19h local
    const next = scheduler.nextRun(from, { preferredHourLocal: 18 });
    assert.equal(next.toISOString(), '2026-11-17T21:00:00.000Z', 'terça 18h local');
  });

  it('sexta após o horário pula o fim de semana e cai na segunda', () => {
    const from = new Date('2026-11-20T22:00:00Z'); // sexta 19h local
    const next = scheduler.nextRun(from, { preferredHourLocal: 18 });
    assert.equal(next.toISOString(), '2026-11-23T21:00:00.000Z', 'segunda 18h local');
  });

  it('sábado nunca é escolhido', () => {
    const from = new Date('2026-11-21T12:00:00Z'); // sábado
    const next = scheduler.nextRun(from, { preferredHourLocal: 18 });
    const parts = scheduler.localParts(next);
    assert.notEqual(parts.weekday, 'Sat');
    assert.notEqual(parts.weekday, 'Sun');
  });

  it('isMarketDay distingue dia útil de fim de semana', () => {
    assert.equal(scheduler.isMarketDay(new Date('2026-11-16T12:00:00Z')), true);
    assert.equal(scheduler.isMarketDay(new Date('2026-11-21T12:00:00Z')), false);
    assert.equal(scheduler.isMarketDay(new Date('2026-11-22T12:00:00Z')), false);
  });

  it('fromLocal devolve o instante local correto', () => {
    const date = scheduler.fromLocal(2026, 11, 16, 18, 0);
    assert.equal(date.toISOString(), '2026-11-16T21:00:00.000Z');
  });
});

describe('locks persistentes', () => {
  const locks = require('../../backend/src/worker/locks');
  const JOB = 'test-job';

  before(() => {
    try {
      fs.unlinkSync(process.env.DATABASE_PATH);
    } catch {
      /* primeiro run */
    }
    db.connect();
  });

  beforeEach(() => {
    db.connect().prepare('DELETE FROM worker_locks').run();
  });

  it('adquire quando livre e recusa quando em posse de outro', () => {
    const first = locks.acquire(JOB, 'worker-a', 60000);
    assert.equal(first.acquired, true);
    const second = locks.acquire(JOB, 'worker-b', 60000);
    assert.equal(second.acquired, false);
    assert.equal(second.owner, 'worker-a');
  });

  it('o dono renova o próprio lease', () => {
    locks.acquire(JOB, 'worker-a', 60000);
    assert.equal(locks.acquire(JOB, 'worker-a', 60000).acquired, true, 'dono pode reentrar');
    assert.equal(locks.heartbeat(JOB, 'worker-a', 60000), true);
    assert.equal(locks.heartbeat(JOB, 'worker-b', 60000), false, 'não-dono não renova');
  });

  it('lease expirado pode ser recuperado por outra instância', () => {
    locks.acquire(JOB, 'worker-a', -1000); // já expirado
    const recovered = locks.acquire(JOB, 'worker-b', 60000);
    assert.equal(recovered.acquired, true, 'lease vencido é recuperável');
    assert.equal(locks.info(JOB).owner, 'worker-b');
  });

  it('release libera para a próxima execução', () => {
    locks.acquire(JOB, 'worker-a', 60000);
    assert.equal(locks.release(JOB, 'worker-a'), true);
    assert.equal(locks.acquire(JOB, 'worker-b', 60000).acquired, true);
  });

  it('release de não-dono não libera o lock alheio', () => {
    locks.acquire(JOB, 'worker-a', 60000);
    assert.equal(locks.release(JOB, 'worker-b'), false);
    assert.equal(locks.info(JOB).owner, 'worker-a');
  });

  it('reapExpired limpa locks vencidos', () => {
    locks.acquire(JOB, 'worker-a', -1000);
    assert.ok(locks.reapExpired() >= 1);
    assert.equal(locks.info(JOB), null);
  });
});

describe('saúde do worker', () => {
  const health = require('../../backend/src/worker/health');

  it('sem heartbeat: not_started', () => {
    db.connect().prepare('DELETE FROM worker_heartbeat').run();
    const status = health.status();
    assert.equal(status.status, 'not_started');
    assert.equal(status.alive, false);
  });

  it('heartbeat recente: ok', () => {
    health.beat('worker-teste');
    const status = health.status();
    assert.equal(status.status, 'ok');
    assert.equal(status.alive, true);
    assert.equal(status.worker_id, 'worker-teste');
  });

  it('heartbeat antigo: down (processo ausente)', () => {
    db.connect()
      .prepare("UPDATE worker_heartbeat SET heartbeat_at = ? WHERE id = 1")
      .run(iso(-10 * 60 * 1000));
    const status = health.status();
    assert.equal(status.status, 'down');
    assert.equal(status.alive, false);
  });

  it('última execução com falha: degraded (API pode estar de pé, worker não)', () => {
    health.beat('worker-teste');
    db.connect()
      .prepare(
        "INSERT INTO worker_runs(job_key, owner, started_at, finished_at, status, series_failed) VALUES('monitor-series','w',?,?,'failed',1)"
      )
      .run(iso(-60000), iso(-59000));
    assert.equal(health.status().status, 'degraded');
  });

  it('próxima execução é sempre no futuro e em dia útil', () => {
    const status = health.status();
    assert.ok(new Date(status.next_run_at).getTime() > Date.now());
  });
});

describe('ciclo do worker', () => {
  const priceService = require('../../backend/src/services/priceService');
  const runner = require('../../backend/src/worker/runner');
  const seriesService = require('../../backend/src/services/seriesService');
  const SERIES = 'yahoo:KC=F:brl:sc60';
  let userId;
  let originalGetSeries;
  let scenario;

  before(() => {
    db.connect();
    userId = makeUser('worker@saden.local');
    originalGetSeries = priceService.getSeries;
    // Substitui a fonte por um cenário controlado (sem rede).
    priceService.getSeries = async (commodityKey) => {
      if (scenario.error) throw scenario.error;
      if (scenario.price != null) seedObservation(commodityKey, scenario.price, scenario.date);
      return { points: [], count: 0, commodity: { key: commodityKey } };
    };
  });

  beforeEach(() => {
    db.connect().prepare('DELETE FROM alerts').run();
    db.connect().prepare('DELETE FROM alert_events').run();
    db.connect().prepare('DELETE FROM price_observations').run();
    db.connect().prepare('DELETE FROM series_state').run();
    db.connect().prepare('DELETE FROM worker_runs').run();
    scenario = { price: null, date: today() };
  });

  it('sem séries com alerta ativo: ciclo vazio e registrado', async () => {
    const summary = await runner.runCycle({ owner: 'test', force: true });
    assert.equal(summary.series_total, 0);
    assert.equal(summary.status, 'ok');
    const row = db.connect().prepare('SELECT * FROM worker_runs WHERE id = ?').get(summary.run_id);
    assert.equal(row.finished_at !== null, true);
  });

  it('persiste a observação e dispara o alerta no mesmo ciclo', async () => {
    makeAlert(userId, SERIES, 'price_above', 150);
    scenario = { price: 200, date: today() };
    const summary = await runner.runCycle({ owner: 'test', force: true });
    assert.equal(summary.series_ok, 1);
    assert.equal(summary.observations_new, 1);
    assert.equal(summary.events_created, 1);

    const event = db.connect().prepare("SELECT * FROM alert_events WHERE event_type = 'trigger'").get();
    assert.equal(event.observed_price, 200);
    const alert = db.connect().prepare('SELECT status FROM alerts').get();
    assert.equal(alert.status, 'triggered');
  });

  it('rodar de novo com a mesma observação não duplica evento', async () => {
    makeAlert(userId, SERIES, 'price_above', 150);
    scenario = { price: 200, date: today() };
    const first = await runner.runCycle({ owner: 'test', force: true });
    // rearma para o motor tentar de novo com a mesma observação
    db.connect().prepare("UPDATE alerts SET status='active', active=1, triggered_at=NULL").run();
    const second = await runner.runCycle({ owner: 'test', force: true });
    const count = db.connect().prepare("SELECT COUNT(*) n FROM alert_events WHERE event_type='trigger'").get().n;
    assert.equal(first.events_created, 1);
    assert.equal(second.events_created, 0, 'idempotência no banco');
    assert.equal(count, 1);
  });

  it('observação nova depois de rearme gera evento novo', async () => {
    makeAlert(userId, SERIES, 'price_above', 150);
    scenario = { price: 200, date: today() };
    await runner.runCycle({ owner: 'test', force: true });
    db.connect().prepare("UPDATE alerts SET status='active', active=1, triggered_at=NULL").run();
    scenario = { price: 210, date: today(1) };
    const second = await runner.runCycle({ owner: 'test', force: true });
    assert.equal(second.events_created, 1);
    assert.equal(second.observations_new, 1);
  });

  it('falha da fonte é registrada sem disparar e sem apagar dado anterior', async () => {
    makeAlert(userId, SERIES, 'price_above', 150);
    scenario = { price: 200, date: today() };
    await runner.runCycle({ owner: 'test', force: true });
    db.connect().prepare("UPDATE alerts SET status='active', active=1, triggered_at=NULL").run();
    scenario = { error: new Error('timeout ao consultar provedor') };
    const summary = await runner.runCycle({ owner: 'test', force: true });
    assert.equal(summary.series_failed, 1);
    assert.equal(summary.events_created, 0, 'falha não dispara');
    const state = db.connect().prepare('SELECT * FROM series_state WHERE series_id = ?').get(SERIES);
    assert.equal(state.consecutive_failures, 1);
    assert.match(state.last_error, /timeout/);
    assert.ok(seriesService.latestObservationFor('cafe'), 'último dado válido preservado');
  });

  it('classificação de erro separa timeout, indisponibilidade e limite', () => {
    assert.equal(runner.classifyError(new Error('timed out')), 'timeout');
    assert.equal(runner.classifyError(Object.assign(new Error('x'), { status: 502 })), 'source_unavailable');
    assert.equal(runner.classifyError(new Error('429 rate limit')), 'rate_limited');
    assert.equal(runner.classifyError(Object.assign(new Error('x'), { status: 401 })), 'auth_error');
  });

  it('intervalo mínimo por série evita consulta repetida', async () => {
    makeAlert(userId, SERIES, 'price_above', 150);
    scenario = { price: 200, date: today() };
    await runner.runCycle({ owner: 'test', force: true });
    const due = runner.dueSeries(new Date());
    assert.equal(due.length, 0, 'série consultada há instantes não está vencida');
  });

  it('métricas agregam execuções sem dados pessoais', async () => {
    makeAlert(userId, SERIES, 'price_above', 150);
    scenario = { price: 200, date: today() };
    await runner.runCycle({ owner: 'test', force: true });
    const metrics = runner.metrics({ windowDays: 1 });
    assert.ok(metrics.runs >= 1);
    assert.ok(metrics.events_created >= 1);
    assert.ok(metrics.success_rate > 0);
    assert.equal(JSON.stringify(metrics).includes('@saden.local'), false, 'sem e-mail nas métricas');
  });
});

describe('encerramento', () => {
  it('shutdown libera o lock e é idempotente', () => {
    const locks = require('../../backend/src/worker/locks');
    const worker = require('../../backend/src/worker/index');
    locks.acquire(worker.config.jobKey, worker.config.workerId, 60000);
    assert.ok(locks.info(worker.config.jobKey));
    const originalExit = process.exit;
    process.exit = () => {};
    try {
      worker.shutdown('SIGTERM');
      worker.shutdown('SIGTERM');
    } finally {
      process.exit = originalExit;
    }
    assert.equal(locks.info(worker.config.jobKey), null, 'lock liberado no shutdown');
  });
});
