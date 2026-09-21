'use strict';

// Erro operacional com status HTTP — nunca vaza detalhes internos.
class AppError extends Error {
  constructor(status, message, details) {
    super(message);
    this.status = status;
    this.details = details;
  }
}

function notFound(msg) {
  return new AppError(404, msg || 'Recurso não encontrado');
}

function badRequest(msg, details) {
  return new AppError(400, msg || 'Requisição inválida', details);
}

function unauthorized(msg) {
  return new AppError(401, msg || 'Não autenticado');
}

function upstream(msg, details) {
  return new AppError(502, msg || 'Fonte externa indisponível', details);
}

// eslint-disable-next-line no-unused-vars
function errorHandler(err, req, res, next) {
  const status = err && err.status ? err.status : 500;
  const payload = {
    error: status === 500 ? 'Erro interno do servidor' : err.message,
  };
  if (err && err.details && status !== 500) payload.details = err.details;
  // Log útil, sem segredos.
  // eslint-disable-next-line no-console
  console.error(
    JSON.stringify({
      level: 'error',
      method: req.method,
      path: req.originalUrl,
      status,
      message: err && err.message,
    })
  );
  res.status(status).json(payload);
}

module.exports = { AppError, notFound, badRequest, unauthorized, upstream, errorHandler };
