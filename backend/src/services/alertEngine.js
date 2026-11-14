'use strict';

// Motor de avaliação dos alertas de preço.
//
// Regras explícitas (semântica de disparo único):
//   1. um alerta avalia **uma** série e **uma** condição;
//   2. só dispara com observação **fresca** (idade ≤ limite da fonte);
//   3. dispara no máximo uma vez por alerta — reativar é ação do usuário;
//   4. a mesma observação nunca gera dois eventos (chave única no banco);
//   5. falha de fonte não dispara, não inventa preço e não marca monitoramento
//      como normal.
//
// O motor é chamado de dois lugares: após a atualização de preços (best-effort,
// nunca derruba a requisição do usuário) e pelo endpoint de avaliação manual.

const { connect } = require('../db');
const seriesService = require('./seriesService');

const CONDITIONS = ['price_above', 'price_below'];
const CONDITION_LABEL = {
  price_above: 'Preço maior ou igual ao limite',
  price_below: 'Preço menor ou igual ao limite',
};

// Mantém compatibilidade com os rótulos antigos da API (kind).
const KIND_TO_CONDITION = {
  price_above: 'price_above',
  price_below: 'price_below',
};

function conditionLabel(condition) {
  return CONDITION_LABEL[condition] || condition;
}

function meetsCondition(condition, threshold, price) {
  if (!Number.isFinite(price)) return false;
  if (condition === 'price_above') return price >= threshold;
  if (condition === 'price_below') return price <= threshold;
  return false;
}

function rowToAlert(row) {
  return {
    ...row,
    active: row.status === 'active',
    kind_label: conditionLabel(row.condition || row.kind),
    condition_label: conditionLabel(row.condition || row.kind),
  };
}

/**
 * Avalia uma regra contra uma observação, sem efeitos colaterais.
 * @returns {{triggered:boolean, price:number|null, observation_date:string|null,
 *            fresh:boolean, blocked:string|null, detail:string}}
 */
function evaluateAlert(alert, observation) {
  const condition = alert.condition || KIND_TO_CONDITION[alert.kind] || null;
  const unit = alert.unit || observation?.unit_br || '';
  if (!observation) {
    return {
      triggered: false,
      price: null,
      observation_date: null,
      fresh: false,
      blocked: 'no_observation',
      detail: 'Sem observação persistida para a série.',
    };
  }
  const freshness = seriesService.freshnessFor(observation.data_date);
  const fresh = freshness.status === 'fresh';
  const price = observation.price_brl;
  const triggered = fresh && meetsCondition(condition, Number(alert.threshold), Number(price));
  const detail = fresh
    ? `Preço ${formatPrice(price)} ${unit} em ${observation.data_date}`
    : `Observação de ${observation.data_date} está desatualizada (${freshness.age_days} dias; limite ${freshness.stale_after_days}).`;
  return {
    triggered,
    price: Number.isFinite(Number(price)) ? Number(price) : null,
    observation_date: observation.data_date || null,
    fresh,
    blocked: fresh ? null : 'stale',
    detail,
  };
}

function formatPrice(value) {
  const n = Number(value);
  return Number.isFinite(n) ? `R$ ${n.toFixed(2)}` : '—';
}

/**
 * Persiste o evento de disparo com garantia de idempotência.
 * A chave única é (alert_id, observation_date, event_type).
 * @returns {boolean} true se o evento foi criado agora (primeira vez)
 */
function recordTrigger(alert, observation, evaluation) {
  const db = connect();
  const info = db
    .prepare(
      `INSERT OR IGNORE INTO alert_events
         (alert_id, event_type, observation_date, observed_price, value, triggered, detail)
       VALUES (?, 'trigger', ?, ?, ?, 1, ?)`
    )
    .run(
      alert.id,
      observation.data_date,
      evaluation.price,
      evaluation.price,
      `${conditionLabel(alert.condition || alert.kind)} ${alert.threshold} ${alert.unit || ''}`.trim() +
        ` — observado ${formatPrice(evaluation.price)} em ${observation.data_date}`
    );
  if (info.changes === 0) return false;
  db.prepare(
    `UPDATE alerts
        SET status = 'triggered',
            active = 0,
            triggered_at = datetime('now'),
            last_evaluated_at = datetime('now'),
            last_price = ?,
            last_observation_date = ?
      WHERE id = ? AND status = 'active'`
  ).run(evaluation.price, observation.data_date, alert.id);
  return true;
}

