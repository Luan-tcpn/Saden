'use strict';

// Catálogo de séries de preço com identidade estável (D1 do produto).
//
// A V1.1 tinha apenas `commodity_key`: "soja" não distingue contrato, fonte,
// moeda nem unidade. Um alerta preso a "soja" não sabe a que preço se refere.
// Aqui cada série tem um `series_id` explícito e imutável:
//
//   yahoo:<ticker>:<moeda>:<unidade>      ex.: yahoo:ZS=F:brl:sc60
//
// O identificador sobrevive a mudanças de nome comercial e impede comparar
// séries incompatíveis. NÃO existe série física brasileira (CEPEA/CONAB sem
// API pública — ver data_sources.status = 'blocked'): o catálogo só publica o
// que realmente entrega dado.

const { connect } = require('../db');
const { notFound } = require('../utils/errors');

// Frequência real da fonte: fechamentos diários em dias úteis (Yahoo).
// A tolerância é expressa em **dias corridos** e cobre fim de semana + feriado:
// uma cotação de sexta continua sendo a mais recente no domingo e na segunda.
// 4 dias = sexta → terça, sem gerar falso "atrasado". Configurável por ambiente.
const DEFAULT_STALE_AFTER_DAYS = 4;

function staleAfterDays() {
  const raw = Number(process.env.SADEN_STALE_AFTER_DAYS);
  return Number.isFinite(raw) && raw > 0 ? raw : DEFAULT_STALE_AFTER_DAYS;
}

// Política por série. Hoje todas são de fechamento diário; a estrutura permite
// frequências diferentes sem mexer na regra de avaliação.
const POLICY = {
  frequency: 'business_daily',
  expected_by: '18:00',
  timezone: 'America/Sao_Paulo',
  weekend_and_holiday_grace: true,
};

const MARKET_BY_TICKER = {
  'ZS=F': 'CBOT (CBoT/CME Group) — Chicago',
  'ZC=F': 'CBOT (CBoT/CME Group) — Chicago',
  'ZW=F': 'CBOT (CBoT/CME Group) — Chicago',
  'KC=F': 'ICE Futures U.S. — Nova York',
  'CT=F': 'ICE Futures U.S. — Nova York',
};

const UNIT_SLUG = {
  'R$/sc 60kg': 'sc60',
  'R$/saca 60kg': 'sc60',
  'R$/lp': 'lp',
  'R$/lb': 'lp',
};

function slugUnit(unit) {
  const key = String(unit || '').trim();
  if (UNIT_SLUG[key]) return UNIT_SLUG[key];
  return key.replace(/[^a-z0-9]+/gi, '').toLowerCase() || 'unit';
}

function seriesIdFor(commodity) {
  return `yahoo:${commodity.yahoo_symbol}:brl:${slugUnit(commodity.unit_br)}`;
}

function parseSeriesId(seriesId) {
  const parts = String(seriesId || '').split(':');
  if (parts.length !== 4 || parts[0] !== 'yahoo' || parts[2] !== 'brl') return null;
  return { provider: parts[0], ticker: parts[1], currency: parts[2], unitSlug: parts[3] };
}

function daysSince(dateIso, reference = Date.now()) {
  const then = new Date(`${dateIso}T12:00:00Z`).getTime();
  if (!Number.isFinite(then)) return null;
  return Math.floor((reference - then) / 86400000);
}

/**
 * Data da sessão mais recente que se poderia esperar (dia útil anterior ou hoje).
 * Limitação declarada: **feriado de mercado não é modelado**. O calendário aqui
 * é só fim de semana; feriado é absorvido pela tolerância (`stale_after_days`).
 */
function expectedSessionDate(now = new Date()) {
  const sp = new Date(now.toLocaleString('en-US', { timeZone: 'America/Sao_Paulo' }));
  const cursor = new Date(sp);
  // Se ainda não fechou o pregão de hoje, a sessão esperada é a anterior.
  const closesAt = 18;
  if (cursor.getHours() < closesAt) cursor.setDate(cursor.getDate() - 1);
  while (cursor.getDay() === 0 || cursor.getDay() === 6) cursor.setDate(cursor.getDate() - 1);
  const pad = (n) => String(n).padStart(2, '0');
  return `${cursor.getFullYear()}-${pad(cursor.getMonth() + 1)}-${pad(cursor.getDate())}`;
}

function isMarketDay(date = new Date()) {
  const sp = new Date(date.toLocaleString('en-US', { timeZone: 'America/Sao_Paulo' }));
  const day = sp.getDay();
  return day !== 0 && day !== 6;
}

/**
 * Estado de frescor. `status` continua binário em `fresh`/`stale` para não
 * quebrar consumidores antigos; `detail` explica o motivo (semana, pregão ainda
 * aberto, atraso real).
 */
function freshnessFor(observationDate, { now = new Date() } = {}) {
  const limit = staleAfterDays();
  const expected = expectedSessionDate(now);
  const marketDay = isMarketDay(now);

  if (!observationDate) {
    return {
      status: 'unknown',
      detail: 'sem_observacao',
      age_days: null,
      stale_after_days: limit,
      expected_session_date: expected,
      market_day: marketDay,
      policy: POLICY,
    };
  }

  const age = daysSince(observationDate, now.getTime());
  const stale = age == null || age > limit;

  // O detalhe nunca "melhora" um atraso real: stale sempre vence.
  let detail;
  if (stale) detail = 'atrasado';
  else if (age === 0) detail = 'atualizado';
  else if (!marketDay) detail = 'sem_pregao_esperado';
  else detail = 'aguardando_pregao';

  return {
    status: stale ? 'stale' : 'fresh',
    detail,
    age_days: age,
    stale_after_days: limit,
    expected_session_date: expected,
    market_day: marketDay,
    policy: POLICY,
  };
}

