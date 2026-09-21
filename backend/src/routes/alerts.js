'use strict';

const express = require('express');
const { connect } = require('../db');
const { requireAuth } = require('../middleware/auth');
const { badRequest, notFound } = require('../utils/errors');
const { requireString, requireNumber } = require('../utils/validate');
const priceService = require('../services/priceService');
const weatherService = require('../services/weatherService');

const router = express.Router();
const KINDS = ['price_below', 'price_above', 'rain_above'];
const KIND_LABEL = {
  price_below: 'Preço abaixo de (R$)',
  price_above: 'Preço acima de (R$)',
  rain_above: 'Chuva 7 dias acima de (mm)',
};

function validateAlert(body) {
  const commodity_key = requireString(body && body.commodity_key, 'commodity_key', { min: 2, max: 30 });
  priceService.getCommodity(commodity_key); // 404 se desconhecida
  const kind = requireString(body && body.kind, 'kind', { min: 2, max: 30 });
  if (!KINDS.includes(kind)) throw badRequest(`kind deve ser um de: ${KINDS.join(', ')}`);
  const threshold = requireNumber(body && body.threshold, 'threshold', { min: 0.0001, max: 1e9 });
  let latitude = null;
  let longitude = null;
  if (kind === 'rain_above') {
    latitude = requireNumber(body && body.latitude, 'latitude', { min: -90, max: 90 });
    longitude = requireNumber(body && body.longitude, 'longitude', { min: -180, max: 180 });
  } else {
    if (body && body.latitude != null) latitude = requireNumber(body.latitude, 'latitude', { min: -90, max: 90 });
    if (body && body.longitude != null) longitude = requireNumber(body.longitude, 'longitude', { min: -180, max: 180 });
  }
  const label = body && body.label != null ? requireString(body.label, 'label', { min: 1, max: 120 }) : null;
  return { commodity_key, kind, threshold, latitude, longitude, label };
}

function rowToJson(r) {
  return { ...r, active: r.active === 1, kind_label: KIND_LABEL[r.kind] || r.kind };
}

router.get('/', requireAuth, (req, res, next) => {
  try {
    const rows = connect()
      .prepare('SELECT * FROM alerts WHERE user_id = ? ORDER BY id DESC')
      .all(req.user.id);
    res.json({ alerts: rows.map(rowToJson), kinds: KINDS });
  } catch (e) {
    next(e);
  }
});

router.post('/', requireAuth, (req, res, next) => {
  try {
    const v = validateAlert(req.body);
    const info = connect()
      .prepare(
        'INSERT INTO alerts(user_id, commodity_key, kind, threshold, latitude, longitude, label) VALUES(?, ?, ?, ?, ?, ?, ?)'
      )
      .run(req.user.id, v.commodity_key, v.kind, v.threshold, v.latitude, v.longitude, v.label);
    const row = connect().prepare('SELECT * FROM alerts WHERE id = ?').get(info.lastInsertRowid);
    res.status(201).json({ alert: rowToJson(row) });
  } catch (e) {
    next(e);
  }
});

router.patch('/:id', requireAuth, (req, res, next) => {
  try {
    const row = connect().prepare('SELECT * FROM alerts WHERE id = ? AND user_id = ?').get(req.params.id, req.user.id);
    if (!row) throw notFound('Alerta não encontrado');
    const active = req.body && req.body.active;
    if (typeof active !== 'boolean') throw badRequest('Campo "active" (true/false) é obrigatório');
    connect().prepare('UPDATE alerts SET active = ? WHERE id = ?').run(active ? 1 : 0, row.id);
    const updated = connect().prepare('SELECT * FROM alerts WHERE id = ?').get(row.id);
    res.json({ alert: rowToJson(updated) });
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

async function evaluateAlert(alert) {
  if (alert.kind === 'price_below' || alert.kind === 'price_above') {
    const latest = await priceService.getLatest(alert.commodity_key);
    const value = latest.price_brl;
    const triggered = alert.kind === 'price_below' ? value < alert.threshold : value > alert.threshold;
    return { triggered, value, detail: `Preço atual R$ ${value} (${latest.unit}) em ${latest.data_date}` };
  }
  const wx = await weatherService.getForecast(alert.latitude, alert.longitude);
  const value = Math.round(wx.daily.slice(0, 7).reduce((a, d) => a + (d.precipitation || 0), 0) * 10) / 10;
  return { triggered: value > alert.threshold, value, detail: `Chuva acumulada 7 dias: ${value} mm` };
}

// Avaliação controlada: só do usuário autenticado, sob demanda.
router.post('/check', requireAuth, async (req, res, next) => {
  try {
    const alerts = connect().prepare('SELECT * FROM alerts WHERE user_id = ? AND active = 1').all(req.user.id);
    const results = [];
    for (const a of alerts) {
      try {
        const ev = await evaluateAlert(a);
        connect().prepare('INSERT INTO alert_events(alert_id, triggered, value, detail) VALUES(?, ?, ?, ?)').run(
          a.id,
          ev.triggered ? 1 : 0,
          ev.value,
          ev.detail
        );
        results.push({ alert: rowToJson(a), ...ev });
      } catch (e) {
        results.push({ alert: rowToJson(a), triggered: false, value: null, detail: `Falha na avaliação: ${e.message}` });
      }
    }
    connect()
      .prepare('DELETE FROM alert_events WHERE id NOT IN (SELECT id FROM alert_events ORDER BY id DESC LIMIT 500)')
      .run();
    res.json({ evaluated: results.length, results, evaluated_at: new Date().toISOString() });
  } catch (e) {
    next(e);
  }
});

router.get('/:id/events', requireAuth, (req, res, next) => {
  try {
    const row = connect().prepare('SELECT * FROM alerts WHERE id = ? AND user_id = ?').get(req.params.id, req.user.id);
    if (!row) throw notFound('Alerta não encontrado');
    const events = connect()
      .prepare('SELECT * FROM alert_events WHERE alert_id = ? ORDER BY id DESC LIMIT 30')
      .all(row.id);
    res.json({ alert: rowToJson(row), events });
  } catch (e) {
    next(e);
  }
});

module.exports = router;
