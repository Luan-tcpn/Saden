'use strict';

const jwt = require('jsonwebtoken');
const config = require('../config');
const { unauthorized } = require('../utils/errors');

function signToken(user) {
  return jwt.sign({ sub: user.id, email: user.email }, config.jwtSecret, {
    expiresIn: config.jwtExpiresIn,
  });
}

// Rotas protegidas: Authorization: Bearer <token>
function requireAuth(req, res, next) {
  const header = req.headers.authorization || '';
  const [scheme, token] = header.split(' ');
  if (scheme !== 'Bearer' || !token) return next(unauthorized('Token ausente. Faça login.'));
  try {
    const payload = jwt.verify(token, config.jwtSecret);
    req.user = { id: payload.sub, email: payload.email };
    return next();
  } catch {
    return next(unauthorized('Sessão inválida ou expirada. Faça login novamente.'));
  }
}

module.exports = { signToken, requireAuth };
