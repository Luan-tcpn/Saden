'use strict';

const { describe, it } = require('node:test');
const assert = require('node:assert/strict');

const { _test } = require('../../backend/src/routes/reports');
const { csvCell } = _test;

describe('csvCell — anti formula-injection sem alterar conteúdo legítimo', () => {
  it('números e datas passam intactos', () => {
    assert.equal(csvCell(147.74), '147.74');
    assert.equal(csvCell('2026-09-08'), '2026-09-08');
    assert.equal(csvCell('ridge'), 'ridge');
  });

  it('prefixa TAB em células que começam com = + - @', () => {
    assert.equal(csvCell('=1+1'), '\t=1+1');
    assert.equal(csvCell('+cmd'), '\t+cmd');
    assert.equal(csvCell('-2'), '\t-2');
    assert.equal(csvCell('@x'), '\t@x');
  });

  it('envolve em aspas campos com separador e dobra aspas internas', () => {
    assert.equal(csvCell('a;b'), '"a;b"');
    assert.equal(csvCell('diz "oi"'), '"diz ""oi"""');
  });

  it('nulo vira vazio', () => {
    assert.equal(csvCell(null), '');
    assert.equal(csvCell(undefined), '');
  });
});
