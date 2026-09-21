'use strict';

const { describe, it } = require('node:test');
const assert = require('node:assert/strict');

const { fetchJson, withRetry } = require('../../backend/src/utils/http');

describe('http — timeout e retry (resiliência upstream)', () => {
  it('timeout curto gera erro 502 sem travar', async () => {
    // Porta fechada em localhost: falha imediata; timeout cobre lentidão real.
    const t0 = Date.now();
    await assert.rejects(() => fetchJson('http://127.0.0.1:1/nada', { timeoutMs: 3000 }), (e) => {
      assert.equal(e.status, 502);
      return true;
    });
    assert.ok(Date.now() - t0 < 3000, 'respondeu rápido sem travar');
  });

  it('withRetry tenta 3x em erro transitório e desiste', async () => {
    let calls = 0;
    await assert.rejects(
      () =>
        withRetry(
          () => {
            calls++;
            const e = new Error('bad gateway');
            e.status = 502;
            throw e;
          },
          { attempts: 3, baseDelayMs: 10 }
        ),
      /bad gateway/
    );
    assert.equal(calls, 3);
  });

  it('withRetry não repete erro não-transitório (400)', async () => {
    let calls = 0;
    await assert.rejects(() =>
      withRetry(() => {
        calls++;
        const e = new Error('bad request');
        e.status = 400;
        throw e;
      })
    );
    assert.equal(calls, 1);
  });

  it('withRetry retorna na primeira tentativa quando ok', async () => {
    const out = await withRetry(async () => 42);
    assert.equal(out, 42);
  });
});
