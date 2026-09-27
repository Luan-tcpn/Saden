'use strict';

// AR(p)+AIC — challenger da Ridge (E3, decisão D37).
//
// NÃO é ARIMA (sem termos MA, sem diferenciação explícita, sem sazonalidade).
// Espelha o protocolo da Ridge em forecastService.js SEM alterá-lo:
// mesma série (Yahoo×PTAX via priceService), mesmo WARMUP=30, mesmo split
// temporal 70/15/15 sem shuffle, mesmas métricas one-step, mesma regra de
// previsão recursiva (cada passo alimenta o próximo, só com passado).
// Seleção de p (1..8) por AIC SOMENTE no treino; teste só para relato.
// Módulo de avaliação: run() NÃO persiste em model_runs (persistência do
// challenger = decisão futura, D38). Erros honestos com status HTTP.
const priceService = require('./priceService');
const forecast = require('./forecastService');
const { olsBeta } = require('../utils/linalg');

const MIN_POINTS = 60; // espelho da Ridge: mesmo gate de série mínima
const WARMUP = 30; // espelho: mesmos índices-alvo de treino/val/teste
const P_MAX = 8; // conforme investigação E2
const H_ALLOWED = [7, 14, 30];

function httpError(status, message) {
  return Object.assign(new Error(message), { status });
}

function assertFinite(values) {
  for (const v of values) {
    if (!Number.isFinite(v)) throw httpError(400, 'Série contém valor não finito');
  }
}

// Ajusta AR(p) com intercepto sobre `history` (valores até a origem, inclusive).
// Lança em matriz singular para que o chamador aplique o fallback documentado.
function fitAR(history, p) {
  if (!Number.isInteger(p) || p < 1) throw httpError(400, `Ordem AR inválida: ${p}`);
  if (history.length <= p) {
    throw httpError(422, `Histórico curto para AR(${p}): ${history.length} pontos`);
  }
  const Y = history.slice(p);
  const X = Y.map((_, i) => [1, ...Array.from({ length: p }, (_, k) => history[i + p - 1 - k])]);
  return { p, beta: olsBeta(X, Y) };
}

function sseOf(beta, history, p) {
  let sse = 0;
  for (let t = p; t < history.length; t++) {
    let pred = beta[0];
    for (let k = 1; k <= p; k++) pred += beta[k] * history[t - k];
    const e = history[t] - pred;
    sse += e * e;
  }
  return sse;
}

// Seleção de ordem por AIC somente no treino. Fallback documentado:
// ordens singulares são ignoradas (tenta as demais); se nenhuma ajustar
// (ex.: série constante), erro 422 honesto em vez de número inventado.
function selectOrder(trainHistory) {
  assertFinite(trainHistory);
  let best = null;
  for (let p = 1; p <= P_MAX; p++) {
    if (trainHistory.length <= p + 1) continue;
    let beta;
    try {
      beta = fitAR(trainHistory, p).beta;
    } catch {
      continue; // singular: tenta outra ordem
    }
    if (!beta.every(Number.isFinite)) continue;
    const n = trainHistory.length - p;
    const sse = sseOf(beta, trainHistory, p);
    if (!(sse > 0)) continue;
    const aic = n * Math.log(sse / n) + 2 * (p + 1);
    if (best === null || aic < best.aic) best = { p, beta, aic };
  }
  if (best === null) {
    throw httpError(422, 'AR(p): série sem variação suficiente para ajuste (todas as ordens singulares)');
  }
  return best;
}

function predictOneStep(beta, p, history) {
  // history: valores até a origem (inclusive); usa só os últimos p.
  if (history.length < p) throw httpError(422, `Histórico curto para AR(${p}) one-step`);
  let s = beta[0];
  for (let k = 1; k <= p; k++) {
    const v = history[history.length - k];
    if (!Number.isFinite(v)) throw httpError(400, 'Histórico com valor não finito');
    s += beta[k] * v;
  }
  if (!Number.isFinite(s)) throw httpError(422, 'AR(p) produziu valor não finito (one-step)');
  return s;
}

function predictRecursive(beta, p, history, steps) {
  // Prova de não-vazamento: só lê `history` (passado até a origem) e as
  // próprias previsões anteriores. Valores futuros observados NUNCA entram:
  // o chamador passa apenas o prefixo até a origem (ver teste de leakage).
  if (!Number.isInteger(steps) || steps < 1) throw httpError(400, `Horizonte inválido: ${steps}`);
  const ext = [...history];
  const out = [];
  for (let h = 0; h < steps; h++) {
    const pred = predictOneStep(beta, p, ext);
    out.push(pred);
    ext.push(pred);
  }
  return out;
}

// Skill recursiva honesta: modelo CONGELADO do treino, origens no segmento de
// teste com H observações futuras disponíveis, sem refit por origem.
function recursiveSkill(beta, p, values, testStartIdx, horizons) {
  const out = {};
  for (const H of horizons) {
    const actualAll = [];
    const predAll = [];
    let origins = 0;
    for (let i = testStartIdx; i + H < values.length; i++) {
      const preds = predictRecursive(beta, p, values.slice(0, i + 1), H);
      for (let h = 0; h < H; h++) {
        predAll.push(preds[h]);
        actualAll.push(values[i + 1 + h]);
      }
      origins++;
    }
    out[`h${H}`] =
      origins === 0
        ? { n: 0, origins: 0, note: 'sem origens com futuro completo no teste' }
        : { origins, ...forecast._test.metrics(actualAll, predAll) };
  }
  return out;
}

