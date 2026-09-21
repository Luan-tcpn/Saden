'use strict';

const express = require('express');
const { requireAuth } = require('../middleware/auth');
const { badRequest } = require('../utils/errors');
const landcover = require('../integrations/landcoverProvider');

const router = express.Router();

// Cache em memória (tiles PNG de dado anual imutável). Instância única;
// 100 tiles recentes — proporcional ao uso do SADEN.
const mem = new Map();
const MAX_TILES = 100;

function tileInt(v, name, min, max) {
  const n = Number(v);
  if (!Number.isInteger(n) || n < min || n > max) throw badRequest(`${name} de tile inválido`);
  return n;
}

// Tiles e metadados são dados públicos (Esri/Impact Observatory) sem PII:
// rotas públicas para que o <img> do Leaflet carregue sem Bearer.
// (O mapa interativo continua atrás de login no frontend.)
router.get('/tile/:z/:x/:y.png', async (req, res, next) => {
  try {
    const z = tileInt(req.params.z, 'z', 0, 14);
    const lim = 2 ** z - 1;
    const x = tileInt(req.params.x, 'x', 0, lim);
    const y = tileInt(req.params.y, 'y', 0, lim);
    const key = `${z}/${x}/${y}`;
    const hit = mem.get(key);
    if (hit) {
      res.setHeader('Content-Type', 'image/png');
      res.setHeader('Cache-Control', 'public, max-age=2592000');
      res.setHeader('X-Saden-Cache', 'hit');
      return res.send(hit);
    }
    const buf = await landcover.tile(z, x, y);
    mem.set(key, buf);
    if (mem.size > MAX_TILES) mem.delete(mem.keys().next().value);
    res.setHeader('Content-Type', 'image/png');
    res.setHeader('Cache-Control', 'public, max-age=2592000');
    res.setHeader('X-Saden-Cache', 'miss');
    return res.send(buf);
  } catch (e) {
    next(e);
  }
});

// Metadados honestos da camada: classes verificadas, limites conhecidos.
router.get('/info', (req, res) => {
  res.json({
    name: 'Sentinel-2 10m Land Use / Land Cover',
    provider: 'Esri + Impact Observatory (Living Atlas)',
    service_url: landcover.SERVICE_URL,
    years: [2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025],
    resolution_m: 10,
    classes: landcover.CLASSES,
    limitations: [
      'Mosaico anual (não é tempo real); ano mais recente exibido.',
      'Consulta de classe por ponto e estatísticas de área indisponíveis sem credencial (identify retorna NoData).',
      'Uso conforme Esri Master License Agreement; obra LULC sob CC BY 4.0 com atribuição.',
    ],
    attribution: 'Esri, Impact Observatory',
    retrieved_at: new Date().toISOString(),
  });
});

module.exports = router;
