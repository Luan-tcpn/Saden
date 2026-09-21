'use strict';

const express = require('express');
const { requireAuth } = require('../middleware/auth');
const referenceService = require('../services/priceReferenceService');

const router = express.Router();

// GET /api/prices/reference?commodity=soja&uf=SP&ibge_code=3543402
router.get('/reference', requireAuth, async (req, res, next) => {
  try {
    const { commodity, uf, ibge_code } = req.query;
    if (!commodity) {
      return res.status(400).json({ error: 'Parâmetro "commodity" é obrigatório' });
    }
    res.json(await referenceService.reference(commodity, { uf, ibgeCode: ibge_code }));
  } catch (e) {
    next(e);
  }
});

module.exports = router;
