'use strict';

// Pipeline quantitativo de previsão (sem LLM, sem valores inventados):
// dados -> validação/limpeza -> features -> split temporal 70/15/15 ->
// baselines (naive, seasonal-naive-5, MM7) -> ridge regression ->
// seleção por RMSE de validação -> avaliação em teste -> previsão recursiva
// com intervalo (±1,96·σ dos resíduos de validação, alargado com o horizonte).
const { connect } = require('../db');
const priceService = require('./priceService');
const { solve } = require('../utils/linalg');

const MIN_POINTS = 60;
const WARMUP = 30; // janela mínima para features estáveis

function clean(points) {
  const sorted = [...points].sort((a, b) => (a.date < b.date ? -1 : 1));
  const seen = new Map();
  for (const p of sorted) {
    if (Number.isFinite(p.price_brl) && p.price_brl > 0) seen.set(p.date, p.price_brl);
  }
  const dates = [...seen.keys()].sort();
  return { dates, values: dates.map((d) => seen.get(d)) };
}

function featuresFor(values, i) {
  // features calculadas SOMENTE com dados até o índice i (sem vazamento).
  const lag = (k) => values[i - k];
  const mm = (k) => {
    let s = 0;
    for (let j = i - k + 1; j <= i; j++) s += values[j];
    return s / k;
  };
  let vol = 0;
  if (i >= 14) {
    const rets = [];
    for (let j = i - 13; j <= i; j++) rets.push(Math.log(values[j] / values[j - 1]));
    const m = rets.reduce((a, b) => a + b, 0) / rets.length;
    vol = Math.sqrt(rets.reduce((a, b) => a + (b - m) ** 2, 0) / rets.length);
  }
  return [lag(1), lag(2), lag(5), mm(7), mm(30), vol, i];
}

// Linhas de treino: { x: [...], y: values[i+1] } para i em [WARMUP, n-2].
function buildRows(values) {
  const rows = [];
  for (let i = WARMUP; i < values.length - 1; i++) {
    rows.push({ x: featuresFor(values, i), y: values[i + 1] });
  }
  return rows;
}

function splitRows(rows) {
  const n = rows.length;
  const nTrain = Math.floor(n * 0.7);
  const nVal = Math.floor(n * 0.15);
  return {
    train: rows.slice(0, nTrain),
    val: rows.slice(nTrain, nTrain + nVal),
    test: rows.slice(nTrain + nVal),
  };
}

// ---- Ridge regression (implementação própria, sem dependências) ----
function standardize(X) {
  const p = X[0].length;
  const mean = new Array(p).fill(0);
  const sd = new Array(p).fill(0);
  for (const row of X) for (let j = 0; j < p; j++) mean[j] += row[j];
  for (let j = 0; j < p; j++) mean[j] /= X.length;
  for (const row of X) for (let j = 0; j < p; j++) sd[j] += (row[j] - mean[j]) ** 2;
  for (let j = 0; j < p; j++) {
    sd[j] = Math.sqrt(sd[j] / X.length) || 1;
  }
  const Xs = X.map((row) => row.map((v, j) => (v - mean[j]) / sd[j]));
  return { Xs, mean, sd };
}

function fitRidge(X, y, lambda) {
  const { Xs, mean, sd } = standardize(X);
  const n = Xs.length;
  const p = Xs[0].length;
  const Xd = Xs.map((row) => [1, ...row]); // intercepto
  const d = p + 1;
  const XtX = Array.from({ length: d }, () => new Array(d).fill(0));
  const Xty = new Array(d).fill(0);
  for (let i = 0; i < n; i++) {
    for (let a = 0; a < d; a++) {
      Xty[a] += Xd[i][a] * y[i];
      for (let b = 0; b < d; b++) XtX[a][b] += Xd[i][a] * Xd[i][b];
    }
  }
  for (let j = 1; j < d; j++) XtX[j][j] += lambda; // sem penalizar intercepto
  const beta = solve(XtX, Xty);
  return {
    beta,
    mean,
    sd,
    predict(x) {
      const xs = x.map((v, j) => (v - mean[j]) / sd[j]);
      let s = beta[0];
      for (let j = 0; j < p; j++) s += beta[j + 1] * xs[j];
      return s;
    },
  };
}