/** Registra a avaliação do modo legado (/check) — não é evento de disparo. */
function recordEvaluation(alert, evaluation) {
  const info = connect()
    .prepare(
      `INSERT OR IGNORE INTO alert_events
         (alert_id, event_type, observation_date, observed_price, value, triggered, detail)
       VALUES (?, 'evaluation', ?, ?, ?, ?, ?)`
    )
    .run(
      alert.id,
      evaluation.observation_date,
      evaluation.price,
      evaluation.price,
      evaluation.triggered ? 1 : 0,
      evaluation.detail
    );
  connect()
    .prepare("UPDATE alerts SET last_evaluated_at = datetime('now'), last_price = ? WHERE id = ?")
    .run(evaluation.price, alert.id);
  return info.changes > 0;
}

function alertsForSeries(seriesId, { userId = null, onlyActive = true } = {}) {
  const clauses = ['series_id = ?'];
  const params = [seriesId];
  if (onlyActive) clauses.push("status = 'active'");
  if (userId != null) {
    clauses.push('user_id = ?');
    params.push(userId);
  }
  return connect()
    .prepare(`SELECT * FROM alerts WHERE ${clauses.join(' AND ')} ORDER BY id`)
    .all(...params);
}

/**
 * Avalia todas as regras de uma série contra a última observação persistida.
 * Nunca inventa preço: usa apenas `price_observations`.
 */
function evaluateSeries(seriesId, { userId = null, logEvaluations = false } = {}) {
  const series = seriesService.get(seriesId);
  const observation = seriesService.latestObservationFor(series.commodity_key);
  const alerts = alertsForSeries(seriesId, { userId, onlyActive: true });
  const results = [];
  let triggered = 0;
  let created = 0;

  for (const alert of alerts) {
    if (!CONDITIONS.includes(alert.condition)) continue; // chuva/legado: fora do motor de preço
    const evaluation = evaluateAlert(alert, observation);
    if (logEvaluations) recordEvaluation(alert, evaluation);
    if (evaluation.triggered) {
      triggered++;
      if (recordTrigger(alert, observation, evaluation)) created++;
    }
    results.push({
      alert: rowToAlert(alert),
      triggered: evaluation.triggered,
      value: evaluation.price,
      detail: evaluation.detail,
      fresh: evaluation.fresh,
      blocked: evaluation.blocked,
      observation_date: evaluation.observation_date,
    });
  }
  return {
    series_id: seriesId,
    series,
    observation_date: observation ? observation.data_date : null,
    fresh: observation ? seriesService.freshnessFor(observation.data_date).status === 'fresh' : false,
    evaluated: results.length,
    triggered,
    events_created: created,
    results,
  };
}

/**
 * Gancho pós-atualização de preços. Best-effort: uma falha aqui nunca deve
 * impedir a resposta de preço ao usuário. Retorna um resumo para log.
 */
function runAfterPriceRefresh(commodityKey) {
  try {
    const seriesId = seriesService.seriesIdForCommodity(commodityKey);
    if (!seriesId) return { status: 'unknown_series', commodity: commodityKey };
    const summary = evaluateSeries(seriesId, { userId: null, logEvaluations: false });
    return {
      status: 'ok',
      series_id: seriesId,
      evaluated: summary.evaluated,
      triggered: summary.triggered,
      events_created: summary.events_created,
      fresh: summary.fresh,
    };
  } catch (error) {
    // eslint-disable-next-line no-console
    console.error(
      JSON.stringify({ level: 'warn', kind: 'alert_engine', commodity: commodityKey, message: error.message })
    );
    return { status: 'error', message: error.message };
  }
}

module.exports = {
  CONDITIONS,
  CONDITION_LABEL,
  KIND_TO_CONDITION,
  conditionLabel,
  meetsCondition,
  evaluateAlert,
  recordTrigger,
  recordEvaluation,
  alertsForSeries,
  evaluateSeries,
  runAfterPriceRefresh,
  rowToAlert,
  formatPrice,
};
