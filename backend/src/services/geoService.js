'use strict';

const { cacheGet, cacheSet } = require('../db');
const config = require('../config');
const ibge = require('../integrations/ibgeProvider');
const openmeteo = require('../integrations/openmeteoProvider');
const nominatim = require('../integrations/nominatimProvider');
const { requireString, requireNumber } = require('../utils/validate');
const { badRequest } = require('../utils/errors');
const { parseCoordinates } = require('../utils/coords');

async function getEstados() {
  const key = 'geo:estados';
  const cached = cacheGet(key);
  if (cached) return cached;
  const data = await ibge.estados();
  cacheSet(key, data, config.cacheGeoTtlDays * 24 * 3600 * 1000);
  return data;
}

async function getMunicipios(UF) {
  const uf = requireString(UF, 'UF', { min: 2, max: 2 }).toUpperCase();
  const key = `geo:municipios:${uf}`;
  const cached = cacheGet(key);
  if (cached) return cached;
  const data = await ibge.municipios(uf);
  cacheSet(key, data, config.cacheGeoTtlDays * 24 * 3600 * 1000);
  return data;
}

// Busca unificada: detecta coordenadas (→ reverse); senão combina
// Open-Meteo (cidades/lugares) + Nominatim/OSM (ruas/endereços), com
// ancoragem IBGE quando estado+município são conhecidos.
async function search(q) {
  const query = requireString(q, 'q', { min: 2, max: 200 });
  const key = `geo:search:${query.toLowerCase()}`;
  const cached = cacheGet(key);
  if (cached) return { ...cached, cached: true };

  const asCoords = parseCoordinates(query);
  if (asCoords && asCoords.invalid) {
    throw badRequest('Coordenadas fora das faixas válidas (latitude -90..90, longitude -180..180)');
  }
  let results;
  let mode;
  if (asCoords) {
    mode = 'coordinates';
    results = [await reverseToResult(asCoords.lat, asCoords.lon)];
  } else {
    mode = 'text';
    const [om, osm] = await Promise.all([
      openmeteo.geocode(query).catch(() => []),
      nominatim.search(query).catch(() => []),
    ]);
    results = await mergeResults(om, osm);
  }
  const payload = { cached: false, query, mode, count: results.length, results, retrieved_at: new Date().toISOString() };
  cacheSet(key, payload, config.cacheGeoTtlDays * 24 * 3600 * 1000);
  return payload;
}

async function mergeResults(om, osm) {
  const out = [];
  const seen = new Set();
  const push = (r) => {
    const k = `${r.latitude.toFixed(2)},${r.longitude.toFixed(2)}`;
    if (seen.has(k)) return;
    seen.add(k);
    out.push(r);
  };
  for (const g of (om || []).slice(0, 5)) {
    let ibgeCode = null;
    let uf = g.admin1 || null;
    if (g.admin2 && g.admin1) {
      const match = await matchMunicipioIBGE(g.admin2, g.admin1).catch(() => null);
      if (match) {
        ibgeCode = match.id;
        uf = match.uf;
      }
    }
    push({
      name: g.name,
      label: [g.name, g.admin1, g.country].filter(Boolean).join(', '),
      admin1: g.admin1,
      admin2: g.admin2,
      uf,
      country: g.country,
      latitude: g.latitude,
      longitude: g.longitude,
      ibge_code: ibgeCode,
      provider: 'open-meteo-geocoding',
    });
  }
  for (const n of (osm || []).slice(0, 5)) {
    const a = n.address || {};
    const city = a.city || a.town || a.village || a.municipality || null;
    const state = a.state || null;
    let uf = null;
    let ibgeCode = null;
    if (a['ISO3166-2-lvl4']) {
      const m = String(a['ISO3166-2-lvl4']).match(/BR-(..)/);
      if (m) uf = m[1];
    }
    if (city && state) {
      const match = await matchMunicipioIBGE(city, state).catch(() => null);
      if (match) {
        ibgeCode = match.id;
        uf = match.uf;
      }
    }
    push({
      name: n.name || (a.road ? `${a.road}` : n.display_name.split(',')[0]),
      label: n.display_name,
      admin1: state,
      admin2: city,
      uf,
      country: a.country || null,
      latitude: Number(n.lat),
      longitude: Number(n.lon),
      ibge_code: ibgeCode,
      provider: 'nominatim',
    });
  }
  return out.slice(0, 8);
}

