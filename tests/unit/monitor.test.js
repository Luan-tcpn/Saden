'use strict';

process.env.DATABASE_PATH = require('path').join(__dirname, '..', '..', 'tmp', 'test-monitor.db');

const { describe, it, before, after } = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const fs = require('node:fs');

const monitor = require('../../backend/src/worker/monitor');

function startServer(handler) {
  return new Promise((resolve) => {
    const server = http.createServer(handler);
    server.listen(0, '127.0.0.1', () => resolve(server));
  });
}

describe('monitor externo — configuração', () => {
  it('desabilitado sem URL', async () => {
    const previous = process.env.SADEN_MONITOR_PING_URL;
    delete process.env.SADEN_MONITOR_PING_URL;
    try {
      assert.equal(monitor.enabled(), false);
      const result = await monitor.ping('start');
      assert.equal(result.status, 'disabled');
      assert.equal(monitor.describe(result), null);
    } finally {
      if (previous !== undefined) process.env.SADEN_MONITOR_PING_URL = previous;
    }
  });

  it('monta os sufixos do protocolo', () => {
    const base = 'https://hc.example.com/ping/abc-123';
    assert.equal(monitor.endpoint('start', base), `${base}/start`);
    assert.equal(monitor.endpoint('success', base), base);
    assert.equal(monitor.endpoint('fail', base), `${base}/fail`);
    assert.equal(monitor.endpoint('start', `${base}/`), `${base}/start`);
  });

  it('recusa evento desconhecido', () => {
    assert.throws(() => monitor.endpoint('nope', 'https://x/y'), /evento de monitor desconhecido/);
  });

  it('redige o token da URL antes de logar', () => {
    const redacted = monitor.redact('https://hc-ping.com/1234-secret-token/start?x=1');
    assert.equal(redacted, 'https://hc-ping.com/…');
    assert.ok(!redacted.includes('secret'));
  });
});

describe('monitor externo — envio', () => {
  let server;
  let paths;
  let status = 200;
  let base;

  before(async () => {
    paths = [];
    server = await startServer((req, res) => {
      paths.push(req.url);
      res.writeHead(status).end('ok');
    });
    base = `http://127.0.0.1:${server.address().port}/ping/uuid-teste`;
  });

  after(() => new Promise((resolve) => server.close(resolve)));

  it('envia início, sucesso e falha para os caminhos corretos', async () => {
    paths.length = 0;
    status = 200;
    const start = await monitor.ping('start', { base });
    const success = await monitor.ping('success', { base });
    const fail = await monitor.ping('fail', { base });
    assert.deepEqual(
      [start.status, success.status, fail.status],
      ['ok', 'ok', 'ok']
    );
    assert.deepEqual(paths, ['/ping/uuid-teste/start', '/ping/uuid-teste', '/ping/uuid-teste/fail']);
  });

  it('não lança quando o serviço responde erro', async () => {
    status = 503;
    const result = await monitor.ping('success', { base });
    assert.equal(result.status, 'error');
    assert.equal(result.reason, 'http_error');
    assert.equal(result.code, 503);
  });

  it('não lança quando o serviço está fora do ar', async () => {
    const result = await monitor.ping('start', { base: 'http://127.0.0.1:1/ping/x' });
    assert.equal(result.status, 'error');
    assert.equal(result.reason, 'network_error');
  });

  it('respeita o timeout sem travar o ciclo', async () => {
    const slow = await startServer((req, res) => setTimeout(() => res.writeHead(200).end(), 2000));
    try {
      const baseSlow = `http://127.0.0.1:${slow.address().port}/ping/x`;
      const began = Date.now();
      const result = await monitor.ping('success', { base: baseSlow, timeoutMs: 150 });
      const elapsed = Date.now() - began;
      assert.equal(result.status, 'error');
      assert.equal(result.reason, 'timeout');
      assert.ok(elapsed < 1500, `demorou ${elapsed}ms`);
    } finally {
      await new Promise((resolve) => slow.close(resolve));
    }
  });

  it('não envia dados de usuário: só um GET no caminho do ping', async () => {
    paths.length = 0;
    await monitor.ping('success', { base });
    assert.equal(paths.length, 1);
    assert.ok(!/email|user|token|price/i.test(paths[0]));
  });
});

describe('monitor externo — integração com o ciclo', () => {
  it('runCycle informa o monitor e não quebra quando ele falha', async () => {
    const db = require('../../backend/src/db');
    try {
      fs.unlinkSync(process.env.DATABASE_PATH);
    } catch {
      /* primeiro run */
    }
    db.connect();
    const config = require('../../backend/src/worker/config');
    const runner = require('../../backend/src/worker/runner');

    process.env.SADEN_MONITOR_PING_URL = 'http://127.0.0.1:1/ping/falha';
    const summary = await runner.runCycle({ owner: 'teste-monitor', force: true });
    assert.equal(summary.status, 'ok');
    assert.equal(summary.monitor.start.monitor, 'error');
    assert.equal(summary.monitor.end.monitor, 'error');
    assert.equal(summary.series_total, 0);
    delete process.env.SADEN_MONITOR_PING_URL;
  });
});
