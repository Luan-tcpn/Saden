'use strict';

const express = require('express');
const { connect } = require('../db');
const { requireAuth } = require('../middleware/auth');
const { badRequest, notFound } = require('../utils/errors');
const { requireString, requireNumber } = require('../utils/validate');
const rateLimit = require('../middleware/rateLimit');
const seriesService = require('../services/seriesService');
const alertEngine = require('../services/alertEngine');

const router = express.Router();

const LEGACY_ONLY_KINDS = ['rain_above'];

// Limites por usuario (Release 2): o endpoint de avaliacao pode gerar chamada
// externa; sem limite, uma conta conseguiria consumir a cota do provedor.
function keyOf(req, scope) {
  const identity = req.user ? `u:${req.user.id}` : `ip:${req.ip}`;
  return `alert-${scope}:${identity}`;
}

const LIMITS = {
  create: rateLimit({ windowMs: 10 * 60 * 1000, max: 30, key: (req) => keyOf(req, 'create') }),
  evaluate: rateLimit({ windowMs: 10 * 60 * 1000, max: 20, key: (req) => keyOf(req, 'evaluate') }),
  read: rateLimit({ windowMs: 10 * 60 * 1000, max: 120, key: (req) => keyOf(req, 'read') }),
};

// Aceita o contrato novo (series_id + condition) e o contrato V1.1
// (commodity_key + kind), resolvendo os dois para a mesma regra.
function validateAlert(body) {
  const source = body || {};
  let series;

  if (source.series_id != null) {
    const seriesId = requireString(source.series_id, 'series_id', { min: 5, max: 120 });
    series = seriesService.get(seriesId); // 404 se não existir
  } else {
    const commodityKey = requireString(source.commodity_key, 'commodity_key', { min: 2, max: 30 });
    const seriesId = seriesService.seriesIdForCommodity(commodityKey);
    if (!seriesId) throw notFound(`Commodity "${commodityKey}" não cadastrada`);
    series = seriesService.get(seriesId);
  }

  const legacyKind = source.kind != null ? requireString(source.kind, 'kind', { min: 2, max: 30 }) : null;
  if (legacyKind && LEGACY_ONLY_KINDS.includes(legacyKind)) {
    throw badRequest(
      'Alertas de chuva não são oferecidos nesta versão. Use um alerta de preço sobre uma série disponível.'
    );
  }
  const condition = legacyKind || requireString(source.condition, 'condition', { min: 5, max: 30 });
  if (!alertEngine.CONDITIONS.includes(condition)) {
    throw badRequest(`condition deve ser um de: ${alertEngine.CONDITIONS.join(', ')}`);
  }

  const threshold = requireNumber(source.threshold, 'threshold', { min: 0.0001, max: 1e9 });
  if (source.currency != null && String(source.currency).toUpperCase() !== series.currency) {
    throw badRequest(`Série ${series.series_id} usa ${series.currency}; moeda informada incompatível`);
  }
  if (source.unit != null && String(source.unit) !== series.unit) {
    throw badRequest(`Série ${series.series_id} usa "${series.unit}"; unidade informada incompatível`);
  }
  const label = source.label != null ? requireString(source.label, 'label', { min: 1, max: 120 }) : null;

  return {
    series,
    condition,
    kind: condition, // coluna legada mantida em sincronia
    threshold,
    label,
    latitude: source.latitude != null ? requireNumber(source.latitude, 'latitude', { min: -90, max: 90 }) : null,
    longitude: source.longitude != null ? requireNumber(source.longitude, 'longitude', { min: -180, max: 180 }) : null,
  };
}

function alertJson(row) {
  const base = alertEngine.rowToAlert(row);
  const unread = connect()
    .prepare("SELECT COUNT(*) AS n FROM alert_events WHERE alert_id = ? AND event_type = 'trigger' AND read_at IS NULL")
    .get(row.id).n;
  return {
    ...base,
    unread_events: unread,
    series: row.series_id
      ? {
          series_id: row.series_id,
          market: row.market,
          instrument: row.instrument,
          source: row.source,
          currency: row.currency,
          unit: row.unit,
          price_type: row.price_type,
        }
      : null,
  };
}

function eventJson(row) {
  return {
    id: row.id,
    alert_id: row.alert_id,
    type: row.event_type,
    observation_date: row.observation_date,
    observed_price: row.observed_price,
    triggered: row.triggered === 1,
    detail: row.detail,
    created_at: row.evaluated_at,
    read_at: row.read_at,
    read: row.read_at != null,
  };
}

