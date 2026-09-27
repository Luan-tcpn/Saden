'use strict';

const express = require('express');
const { connect } = require('../db');
const { requireAuth } = require('../middleware/auth');
const priceService = require('../services/priceService');
const weatherService = require('../services/weatherService');
const arService = require('../services/arService');

const router = express.Router();

// Monta o relatório consolidado (também usado pela página de impressão -> PDF).
router.get('/:key', requireAuth, async (req, res, next) => {
  try {
    const { key } = req.params;
    const { lat, lon, horizon, model } = req.query;
    const [series, forecast, weather] = await Promise.all([
      priceService.getSeries(key, '1y'),
      arService.runFor(model, key, horizon || 14),
      lat && lon
        ? weatherService.getForecast(lat, lon).catch(() => null)
        : Promise.resolve(null),
    ]);
    const payload = {
      commodity: series.commodity,
      unit: series.unit,
      generated_at: new Date().toISOString(),
      price: {
        current_brl: forecast.current_price_brl,
        data_start: series.data_start,
        data_end: series.data_end,
        provider: series.provider,
        fx_provider: series.fx_provider,
        fx_last: series.fx_last,
      },
      history_tail: series.points.slice(-90),
      forecast: {
        model: forecast.model,
        model_selected: forecast.model_selected,
        metrics: forecast.metrics,
        baselines: forecast.baselines,
        trend: forecast.trend,
        points: forecast.forecast,
        limitations: forecast.limitations,
      },
      weather: weather
        ? { latitude: weather.latitude, longitude: weather.longitude, current: weather.current, daily: weather.daily }
        : null,
      sources: sourceList(),
    };
    if (req.user && req.user.id) {
      connect()
        .prepare('INSERT INTO reports(user_id, commodity_key, payload_json) VALUES(?, ?, ?)')
        .run(req.user.id, key, JSON.stringify(payload));
    }
    res.json(payload);
  } catch (e) {
    next(e);
  }
});

// Sanitização anti formula-injection (OWASP): prefixa com TAB células que
// começam com = + - @, tab ou quebra de linha; envolve em aspas quando o
// campo contém separador, aspas ou quebra. Números/datas passam intactos.
function csvCell(v) {
  let s = String(v == null ? '' : v);
  if (/^[=+\-@\t\r\n]/.test(s)) s = `\t${s}`;
  if (/[;"\r\n]/.test(s)) s = `"${s.replace(/"/g, '""')}"`;
  return s;
}

// Exportação CSV do relatório (history + forecast em um arquivo).
router.get('/:key/csv', requireAuth, async (req, res, next) => {
  try {
    const { key } = req.params;
    const { lat, lon, horizon, model } = req.query;
    const [series, forecast] = await Promise.all([
      priceService.getSeries(key, '1y'),
      arService.runFor(model, key, horizon || 14),
    ]);
    void lat;
    void lon;
    const lines = [
      '# SADEN — relatório. Referência internacional convertida (Yahoo Finance + PTAX); não é indicador CEPEA.',
      `# commodity: ${csvCell(`${series.commodity.name} (${series.commodity.key})`)}`,
      `# unidade: ${csvCell(series.unit)}`,
      `# gerado_em: ${new Date().toISOString()}`,
      `# modelo: ${csvCell(modelTag(forecast))}; metricas_test_rmse=${forecast.metrics.test.rmse}`,
      'secao;data;preco_brl;limite_inferior;limite_superior;fonte',
    ];
    for (const p of series.points) {
      lines.push(['historico', p.date, p.price_brl, '', '', `${series.provider}+${series.fx_provider}`].map(csvCell).join(';'));
    }
    for (const f of forecast.forecast) {
      lines.push(['previsao', f.date, f.price_brl, f.lower_brl, f.upper_brl, forecast.model].map(csvCell).join(';'));
    }
    const csv = lines.join('\n');
    res.setHeader('Content-Type', 'text/csv; charset=utf-8');
    res.setHeader('Content-Disposition', `attachment; filename="saden-${key}-relatorio.csv"`);
    res.send(`\uFEFF${csv}\n`);
  } catch (e) {
    next(e);
  }
});

function sourceList() {
  return connect().prepare('SELECT key, name, base_url, docs_url, kind, status FROM data_sources').all();
}

// Identificação do modelo no CSV (D38): Ridge mantém `lambda`; AR usa `order`.
// Nunca emite `lambda=undefined`.
function modelTag(fc) {
  if (fc && fc.model === 'ar') return `ar (order=${fc.ar_order})`;
  return `${fc ? fc.model : 'ridge'} (lambda=${fc ? fc.lambda : '?'})`;
}

module.exports = router;
module.exports._test = { csvCell, modelTag };
