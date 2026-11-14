'use strict';

// Testes determinísticos do catálogo de séries e do motor de alertas.
// Banco temporário; nenhuma chamada de rede.
process.env.DATABASE_PATH = require('path').join(__dirname, '..', '..', 'tmp', 'test-alerts-unit.db');

const fs = require('fs');
const { describe, it, before, beforeEach } = require('node:test');
const assert = require('node:assert/strict');

const db = require('../../backend/src/db');

function today(offsetDays = 0) {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() + offsetDays);
  return d.toISOString().slice(0, 10);
}

function seedObservation(commodityKey, price, date = today(), unit = 'R$/sc 60kg') {
  db.connect()
    .prepare(
      `INSERT OR REPLACE INTO price_observations
         (commodity_key, data_date, price_usd, fx_rate, price_brl, unit_br, provider)
       VALUES (?, ?, ?, ?, ?, ?, 'yahoo')`
    )
    .run(commodityKey, date, price / 5.5, 5.5, price, unit);
}

function makeUser(email) {
  const info = db
    .connect()
    .prepare('INSERT INTO users(name, email, password_hash) VALUES(?, ?, ?)')
    .run('Teste', email, 'x');
  return Number(info.lastInsertRowid);
}

function makeAlert(userId, seriesId, condition, threshold, commodityKey) {
  const info = db
    .connect()
    .prepare(
      `INSERT INTO alerts(user_id, commodity_key, kind, condition, series_id, threshold, currency, unit, status, active, updated_at)
       VALUES(?, ?, ?, ?, ?, ?, 'BRL', 'R$/sc 60kg', 'active', 1, datetime('now'))`
    )
    .run(userId, commodityKey, condition, condition, seriesId, threshold);
  return Number(info.lastInsertRowid);
}

describe('catálogo de séries — identidade estável', () => {
  before(() => {
    try {
      fs.unlinkSync(process.env.DATABASE_PATH);
    } catch {
      /* primeiro run */
    }
    db.connect();
  });

  const seriesService = require('../../backend/src/services/seriesService');

  it('lista as 5 séries reais com id estável e único', () => {
    const list = seriesService.list();
    assert.equal(list.length, 5);
    const ids = list.map((s) => s.series_id);
    assert.equal(new Set(ids).size, ids.length, 'ids únicos');
    for (const s of list) {
      assert.match(s.series_id, /^yahoo:[A-Z]{2}=F:brl:(sc60|lp)$/);
      assert.equal(s.currency, 'BRL');
      assert.ok(s.unit.startsWith('R$/'));
      assert.ok(s.market.includes('CBOT') || s.market.includes('ICE'));
      assert.ok(s.limitations.some((l) => /produtor/.test(l)));
    }
  });

  it('o id distingue instrumento, moeda e unidade', () => {
    const byKey = Object.fromEntries(seriesService.list().map((s) => [s.commodity_key, s]));
    assert.equal(byKey.soja.series_id, 'yahoo:ZS=F:brl:sc60');
    assert.equal(byKey.milho.series_id, 'yahoo:ZC=F:brl:sc60');
    assert.equal(byKey.algodao.series_id, 'yahoo:CT=F:brl:lp');
    assert.notEqual(byKey.soja.series_id, byKey.milho.series_id, 'tickers diferentes ⇒ ids diferentes');
  });

  it('get() devolve a série pedida e 404 para id inexistente', () => {
    const s = seriesService.get('yahoo:ZS=F:brl:sc60');
    assert.equal(s.commodity_key, 'soja');
    assert.throws(() => seriesService.get('yahoo:ZS=F:usd:sc60'), (e) => e.status === 404);
    assert.throws(() => seriesService.get('lixo'), (e) => e.status === 404);
    assert.throws(() => seriesService.get('yahoo:XX=F:brl:sc60'), (e) => e.status === 404);
  });

  it('resolução commodity → série (compatibilidade V1.1)', () => {
    assert.equal(seriesService.seriesIdForCommodity('soja'), 'yahoo:ZS=F:brl:sc60');
    assert.equal(seriesService.seriesIdForCommodity('inexistente'), null);
  });

  it('freshness: recente = fresh, antigo = stale, ausente = unknown', () => {
    assert.equal(seriesService.freshnessFor(today(0)).status, 'fresh');
    assert.equal(seriesService.freshnessFor(today(-3)).status, 'fresh');
    assert.equal(seriesService.freshnessFor(today(-30)).status, 'stale');
    assert.equal(seriesService.freshnessFor(null).status, 'unknown');
    // Release 2: tolerancia de 4 dias corridos cobre fim de semana + feriado
    assert.equal(seriesService.freshnessFor(today(-30)).stale_after_days, 4);
    assert.equal(seriesService.freshnessFor(today(-4)).status, 'fresh', 'sexta ainda vale na terca');
    assert.equal(seriesService.freshnessFor(today(-8)).status, 'stale');
  });
});

