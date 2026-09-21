'use strict';

const express = require('express');
const forecastService = require('../services/forecastService');
const { requireAuth } = require('../middleware/auth');

const router = express.Router();

router.get('/:key', requireAuth, async (req, res, next) => {
  try {
    res.json(await forecastService.run(req.params.key, req.query.horizon));
  } catch (e) {
    next(e);
  }
});

module.exports = router;
