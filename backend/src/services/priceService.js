'use strict';

const { connect, cacheGet, cacheSet } = require('../db');
const config = require('../config');
const yahoo = require('../integrations/yahooProvider');
const bcb = require('../integrations/bcbProvider');
const { toBRL, converter } = require('./fxService');
const { notFound } = require('../utils/errors');

function getCommodity(key) {
  const row = connect().prepare('SELECT * FROM commodities WHERE key = ?').get(key);
  if (!row) throw notFound(`Commodity "${key}" não cadastrada`);
  return row;
}

function listCommodities() {
  return connect().prepare('SELECT * FROM commodities ORDER BY name').all();
}

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

// Série BRL com rastreabilidade. Cache em memória-DB por TTL.
async function getSeries(commodityKey, range = '1y') {
  const commodity = getCommodity(commodityKey);
  const cacheKey = `prices:${commodityKey}:${range}`;
  const cached = cacheGet(cacheKey);
  if (cached) return { ...cached, cached: true };

  const { series, meta } = await yahoo.dailyCloses(commodity.yahoo_symbol, range);
  const start = series[0].date;
  const fxMap = await bcb.dolarPeriodo(start, todayIso()).catch(() => null);

  let lastFx = null;
  let fxUsed = 0;
  let fxFallbackDays = 0;
  const points = [];
  for (const p of series) {
    let fx = fxMap ? fxMap.get(p.date) : null;
    if (fx == null && lastFx != null) {
      fx = lastFx;
      fxFallbackDays++;
    }
    if (fx == null) continue; // sem câmbio de referência: descarta o ponto, não inventa
    lastFx = fx;
    fxUsed = fx;
    points.push({
      date: p.date,
      price_usd_cents: round2(p.close),
      fx_venda: fx,
      price_brl: round2(toBRL(commodityKey, p.close, fx)),
    });
  }
  if (points.length < 10) {
    throw Object.assign(new Error('Série insuficiente após cruzamento com o câmbio'), { status: 502 });
  }

  persistObservations(commodityKey, commodity.unit_br, points);

  const payload = {
    cached: false,
    commodity: {
      key: commodity.key,
      name: commodity.name,
      unit_br: commodity.unit_br,
      yahoo_symbol: commodity.yahoo_symbol,
      conversion: converter(commodityKey),
    },
    unit: commodity.unit_br,
    count: points.length,
    data_start: points[0].date,
    data_end: points[points.length - 1].date,
    provider: 'yahoo',
    fx_provider: fxMap ? 'bcb-ptax' : 'bcb-ptax-fallback',
    fx_last: fxUsed,
    fx_fallback_days: fxFallbackDays,
    retrieved_at: new Date().toISOString(),
    points,
    meta: { exchange: meta.exchangeName || meta.fullExchangeName, currency: meta.currency },
  };
  cacheSet(cacheKey, payload, config.cachePricesTtlMin * 60 * 1000);
  return payload;
}

async function getLatest(commodityKey) {
  const s = await getSeries(commodityKey, '3mo');
  const pts = s.points;
  const last = pts[pts.length - 1];
  const prev = pts[pts.length - 2];
  const variation = prev ? ((last.price_brl - prev.price_brl) / prev.price_brl) * 100 : 0;
  return {
    commodity: s.commodity,
    unit: s.unit,
    price_brl: last.price_brl,
    price_usd_cents: last.price_usd_cents,
    fx_venda: last.fx_venda,
    data_date: last.date,
    previous_date: prev ? prev.date : null,
    variation_pct: round2(variation),
    provider: s.provider,
    fx_provider: s.fx_provider,
    retrieved_at: s.retrieved_at,
    cached: s.cached,
  };
}

function persistObservations(commodityKey, unit, points) {
  const stmt = connect().prepare(
    `INSERT OR REPLACE INTO price_observations
     (commodity_key, data_date, price_usd, fx_rate, price_brl, unit_br, provider)
     VALUES(?, ?, ?, ?, ?, ?, 'yahoo')`
  );
  const tx = connect().transaction((rows) => {
    for (const p of rows) {
      stmt.run(commodityKey, p.date, p.price_usd_cents, p.fx_venda, p.price_brl, unit);
    }
  });
  tx(points);
}

function round2(n) {
  return Math.round(n * 100) / 100;
}

module.exports = { getCommodity, listCommodities, getSeries, getLatest };