function inBrazil(lat, lon) {
  return lat >= -34 && lat <= 6 && lon >= -75 && lon <= -32;
}

// Reverse geocoding (Nominatim) → resultado no formato unificado.
async function reverse(lat, lon) {
  const la = requireNumber(lat, 'latitude', { min: -90, max: 90 });
  const lo = requireNumber(lon, 'longitude', { min: -180, max: 180 });
  const key = `geo:rev:${la.toFixed(4)},${lo.toFixed(4)}`;
  const cached = cacheGet(key);
  if (cached) return { ...cached, cached: true };
  const payload = { ...(await reverseToResult(la, lo)), cached: false };
  cacheSet(key, payload, config.cacheGeoTtlDays * 24 * 3600 * 1000);
  return payload;
}

async function reverseToResult(lat, lon) {
  const n = await nominatim.reverse(lat, lon);
  const a = n.address || {};
  const city = a.city || a.town || a.village || a.municipality || a.county || null;
  const state = a.state || null;
  let uf = null;
  let ibgeCode = null;
  if (a['ISO3166-2-lvl4']) {
    const m = String(a['ISO3166-2-lvl4']).match(/BR-(..)/);
    if (m) uf = m[1];
  }
  if (city && state) {
    const match = await matchMunicipioIBGE(city, state).catch(() => null);
    if (match) {
      ibgeCode = match.id;
      uf = match.uf;
    }
  }
  return {
    name: city || n.name || `${lat.toFixed(4)}, ${lon.toFixed(4)}`,
    label: n.display_name,
    admin1: state,
    admin2: city,
    uf,
    country: a.country || null,
    latitude: Number(n.lat),
    longitude: Number(n.lon),
    ibge_code: ibgeCode,
    provider: 'nominatim-reverse',
    in_brazil: inBrazil(lat, lon),
    retrieved_at: new Date().toISOString(),
  };
}

// Ancora o resultado do geocoding no IBGE quando possível:
// se admin1 corresponde a um estado, busca os municípios da UF e tenta
// casamento exato de nome (normalizado). Sem casamento: ibge_code=null
// (declarado, nunca inventado).
const UF_BY_STATE_NAME = {
  acre: 'AC', alagoas: 'AL', amapa: 'AP', amazonas: 'AM', bahia: 'BA', ceara: 'CE',
  'distrito federal': 'DF', 'espirito santo': 'ES', goias: 'GO', maranhao: 'MA',
  'mato grosso': 'MT', 'mato grosso do sul': 'MS', 'minas gerais': 'MG', para: 'PA',
  paraiba: 'PB', parana: 'PR', pernambuco: 'PE', piaui: 'PI', 'rio de janeiro': 'RJ',
  'rio grande do norte': 'RN', 'rio grande do sul': 'RS', rondonia: 'RO', roraima: 'RR',
  'santa catarina': 'SC', 'sao paulo': 'SP', sergipe: 'SE', tocantins: 'TO',
};

function norm(s) {
  return String(s || '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .trim();
}

async function matchMunicipioIBGE(nomeMunicipio, nomeEstado) {
  const uf = UF_BY_STATE_NAME[norm(nomeEstado)];
  if (!uf) return null;
  const list = await getMunicipios(uf);
  const target = norm(nomeMunicipio);
  const found = list.find((m) => norm(m.nome) === target);
  if (!found) return null;
  return { id: found.id, uf };
}

module.exports = { getEstados, getMunicipios, search, reverse };
