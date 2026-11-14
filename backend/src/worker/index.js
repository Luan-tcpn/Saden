'use strict';

// Processo do monitoramento automático (Release 2).
//
// Independente do processo HTTP: roda com `node backend/src/worker/index.js`
// (ou como serviço separado no Docker Compose). Atende a agenda, adquire o
// lease, executa o ciclo e mantém o heartbeat. Encerra de forma graciosa em
// SIGTERM/SIGINT (inclusive `docker stop`).

const config = require('./config');
const locks = require('./locks');
const health = require('./health');
const runner = require('./runner');
const scheduler = require('./scheduler');
const { connect } = require('../db');

function log(level, message, extra = {}) {
  // eslint-disable-next-line no-console
  console.log(JSON.stringify({ level, kind: 'worker', worker: config.workerId, message, ...extra }));
}

let stopping = false;
let heartbeatTimer = null;
let tickTimer = null;
let renewTimer = null;

function startHeartbeat() {
  const beat = () => {
    try {
      health.beat(config.workerId);
    } catch (error) {
      log('error', 'falha ao registrar heartbeat', { error: error.message });
    }
  };
  beat();
  // NÃO usar unref(): o processo precisa permanecer vivo aguardando a próxima
  // execução. Sem isso, o worker encerra logo após o ciclo inicial (bug pego no
  // teste em container: status "Restarting" com exit 0).
  heartbeatTimer = setInterval(beat, config.heartbeatMs);
}

function scheduleNextRun() {
  if (stopping) return;
  const next = scheduler.nextRun(new Date(), {
    preferredHourLocal: config.preferredHourLocal,
    timezone: config.timezone,
  });
  const delay = Math.max(1000, next.getTime() - Date.now());
  log('info', 'proxima execucao agendada', { at: next.toISOString(), in_ms: delay });
  tickTimer = setTimeout(runOnce, delay);
}

async function runOnce() {
  if (stopping) return;
  const jobKey = config.jobKey;
  const lock = locks.acquire(jobKey, config.workerId, config.lockTtlMs);
  if (!lock.acquired) {
    log('warn', 'ciclo ignorado: lock em posse de outra instancia', { owner: lock.owner });
    scheduleNextRun();
    return;
  }

  // Renova o lease enquanto o ciclo roda (ciclo longo não perde o lock).
  renewTimer = setInterval(() => {
    if (!locks.heartbeat(jobKey, config.workerId, config.lockTtlMs)) {
      log('warn', 'lease perdido durante o ciclo');
    }
  }, Math.max(5000, Math.floor(config.lockTtlMs / 3)));
  renewTimer.unref?.();

  try {
    health.beat(config.workerId);
    const summary = await runner.runCycle({ owner: config.workerId });
    log('info', 'ciclo concluido', {
      status: summary.status,
      series: summary.series_total,
      ok: summary.series_ok,
      failed: summary.series_failed,
      new_observations: summary.observations_new,
      events: summary.events_created,
      duration_ms: summary.duration_ms,
    });
    health.pruneRuns();
  } catch (error) {
    log('error', 'falha no ciclo', { error: error.message });
  } finally {
    if (renewTimer) clearInterval(renewTimer);
    renewTimer = null;
    locks.release(jobKey, config.workerId);
    scheduleNextRun();
  }
}

function shutdown(signal) {
  if (stopping) return;
  stopping = true;
  log('info', 'encerrando', { signal });
  if (tickTimer) clearTimeout(tickTimer);
  if (renewTimer) clearInterval(renewTimer);
  if (heartbeatTimer) clearInterval(heartbeatTimer);
  // Libera o lock para a próxima instância não esperar o TTL.
  try {
    locks.release(config.jobKey, config.workerId);
  } catch (error) {
    log('warn', 'nao foi possivel liberar o lock', { error: error.message });
  }
  log('info', 'encerrado');
  // Deixa o event loop esvaziar (SQLite fecha) antes de sair.
  setTimeout(() => process.exit(0), 200);
}

async function main() {
  connect();
  health.beat(config.workerId);
  locks.reapExpired();
  startHeartbeat();
  log('info', 'worker iniciado', {
    schedule: `${config.preferredHourLocal}h ${config.timezone}`,
    lock_ttl_ms: config.lockTtlMs,
    min_series_interval_ms: config.minSeriesIntervalMs,
  });

  process.on('SIGTERM', () => shutdown('SIGTERM'));
  process.on('SIGINT', () => shutdown('SIGINT'));
  process.on('uncaughtException', (error) => {
    log('error', 'excecao nao tratada', { error: error.message });
  });
  process.on('unhandledRejection', (error) => {
    log('error', 'promise rejeitada sem tratamento', { error: String(error) });
  });

  if (config.runOnStart) {
    log('info', 'executando ciclo inicial');
    await runOnce();
  } else {
    scheduleNextRun();
  }
}

if (require.main === module) {
  main().catch((error) => {
    log('error', 'falha fatal na inicializacao', { error: error.message });
    process.exit(1);
  });
}

module.exports = { main, runOnce, shutdown, config };
