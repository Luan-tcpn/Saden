'use strict';

// Autorização administrativa real para a visão operacional.
// Definida por SADEN_ADMIN_EMAILS (lista separada por vírgula). Sem configuração,
// ninguém é admin — o padrão seguro é negar, não expor.

const { forbidden } = require('../utils/errors');

function adminEmails() {
  return String(process.env.SADEN_ADMIN_EMAILS || '')
    .split(',')
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean);
}

function isAdmin(user) {
  if (!user || !user.email) return false;
  const allowed = adminEmails();
  if (allowed.length === 0) return false;
  return allowed.includes(String(user.email).toLowerCase());
}

function requireAdmin(req, res, next) {
  if (!req.user) return next(forbidden('Autenticação necessária'));
  if (!isAdmin(req.user)) return next(forbidden('Acesso restrito ao operador'));
  return next();
}

module.exports = { isAdmin, requireAdmin, adminEmails };
