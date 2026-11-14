'use strict';

// Agenda do worker: quando a próxima verificação deve acontecer.
//
// Regras (todas testáveis, sem timers reais):
// - dia útil (seg–sex) no fuso operacional America/Sao_Paulo;
// - horário preferencial após o fechamento do mercado e da PTAX;
// - fim de semana não gera execução (mercado fechado, não é falha);
// - feriado de mercado não é modelado: a tolerância de frescor cobre o caso.

const TIMEZONE = 'America/Sao_Paulo';

// Partes de data/hora locais para um instante, sem depender do TZ do host.
function localParts(date, timezone = TIMEZONE) {
  const formatter = new Intl.DateTimeFormat('en-CA', {
    timeZone: timezone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
    weekday: 'short',
  });
  const parts = Object.fromEntries(formatter.formatToParts(date).map((p) => [p.type, p.value]));
  return {
    year: Number(parts.year),
    month: Number(parts.month),
    day: Number(parts.day),
    hour: Number(parts.hour === '24' ? '0' : parts.hour),
    minute: Number(parts.minute),
    second: Number(parts.second),
    weekday: parts.weekday, // Mon, Tue, ...
  };
}

// Offset (ms) entre o fuso local e UTC no instante dado — trata DST quando existir.
function zoneOffsetMs(date, timezone = TIMEZONE) {
  const parts = localParts(date, timezone);
  const asUtc = Date.UTC(parts.year, parts.month - 1, parts.day, parts.hour, parts.minute, parts.second);
  return asUtc - date.getTime();
}

/** Constrói um instante a partir de data/hora **locais**. */
function fromLocal(year, month, day, hour, minute = 0, timezone = TIMEZONE) {
  const guess = Date.UTC(year, month - 1, day, hour, minute, 0);
  let candidate = new Date(guess);
  // Duas passadas bastam para acertar o offset mesmo em mudança de horário.
  for (let i = 0; i < 2; i++) {
    const offset = zoneOffsetMs(candidate, timezone);
    candidate = new Date(guess - offset);
  }
  return candidate;
}

function isWeekend(date, timezone = TIMEZONE) {
  const { weekday } = localParts(date, timezone);
  return weekday === 'Sat' || weekday === 'Sun';
}

/** Dia de mercado (seg–sex). Feriados exigem calendário externo e não são modelados. */
function isMarketDay(date, timezone = TIMEZONE) {
  return !isWeekend(date, timezone);
}

/**
 * Próxima execução a partir de `from`.
 * Se ainda for dia útil antes do horário preferencial, executa hoje; senão, no
 * próximo dia útil no mesmo horário.
 */
function nextRun(from = new Date(), { preferredHourLocal = 18, timezone = TIMEZONE } = {}) {
  const parts = localParts(from, timezone);
  const todayTarget = fromLocal(parts.year, parts.month, parts.day, preferredHourLocal, 0, timezone);
  if (isMarketDay(from, timezone) && from < todayTarget) return todayTarget;

  const cursor = new Date(from.getTime());
  for (let i = 1; i <= 8; i++) {
    cursor.setUTCDate(cursor.getUTCDate() + 1);
    const next = localParts(cursor, timezone);
    if (isWeekend(cursor, timezone)) continue;
    const target = fromLocal(next.year, next.month, next.day, preferredHourLocal, 0, timezone);
    if (target > from) return target;
  }
  // Fallback improvável (8 dias sem dia útil).
  return new Date(from.getTime() + 24 * 3600 * 1000);
}

module.exports = {
  TIMEZONE,
  localParts,
  zoneOffsetMs,
  fromLocal,
  isWeekend,
  isMarketDay,
  nextRun,
};
