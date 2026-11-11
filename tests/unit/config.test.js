'use strict';

const { describe, it } = require('node:test');
const assert = require('node:assert/strict');

const { _test } = require('../../backend/src/config');
const { assertProductionSecret } = _test;

describe('config — segredo JWT em produção', () => {
  it('produção sem JWT_SECRET falha explicitamente', () => {
    assert.throws(() => assertProductionSecret({ NODE_ENV: 'production' }), /JWT_SECRET ausente/);
    assert.throws(
      () => assertProductionSecret({ NODE_ENV: 'production', JWT_SECRET: '' }),
      /JWT_SECRET ausente/
    );
  });

  it('produção com segredo e desenvolvimento sem segredo não falham', () => {
    assert.doesNotThrow(() => assertProductionSecret({ NODE_ENV: 'production', JWT_SECRET: 'segredo-forte' }));
    assert.doesNotThrow(() => assertProductionSecret({ NODE_ENV: 'development' }));
    assert.doesNotThrow(() => assertProductionSecret({}));
  });
});
