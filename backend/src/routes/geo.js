'use strict';

const express = require('express');
const geoService = require('../services/geoService');
const { requireAuth } = require('../middleware/auth');

const router = express.Router();

router.get('/search', requireAuth, async (req, res, next) => {
  try {
    res.json(await geoService.search(req.query.q));
  } catch (e) {
    next(e);
  }
});

router.get('/reverse', requireAuth, async (req, res, next) => {
  try {
    res.json(await geoService.reverse(req.query.lat, req.query.lon));
  } catch (e) {
    next(e);
  }
});

router.get('/estados', requireAuth, async (req, res, next) => {
  try {
    res.json({ estados: await geoService.getEstados() });
  } catch (e) {
    next(e);
  }
});

router.get('/estados/:uf/municipios', requireAuth, async (req, res, next) => {
  try {
    res.json({ uf: req.params.uf.toUpperCase(), municipios: await geoService.getMunicipios(req.params.uf) });
  } catch (e) {
    next(e);
  }
});

module.exports = router;
