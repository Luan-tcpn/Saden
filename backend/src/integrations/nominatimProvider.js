'use strict';

// Nominatim (OpenStreetMap) — geocoding de endereços/ruas + reverse.
// Documentação/uso: https://operations.osmfoundation.org/policies/nominatim/
// Política: máx. 1 req/s, User-Agent identificável, atribuição OSM obrigatória.
// Sem chave. Cobertura global; aqui com viés Brasil (countrycodes=br).
const { fetchJson, withRetry } = require('../utils/http');
const { upstream } = require('../utils/errors');

const BASE = 'https://nominatim.openstreetmap.org';
const UA = 'SADEN-TCC/0.1 (pesquisa-academica; contato via repositorio)';
let lastCall = 0;

async function throttle() {
  const wait = 1100 - (Date.now() - lastCall);
  if (wait > 0) await new Promise((r) => setTimeout(r, wait));
  lastCall = Date.now();
}

async function get(path) {
  await throttle();
  const json = await withRetry(() =>
    fetchJson(`${BASE}${path}`, { headers: { 'User-Agent': UA, Referer: 'http://localhost:3001/' } })
  );
  return json;
}

async function search(q) {
  const url =
    `/search?q=${encodeURIComponent(q)}&format=jsonv2&limit=5` +
    `&countrycodes=br&addressdetails=1&accept-language=pt-BR`;
  const arr = await get(url);
  if (!Array.isArray(arr)) throw upstream('Nominatim respondeu formato inesperado');
  return arr;
}

async function reverse(lat, lon) {
  const url = `/reverse?lat=${lat}&lon=${lon}&format=jsonv2&addressdetails=1&accept-language=pt-BR&zoom=14`;
  const obj = await get(url);
  if (!obj || obj.error || !obj.lat) {
    const err = new Error('Localidade não encontrada para estas coordenadas');
    err.status = 404;
    throw err;
  }
  return obj;
}

module.exports = { search, reverse };
