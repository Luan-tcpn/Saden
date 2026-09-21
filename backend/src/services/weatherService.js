'use strict';

const { connect, cacheGet, cacheSet } = require('../db');
const config = require('../config');
const openmeteo = require('../integrations/openmeteoProvider');
const { requireNumber, optionalDate } = require('../utils/validate');

function coords(lat, lon) {
  const la = requireNumber(lat, 'latitude', { min: -34, max: 6 });
  const lo = requireNumber(lon, 'longitude', { min: -75, max: -32 });
  return { lat: la, lon: lo };
}

function toDaily(json) {
  const d = json.daily;
  return d.time.map((t, i) => ({
    date: t,
    t_max: d.temperature_2m_max ? d.temperature_2m_max[i] : null,
    t_min: d.temperature_2m_min ? d.temperature_2m_min[i] : null,
    t_mean: d.temperature_2m_mean ? d.temperature_2m_mean[i] : null,
    precipitation: d.precipitation_sum ? d.precipitation_sum[i] : null,
    humidity: d.relative_humidity_2m_mean ? d.relative_humidity_2m_mean[i] : null,
    wind_max: d.wind_speed_10m_max ? d.wind_speed_10m_max[i] : null,
    weather_code: d.weather_code ? d.weather_code[i] : null,
  }));
}

async function getForecast(lat, lon) {
  const { lat: la, lon: lo } = coords(lat, lon);
  const key = `wx:fc:${la.toFixed(3)},${lo.toFixed(3)}`;
  const cached = cacheGet(key);
  if (cached) return { ...cached, cached: true };
  const json = await openmeteo.forecast(la, lo);
  const payload = {
    cached: false,
    latitude: json.latitude,
    longitude: json.longitude,
    timezone: json.timezone,
    provider: 'open-meteo',
    retrieved_at: new Date().toISOString(),
    current: json.current,
    daily: toDaily(json),
  };
  cacheSet(key, payload, config.cacheWeatherTtlMin * 60 * 1000);
  return payload;
}

async function getHistory(lat, lon, start, end) {
  const { lat: la, lon: lo } = coords(lat, lon);
  const s = optionalDate(start, 'start') || defaultStart();
  const e = optionalDate(end, 'end') || todayIso();
  if (s > e) throw Object.assign(new Error('"start" posterior a "end"'), { status: 400 });
  const key = `wx:hist:${la.toFixed(3)},${lo.toFixed(3)}:${s}:${e}`;
  const cached = cacheGet(key);
  if (cached) return { ...cached, cached: true };
  const json = await openmeteo.history(la, lo, s, e);
  persistWeather(la, lo, toDaily(json));
  const payload = {
    cached: false,
    latitude: json.latitude,
    longitude: json.longitude,
    timezone: json.timezone,
    provider: 'open-meteo',
    start: s,
    end: e,
    retrieved_at: new Date().toISOString(),
    daily: toDaily(json),
  };
  cacheSet(key, payload, config.cacheWeatherTtlMin * 60 * 1000);
  return payload;
}

function persistWeather(lat, lon, daily) {
  const stmt = connect().prepare(
    `INSERT OR REPLACE INTO weather_observations
     (latitude, longitude, data_date, t_mean, t_max, t_min, precipitation, humidity, wind, provider)
     VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, 'open-meteo')`
  );
  const tx = connect().transaction((rows) => {
    for (const r of rows) {
      stmt.run(lat, lon, r.date, r.t_mean, r.t_max, r.t_min, r.precipitation, r.humidity, r.wind_max);
    }
  });
  tx(daily);
}

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

function defaultStart() {
  const d = new Date();
  d.setDate(d.getDate() - 90);
  return d.toISOString().slice(0, 10);
}

module.exports = { getForecast, getHistory };
