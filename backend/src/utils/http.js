'use strict';

const config = require('../config');

// fetch com timeout + User-Agent identificável. Usado por todas as integrações.
async function fetchJson(url, { headers = {}, timeoutMs = config.httpTimeoutMs } = {}) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  const started = Date.now();
  try {
    const res = await fetch(url, {
      signal: ctrl.signal,
      headers: { 'User-Agent': config.yahooUA, Accept: 'application/json', ...headers },
    });
    if (!res.ok) {
      const err = new Error(`Fonte externa respondeu ${res.status} para ${shortUrl(url)}`);
      err.status = 502;
      err.upstreamStatus = res.status;
      throw err;
    }
    return await res.json();
  } catch (e) {
    if (e.name === 'AbortError') {
      const err = new Error(`Timeout (${timeoutMs}ms) ao consultar ${shortUrl(url)}`);
      err.status = 502;
      throw err;
    }
    if (!e.status) e.status = 502;
    throw e;
  } finally {
    clearTimeout(t);
    void started;
  }
}

function shortUrl(url) {
  try {
    const u = new URL(url);
    return `${u.host}${u.pathname}`;
  } catch {
    return 'fonte externa';
  }
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

// Retry simples com backoff para erros transitórios (502/429/timeout).
async function withRetry(fn, { attempts = 3, baseDelayMs = 600 } = {}) {
  let last;
  for (let i = 1; i <= attempts; i++) {
    try {
      return await fn(i);
    } catch (e) {
      last = e;
      const retryable = e.status === 502 || e.status === 429;
      if (!retryable || i === attempts) throw e;
      await sleep(baseDelayMs * i);
    }
  }
  throw last;
}

module.exports = { fetchJson, withRetry };