describe('motor de alertas — condição, frescor, idempotência e estado', () => {
  let engine;
  let seriesService;
  let userId;
  const SERIES = 'yahoo:KC=F:brl:sc60';

  before(() => {
    engine = require('../../backend/src/services/alertEngine');
    seriesService = require('../../backend/src/services/seriesService');
    db.connect();
    userId = makeUser('engine@saden.local');
  });

  beforeEach(() => {
    const dbc = db.connect();
    dbc.prepare('DELETE FROM alert_events').run();
    dbc.prepare('DELETE FROM alerts').run();
    dbc.prepare("DELETE FROM price_observations WHERE commodity_key = 'cafe'").run();
  });

  it('meetsCondition respeita os limites (>= e <=)', () => {
    assert.equal(engine.meetsCondition('price_above', 100, 100), true, 'igual satisfaz acima');
    assert.equal(engine.meetsCondition('price_above', 100, 99.99), false);
    assert.equal(engine.meetsCondition('price_below', 100, 100), true, 'igual satisfaz abaixo');
    assert.equal(engine.meetsCondition('price_below', 100, 100.01), false);
    assert.equal(engine.meetsCondition('price_above', 100, NaN), false);
    assert.equal(engine.meetsCondition('desconhecida', 100, 200), false);
  });

  it('sem observação: não dispara e explica', () => {
    const alert = { id: 1, commodity_key: 'cafe', condition: 'price_above', threshold: 1, unit: 'R$/sc 60kg' };
    const ev = engine.evaluateAlert(alert, undefined);
    assert.equal(ev.triggered, false);
    assert.equal(ev.blocked, 'no_observation');
    assert.equal(ev.price, null);
  });

  it('dispara quando a condição é satisfeita por observação fresca', () => {
    const alert = { id: 1, commodity_key: 'cafe', condition: 'price_above', threshold: 150, unit: 'R$/sc 60kg' };
    const ev = engine.evaluateAlert(alert, { data_date: today(), price_brl: 200 });
    assert.equal(ev.triggered, true);
    assert.equal(ev.price, 200);
    assert.equal(ev.fresh, true);
  });

  it('NÃO dispara com observação desatualizada, mesmo satisfazendo a condição', () => {
    const alert = { id: 1, commodity_key: 'cafe', condition: 'price_above', threshold: 150, unit: 'R$/sc 60kg' };
    const ev = engine.evaluateAlert(alert, { data_date: today(-30), price_brl: 999 });
    assert.equal(ev.triggered, false, 'dado antigo não dispara');
    assert.equal(ev.blocked, 'stale');
    assert.match(ev.detail, /desatualizada/);
  });

  it('evento de disparo é idempotente para a mesma observação', () => {
    const alertId = makeAlert(userId, SERIES, 'price_above', 150, 'cafe');
    seedObservation('cafe', 200);
    const observation = seriesService.latestObservationFor('cafe');
    const alert = db.connect().prepare('SELECT * FROM alerts WHERE id = ?').get(alertId);

    const first = engine.evaluateAlert(alert, observation);
    assert.equal(engine.recordTrigger(alert, observation, first), true, 'primeiro cria');
    const repeated = engine.evaluateAlert(
      db.connect().prepare('SELECT * FROM alerts WHERE id = ?').get(alertId),
      observation
    );
    assert.equal(engine.recordTrigger(alert, observation, repeated), false, 'segundo não cria');
    const count = db.connect().prepare("SELECT COUNT(*) AS n FROM alert_events WHERE event_type = 'trigger'").get().n;
    assert.equal(count, 1, 'uma linha só');
  });

  it('após disparar, o alerta sai de "active" (disparo único)', () => {
    const alertId = makeAlert(userId, SERIES, 'price_above', 150, 'cafe');
    seedObservation('cafe', 200);
    const observation = seriesService.latestObservationFor('cafe');
    const alert = db.connect().prepare('SELECT * FROM alerts WHERE id = ?').get(alertId);
    engine.recordTrigger(alert, observation, engine.evaluateAlert(alert, observation));

    const row = db.connect().prepare('SELECT * FROM alerts WHERE id = ?').get(alertId);
    assert.equal(row.status, 'triggered');
    assert.equal(row.active, 0);
    assert.ok(row.triggered_at);
    assert.equal(engine.alertsForSeries(SERIES, { userId }).length, 0, 'não é mais avaliado');
  });

  it('reativar rearma e permite disparar com outra observação', () => {
    const alertId = makeAlert(userId, SERIES, 'price_above', 150, 'cafe');
    seedObservation('cafe', 200);
    let observation = seriesService.latestObservationFor('cafe');
    let alert = db.connect().prepare('SELECT * FROM alerts WHERE id = ?').get(alertId);
    engine.recordTrigger(alert, observation, engine.evaluateAlert(alert, observation));

    db.connect().prepare("UPDATE alerts SET status='active', active=1, triggered_at=NULL WHERE id = ?").run(alertId);
    seedObservation('cafe', 210, today(1));
    observation = seriesService.latestObservationFor('cafe');
    alert = db.connect().prepare('SELECT * FROM alerts WHERE id = ?').get(alertId);
    assert.equal(engine.recordTrigger(alert, observation, engine.evaluateAlert(alert, observation)), true);
    const rows = db.connect().prepare("SELECT observation_date FROM alert_events WHERE event_type='trigger' ORDER BY id").all();
    assert.equal(rows.length, 2, 'um evento por observação');
    assert.notEqual(rows[0].observation_date, rows[1].observation_date);
  });

  it('condição abaixo do limite dispara com preço menor', () => {
    const alertId = makeAlert(userId, SERIES, 'price_below', 150, 'cafe');
    seedObservation('cafe', 120);
    const observation = seriesService.latestObservationFor('cafe');
    const alert = db.connect().prepare('SELECT * FROM alerts WHERE id = ?').get(alertId);
    const ev = engine.evaluateAlert(alert, observation);
    assert.equal(ev.triggered, true);
    assert.equal(engine.recordTrigger(alert, observation, ev), true);
  });

  it('alertas de chuva (legado) são ignorados pelo motor de preço', () => {
    db.connect()
      .prepare(
        `INSERT INTO alerts(user_id, commodity_key, kind, condition, series_id, threshold, status, active, updated_at)
         VALUES(?, 'soja', 'rain_above', NULL, NULL, 50, 'active', 1, datetime('now'))`
      )
      .run(userId);
    const summary = engine.evaluateSeries('yahoo:ZS=F:brl:sc60', { userId });
    assert.equal(summary.evaluated, 0, 'nenhuma regra de preço avaliada');
  });

  it('evaluateSeries considera só alertas do usuário pedido', () => {
    const other = makeUser('outro-engine@saden.local');
    const mine = makeAlert(userId, SERIES, 'price_above', 150, 'cafe');
    const theirs = makeAlert(other, SERIES, 'price_above', 150, 'cafe');
    seedObservation('cafe', 200);
    const summary = engine.evaluateSeries(SERIES, { userId });
    assert.equal(summary.evaluated, 1);
    const dbc = db.connect();
    assert.equal(dbc.prepare("SELECT COUNT(*) AS n FROM alert_events WHERE alert_id = ?").get(theirs).n, 0);
    assert.equal(dbc.prepare("SELECT COUNT(*) AS n FROM alert_events WHERE alert_id = ?").get(mine).n, 1);
  });

  it('runAfterPriceRefresh nunca lança e informa a série', () => {
    const summary = engine.runAfterPriceRefresh('cafe');
    assert.equal(summary.status, 'ok');
    assert.equal(summary.series_id, SERIES);
    const unknown = engine.runAfterPriceRefresh('inexistente');
    assert.equal(unknown.status, 'unknown_series');
  });
});
