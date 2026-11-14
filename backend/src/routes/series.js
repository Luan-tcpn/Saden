'use strict';

// Catálogo de séries elegíveis para monitoramento.
// Só entra aqui o que o backend realmente entrega: hoje, futuros internacionais
// convertidos por PTAX. Fontes bloqueadas (CEPEA/CONAB) não aparecem.
const express = require('express');
const { requireAuth } = require('../middleware/auth');
const seriesService = require('../services/seriesService');
const alertEngine = require('../services/alertEngine');

const router = express.Router();

router.get('/', requireAuth, (req, res, next) => {
  try {
    const series = seriesService.list();
    res.json({
      series,
      conditions: alertEngine.CONDITIONS.map((value) => ({
        value,
        label: alertEngine.CONDITION_LABEL[value],
      })),
      stale_after_days: seriesService.STALE_AFTER_DAYS,
      note:
        'Preços são referências internacionais convertidas pela PTAX — não são o preço recebido pelo produtor. ' +
        'Não há série física regional: CEPEA e CONAB não oferecem API pública.',
    });
  } catch (e) {
    next(e);
  }
});

router.get('/:id', requireAuth, (req, res, next) => {
  try {
    res.json({ series: seriesService.get(req.params.id) });
  } catch (e) {
    next(e);
  }
});

module.exports = router;
