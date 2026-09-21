'use strict';

const { describe, it } = require('node:test');
const assert = require('node:assert/strict');

const { parseCoordinates } = require('../../backend/src/utils/coords');

describe('coords — interpretação de entradas de coordenadas', () => {
  it('aceita "lat, lon" com e sem espaço', () => {
    assert.deepEqual(parseCoordinates('-21.1775,-47.8103'), { lat: -21.1775, lon: -47.8103 });
    assert.deepEqual(parseCoordinates('-21.1775, -47.8103'), { lat: -21.1775, lon: -47.8103 });
  });

  it('aceita parênteses e formatos rotulados', () => {
    assert.deepEqual(parseCoordinates('(-21.17, -47.81)'), { lat: -21.17, lon: -47.81 });
    assert.deepEqual(parseCoordinates('lat: -21.17 lng: -47.81'), { lat: -21.17, lon: -47.81 });
    assert.deepEqual(parseCoordinates('lat=-21.17, lon=-47.81'), { lat: -21.17, lon: -47.81 });
  });

  it('rejeita texto comum e formatos incompletos', () => {
    assert.equal(parseCoordinates('Ribeirão Preto'), null);
    assert.equal(parseCoordinates('-21.17'), null);
    assert.equal(parseCoordinates('abc, def'), null);
    assert.equal(parseCoordinates(''), null);
    assert.equal(parseCoordinates(null), null);
  });

  it('sinaliza fora de faixa em vez de aceitar', () => {
    const r = parseCoordinates('-100, -47.8');
    assert.equal(r.invalid, true);
    assert.equal(parseCoordinates('10, 200').invalid, true);
  });
});
