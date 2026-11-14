'use strict';

// Configuração do monitoramento automático (Release 2).
// Tudo por ambiente, com defaults conservadores: o worker não deve ser agressivo
// com provedores públicos nem gerar carga desnecessária no SQLite.

const os = require('os');

function num(name, fallback) {
  const value = Number(process.env[name]);
  return Number.isFinite(value) && value > 0 ? value : fallback;
}

const startedAt = new Date();

module.exports = {
  // Identidade desta instância (aparece nos locks e no histórico de execuções).
  workerId: process.env.SADEN_WORKER_ID || `${os.hostname()}-${process.pid}-${startedAt.getTime()}`,
  jobKey: 'monitor-series',

  // Agenda: cotação diária em dia útil. O horário preferencial é local (SP),
  // depois do fechamento de Chicago e da publicação da PTAX.
  timezone: 'America/Sao_Paulo',
  preferredHourLocal: num('SADEN_WORKER_HOUR', 18),
  intervalMs: num('SADEN_WORKER_INTERVAL_MS', 15 * 60 * 1000),
  tickMs: num('SADEN_WORKER_TICK_MS', 30 * 1000),
  runOnStart: String(process.env.SADEN_WORKER_RUN_ON_START || '1') !== '0',

  // Não consulta a mesma série mais de uma vez por hora (proteção do provedor).
  minSeriesIntervalMs: num('SADEN_WORKER_MIN_SERIES_MS', 60 * 60 * 1000),

  // Lock/lease: o TTL precisa ser maior que a duração de um ciclo normal.
  lockTtlMs: num('SADEN_WORKER_LOCK_TTL_MS', 5 * 60 * 1000),
  heartbeatMs: num('SADEN_WORKER_HEARTBEAT_MS', 20 * 1000),

  // Retry com backoff exponencial (limitado).
  retries: num('SADEN_WORKER_RETRIES', 2),
  retryBaseMs: num('SADEN_WORKER_RETRY_BASE_MS', 1500),
  httpTimeoutMs: num('SADEN_WORKER_HTTP_TIMEOUT_MS', 12000),

  // Saúde: sem heartbeat por 3 intervalos = processo considerado ausente.
  heartbeatStaleMs: num('SADEN_WORKER_HEARTBEAT_STALE_MS', 3 * 20 * 1000),

  startedAt: startedAt.toISOString(),
};
