'use strict';

const fs = require('fs');
const path = require('path');
const Database = require('better-sqlite3');
const config = require('./config');

let db;

function connect() {
  if (db) return db;
  fs.mkdirSync(path.dirname(config.databasePath), { recursive: true });
  db = new Database(config.databasePath);
  db.pragma('journal_mode = WAL');
  db.pragma('foreign_keys = ON');
  migrate(db);
  prune(db);
  return db;
}

// Retenção proporcional: remove o que expirou ou envelheceu, sem infraestrutura.
// - kv_cache expirado; - resets usados/expirados há +7 dias;
// - relatórios além dos 500 mais recentes; - outbox dev com +7 dias.
function prune(database) {
  try {
    database.prepare('DELETE FROM kv_cache WHERE expires_at <= ?').run(Date.now());
    database
      .prepare("DELETE FROM password_resets WHERE (used_at IS NOT NULL OR expires_at < datetime('now')) AND created_at < datetime('now', '-7 days')")
      .run();
    database
      .prepare('DELETE FROM reports WHERE id NOT IN (SELECT id FROM reports ORDER BY id DESC LIMIT 500)')
      .run();
    const outbox = path.join(__dirname, '..', '..', 'tmp', 'mail-outbox');
    if (fs.existsSync(outbox)) {
      const cutoff = Date.now() - 7 * 24 * 3600 * 1000;
      for (const f of fs.readdirSync(outbox)) {
        const fp = path.join(outbox, f);
        try {
          if (fs.statSync(fp).mtimeMs < cutoff) fs.unlinkSync(fp);
        } catch {
          /* melhor esforço */
        }
      }
    }
  } catch (e) {
    // eslint-disable-next-line no-console
    console.error(JSON.stringify({ level: 'warn', kind: 'prune', message: e.message }));
  }
}

function migrate(database) {
  database.exec(`
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      email TEXT NOT NULL UNIQUE,
      password_hash TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS data_sources (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      key TEXT NOT NULL UNIQUE,
      name TEXT NOT NULL,
      base_url TEXT NOT NULL,
      docs_url TEXT,
      kind TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'active',
      notes TEXT
    );

    CREATE TABLE IF NOT EXISTS commodities (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      key TEXT NOT NULL UNIQUE,
      name TEXT NOT NULL,
      yahoo_symbol TEXT NOT NULL,
      unit_br TEXT NOT NULL,
      description TEXT
    );

    CREATE TABLE IF NOT EXISTS regions (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      kind TEXT NOT NULL,            -- 'state' | 'municipality' | 'point'
      uf TEXT,
      name TEXT NOT NULL,
      ibge_code INTEGER,
      latitude REAL,
      longitude REAL,
      UNIQUE(kind, ibge_code, latitude, longitude)
    );

    CREATE TABLE IF NOT EXISTS price_observations (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      commodity_key TEXT NOT NULL,
      data_date TEXT NOT NULL,
      price_usd REAL,
      fx_rate REAL,
      price_brl REAL NOT NULL,
      unit_br TEXT NOT NULL,
      provider TEXT NOT NULL,
      retrieved_at TEXT NOT NULL DEFAULT (datetime('now')),
      UNIQUE(commodity_key, data_date, provider)
    );
    CREATE INDEX IF NOT EXISTS idx_prices_commodity_date
      ON price_observations(commodity_key, data_date);

    CREATE TABLE IF NOT EXISTS weather_observations (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      latitude REAL NOT NULL,
      longitude REAL NOT NULL,
      data_date TEXT NOT NULL,
      t_mean REAL,
      t_max REAL,
      t_min REAL,
      precipitation REAL,
      humidity REAL,
      wind REAL,
      provider TEXT NOT NULL,
      retrieved_at TEXT NOT NULL DEFAULT (datetime('now')),
      UNIQUE(latitude, longitude, data_date, provider)
    );
    CREATE INDEX IF NOT EXISTS idx_weather_latlon_date
      ON weather_observations(latitude, longitude, data_date);

    CREATE TABLE IF NOT EXISTS model_runs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      commodity_key TEXT NOT NULL,
      model TEXT NOT NULL,
      horizon_days INTEGER NOT NULL,
      metrics_json TEXT NOT NULL,
      params_json TEXT,
      trained_at TEXT NOT NULL DEFAULT (datetime('now')),
      data_start TEXT,
      data_end TEXT
    );

    CREATE TABLE IF NOT EXISTS forecasts (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      model_run_id INTEGER NOT NULL REFERENCES model_runs(id) ON DELETE CASCADE,
      target_date TEXT NOT NULL,
      price_brl REAL NOT NULL,
      lower_brl REAL,
      upper_brl REAL
    );
    CREATE INDEX IF NOT EXISTS idx_forecasts_run ON forecasts(model_run_id);

    CREATE TABLE IF NOT EXISTS reports (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
      commodity_key TEXT NOT NULL,
      payload_json TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS password_resets (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      token_hash TEXT NOT NULL UNIQUE,
      expires_at TEXT NOT NULL,
      used_at TEXT,
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE INDEX IF NOT EXISTS idx_resets_token ON password_resets(token_hash);
    CREATE INDEX IF NOT EXISTS idx_resets_user ON password_resets(user_id);

    CREATE TABLE IF NOT EXISTS kv_cache (
      key TEXT PRIMARY KEY,
      value TEXT NOT NULL,
      expires_at INTEGER NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_kv_expires ON kv_cache(expires_at);

    CREATE TABLE IF NOT EXISTS alerts (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      commodity_key TEXT NOT NULL,
      kind TEXT NOT NULL,
      threshold REAL NOT NULL,
      latitude REAL,
      longitude REAL,
      label TEXT,
      active INTEGER NOT NULL DEFAULT 1,
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE INDEX IF NOT EXISTS idx_alerts_user ON alerts(user_id);

    CREATE TABLE IF NOT EXISTS alert_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      alert_id INTEGER NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
      evaluated_at TEXT NOT NULL DEFAULT (datetime('now')),
      triggered INTEGER NOT NULL,
      value REAL,
      detail TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_events_alert ON alert_events(alert_id);

    CREATE TABLE IF NOT EXISTS user_places (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      label TEXT NOT NULL,
      latitude REAL NOT NULL,
      longitude REAL NOT NULL,
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE INDEX IF NOT EXISTS idx_places_user ON user_places(user_id);
  `);
  seedCommodities(database);
  seedSources(database);
  upgradeAlerts(database);
  upgradeWorker(database);
}

