'use strict';

// Rate limit em memória (janela deslizante) para endpoints sensíveis.
// Suficiente para o escopo do SADEN (instância única); documentado em DECISIONS.
const hits = new Map(); // key -> timestamps[]

function rateLimit({ windowMs = 10 * 60 * 1000, max = 10 } = {}) {
  return (req, res, next) => {
    const key = `${req.ip}:${req.path}`;
    const now = Date.now();
    const arr = (hits.get(key) || []).filter((t) => now - t < windowMs);
    if (arr.length >= max) {
      return res.status(429).json({ error: 'Muitas tentativas. Aguarde alguns minutos.' });
    }
    arr.push(now);
    hits.set(key, arr);
    next();
  };
}

// Expõe limpeza para testes.
rateLimit._reset = () => hits.clear();

module.exports = rateLimit;
