'use strict';

const { describe, it } = require('node:test');
const assert = require('node:assert/strict');

const { converter, toBRL } = require('../../backend/src/services/fxService');

describe('fxService — conversão futuro internacional -> BRL', () => {
  it('soja/milho/trigo usam fator saca 60kg (60/27.2155 bu)', () => {
    for (const k of ['soja', 'milho', 'trigo']) {
      const c = converter(k);
      assert.ok(Math.abs(c.factor - 60 / 27.2155) < 1e-9);
      assert.equal(c.toUnit, 'R$/sc 60kg');
    }
  });

  it('café usa fator 60kg em libras (60/0.45359237)', () => {
    const c = converter('cafe');
    assert.ok(Math.abs(c.factor - 60 / 0.45359237) < 1e-9);
  });

  it('algodão é direto R$/libra-peso (fator 1)', () => {
    assert.equal(converter('algodao').factor, 1);
  });

  it('toBRL: 100 cents com PTAX 5 => soja R$ 11,02/sc', () => {
    // (100/100) * 5 * 2.20462 = 11.0231
    assert.ok(Math.abs(toBRL('soja', 100, 5) - 11.0231) < 0.001);
  });

  it('commodity desconhecida lança erro', () => {
    assert.throws(() => converter('petroleo'), /desconhecida/);
  });
});