// ---- Métricas ----
function metrics(actual, predicted) {
  const n = actual.length;
  let ae = 0;
  let se = 0;
  let ape = 0;
  for (let i = 0; i < n; i++) {
    const e = actual[i] - predicted[i];
    ae += Math.abs(e);
    se += e * e;
    ape += Math.abs(e / actual[i]);
  }
  return {
    n,
    mae: r4(ae / n),
    rmse: r4(Math.sqrt(se / n)),
    mape_pct: r4((ape / n) * 100),
  };
}

function baselinePredict(kind, values, fromIdx, steps) {
  // Previsão constante ingênua a partir do histórico até fromIdx.
  const out = [];
  for (let h = 0; h < steps; h++) {
    if (kind === 'naive') out.push(values[fromIdx]);
    else if (kind === 'seasonal_naive_5') out.push(values[fromIdx - 4] ?? values[fromIdx]);
    else if (kind === 'ma7') {
      let s = 0;
      for (let j = fromIdx - 6; j <= fromIdx; j++) s += values[j];
      out.push(s / 7);
    }
  }
  return out;
}

function r4(n) {
  return Math.round(n * 10000) / 10000;
}
function r2(n) {
  return Math.round(n * 100) / 100;
}

function nextBusinessDates(lastDateIso, h) {
  // Datas futuras em dias corridos (rótulo honesto: pregões futuros aproximados).
  const out = [];
  const d = new Date(`${lastDateIso}T12:00:00Z`);
  for (let i = 1; i <= h; i++) {
    const nd = new Date(d);
    nd.setUTCDate(nd.getUTCDate() + i);
    out.push(nd.toISOString().slice(0, 10));
  }
  return out;
}