// Estado operacional da série (preenchido pelo worker): separa "sem cotação
// nova" de "fonte com erro". Sem isso, um alerta parece saudável com a fonte
// quebrada.
function stateFor(seriesId) {
  try {
    const row = connect().prepare('SELECT * FROM series_state WHERE series_id = ?').get(seriesId);
    if (!row) return null;
    return {
      last_attempt_at: row.last_attempt_at,
      last_success_at: row.last_success_at,
      last_error: row.last_error,
      last_error_at: row.last_error_at,
      consecutive_failures: row.consecutive_failures,
      last_observation_date: row.last_observation_date,
      last_price: row.last_price,
    };
  } catch {
    return null;
  }
}

// Estado legível para a interface. Combina frescor do dado + saúde da fonte.
// A ordem importa: erro de fonte prevalece sobre "sem pregão", porque uma fonte
// quebrada pode estar escondida atrás de um fim de semana.
function operationalStatus(series, state) {
  const freshness = freshnessFor(series.observation_date);
  if (freshness.status === 'unknown') {
    if (state && state.last_error) return { status: 'source_error', label: 'erro na fonte' };
    return { status: 'awaiting', label: 'aguardando nova observação' };
  }
  if (freshness.status === 'stale') {
    if (state && state.last_error) return { status: 'source_error', label: 'erro na fonte' };
    return { status: 'late', label: 'atrasado' };
  }
  if (state && state.last_error) return { status: 'source_error', label: 'erro na fonte' };
  if (freshness.detail === 'sem_pregao_esperado') {
    return { status: 'no_session', label: 'sem pregão esperado hoje' };
  }
  if (freshness.detail === 'aguardando_pregao') {
    return { status: 'awaiting_session', label: 'aguardando fechamento do pregão' };
  }
  return { status: 'updated', label: 'atualizado' };
}

function buildSeries(commodity, observation) {
  const observationDate = observation ? observation.data_date : null;
  const freshness = freshnessFor(observationDate);
  const seriesId = seriesIdFor(commodity);
  const state = stateFor(seriesId);
  const base = {
    series_id: seriesId,
    commodity_key: commodity.key,
    commodity_name: commodity.name,
    instrument: 'Contrato futuro (vencimento mais líquido)',
    market: MARKET_BY_TICKER[commodity.yahoo_symbol] || 'Mercado internacional',
    ticker: commodity.yahoo_symbol,
    source: 'yahoo + bcb-ptax',
    source_label: 'Yahoo Finance (futuro) convertido pela PTAX de venda (BCB)',
    price_type: 'referência internacional convertida',
    currency: 'BRL',
    unit: commodity.unit_br,
    location: 'Brasil (referência nacional)',
    frequency: 'diária (dias úteis)',
    expected_by: POLICY.expected_by,
    timezone: POLICY.timezone,
    observation_date: observationDate,
    last_price: observation ? observation.price_brl : null,
    last_updated_at: observation ? observation.retrieved_at : null,
    freshness_status: freshness.status,
    freshness_detail: freshness.detail,
    expected_session_date: freshness.expected_session_date,
    market_day: freshness.market_day,
    age_days: freshness.age_days,
    stale_after_days: freshness.stale_after_days,
    operational: operationalStatus({ observation_date: observationDate }, state),
    source_state: state,
    limitations: [
      'É referência internacional convertida, não o preço recebido pelo produtor brasileiro.',
      'Não inclui base local, prêmio portuário, frete nem custo de exportação.',
      'Fonte física regional (CEPEA/CONAB) não possui API pública: não há série municipal.',
    ],
  };
  return base;
}

function latestObservationFor(commodityKey) {
  return connect()
    .prepare(
      `SELECT commodity_key, data_date, price_brl, unit_br, provider, retrieved_at
         FROM price_observations
        WHERE commodity_key = ?
        ORDER BY data_date DESC, id DESC
        LIMIT 1`
    )
    .get(commodityKey);
}

function list() {
  const commodities = connect().prepare('SELECT * FROM commodities ORDER BY name').all();
  return commodities.map((c) => buildSeries(c, latestObservationFor(c.key)));
}

function get(seriesId) {
  const parsed = parseSeriesId(seriesId);
  if (!parsed) throw notFound(`Série "${seriesId}" não existe`);
  const commodity = connect()
    .prepare('SELECT * FROM commodities WHERE yahoo_symbol = ?')
    .get(parsed.ticker);
  if (!commodity) throw notFound(`Série "${seriesId}" não existe`);
  const series = buildSeries(commodity, latestObservationFor(commodity.key));
  if (series.series_id !== seriesId) throw notFound(`Série "${seriesId}" não existe`);
  return series;
}

function exists(seriesId) {
  try {
    get(seriesId);
    return true;
  } catch {
    return false;
  }
}

// Usado pela migração e pelo caminho legado (commodity_key → série única).
function seriesIdForCommodity(commodityKey) {
  const commodity = connect().prepare('SELECT * FROM commodities WHERE key = ?').get(commodityKey);
  return commodity ? seriesIdFor(commodity) : null;
}

module.exports = {
  staleAfterDays,
  get STALE_AFTER_DAYS() {
    return staleAfterDays();
  },
  POLICY,
  list,
  get,
  exists,
  seriesIdFor,
  seriesIdForCommodity,
  latestObservationFor,
  freshnessFor,
  expectedSessionDate,
  isMarketDay,
  stateFor,
  operationalStatus,
  slugUnit,
};
