'use strict';

// Saúde do monitoramento (Release 2).
//
// Regra central: **API saudável não prova worker saudável.** O estado é
// derivado do heartbeat do processo e do histórico de execuções — nunca da
// existência de alertas. Um alerta "ativo" com worker parado é justamente o
// caso que esta função precisa expor.

const { connect } = require('../db');
const config = require('./config');
const scheduler = require('./scheduler');

const RUNS_KEEP = 500;

function beat(owner) {
  connect()
    .prepare(
      `INSERT INTO worker_heartbeat(id, owner, started_at, heartbeat_at)
       VALUES(1, ?, ?, ?)
       ON CONFLICT(id) DO UPDATE SET owner = excluded.owner, heartbeat_at = excluded.heartbeat_at`
    )
    .run(owner, new Date().toISOString(), new Date().toISOString());
}

function pruneRuns() {
  return connect()
    .prepare('DELETE FROM worker_runs WHERE id NOT IN (SELECT id FROM worker_runs ORDER BY id DESC LIMIT ?)')
    .run(RUNS_KEEP).changes;
}

function lastRuns(limit = 5) {
  return connect()
    .prepare(
      `SELECT id, job_key, owner, started_at, finished_at, status, series_total, series_ok,
              series_failed, observations_new, alerts_evaluated, events_created,
              duplicates_blocked, duration_ms
         FROM worker_runs ORDER BY id DESC LIMIT ?`
    )
    .all(limit);
}

/**
 * Estado consolidado do worker.
 * status: 'ok' | 'degraded' | 'down' | 'not_started'
 */
function status({ now = new Date() } = {}) {
  const db = connect();
  const heartbeat = db.prepare('SELECT * FROM worker_heartbeat WHERE id = 1').get();
  const last = db.prepare("SELECT * FROM worker_runs WHERE status != 'running' ORDER BY id DESC LIMIT 1").get();
  const lastOk = db.prepare("SELECT * FROM worker_runs WHERE status = 'ok' ORDER BY id DESC LIMIT 1").get();
  const lastFailure = db
    .prepare("SELECT * FROM worker_runs WHERE status IN ('failed','partial') ORDER BY id DESC LIMIT 1")
    .get();

  const heartbeatAgeMs = heartbeat
    ? now.getTime() - new Date(heartbeat.heartbeat_at).getTime()
    : null;
  const alive = heartbeatAgeMs != null && heartbeatAgeMs <= config.heartbeatStaleMs;

  let state = 'ok';
  if (!heartbeat) state = 'not_started';
  else if (!alive) state = 'down';
  else if (last && last.status !== 'ok') state = 'degraded';

  const anchor = last ? new Date(last.started_at) : now;
  const next = scheduler.nextRun(anchor, {
    preferredHourLocal: config.preferredHourLocal,
    timezone: config.timezone,
  });

  return {
    status: state,
    alive,
    worker_id: heartbeat ? heartbeat.owner : null,
    started_at: heartbeat ? heartbeat.started_at : null,
    heartbeat_at: heartbeat ? heartbeat.heartbeat_at : null,
    heartbeat_age_ms: heartbeatAgeMs,
    heartbeat_stale_after_ms: config.heartbeatStaleMs,
    last_run: last
      ? {
          id: last.id,
          started_at: last.started_at,
          finished_at: last.finished_at,
          status: last.status,
          series_total: last.series_total,
          series_failed: last.series_failed,
          observations_new: last.observations_new,
          events_created: last.events_created,
          duration_ms: last.duration_ms,
        }
      : null,
    last_success_at: lastOk ? lastOk.finished_at || lastOk.started_at : null,
    last_failure_at: lastFailure ? lastFailure.finished_at || lastFailure.started_at : null,
    next_run_at: next.toISOString(),
    schedule: {
      timezone: config.timezone,
      preferred_hour_local: config.preferredHourLocal,
      interval_ms: config.intervalMs,
    },
    lock: (() => {
      const row = db.prepare('SELECT * FROM worker_locks WHERE job_key = ?').get(config.jobKey);
      if (!row) return null;
      return {
        owner: row.owner,
        acquired_at: row.acquired_at,
        expires_at: row.expires_at,
        active: row.expires_at > now.toISOString(),
      };
    })(),
  };
}

/**
 * Saúde por fonte/série: distingue "sem cotação nova" de "fonte com erro".
 * Não marca indisponibilidade só porque o mercado estava fechado.
 */
function sources() {
  const seriesService = require('../services/seriesService');
  return seriesService.list().map((series) => {
    const state = series.source_state;
    return {
      series_id: series.series_id,
      commodity_key: series.commodity_key,
      market: series.market,
      unit: series.unit,
      last_observation_date: series.observation_date,
      last_price: series.last_price,
      freshness_status: series.freshness_status,
      age_days: series.age_days,
      operational: series.operational,
      consecutive_failures: state ? state.consecutive_failures : 0,
      last_error: state ? state.last_error : null,
      last_error_at: state ? state.last_error_at : null,
      last_success_at: state ? state.last_success_at : null,
    };
  });
}

module.exports = { beat, status, sources, lastRuns, pruneRuns, RUNS_KEEP };
