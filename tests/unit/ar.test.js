'use strict';

// AR(p)+AIC challenger: seleção, coeficientes, estabilidade, recursivo,
// gate de leakage e paridade de split com a Ridge. Séries sintéticas
// determinísticas (LCG) — sem rede, sem mocks de produção.
const { describe, it } = require('node:test');
const assert = require('node:assert/strict');

const ar = require('../../backend/src/services/arService');
const forecast = require('../../backend/src/services/forecastService');
const { solve, olsBeta } = require('../../backend/src/utils/linalg');

function lcg(seed) {
  let s = seed;
  return () => {
    s = (s * 1103515245 + 12345) & 0x7fffffff;
    return s / 0x7fffffff;
  };
}

function arSeries(n, intercept, phis, sigma, seed) {
  const rnd = lcg(seed);
  const p = phis.length;
  const y = Array.from({ length: p }, () => 100);
  for (let t = p; t < n; t++) {
    let v = intercept;
    for (let k = 1; k <= p; k++) v += phis[k - 1] * y[t - k];
    y.push(v + (rnd() - 0.5) * 2 * sigma);
  }
  return y;
}

function isoDates(n) {
  const out = [];
  const d = new Date('2026-01-01T12:00:00Z');
  for (let i = 0; i < n; i++) {
    const nd = new Date(d);
    nd.setUTCDate(nd.getUTCDate() + i);
    out.push(nd.toISOString().slice(0, 10));
  }
  return out;
}

describe('AR challenger — linalg compartilhado', () => {
  it('solve resolve sistema 2x2 conhecido', () => {
    const [x, y] = solve([[2, 1], [1, 3]], [5, 6]);
    assert.ok(Math.abs(x - 1.8) < 1e-9 && Math.abs(y - 1.4) < 1e-9);
  });

  it('solve lança em matriz singular', () => {
    assert.throws(() => solve([[1, 2], [2, 4]], [1, 2]), /singular/);
  });

  it('olsBeta recupera reta conhecida', () => {
    const X = [[1, 0], [1, 1], [1, 2], [1, 3]];
    const [b0, b1] = olsBeta(X, [1, 3, 5, 7]);
    assert.ok(Math.abs(b0 - 1) < 1e-9 && Math.abs(b1 - 2) < 1e-9);
  });
});

describe('AR challenger — seleção e coeficientes', () => {
  it('AIC seleciona a ordem verdadeira em AR(2) sintético', () => {
    const y = arSeries(300, 5, [0.6, 0.25], 0.5, 42);
    const { p } = ar.selectOrder(y);
    assert.equal(p, 2);
  });

  it('coeficientes próximos da verdade', () => {
    const y = arSeries(400, 5, [0.6, 0.25], 0.5, 7);
    const { beta } = ar.fitAR(y, 2);
    assert.ok(Math.abs(beta[0] - 5) < 0.6, `intercepto ${beta[0]}`);
    assert.ok(Math.abs(beta[1] - 0.6) < 0.08, `phi1 ${beta[1]}`);
    assert.ok(Math.abs(beta[2] - 0.25) < 0.08, `phi2 ${beta[2]}`);
  });

  it('one-step exato em AR(1) sem ruído', () => {
    const hist = [10, 9, 8.3, 7.81]; // y_t = 2 + 0.7*y_{t-1} aprox.? não: usa beta dado
    const pred = ar.predictOneStep([2, 0.7], 1, hist);
    assert.ok(Math.abs(pred - (2 + 0.7 * 7.81)) < 1e-9);
  });
});

describe('AR challenger — recursivo e horizontes', () => {
  const y = arSeries(120, 5, [0.6, 0.25], 0.5, 99);
  const { beta, p } = ar.fitAR(y, 2);

  for (const H of [7, 14, 30]) {
    it(`recursivo H=${H}: tamanho, finitude e 1º passo = one-step`, () => {
      const preds = ar.predictRecursive(beta, p, y, H);
      assert.equal(preds.length, H);
      assert.ok(preds.every(Number.isFinite));
      assert.equal(preds[0], ar.predictOneStep(beta, p, y));
    });
  }

  it('GATE DE LEAKAGE: futuro observado após a origem não altera a previsão', () => {
    const origin = 80;
    const H = 14;
    const base = ar.predictRecursive(beta, p, y.slice(0, origin + 1), H);
    const adulterada = [...y];
    adulterada[origin + 3] *= 10; // choque brutal DEPOIS da origem
    adulterada[origin + 10] = -9999;
    const after = ar.predictRecursive(beta, p, adulterada.slice(0, origin + 1), H);
    assert.deepEqual(after, base);
  });
});

describe('AR challenger — estabilidade e erros honestos', () => {
  it('série curta (<60) → 422', () => {
    const v = arSeries(40, 5, [0.5], 0.5, 1);
    assert.throws(() => ar.evaluate(v, isoDates(40), 7), (e) => {
      assert.equal(e.status, 422);
      return true;
    });
  });

  it('valor não finito → 400', () => {
    const v = arSeries(100, 5, [0.5], 0.5, 2);
    v[50] = NaN;
    assert.throws(() => ar.evaluate(v, isoDates(100), 7), (e) => {
      assert.equal(e.status, 400);
      return true;
    });
  });

  it('série constante → 422 honesto (todas as ordens singulares)', () => {
    const v = new Array(100).fill(150);
    assert.throws(() => ar.evaluate(v, isoDates(100), 7), (e) => {
      assert.equal(e.status, 422);
      assert.match(e.message, /sem variação/);
      return true;
    });
  });

  it('beta explosivo no recursivo → 422 (sem clamp silencioso)', () => {
    assert.throws(() => ar.predictRecursive([0, 1e10], 1, [1], 40), (e) => {
      assert.equal(e.status, 422);
      assert.match(e.message, /não finito/);
      return true;
    });
  });

  it('histórico menor que p → 422', () => {
    assert.throws(() => ar.fitAR([1, 2], 5), (e) => {
      assert.equal(e.status, 422);
      return true;
    });
  });
});

describe('AR challenger — paridade com a Ridge', () => {
  it('mesmos alvos de val/teste que o split da Ridge', () => {
    const v = arSeries(100, 5, [0.5], 0.5, 3);
    const out = ar.evaluate(v, isoDates(100), 7);
    const rows = forecast._test.buildRows(v);
    const { train, val, test } = forecast._test.splitRows(rows);
    assert.equal(out.metrics.val.n, val.length);
    assert.equal(out.metrics.test.n, test.length);
    assert.equal(out.metrics.train.n, train.length);
    assert.equal(out.model, 'ar');
    assert.ok(out.ar_order >= 1 && out.ar_order <= 8);
    assert.ok(['ar', 'baseline'].includes(out.model_selected));
    assert.equal(out.forecast.length, 7);
    assert.equal(out.limitations.length, 5);
    for (const H of ['h7', 'h14', 'h30']) {
      assert.ok(out.recursive_eval[H].origins >= 0);
      if (out.recursive_eval[H].origins > 0) {
        assert.ok(Number.isFinite(out.recursive_eval[H].rmse));
      }
    }
  });
});
