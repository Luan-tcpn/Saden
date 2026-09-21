'use strict';

const path = require('path');
require('dotenv').config({ path: path.join(__dirname, '..', '..', '.env') });

function num(name, fallback) {
  const v = Number(process.env[name]);
  return Number.isFinite(v) ? v : fallback;
}

// Produção nunca inicializa silenciosamente com segredo público de exemplo.
if (process.env.NODE_ENV === 'production' && !process.env.JWT_SECRET) {
  throw new Error('JWT_SECRET ausente: defina um segredo forte no .env antes de iniciar em produção');
}

// Raiz do projeto (independe do cwd de quem iniciou o processo).
const ROOT = path.join(__dirname, '..', '..');

function resolveDbPath() {
  const raw = process.env.DATABASE_PATH || 'data/saden.db';
  return path.isAbsolute(raw) ? raw : path.join(ROOT, raw);
}

module.exports = {
  port: num('PORT', 3001),
  jwtSecret: process.env.JWT_SECRET || 'dev-secret-troque-em-producao',
  jwtExpiresIn: process.env.JWT_EXPIRES_IN || '12h',
  databasePath: resolveDbPath(),
  frontendOrigin: process.env.FRONTEND_ORIGIN || 'http://localhost:3001',
  yahooUA: process.env.YAHOO_UA || 'SADEN-TCC/0.1 (contato-academico)',
  httpTimeoutMs: num('HTTP_TIMEOUT_MS', 12000),
  cachePricesTtlMin: num('CACHE_PRICES_TTL_MIN', 60),
  cacheWeatherTtlMin: num('CACHE_WEATHER_TTL_MIN', 60),
  cacheGeoTtlDays: num('CACHE_GEO_TTL_DAYS', 30),
  isProd: process.env.NODE_ENV === 'production',
};
