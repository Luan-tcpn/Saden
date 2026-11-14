'use strict';

// Rate limit em memória (janela deslizante) para endpoints sensíveis.
// Suficiente para o escopo do SADEN (instância única); documentado em DECISIONS.
//
// `key` permite limitar por usuário autenticado em vez de IP — necessário nos
// endpoints de alerta, onde o custo é por conta (e pode gerar chamada externa).
// O limite é um controle de abuso do usuário; o worker tem controle próprio de
// frequência junto aos provedores (não passa por aqui).
const hits = new Map(); // key -> timestamps[]

function rateLimit({ windowMs = 10 * 60 * 1000, max = 10, key } = {}) {
  const keyOf = key || ((req) => `${req.ip}:${req.path}`);
  return (req, res, next) => {
    const bucket = keyOf(req);
    const now = Date.now();
    const arr = (hits.get(bucket) || []).filter((t) => now - t < windowMs);
    if (arr.length >= max) {
      res.setHeader('Retry-After', String(Math.ceil(windowMs / 1000)));
      return res.status(429).json({ error: 'Muitas solicitações. Aguarde alguns minutos.' });
    }
    arr.push(now);
    hits.set(bucket, arr);
    next();
  };
}

// Expõe limpeza para testes.
rateLimit._reset = () => hits.clear();

module.exports = rateLimit;
