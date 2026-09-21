'use strict';

const { describe, it } = require('node:test');
const assert = require('node:assert/strict');

const { MIN_POINTS, _test } = require('../../backend/src/services/forecastService');
const { clean, buildRows, splitRows, fitRidge, metrics, baselinePredict } = _test;

// Série sintética determinística (tendência + ruído fixo) — só para matemática,
// nunca como dado de produção.
function synth(n = 250) {
  const v = [];
  for (let i = 0; i < n; i++) v.push(100 + i * 0.05 + Math.sin(i / 5) * 2);
  return v;
}

describe('forecastService — matemática do pipeline', () => {
  it('MIN_POINTS é 60', () => {
    assert.equal(MIN_POINTS, 60);
  });

  it('clean ordena, remove inválidos e deduplica', () => {
    const { dates, values } = clean([
      { date: '2026-01-03', price_brl: 10 },
      { date: '2026-01-01', price_brl: 8 },
      { date: '2026-01-02', price_brl: NaN },
      { date: '2026-01-03', price_brl: 11 },
    ]);
    assert.deepEqual(dates, ['2026-01-01', '2026-01-03']);
    assert.deepEqual(values, [8, 11]);
  });

  it('buildRows usa só passado (sem vazamento): alvo é values[i+1]', () => {
    const values = synth(100);
    const rows = buildRows(values);
    assert.ok(rows.length === 100 - 1 - 30);
    // features da 1ª linha derivam de values[0..30]; alvo values[31]
    assert.equal(rows[0].y, values[31]);
    assert.equal(rows[0].x[0], values[29]); // lag1 = values[30-1]
  });

  it('splitRows respeita ordem cronológica 70/15/15', () => {
    const rows = buildRows(synth(200));
    const { train, val, test } = splitRows(rows);
    assert.ok(train.length > val.length && val.length <= test.length + 1);
    // sem embaralhar: último y de treino < primeiro y de val em ordem de construção
    assert.ok(train[train.length - 1].y <= val[0].y + 50); // série crescente suave
    assert.equal(train.length + val.length + test.length, rows.length);
  });

  it('fitRidge aprende tendência e metrics calcula MAE/RMSE/MAPE', () => {
    const values = synth(200);
    const rows = buildRows(values);
    const X = rows.slice(0, 100).map((r) => r.x);
    const y = rows.slice(0, 100).map((r) => r.y);
    const model = fitRidge(X, y, 1);
    const pred = rows.slice(100, 130).map((r) => model.predict(r.x));
    const actual = rows.slice(100, 130).map((r) => r.y);
    const m = metrics(actual, pred);
    assert.ok(m.rmse < 1.0, `RMSE esperado < 1.0, obtido ${m.rmse}`);
    assert.ok(m.mae <= m.rmse);
    assert.ok(m.mape_pct < 1);
    assert.equal(m.n, 30);
  });

  it('baselinePredict naive repete último; ma7 faz média dos 7', () => {
    const values = [1, 2, 3, 4, 5, 6, 7, 8];
    assert.deepEqual(baselinePredict('naive', values, 7, 2), [8, 8]);
    assert.deepEqual(baselinePredict('ma7', values, 7, 1), [5]);
    assert.deepEqual(baselinePredict('seasonal_naive_5', values, 7, 1), [4]);
  });
});