// GET /api/alerts — regras do usuário + resumo de eventos
router.get('/', requireAuth, (req, res, next) => {
  try {
    const rows = connect()
      .prepare('SELECT * FROM alerts WHERE user_id = ? ORDER BY id DESC')
      .all(req.user.id);
    const unread = connect()
      .prepare(
        `SELECT COUNT(*) AS n FROM alert_events e
           JOIN alerts a ON a.id = e.alert_id
          WHERE a.user_id = ? AND e.event_type = 'trigger' AND e.read_at IS NULL`
      )
      .get(req.user.id).n;
    res.json({
      alerts: rows.map(alertJson),
      kinds: alertEngine.CONDITIONS,
      conditions: alertEngine.CONDITIONS.map((c) => ({ value: c, label: alertEngine.conditionLabel(c) })),
      unread_events: unread,
    });
  } catch (e) {
    next(e);
  }
});

// GET /api/alerts/events — feed do usuário (eventos de disparo)
router.get('/events', requireAuth, (req, res, next) => {
  try {
    const onlyUnread = String(req.query.unread || '') === '1';
    const rows = connect()
      .prepare(
        `SELECT e.*, a.label, a.condition, a.threshold, a.unit, a.series_id, a.commodity_key
           FROM alert_events e
           JOIN alerts a ON a.id = e.alert_id
          WHERE a.user_id = ? AND e.event_type = 'trigger'
            ${onlyUnread ? 'AND e.read_at IS NULL' : ''}
          ORDER BY e.id DESC
          LIMIT 100`
      )
      .all(req.user.id);
    res.json({
      events: rows.map((row) => ({
        ...eventJson(row),
        label: row.label,
        condition: row.condition,
        condition_label: alertEngine.conditionLabel(row.condition),
        threshold: row.threshold,
        unit: row.unit,
        series_id: row.series_id,
        commodity_key: row.commodity_key,
      })),
      unread: rows.filter((row) => row.read_at == null).length,
    });
  } catch (e) {
    next(e);
  }
});

// POST /api/alerts/events/read — marca como lidas (todas ou por id)
router.post('/events/read', requireAuth, LIMITS.read, (req, res, next) => {
  try {
    const ids = Array.isArray(req.body && req.body.ids) ? req.body.ids : null;
    const db = connect();
    if (!ids) {
      const info = db
        .prepare(
          `UPDATE alert_events SET read_at = datetime('now')
            WHERE read_at IS NULL AND event_type = 'trigger'
              AND alert_id IN (SELECT id FROM alerts WHERE user_id = ?)`
        )
        .run(req.user.id);
      return res.json({ updated: info.changes });
    }
    if (ids.length === 0 || ids.length > 200) throw badRequest('Informe de 1 a 200 ids');
    const placeholders = ids.map(() => '?').join(',');
    const info = db
      .prepare(
        `UPDATE alert_events SET read_at = datetime('now')
          WHERE read_at IS NULL AND id IN (${placeholders})
            AND alert_id IN (SELECT id FROM alerts WHERE user_id = ?)`
      )
      .run(...ids, req.user.id);
    res.json({ updated: info.changes });
  } catch (e) {
    next(e);
  }
});

// POST /api/alerts — cria regra
router.post('/', requireAuth, LIMITS.create, (req, res, next) => {
  try {
    const v = validateAlert(req.body);
    const db = connect();
    const info = db
      .prepare(
        `INSERT INTO alerts
           (user_id, commodity_key, kind, condition, series_id, threshold, currency, unit,
            instrument, market, source, price_type, latitude, longitude, label, active, status, updated_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'active', datetime('now'))`
      )
      .run(
        req.user.id,
        v.series.commodity_key,
        v.kind,
        v.condition,
        v.series.series_id,
        v.threshold,
        v.series.currency,
        v.series.unit,
        v.series.instrument,
        v.series.market,
        v.series.source,
        v.series.price_type,
        v.latitude,
        v.longitude,
        v.label
      );
    const row = db.prepare('SELECT * FROM alerts WHERE id = ?').get(info.lastInsertRowid);

    // Aviso honesto: se a última observação já satisfaz a condição, o alerta
    // dispara na primeira avaliação. A interface mostra isso antes de confirmar.
    const observation = seriesService.latestObservationFor(v.series.commodity_key);
    const evaluation = alertEngine.evaluateAlert(row, observation);
    res.status(201).json({
      alert: alertJson(row),
      would_trigger_now: evaluation.triggered,
      current: {
        price: evaluation.price,
        observation_date: evaluation.observation_date,
        fresh: evaluation.fresh,
        detail: evaluation.detail,
      },
      note: evaluation.triggered
        ? 'A última observação já satisfaz a condição: o alerta dispara na próxima avaliação.'
        : null,
    });
  } catch (e) {
    next(e);
  }
});

