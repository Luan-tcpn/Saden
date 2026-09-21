'use strict';

const express = require('express');
const { connect } = require('../db');
const { requireAuth } = require('../middleware/auth');
const { badRequest, notFound } = require('../utils/errors');
const { requireString, requireNumber } = require('../utils/validate');

const router = express.Router();

function rowToJson(r) {
  return { id: r.id, label: r.label, latitude: r.latitude, longitude: r.longitude, created_at: r.created_at };
}

router.get('/', requireAuth, (req, res, next) => {
  try {
    const rows = connect().prepare('SELECT * FROM user_places WHERE user_id = ? ORDER BY id DESC LIMIT 50').all(req.user.id);
    res.json({ places: rows.map(rowToJson) });
  } catch (e) {
    next(e);
  }
});

router.post('/', requireAuth, (req, res, next) => {
  try {
    const label = requireString(req.body && req.body.label, 'label', { min: 1, max: 120 });
    const latitude = requireNumber(req.body && req.body.latitude, 'latitude', { min: -90, max: 90 });
    const longitude = requireNumber(req.body && req.body.longitude, 'longitude', { min: -180, max: 180 });
    const info = connect()
      .prepare('INSERT INTO user_places(user_id, label, latitude, longitude) VALUES(?, ?, ?, ?)')
      .run(req.user.id, label, latitude, longitude);
    const row = connect().prepare('SELECT * FROM user_places WHERE id = ?').get(info.lastInsertRowid);
    res.status(201).json({ place: rowToJson(row) });
  } catch (e) {
    next(e);
  }
});

router.delete('/:id', requireAuth, (req, res, next) => {
  try {
    const info = connect().prepare('DELETE FROM user_places WHERE id = ? AND user_id = ?').run(req.params.id, req.user.id);
    if (info.changes === 0) throw notFound('Local não encontrado');
    res.json({ deleted: true });
  } catch (e) {
    next(e);
  }
});

module.exports = router;
