'use strict';

// Heartbeat para monitoramento externo (Release 1.2.1).
//
// Protocolo: o worker avisa um serviço externo (Healthchecks.io e compatíveis)
// quando começa, quando termina bem e quando falha. Se o processo morrer no
// meio, o serviço **não recebe** o sinal final e dispara o alerta por ausência.
// É isso que transforma "detectar internamente" em "avisar alguém".
//
// Regras de segurança e robustez:
// - desabilitado quando SADEN_MONITOR_PING_URL está vazia;
// - nunca lança: falha do monitor não pode afetar a avaliação de preços;
// - timeout curto e sem retry (o próximo ciclo já manda novo sinal);
// - a URL é segredo (contém o token): nunca é logada, só o host.

const config = require('./config');

// Healthchecks.io: base = .../<uuid>; sufixos /start e /fail são opcionais.
const SUFFIX = { start: '/start', success: '', fail: '/fail' };
const EVENTS = Object.keys(SUFFIX);

function pingUrl() {
  return String(process.env.SADEN_MONITOR_PING_URL || '').trim();
}

function enabled() {
  return pingUrl().length > 0;
}

/** Remove caminho e query: o token do monitor fica no caminho. */
function redact(target) {
  try {
    const parsed = new URL(target);
    return `${parsed.protocol}//${parsed.host}/…`;
  } catch {
    return '<url-invalida>';
  }
}

function endpoint(event, base = pingUrl()) {
  if (!base) return null;
  if (!EVENTS.includes(event)) throw new Error(`evento de monitor desconhecido: ${event}`);
  return `${base.replace(/\/+$/, '')}${SUFFIX[event]}`;
}

/**
 * Envia o sinal. Nunca lança.
 * @returns {{status:'disabled'|'ok'|'error', code:number|null, reason:string|null}}
 */
async function ping(event, { timeoutMs = config.monitorTimeoutMs, base } = {}) {
  const target = endpoint(event, base === undefined ? pingUrl() : base);
  if (!target) return { status: 'disabled', code: null, reason: null };
  try {
    const response = await fetch(target, {
      method: 'GET',
      signal: AbortSignal.timeout(timeoutMs),
      headers: { 'User-Agent': 'saden-worker/1.2.1' },
      redirect: 'follow',
    });
    if (!response.ok) {
      return { status: 'error', code: response.status, reason: 'http_error' };
    }
    return { status: 'ok', code: response.status, reason: null };
  } catch (error) {
    const name = (error && error.name) || '';
    const reason = name === 'TimeoutError' || name === 'AbortError' ? 'timeout' : 'network_error';
    return { status: 'error', code: null, reason };
  }
}

/** Resumo para log: sem URL, sem token. */
function describe(result) {
  if (!result || result.status === 'disabled') return null;
  return { monitor: result.status, code: result.code, reason: result.reason };
}

module.exports = { enabled, ping, endpoint, redact, describe, EVENTS, SUFFIX, pingUrl };