async function run(commodityKey, horizonDays = 14) {
  const H = [7, 14, 30].includes(Number(horizonDays)) ? Number(horizonDays) : 14;
  const series = await priceService.getSeries(commodityKey, '1y');
  const { dates, values } = clean(series.points);
  if (values.length < MIN_POINTS) {
    throw Object.assign(
      new Error(`Série insuficiente para modelagem (${values.length} pontos, mínimo ${MIN_POINTS})`),
      { status: 422 }
    );
  }

  const rows = buildRows(values);
  const { train, val, test } = splitRows(rows);
  if (train.length < 20 || val.length < 5 || test.length < 5) {
    throw Object.assign(new Error('Série curta demais para split temporal 70/15/15'), { status: 422 });
  }

  const Xtr = train.map((r) => r.x);
  const ytr = train.map((r) => r.y);
  const Xva = val.map((r) => r.x);
  const yva = val.map((r) => r.y);
  const Xte = test.map((r) => r.x);
  const yte = test.map((r) => r.y);

  // Baselines avaliados no segmento de validação (one-step-ahead).
  const valStartIdx = WARMUP + train.length; // índice em `values` do 1º alvo de val
  const baseResults = {};
  for (const kind of ['naive', 'seasonal_naive_5', 'ma7']) {
    const preds = yva.map((_, k) => baselinePredict(kind, values, valStartIdx + k - 1, 1)[0]);
    baseResults[kind] = { metrics: metrics(yva, preds) };
  }

  // Ridge: grade de lambda, seleção pelo RMSE de validação.
  let best = null;
  for (const lambda of [0.1, 1, 10, 100]) {
    const model = fitRidge(Xtr, ytr, lambda);
    const pv = Xva.map((x) => model.predict(x));
    const m = metrics(yva, pv);
    if (!best || m.rmse < best.metrics.rmse) best = { lambda, model, metrics: m, predsVal: pv };
  }

  const ptr = Xtr.map((x) => best.model.predict(x));
  const pte = Xte.map((x) => best.model.predict(x));
  const mTrain = metrics(ytr, ptr);
  const mTest = metrics(yte, pte);
  const winner =
    best.metrics.rmse < Math.min(baseResults.naive.metrics.rmse, baseResults.seasonal_naive_5.metrics.rmse, baseResults.ma7.metrics.rmse)
      ? 'ridge'
      : 'baseline';

  // Previsão recursiva H passos à frente.
  const extended = [...values];
  const pointForecast = [];
  for (let h = 0; h < H; h++) {
    const i = extended.length - 1;
    const x = featuresFor(extended, i);
    const yhat = best.model.predict(x);
    extended.push(yhat);
    pointForecast.push(yhat);
  }
  // Intervalo: σ dos resíduos de validação, alargado com sqrt(h).
  const resid = yva.map((y, k) => y - best.predsVal[k]);
  const sigma = Math.sqrt(resid.reduce((a, e) => a + e * e, 0) / resid.length);
  const futureDates = nextBusinessDates(dates[dates.length - 1], H);
  const forecast = pointForecast.map((p, h) => {
    const w = 1.96 * sigma * Math.sqrt(h + 1);
    // Preço não pode ser negativo: trunca o limite inferior em zero.
    return { date: futureDates[h], price_brl: r2(p), lower_brl: Math.max(0, r2(p - w)), upper_brl: r2(p + w) };
  });

  const lastPrice = values[values.length - 1];
  const trend =
    pointForecast[H - 1] > lastPrice * 1.01 ? 'alta' : pointForecast[H - 1] < lastPrice * 0.99 ? 'baixa' : 'estável';

  const payload = {
    commodity: series.commodity,
    unit: series.unit,
    model: 'ridge',
    model_selected: winner,
    lambda: best.lambda,
    horizon_days: H,
    data_start: dates[0],
    data_end: dates[dates.length - 1],
    n_points: values.length,
    current_price_brl: r2(lastPrice),
    trend,
    baselines: {
      naive: baseResults.naive.metrics,
      seasonal_naive_5: baseResults.seasonal_naive_5.metrics,
      ma7: baseResults.ma7.metrics,
    },
    metrics: { train: mTrain, val: best.metrics, test: mTest },
    interval_sigma: r4(sigma),
    history_tail: dates.slice(-60).map((d, k) => ({ date: d, price_brl: r2(values.slice(-60)[k]) })),
    forecast,
    limitations: [
      'Previsão sobre referência internacional convertida (Yahoo Finance + PTAX), não sobre preço físico regional.',
      'Modelo univariado: usa apenas o histórico de preços; clima e câmbio entram como contexto, não como features.',
      'Datas futuras em dias corridos; pregões reais variam com feriados.',
      'Intervalo assume resíduos gaussianos — em choques de mercado o erro real pode exceder a faixa.',
    ],
    retrieved_at: new Date().toISOString(),
  };

  persistRun(commodityKey, payload);
  return payload;
}

function persistRun(commodityKey, payload) {
  const db = connect();
  const info = db
    .prepare(
      `INSERT INTO model_runs(commodity_key, model, horizon_days, metrics_json, params_json, data_start, data_end)
       VALUES(?, ?, ?, ?, ?, ?, ?)`
    )
    .run(
      commodityKey,
      `ridge(lambda=${payload.lambda})`,
      payload.horizon_days,
      JSON.stringify(payload.metrics),
      JSON.stringify({ winner: payload.model_selected, interval_sigma: payload.interval_sigma }),
      payload.data_start,
      payload.data_end
    );
  const stmt = db.prepare(
    'INSERT INTO forecasts(model_run_id, target_date, price_brl, lower_brl, upper_brl) VALUES(?, ?, ?, ?, ?)'
  );
  const tx = db.transaction((rows) => {
    for (const f of rows) stmt.run(info.lastInsertRowid, f.date, f.price_brl, f.lower_brl, f.upper_brl);
  });
  tx(payload.forecast);
}

module.exports = {
  run,
  MIN_POINTS,
  _test: { clean, featuresFor, buildRows, splitRows, fitRidge, metrics, baselinePredict, nextBusinessDates },
};