// Estruturas do monitoramento automático (Release 2).
// - worker_locks: lease persistente, uma linha por job.
// - worker_runs: histórico de ciclos (auditoria, métricas, diagnóstico).
// - series_state: estado operacional por série (falhas, última tentativa).
// - feedback: canal simples de retorno do usuário (sem dados pessoais extras).
function upgradeWorker(database) {
  database.exec(`
    CREATE TABLE IF NOT EXISTS worker_locks (
      job_key TEXT PRIMARY KEY,
      owner TEXT NOT NULL,
      acquired_at TEXT NOT NULL,
      heartbeat_at TEXT NOT NULL,
      expires_at TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'held'
    );

    CREATE TABLE IF NOT EXISTS worker_runs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      job_key TEXT NOT NULL,
      owner TEXT,
      started_at TEXT NOT NULL,
      finished_at TEXT,
      status TEXT NOT NULL,
      series_total INTEGER NOT NULL DEFAULT 0,
      series_ok INTEGER NOT NULL DEFAULT 0,
      series_failed INTEGER NOT NULL DEFAULT 0,
      series_skipped INTEGER NOT NULL DEFAULT 0,
      observations_new INTEGER NOT NULL DEFAULT 0,
      alerts_evaluated INTEGER NOT NULL DEFAULT 0,
      events_created INTEGER NOT NULL DEFAULT 0,
      duplicates_blocked INTEGER NOT NULL DEFAULT 0,
      duration_ms INTEGER,
      error TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_worker_runs_started ON worker_runs(started_at);

    CREATE TABLE IF NOT EXISTS series_state (
      series_id TEXT PRIMARY KEY,
      last_attempt_at TEXT,
      last_success_at TEXT,
      last_error TEXT,
      last_error_at TEXT,
      consecutive_failures INTEGER NOT NULL DEFAULT 0,
      last_observation_date TEXT,
      last_price REAL
    );

    -- Sinal de vida do processo worker. Uma linha só: quem escreve é o worker.
    CREATE TABLE IF NOT EXISTS worker_heartbeat (
      id INTEGER PRIMARY KEY CHECK (id = 1),
      owner TEXT NOT NULL,
      started_at TEXT NOT NULL,
      heartbeat_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS feedback (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
      kind TEXT NOT NULL,
      message TEXT NOT NULL,
      context_json TEXT,
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE INDEX IF NOT EXISTS idx_feedback_created ON feedback(created_at);
  `);
}

