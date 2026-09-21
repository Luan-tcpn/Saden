'use strict';

// IBGE Serviço de Dados — Localidades. Público, sem chave.
// Docs: https://servicodados.ibge.gov.br/api/docs/localidades
// Base: https://servicodados.ibge.gov.br/api/v1/localidades
const { fetchJson, withRetry } = require('../utils/http');

const BASE = 'https://servicodados.ibge.gov.br/api/v1/localidades';

async function estados() {
  return withRetry(() => fetchJson(`${BASE}/estados?orderBy=nome`));
}

async function municipios(UF) {
  return withRetry(() => fetchJson(`${BASE}/estados/${encodeURIComponent(UF)}/municipios?orderBy=nome`));
}

async function municipioById(id) {
  return withRetry(() => fetchJson(`${BASE}/municipios/${encodeURIComponent(id)}`));
}

module.exports = { estados, municipios, municipioById };