// PATCH /api/alerts/:id — pausar, reativar ou rearmar
router.patch('/:id', requireAuth, (req, res, next) => {
  try {
    const db = connect();
    const row = db.prepare('SELECT * FROM alerts WHERE id = ? AND user_id = ?').get(req.params.id, req.user.id);
    if (!row) throw notFound('Alerta não encontrado');

    const body = req.body || {};
    let status = null;
    if (typeof body.active === 'boolean') status = body.active ? 'active' : 'paused';
    else if (typeof body.status === 'string') {
      if (!['active', 'paused'].includes(body.status)) {
        throw badRequest('status deve ser "active" ou "paused" (disparado só muda pelo motor)');
      }
      status = body.status;
    } else {
      throw badRequest('Informe "active" (true/false) ou "status"');
    }

    db.prepare(
      `UPDATE alerts SET status = ?, active = ?, triggered_at = CASE WHEN ? = 'active' THEN NULL ELSE triggered_at END,
              updated_at = datetime('now') WHERE id = ?`
    ).run(status, status === 'active' ? 1 : 0, status, row.id);

    // Reativar rearma: o mesmo alerta pode disparar de novo com observação nova
    // (a chave única de evento impede duplicar a mesma observação).
    const updated = db.prepare('SELECT * FROM alerts WHERE id = ?').get(row.id);
    res.json({ alert: alertJson(updated) });
  } catch (e) {
    next(e);
  }
});

router.delete('/:id', requireAuth, (req, res, next) => {
  try {
    const info = connect().prepare('DELETE FROM alerts WHERE id = ? AND user_id = ?').run(req.params.id, req.user.id);
    if (info.changes === 0) throw notFound('Alerta não encontrado');
    res.json({ deleted: true });
  } catch (e) {
    next(e);
  }
});

// POST /api/alerts/check — avaliação manual (contrato V1.1 preservado)
router.post('/check', requireAuth, LIMITS.evaluate, async (req, res, next) => {
  try {
    const db = connect();
    const alerts = db
      .prepare("SELECT * FROM alerts WHERE user_id = ? AND status = 'active'")
      .all(req.user.id);
    const results = [];
    let eventsCreated = 0;

    for (const alert of alerts) {
      if (!alertEngine.CONDITIONS.includes(alert.condition)) continue; // legado de chuva
      const observation = seriesService.latestObservationFor(alert.commodity_key);
      const evaluation = alertEngine.evaluateAlert(alert, observation);
      alertEngine.recordEvaluation(alert, evaluation);
      if (evaluation.triggered && alertEngine.recordTrigger(alert, observation, evaluation)) {
        eventsCreated++;
      }
      results.push({
        alert: alertJson(alert),
        triggered: evaluation.triggered,
        value: evaluation.price,
        detail: evaluation.detail,
        fresh: evaluation.fresh,
        blocked: evaluation.blocked,
      });
    }

    res.json({
      evaluated: results.length,
      events_created: eventsCreated,
      results,
      evaluated_at: new Date().toISOString(),
    });
  } catch (e) {
    next(e);
  }
});

// POST /api/alerts/evaluate — avalia todas as séries do usuário (motor)
router.post('/evaluate', requireAuth, LIMITS.evaluate, (req, res, next) => {
  try {
    const seriesIds = connect()
      .prepare("SELECT DISTINCT series_id FROM alerts WHERE user_id = ? AND status = 'active' AND series_id IS NOT NULL")
      .all(req.user.id)
      .map((row) => row.series_id);
    const runs = seriesIds.map((id) => {
      try {
        const summary = alertEngine.evaluateSeries(id, { userId: req.user.id });
        return {
          series_id: id,
          evaluated: summary.evaluated,
          triggered: summary.triggered,
          events_created: summary.events_created,
          fresh: summary.fresh,
          observation_date: summary.observation_date,
        };
      } catch (error) {
        return { series_id: id, error: error.message };
      }
    });
    res.json({
      series: runs,
      evaluated: runs.reduce((total, run) => total + (run.evaluated || 0), 0),
      events_created: runs.reduce((total, run) => total + (run.events_created || 0), 0),
      evaluated_at: new Date().toISOString(),
    });
  } catch (e) {
    next(e);
  }
});

router.get('/:id/events', requireAuth, (req, res, next) => {
  try {
    const row = connect().prepare('SELECT * FROM alerts WHERE id = ? AND user_id = ?').get(req.params.id, req.user.id);
    if (!row) throw notFound('Alerta não encontrado');
    const events = connect()
      .prepare('SELECT * FROM alert_events WHERE alert_id = ? ORDER BY id DESC LIMIT 50')
      .all(row.id);
    res.json({ alert: alertJson(row), events: events.map(eventJson) });
  } catch (e) {
    next(e);
  }
});

module.exports = router;
