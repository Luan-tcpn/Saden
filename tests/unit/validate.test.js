'use strict';

const { describe, it } = require('node:test');
const assert = require('node:assert/strict');

const { isEmail, requireString, requireNumber, optionalDate } = require('../../backend/src/utils/validate');

describe('validate — validação de entrada', () => {
  it('isEmail aceita/rejeita formatos', () => {
    assert.equal(isEmail('a@b.com'), true);
    assert.equal(isEmail('sem-arroba'), false);
    assert.equal(isEmail(''), false);
    assert.equal(isEmail(null), false);
  });

  it('requireString falha com status 400', () => {
    assert.throws(() => requireString('', 'nome'), (e) => e.status === 400);
    assert.throws(() => requireString(123, 'nome'), (e) => e.status === 400);
    assert.equal(requireString('  ok  ', 'nome'), 'ok');
  });

  it('requireNumber respeita limites', () => {
    assert.equal(requireNumber('-21.17', 'latitude', { min: -34, max: 6 }), -21.17);
    assert.throws(() => requireNumber(999, 'latitude', { min: -34, max: 6 }), (e) => e.status === 400);
    assert.throws(() => requireNumber('abc', 'x'), (e) => e.status === 400);
  });

  it('optionalDate exige AAAA-MM-DD', () => {
    assert.equal(optionalDate('2026-09-08', 'start'), '2026-09-08');
    assert.equal(optionalDate('', 'start'), undefined);
    assert.throws(() => optionalDate('08/09/2026', 'start'), (e) => e.status === 400);
  });
});