function evaluate(values, dates, horizonDays) {
  assertFinite(values);
  const H = H_ALLOWED.includes(Number(horizonDays)) ? Number(horizonDays) : 14;
  if (values.length < MIN_POINTS) {
    throw httpError(422, `Série insuficiente para modelagem (${values.length} pontos, mínimo ${MIN_POINTS})`);
  }
  // Mesmo split da Ridge: linhas [WARMUP, n-2] -> mesmos alvos 70/15/15.
  const nRows = values.length - 1 - WARMUP;
  const nTrain = Math.floor(nRows * 0.7);
  const nVal = Math.floor(nRows * 0.15);
  if (nTrain < 20 || nVal < 5 || nRows - nTrain - nVal < 5) {
    throw httpError(422, 'Série curta demais para split temporal 70/15/15');
  }
  const t0 = WARMUP + 1; // índice em `values` do 1º alvo
  const ytr = values.slice(t0, t0 + nTrain);
  const yva = values.slice(t0 + nTrain, t0 + nTrain + nVal);
  const yte = values.slice(t0 + nTrain + nVal);

  const trainHistory = values.slice(0, t0 + nTrain);
  const { p, beta } = selectOrder(trainHistory);

  const M = forecast._test.metrics;
  const pv = yva.map((_, k) => predictOneStep(beta, p, values.slice(0, t0 + nTrain + k)));
  const ptr = ytr.map((_, k) => predictOneStep(beta, p, values.slice(0, t0 + k)));
  const pte = yte.map((_, k) => predictOneStep(beta, p, values.slice(0, t0 + nTrain + nVal + k)));

  // Baselines idênticos aos da Ridge, no mesmo segmento de validação.
  const valStartIdx = WARMUP + nTrain;
  const baseResults = {};
  for (const kind of ['naive', 'seasonal_naive_5', 'ma7']) {
    const preds = yva.map((_, k) => forecast._test.baselinePredict(kind, values, valStartIdx + k - 1, 1)[0]);
    baseResults[kind] = { metrics: M(yva, preds) };
  }
  const mVal = M(yva, pv);
  const winner =
    mVal.rmse < Math.min(baseResults.naive.metrics.rmse, baseResults.seasonal_naive_5.metrics.rmse, baseResults.ma7.metrics.rmse)
      ? 'ar'
      : 'baseline';

  // Intervalo: MESMA metodologia da Ridge (±1,96·σ dos resíduos de validação,
  // alargado com sqrt(h)) — coerente porque o AR também é preditor pontual.
  const resid = yva.map((y, k) => y - pv[k]);
  const sigma = Math.sqrt(resid.reduce((a, e) => a + e * e, 0) / resid.length);

  const operational = predictRecursive(beta, p, values, H);
  const futureDates = forecast._test.nextBusinessDates(dates[dates.length - 1], H);
  const lastPrice = values[values.length - 1];
  const forecastPts = operational.map((f, h) => {
    const w = 1.96 * sigma * Math.sqrt(h + 1);
    return { date: futureDates[h], price_brl: r2(f), lower_brl: Math.max(0, r2(f - w)), upper_brl: r2(f + w) };
  });

  return {
    commodity: null, // preenchido por run()
    unit: null,
    model: 'ar',
    model_selected: winner,
    ar_order: p,
    horizon_days: H,
    data_start: dates[0],
    data_end: dates[dates.length - 1],
    n_points: values.length,
    current_price_brl: r2(lastPrice),
    trend:
      operational[H - 1] > lastPrice * 1.01 ? 'alta' : operational[H - 1] < lastPrice * 0.99 ? 'baixa' : 'estável',
    baselines: {
      naive: baseResults.naive.metrics,
      seasonal_naive_5: baseResults.seasonal_naive_5.metrics,
      ma7: baseResults.ma7.metrics,
    },
    metrics: { train: M(ytr, ptr), val: mVal, test: M(yte, pte) },
    recursive_eval: recursiveSkill(beta, p, values, t0 + nTrain + nVal, H_ALLOWED),
    interval_sigma: round4(sigma),
    history_tail: dates.slice(-60).map((d, k) => ({ date: d, price_brl: r2(values.slice(-60)[k]) })),
    forecast: forecastPts,
    limitations: [
      'Previsão sobre referência internacional convertida (Yahoo Finance + PTAX), não sobre preço físico regional.',
      'Modelo univariado: usa apenas o histórico de preços; clima e câmbio entram como contexto, não como features.',
      'Datas futuras em dias corridos; pregões reais variam com feriados.',
      'Intervalo assume resíduos gaussianos — em choques de mercado o erro real pode exceder a faixa.',
      'Challenger AR(p): ordem selecionada por AIC no treino; skill recursiva em `recursive_eval` (origens no teste, modelo congelado). Não é ARIMA: sem termos MA, sem diferenciação explícita, sem sazonalidade.',
    ],
    retrieved_at: new Date().toISOString(),
  };
}

function r2(n) {
  return Math.round(n * 100) / 100;
}
function round4(n) {
  return Math.round(n * 10000) / 10000;
}

async function run(commodityKey, horizonDays = 14) {
  const series = await priceService.getSeries(commodityKey, '1y');
  const { dates, values } = forecast._test.clean(series.points);
  const payload = evaluate(values, dates, horizonDays);
  payload.commodity = series.commodity;
  payload.unit = series.unit;
  return payload;
}

module.exports = {
  run,
  evaluate,
  fitAR,
  selectOrder,
  predictOneStep,
  predictRecursive,
  recursiveSkill,
  MIN_POINTS,
  WARMUP,
  P_MAX,
};