// Migração aditiva e idempotente dos alertas (v1.1 → product release 1).
// Não remove nem renomeia nada: a V1.1 continua funcionando com commodity_key
// e `active`, e as colunas novas são preenchidas por backfill.
function columnExists(database, table, column) {
  return database
    .prepare(`PRAGMA table_info(${table})`)
    .all()
    .some((row) => row.name === column);
}

function addColumn(database, table, definition) {
  const name = definition.trim().split(/\s+/)[0];
  if (!columnExists(database, table, name)) {
    database.exec(`ALTER TABLE ${table} ADD COLUMN ${definition}`);
  }
}

function upgradeAlerts(database) {
  // --- regras
  addColumn(database, 'alerts', 'series_id TEXT');
  addColumn(database, 'alerts', 'condition TEXT');
  addColumn(database, 'alerts', 'currency TEXT');
  addColumn(database, 'alerts', 'unit TEXT');
  addColumn(database, 'alerts', 'instrument TEXT');
  addColumn(database, 'alerts', 'market TEXT');
  addColumn(database, 'alerts', 'source TEXT');
  addColumn(database, 'alerts', 'price_type TEXT');
  addColumn(database, 'alerts', 'status TEXT');
  addColumn(database, 'alerts', 'last_evaluated_at TEXT');
  addColumn(database, 'alerts', 'triggered_at TEXT');
  addColumn(database, 'alerts', 'last_price REAL');
  addColumn(database, 'alerts', 'last_observation_date TEXT');
  addColumn(database, 'alerts', 'updated_at TEXT');

  // --- eventos
  addColumn(database, 'alert_events', "event_type TEXT NOT NULL DEFAULT 'evaluation'");
  addColumn(database, 'alert_events', 'observation_date TEXT');
  addColumn(database, 'alert_events', 'observed_price REAL');
  addColumn(database, 'alert_events', 'read_at TEXT');

  // --- backfill das regras legadas
  database.prepare("UPDATE alerts SET condition = kind WHERE condition IS NULL AND kind IN ('price_above','price_below')").run();
  database
    .prepare("UPDATE alerts SET status = CASE WHEN active = 1 THEN 'active' ELSE 'paused' END WHERE status IS NULL")
    .run();
  database.prepare("UPDATE alerts SET updated_at = created_at WHERE updated_at IS NULL").run();
  database.prepare("UPDATE alert_events SET event_type = 'evaluation' WHERE event_type IS NULL").run();

  const commodities = database.prepare('SELECT key, yahoo_symbol, unit_br FROM commodities').all();
  // Helper local (evita ciclo de require com services/seriesService).
  const slug = (unit) => {
    const known = { 'R$/sc 60kg': 'sc60', 'R$/saca 60kg': 'sc60', 'R$/lp': 'lp', 'R$/lb': 'lp' };
    const key = String(unit || '').trim();
    return known[key] || key.replace(/[^a-z0-9]+/gi, '').toLowerCase() || 'unit';
  };
  const updateSeries = database.prepare('UPDATE alerts SET series_id = ? WHERE series_id IS NULL AND commodity_key = ?');
  for (const c of commodities) {
    updateSeries.run(`yahoo:${c.yahoo_symbol}:brl:${slug(c.unit_br)}`, c.key);
  }

  // --- índices (inclui a chave de idempotência dos eventos)
  database.exec(`
    CREATE INDEX IF NOT EXISTS idx_alerts_series ON alerts(series_id);
    CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status);
    CREATE UNIQUE INDEX IF NOT EXISTS idx_alert_events_unique
      ON alert_events(alert_id, event_type, observation_date);
    CREATE INDEX IF NOT EXISTS idx_alert_events_read ON alert_events(read_at);
  `);
}

function seedCommodities(database) {
  const rows = [
    ['soja', 'Soja', 'ZS=F', 'R$/sc 60kg', 'Futuro CBOT convertido para R$/saca de 60kg via PTAX'],
    ['milho', 'Milho', 'ZC=F', 'R$/sc 60kg', 'Futuro CBOT convertido para R$/saca de 60kg via PTAX'],
    ['cafe', 'Café arábica', 'KC=F', 'R$/sc 60kg', 'Futuro ICE convertido para R$/saca de 60kg via PTAX'],
    ['trigo', 'Trigo', 'ZW=F', 'R$/sc 60kg', 'Futuro CBOT convertido para R$/saca de 60kg via PTAX'],
    ['algodao', 'Algodão', 'CT=F', 'R$/lp', 'Futuro ICE em R$/libra-peso via PTAX'],
  ];
  const stmt = database.prepare(
    `INSERT OR IGNORE INTO commodities(key, name, yahoo_symbol, unit_br, description)
     VALUES(?, ?, ?, ?, ?)`
  );
  for (const r of rows) stmt.run(...r);
}

