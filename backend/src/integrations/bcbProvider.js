'use strict';

// Banco Central — PTAX (OData público, sem chave).
// Docs: https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/documentacao
// CotacaoDolarDia:      ?@dataCotacao='MM-DD-AAAA'
// CotacaoDolarPeriodo:  ?@dataInicial='MM-DD-AAAA'&@dataFinalCotacao='MM-DD-AAAA'
const { fetchJson, withRetry } = require('../utils/http');
const { upstream } = require('../utils/errors');

const BASE = 'https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata';

function toBcb(dash) {
  // 'AAAA-MM-DD' -> 'MM-DD-AAAA'
  const [y, m, d] = dash.split('-');
  return `${m}-${d}-${y}`;
}

function toIso(bcbDateTime) {
  // '2026-09-04 13:03:59.556874' -> '2026-09-04'
  return String(bcbDateTime).slice(0, 10);
}

async function dolarDia(isoDate) {
  const url =
    `${BASE}/CotacaoDolarDia(dataCotacao=@dataCotacao)` +
    `?@dataCotacao='${toBcb(isoDate)}'&$top=10&$format=json`;
  const json = await withRetry(() => fetchJson(url));
  const values = (json && json.value) || [];
  if (values.length === 0) return null; // fim de semana/feriado: sem cotação
  const v = values[values.length - 1];
  return { date: toIso(v.dataHoraCotacao), compra: v.cotacaoCompra, venda: v.cotacaoVenda };
}

// Mapa data -> venda para um período (1 chamada). Dias sem pregão ficam ausentes.
async function dolarPeriodo(isoStart, isoEnd) {
  const url =
    `${BASE}/CotacaoDolarPeriodo(dataInicial=@dataInicial,dataFinalCotacao=@dataFinalCotacao)` +
    `?@dataInicial='${toBcb(isoStart)}'&@dataFinalCotacao='${toBcb(isoEnd)}'` +
    `&$top=1000&$orderby=dataHoraCotacao&$format=json&$select=cotacaoVenda,dataHoraCotacao`;
  const json = await withRetry(() => fetchJson(url));
  const values = (json && json.value) || [];
  if (values.length === 0) throw upstream('PTAX sem cotações no período solicitado');
  const map = new Map();
  for (const v of values) map.set(toIso(v.dataHoraCotacao), v.cotacaoVenda);
  return map;
}

module.exports = { dolarDia, dolarPeriodo };
