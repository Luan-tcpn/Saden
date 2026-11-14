'use strict';

// Um ciclo do monitoramento automático.
//
// Ordem obrigatória: **persistir a observação antes de avaliar**. O worker nunca
// avalia com dado antigo como se fosse novo, e nunca inventa preço quando a
// fonte falha.
//
// Uma consulta por série por ciclo (não por alerta): os alertas são agrupados
// por `series_id`. O intervalo mínimo por série protege o provedor externo.

const { connect } = require('../db');
const seriesService = require('../services/seriesService');
const alertEngine = require('../services/alertEngine');
const config = require('./config');

function nowIso() {
  return new Date().toISOString();
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// Classifica o erro da fonte para não tratar tudo como "indisponível".
// Considera o status HTTP quando existe (erros do nosso próprio backend) e o
// texto quando o erro vem de baixo (fetch/DNS/timeout).
function classifyError(error) {
  const status = error && (error.status || error.statusCode);
  const message = String((error && error.message) || error || '');
  if (status === 401 || status === 403) return 'auth_error';
  if (status === 429) return 'rate_limited';
  if (status === 502 || status === 503 || status === 504) return 'source_unavailable';
  if (/timeout|timed out|ETIMEDOUT|ECONNRESET|ENOTFOUND|EAI_AGAIN/i.test(message)) return 'timeout';
  if (/429|rate.?limit/i.test(message)) return 'rate_limited';
  if (/401|403|auth/i.test(message)) return 'auth_error';
  if (/insuficiente/i.test(message)) return 'insufficient_data';
  return 'error';
}

async function withRetry(task, { retries = config.retries, baseMs = config.retryBaseMs } = {}) {
  let lastError;
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      return { ok: true, value: await task(), attempts: attempt + 1 };
    } catch (error) {
      lastError = error;
      if (attempt < retries) await sleep(baseMs * 2 ** attempt);
    }
  }
  return { ok: false, error: lastError, attempts: retries + 1 };
}

function activeSeriesIds() {
  return connect()
    .prepare("SELECT DISTINCT series_id FROM alerts WHERE status = 'active' AND series_id IS NOT NULL")
    .all()
    .map((row) => row.series_id);
}

function dueSeries(now = new Date()) {
  const state = connect().prepare('SELECT * FROM series_state').all();
  const lastAttempt = Object.fromEntries(state.map((row) => [row.series_id, row.last_attempt_at]));
  return activeSeriesIds().filter((seriesId) => {
    const attempted = lastAttempt[seriesId];
    if (!attempted) return true;
    return now.getTime() - new Date(attempted).getTime() >= config.minSeriesIntervalMs;
  });
}

function recordSeriesState(seriesId, { ok, error, observationDate, price }) {
  const db = connect();
  const now = nowIso();
  const existing = db.prepare('SELECT * FROM series_state WHERE series_id = ?').get(seriesId);
  if (!existing) {
    db.prepare(
      `INSERT INTO series_state(series_id, last_attempt_at, last_success_at, last_error, last_error_at,
                                consecutive_failures, last_observation_date, last_price)
       VALUES(?, ?, ?, ?, ?, ?, ?, ?)`
    ).run(
      seriesId,
      now,
      ok ? now : null,
      ok ? null : String(error || 'erro'),
      ok ? null : now,
      ok ? 0 : 1,
      observationDate || null,
      price == null ? null : price
    );
    return;
  }
  db.prepare(
    `UPDATE series_state
        SET last_attempt_at = ?,
            last_success_at = CASE WHEN ? THEN ? ELSE last_success_at END,
            last_error = ?,
            last_error_at = CASE WHEN ? THEN null ELSE ? END,
            consecutive_failures = CASE WHEN ? THEN 0 ELSE consecutive_failures + 1 END,
            last_observation_date = COALESCE(?, last_observation_date),
            last_price = COALESCE(?, last_price)
      WHERE series_id = ?`
  ).run(
    now,
    ok ? 1 : 0,
    now,
    ok ? null : String(error || 'erro'),
    ok ? 1 : 0,
    now,
    ok ? 1 : 0,
    observationDate || null,
    price == null ? null : price,
    seriesId
  );
}

/**
 * Executa um ciclo. Não adquire lock — quem chama garante exclusividade.
 * `force` ignora o intervalo mínimo por série (usado em teste e em verificação
 * manual administrativa).
 */