function seedSources(database) {
  const rows = [
    ['yahoo', 'Yahoo Finance (cotações futuros)', 'https://query1.finance.yahoo.com', 'https://finance.yahoo.com', 'prices', 'active', 'Sem chave; exige User-Agent. Proxy via backend (sem CORS p/ browser).'],
    ['bcb-ptax', 'Banco Central — PTAX', 'https://olinda.bcb.gov.br', 'https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/documentacao', 'fx', 'active', 'OData público, sem chave.'],
    ['open-meteo', 'Open-Meteo (clima)', 'https://api.open-meteo.com', 'https://open-meteo.com/en/docs', 'weather', 'active', 'Sem chave; 10 mil req/dia uso não-comercial.'],
    ['ibge', 'IBGE Localidades', 'https://servicodados.ibge.gov.br', 'https://servicodados.ibge.gov.br/api/docs/localidades', 'geo', 'active', 'Público, sem chave.'],
    ['open-meteo-geocoding', 'Open-Meteo Geocoding', 'https://geocoding-api.open-meteo.com', 'https://open-meteo.com/en/docs/geocoding-api', 'geo', 'active', 'Público, sem chave.'],
    ['nominatim', 'Nominatim / OpenStreetMap', 'https://nominatim.openstreetmap.org', 'https://nominatim.org/release-docs/develop/api/Overview/', 'geo', 'active', 'Endereços/ruas + reverse. Sem chave; 1 req/s, atribuição OSM obrigatória.'],
    ['landcover', 'Sentinel-2 Land Cover (Esri/Impact Observatory)', 'https://ic.imagery1.arcgis.com/arcgis/rest/services/Sentinel2_10m_LandCover/ImageServer', 'https://ic.imagery1.arcgis.com/arcgis/rest/services/Sentinel2_10m_LandCover/ImageServer', 'landcover', 'active', 'Tiles + legenda + catálogo verificados; identify pixel exige credencial.'],
    ['cepea', 'CEPEA/ESALQ', 'https://cepea.org.br', 'https://cepea.org.br/br/consultas-ao-banco-de-dados-do-site.aspx', 'prices', 'blocked', 'Sem API pública documentada; consulta manual via site. Não integrado.'],
    ['conab', 'CONAB — Preços Agropecuários', 'https://consultaprecosdemercado.conab.gov.br', 'https://www.gov.br/conab/pt-br/atuacao/informacoes-agropecuarias/precos-agropecuarios', 'prices', 'blocked', 'Portal com reCAPTCHA (verificado); contornar é proibido. Sem API REST pública. Não integrado.'],
    ['conab-freight', 'CONAB/ANTT — Frete', 'https://calculadorafrete.antt.gov.br/', 'https://www.gov.br/antt/pt-br/assuntos/ultimas-noticias/antt-reajusta-tabela-dos-pisos-minimos-de-frete-1', 'freight', 'blocked', 'Sem fonte estruturada: coeficientes em DOU/calculadora interativa; sem cálculo automático no SADEN. Referência manual.'],
  ];
  const stmt = database.prepare(
    `INSERT OR IGNORE INTO data_sources(key, name, base_url, docs_url, kind, status, notes)
     VALUES(?, ?, ?, ?, ?, ?, ?)`
  );
  for (const r of rows) stmt.run(...r);
}

// Cache KV simples com TTL (ms epoch).
function cacheGet(key) {
  const row = connect().prepare('SELECT value, expires_at FROM kv_cache WHERE key = ?').get(key);
  if (!row) return null;
  if (row.expires_at <= Date.now()) {
    connect().prepare('DELETE FROM kv_cache WHERE key = ?').run(key);
    return null;
  }
  try {
    return JSON.parse(row.value);
  } catch {
    return null;
  }
}

function cacheSet(key, value, ttlMs) {
  connect()
    .prepare('INSERT OR REPLACE INTO kv_cache(key, value, expires_at) VALUES(?, ?, ?)')
    .run(key, JSON.stringify(value), Date.now() + ttlMs);
}

module.exports = { connect, cacheGet, cacheSet };
