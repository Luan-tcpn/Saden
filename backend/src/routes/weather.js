'use strict';

const express = require('express');
const weatherService = require('../services/weatherService');
const { requireAuth } = require('../middleware/auth');

const router = express.Router();

router.get('/forecast', requireAuth, async (req, res, next) => {
  try {
    res.json(await weatherService.getForecast(req.query.lat, req.query.lon));
  } catch (e) {
    next(e);
  }
});

router.get('/history', requireAuth, async (req, res, next) => {
  try {
    res.json(await weatherService.getHistory(req.query.lat, req.query.lon, req.query.start, req.query.end));
  } catch (e) {
    next(e);
  }
});

module.exports = router;
