'use strict';

// Migração V1.1 → product release 1: um banco com o schema antigo (sem as
// colunas novas) precisa ser atualizado sem perda de dados, com backfill.
process.env.DATABASE_PATH = require('path').join(__dirname, '..', '..', 'tmp', 'test-migration.db');

const fs = require('fs');
const { describe, it, before } = require('node:test');
const assert = require('node:assert/strict');

const Database = require('../../backend/node_modules/better-sqlite3');

describe('migração do schema V1.1 de alertas', () => {
  let legacy;
  let userId;

  before(() => {
    try {
      fs.unlinkSync(process.env.DATABASE_PATH);
    } catch {
      /* primeiro run */
    }
    fs.mkdirSync(require('path').dirname(process.env.DATABASE_PATH), { recursive: true });
    // Banco no formato exato da V1.1 (alerts/alert_events originais).
    legacy = new Database(process.env.DATABASE_PATH);
    legacy.exec(`
      CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT (datetime('now'))
      );
      CREATE TABLE alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        commodity_key TEXT NOT NULL, kind TEXT NOT NULL, threshold REAL NOT NULL,
        latitude REAL, longitude REAL, label TEXT,
        active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
      );
      CREATE TABLE alert_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        alert_id INTEGER NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
        evaluated_at TEXT NOT NULL DEFAULT (datetime('now')),
        triggered INTEGER NOT NULL, value REAL, detail TEXT
      );
    `);
    userId = Number(
      legacy.prepare("INSERT INTO users(name, email, password_hash) VALUES('Legado', 'legado@saden.local', 'x')").run()
        .lastInsertRowid
    );
    legacy
      .prepare("INSERT INTO alerts(user_id, commodity_key, kind, threshold, label, active) VALUES(?, 'soja', 'price_below', 120.5, 'legado ativo', 1)")
      .run(userId);
    legacy
      .prepare("INSERT INTO alerts(user_id, commodity_key, kind, threshold, label, active) VALUES(?, 'milho', 'price_above', 70, 'legado pausado', 0)")
      .run(userId);
    legacy
      .prepare("INSERT INTO alert_events(alert_id, triggered, value, detail) VALUES(1, 1, 120.5, 'antigo')")
      .run();
    legacy.close();
  });

  it('aplica as colunas novas mantendo as antigas', () => {
    const db = require('../../backend/src/db');
    const connection = db.connect();
    const alerts = connection.prepare('PRAGMA table_info(alerts)').all().map((c) => c.name);
    for (const column of ['series_id', 'condition', 'status', 'triggered_at', 'last_price', 'unit', 'currency']) {
      assert.ok(alerts.includes(column), `alerts.${column} criada`);
    }
    for (const column of ['commodity_key', 'kind', 'threshold', 'active', 'latitude']) {
      assert.ok(alerts.includes(column), `alerts.${column} preservada`);
    }
    const events = connection.prepare('PRAGMA table_info(alert_events)').all().map((c) => c.name);
    for (const column of ['event_type', 'observation_date', 'observed_price', 'read_at']) {
      assert.ok(events.includes(column), `alert_events.${column} criada`);
    }
    for (const column of ['triggered', 'value', 'detail']) {
      assert.ok(events.includes(column), `alert_events.${column} preservada`);
    }
  });

  it('backfill preenche condition, status e series_id', () => {
    const rows = require('../../backend/src/db')
      .connect()
      .prepare('SELECT * FROM alerts ORDER BY id')
      .all();
    assert.equal(rows.length, 2, 'nenhum alerta perdido');
    assert.equal(rows[0].condition, 'price_below');
    assert.equal(rows[0].status, 'active');
    assert.equal(rows[0].series_id, 'yahoo:ZS=F:brl:sc60', 'série derivada da commodity');
    assert.equal(rows[0].label, 'legado ativo');
    assert.equal(rows[1].condition, 'price_above');
    assert.equal(rows[1].status, 'paused');
    assert.equal(rows[1].series_id, 'yahoo:ZC=F:brl:sc60');
  });

  it('eventos antigos são classificados como avaliação', () => {
    const events = require('../../backend/src/db').connect().prepare('SELECT * FROM alert_events').all();
    assert.equal(events.length, 1);
    assert.equal(events[0].event_type, 'evaluation');
    assert.equal(events[0].detail, 'antigo');
  });

  it('a migração é idempotente (segunda execução não quebra nem duplica)', () => {
    const db = require('../../backend/src/db');
    assert.doesNotThrow(() => db.connect());
    const count = db.connect().prepare('SELECT COUNT(*) n FROM alerts').get().n;
    assert.equal(count, 2);
  });

  it('o motor ignora alertas de chuva legados', () => {
    const connection = require('../../backend/src/db').connect();
    connection
      .prepare("INSERT INTO alerts(user_id, commodity_key, kind, condition, series_id, threshold, status, active) VALUES(?, 'soja', 'rain_above', NULL, NULL, 50, 'active', 1)")
      .run(userId);
    const engine = require('../../backend/src/services/alertEngine');
    const summary = engine.evaluateSeries('yahoo:ZS=F:brl:sc60', { userId });
    // Uma regra de preço ativa na soja (a segunda está pausada); a de chuva fica de fora.
    assert.equal(summary.evaluated, 1);
    assert.equal(summary.results[0].alert.condition, 'price_below');
  });
});
