'use strict';

const express = require('express');
const priceService = require('../services/priceService');
const { requireAuth } = require('../middleware/auth');
const { badRequest } = require('../utils/errors');

const router = express.Router();
const RANGES = ['1mo', '3mo', '6mo', '1y', '2y'];

router.get('/', requireAuth, (req, res) => {
  res.json({ commodities: priceService.listCommodities() });
});

router.get('/:key/series', requireAuth, async (req, res, next) => {
  try {
    const range = req.query.range || '1y';
    if (!RANGES.includes(range)) throw badRequest(`range deve ser um de: ${RANGES.join(', ')}`);
    const data = await priceService.getSeries(req.params.key, range);
    res.json(data);
  } catch (e) {
    next(e);
  }
});

router.get('/:key/latest', requireAuth, async (req, res, next) => {
  try {
    res.json(await priceService.getLatest(req.params.key));
  } catch (e) {
    next(e);
  }
});

module.exports = router;
