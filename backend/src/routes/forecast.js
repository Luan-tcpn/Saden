'use strict';

const express = require('express');
const forecastService = require('../services/forecastService');
const { requireAuth } = require('../middleware/auth');

const router = express.Router();

router.get('/:key', requireAuth, async (req, res, next) => {
  try {
    // V1 final (D40): única metodologia = Ridge. `?model=ridge` segue aceito
    // como alias legado; qualquer outro valor → 400 honesto, sem fallback.
    res.json(await forecastService.runFor(req.query.model, req.params.key, req.query.horizon));
  } catch (e) {
    next(e);
  }
});

module.exports = router;
