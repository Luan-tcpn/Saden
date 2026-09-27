'use strict';

const express = require('express');
const arService = require('../services/arService');
const { requireAuth } = require('../middleware/auth');

const router = express.Router();

router.get('/:key', requireAuth, async (req, res, next) => {
  try {
    // D38: Ridge é o default (ausência = comportamento anterior); `?model=ar`
    // opt-in do challenger; qualquer outro valor → 400 honesto, sem fallback.
    res.json(await arService.runFor(req.query.model, req.params.key, req.query.horizon));
  } catch (e) {
    next(e);
  }
});

module.exports = router;