async function runCycle({ owner = 'inline', force = false, now = new Date() } = {}) {
  const db = connect();
  const startedAt = nowIso();
  const runInfo = db
    .prepare("INSERT INTO worker_runs(job_key, owner, started_at, status) VALUES(?, ?, ?, 'running')")
    .run(config.jobKey, owner, startedAt);
  const runId = Number(runInfo.lastInsertRowid);
  const started = Date.now();

  const seriesIds = force ? activeSeriesIds() : dueSeries(now);
  const summary = {
    run_id: runId,
    owner,
    series_total: seriesIds.length,
    series_ok: 0,
    series_failed: 0,
    series_skipped: 0,
    observations_new: 0,
    alerts_evaluated: 0,
    events_created: 0,
    duplicates_blocked: 0,
    results: [],
  };

  // require tardio: priceService depende do alertEngine e do cache; carregar
  // aqui evita ciclo de módulos quando o worker é importado por um teste.
  const priceService = require('../services/priceService');

  for (const seriesId of seriesIds) {
    let series;
    try {
      series = seriesService.get(seriesId);
    } catch (error) {
      summary.series_skipped++;
      summary.results.push({ series_id: seriesId, status: 'unknown_series', error: error.message });
      continue;
    }

    const before = seriesService.latestObservationFor(series.commodity_key);
    const attempt = await withRetry(() =>
      priceService.getSeries(series.commodity_key, '3mo', {
        bypassCache: true,
        evaluateAlerts: false,
      })
    );

    if (!attempt.ok) {
      const reason = classifyError(attempt.error);
      summary.series_failed++;
      summary.results.push({
        series_id: seriesId,
        status: 'source_error',
        reason,
        error: String((attempt.error && attempt.error.message) || attempt.error),
        attempts: attempt.attempts,
      });
      recordSeriesState(seriesId, { ok: false, error: reason });
      continue;
    }

    const after = seriesService.latestObservationFor(series.commodity_key);
    const isNew = (!before && after) || (before && after && before.data_date !== after.data_date);
    if (isNew) summary.observations_new++;

    // Avaliação só depois de persistir — e sempre idempotente no banco.
    const evaluation = alertEngine.evaluateSeries(seriesId, { userId: null, logEvaluations: false });
    summary.alerts_evaluated += evaluation.evaluated;
    summary.events_created += evaluation.events_created;
    summary.duplicates_blocked += Math.max(0, evaluation.triggered - evaluation.events_created);
    summary.series_ok++;

    recordSeriesState(seriesId, {
      ok: true,
      observationDate: after ? after.data_date : null,
      price: after ? after.price_brl : null,
    });
    summary.results.push({
      series_id: seriesId,
      status: after ? 'ok' : 'no_observation',
      observation_date: after ? after.data_date : null,
      new_observation: Boolean(isNew),
      alerts_evaluated: evaluation.evaluated,
      events_created: evaluation.events_created,
      fresh: evaluation.fresh,
    });
  }

  const duration = Date.now() - started;
  const status =
    summary.series_failed === 0 ? 'ok' : summary.series_ok > 0 ? 'partial' : 'failed';
  db.prepare(
    `UPDATE worker_runs
        SET finished_at = ?, status = ?, series_total = ?, series_ok = ?, series_failed = ?,
            series_skipped = ?, observations_new = ?, alerts_evaluated = ?, events_created = ?,
            duplicates_blocked = ?, duration_ms = ?
      WHERE id = ?`
  ).run(
    nowIso(),
    status,
    summary.series_total,
    summary.series_ok,
    summary.series_failed,
    summary.series_skipped,
    summary.observations_new,
    summary.alerts_evaluated,
    summary.events_created,
    summary.duplicates_blocked,
    duration,
    runId
  );

  return { ...summary, status, duration_ms: duration };
}

/** Métricas agregadas para o painel operacional (sem dados pessoais). */
function metrics({ windowDays = 7 } = {}) {
  const db = connect();
  const since = new Date(Date.now() - windowDays * 86400000).toISOString();
  const runs = db
    .prepare('SELECT * FROM worker_runs WHERE started_at >= ? ORDER BY id DESC')
    .all(since);
  const finished = runs.filter((run) => run.finished_at);
  const durations = finished.map((run) => run.duration_ms).filter((value) => Number.isFinite(value));
  const success = runs.filter((run) => run.status === 'ok').length;
  return {
    window_days: windowDays,
    runs: runs.length,
    ok: success,
    partial: runs.filter((run) => run.status === 'partial').length,
    failed: runs.filter((run) => run.status === 'failed').length,
    running: runs.filter((run) => run.status === 'running').length,
    success_rate: runs.length ? Number((success / runs.length).toFixed(4)) : null,
    mean_duration_ms: durations.length
      ? Math.round(durations.reduce((a, b) => a + b, 0) / durations.length)
      : null,
    observations_new: runs.reduce((total, run) => total + (run.observations_new || 0), 0),
    alerts_evaluated: runs.reduce((total, run) => total + (run.alerts_evaluated || 0), 0),
    events_created: runs.reduce((total, run) => total + (run.events_created || 0), 0),
    duplicates_blocked: runs.reduce((total, run) => total + (run.duplicates_blocked || 0), 0),
    last_started_at: runs.length ? runs[0].started_at : null,
  };
}

module.exports = {
  runCycle,
  dueSeries,
  activeSeriesIds,
  classifyError,
  withRetry,
  recordSeriesState,
  metrics,
};
