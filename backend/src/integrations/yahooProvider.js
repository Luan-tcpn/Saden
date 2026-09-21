'use strict';

// Yahoo Finance chart API — NÃO documentada oficialmente como API pública,
// mas endpoint estável e amplamente utilizado. Verificado em 2026-09-08:
// GET https://query1.finance.yahoo.com/v8/finance/chart/ZS=F?interval=1d&range=1y
// Retorna { chart: { result: [{ meta, timestamp[], indicators.quote[0] }] } }.
// Sem chave; exige User-Agent de browser. Sem CORS -> SEMPRE via backend.
const { fetchJson, withRetry } = require('../utils/http');
const { upstream } = require('../utils/errors');

function chartUrl(symbol, range = '1y', interval = '1d') {
  return `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(
    symbol
  )}?interval=${interval}&range=${range}&events=div%7Csplit`;
}

// Retorna [{ date: 'AAAA-MM-DD', close: Number }] em USD (unidade nativa do contrato).
async function dailyCloses(symbol, range = '1y') {
  const json = await withRetry(() => fetchJson(chartUrl(symbol, range)));
  const result = json && json.chart && json.chart.result && json.chart.result[0];
  if (!result || !Array.isArray(result.timestamp)) {
    throw upstream(`Yahoo Finance sem dados para ${symbol}`);
  }
  const quote = result.indicators && result.indicators.quote && result.indicators.quote[0];
  if (!quote || !Array.isArray(quote.close)) throw upstream(`Yahoo Finance sem cotações para ${symbol}`);
  const out = [];
  for (let i = 0; i < result.timestamp.length; i++) {
    const close = quote.close[i];
    if (!Number.isFinite(close)) continue; // pula feriados/falhas sem inventar valor
    const date = new Date(result.timestamp[i] * 1000).toISOString().slice(0, 10);
    out.push({ date, close });
  }
  if (out.length === 0) throw upstream(`Yahoo Finance retornou série vazia para ${symbol}`);
  return { series: out, meta: result.meta || {} };
}

module.exports = { dailyCloses, chartUrl };
