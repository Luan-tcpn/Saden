'use strict';

const { badRequest } = require('./errors');

function isEmail(v) {
  return typeof v === 'string' && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v.trim());
}

function requireString(v, name, { min = 1, max = 255 } = {}) {
  if (typeof v !== 'string' || v.trim().length < min || v.length > max) {
    throw badRequest(`Campo "${name}" inválido`);
  }
  return v.trim();
}

function requireNumber(v, name, { min = -1e12, max = 1e12 } = {}) {
  const n = Number(v);
  if (!Number.isFinite(n) || n < min || n > max) throw badRequest(`Campo "${name}" inválido`);
  return n;
}

function optionalDate(v, name) {
  if (v === undefined || v === null || v === '') return undefined;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(String(v))) throw badRequest(`Campo "${name}" deve usar AAAA-MM-DD`);
  const d = new Date(`${v}T12:00:00Z`);
  if (Number.isNaN(d.getTime())) throw badRequest(`Campo "${name}" inválido`);
  return String(v);
}

module.exports = { isEmail, requireString, requireNumber, optionalDate };
