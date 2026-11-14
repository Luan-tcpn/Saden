'use strict';

// Healthcheck do container do worker.
//
// Critério: heartbeat recente **e** alguma execução concluída. Não olha cotações:
// ausência de cotação nova em fim de semana é normal e não é falha.
// Saída 0 = saudável, 1 = não saudável (Docker reinicia conforme a política).

const health = require('./health');
const config = require('./config');

try {
  const status = health.status();
  const withinSchedule = status.heartbeat_age_ms != null && status.heartbeat_age_ms <= config.heartbeatStaleMs;
  const ranAtLeastOnce = Boolean(status.last_run);
  if (status.alive && withinSchedule && ranAtLeastOnce) {
    // eslint-disable-next-line no-console
    console.log(JSON.stringify({ status: 'ok', heartbeat_age_ms: status.heartbeat_age_ms, last_run: status.last_run.started_at }));
    process.exit(0);
  }
  // eslint-disable-next-line no-console
  console.error(
    JSON.stringify({
      status: status.status,
      alive: status.alive,
      heartbeat_age_ms: status.heartbeat_age_ms,
      ran_at_least_once: ranAtLeastOnce,
    })
  );
  process.exit(1);
} catch (error) {
  // eslint-disable-next-line no-console
  console.error(JSON.stringify({ status: 'error', message: error.message }));
  process.exit(1);
}
