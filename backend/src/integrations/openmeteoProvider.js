'use strict';

// Open-Meteo — sem chave, ~10k req/dia (uso não-comercial).
// Docs: https://open-meteo.com/en/docs
// Forecast:  https://api.open-meteo.com/v1/forecast?latitude=..&longitude=..&daily=..&current=..
// Archive:   https://archive-api.open-meteo.com/v1/archive?latitude=..&longitude=..&start_date=..&end_date=..&daily=..
// Geocoding: https://geocoding-api.open-meteo.com/v1/search?name=..&count=..&language=pt&format=json
const { fetchJson, withRetry } = require('../utils/http');
const { upstream } = require('../utils/errors');

const DAILY_VARS = [
  'temperature_2m_max',
  'temperature_2m_min',
  'temperature_2m_mean',
  'precipitation_sum',
  'relative_humidity_2m_mean',
  'wind_speed_10m_max',
].join(',');

async function forecast(lat, lon) {
  const url =
    `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}` +
    `&current=temperature_2m,relative_humidity_2m,precipitation,weather_code` +
    `&daily=${DAILY_VARS},weather_code&timezone=America%2FSao_Paulo&forecast_days=7`;
  const json = await withRetry(() => fetchJson(url));
  if (!json || !json.daily || !Array.isArray(json.daily.time)) {
    throw upstream('Open-Meteo sem dados de previsão para a localidade');
  }
  return json;
}

async function history(lat, lon, start, end) {
  const url =
    `https://archive-api.open-meteo.com/v1/archive?latitude=${lat}&longitude=${lon}` +
    `&start_date=${start}&end_date=${end}&daily=${DAILY_VARS}&timezone=America%2FSao_Paulo`;
  const json = await withRetry(() => fetchJson(url));
  if (!json || !json.daily || !Array.isArray(json.daily.time)) {
    throw upstream('Open-Meteo sem dados históricos para o período');
  }
  return json;
}

async function geocode(name) {
  const url =
    `https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(name)}` +
    `&count=5&language=pt&format=json&countryCode=BR`;
  const json = await withRetry(() => fetchJson(url));
  return (json && json.results) || [];
}

module.exports = { forecast, history, geocode };
