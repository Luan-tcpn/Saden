'use strict';

const { describe, it, before, after } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const http = require('node:http');

const ROOT = path.join(__dirname, '..', '..');
const TMP = path.join(ROOT, 'tmp');
const DB_PATH = path.join(TMP, 'test-offsite.db');
process.env.DATABASE_PATH = DB_PATH;

const cryptoLib = require('../../backend/src/backup/crypto');
const manifestLib = require('../../backend/src/backup/manifest');
const offsite = require('../../backend/src/backup/offsite');
const backup = require('../../backend/scripts/backup');
const drill = require('../../backend/scripts/restore-drill');
const monitor = require('../../backend/src/worker/monitor');

const PASSPHRASE = 'senha-de-teste-com-32-caracteres';

function tempDir(name) {
  const dir = path.join(TMP, name);
  fs.rmSync(dir, { recursive: true, force: true });
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

function freshDb() {
  try {
    fs.unlinkSync(DB_PATH);
  } catch {
    /* primeiro run */
  }
  const db = require('../../backend/src/db');
  const conn = db.connect();
  conn.prepare("INSERT INTO users(name, email, password_hash) VALUES('Offsite','o@t.local','x')").run();
  conn
    .prepare(
      "INSERT INTO alerts(user_id, commodity_key, kind, condition, series_id, threshold, active, status) VALUES(1,'soja','price','price_above','yahoo:ZS=F:brl:sc60',1,1,'active')"
    )
    .run();
  return conn;
}

describe('criptografia do backup', () => {
  it('cifra e decifra preservando o conteúdo', () => {
    const plain = Buffer.from('conteúdo do banco, com acentuação e bytes \u0000\u00ff');
    const envelope = cryptoLib.encryptBuffer(plain, PASSPHRASE);
    assert.ok(envelope.subarray(0, 8).equals(cryptoLib.MAGIC));
    assert.ok(!envelope.includes(plain), 'texto claro não aparece no envelope');
    assert.deepEqual(cryptoLib.decryptBuffer(envelope, PASSPHRASE), plain);
  });

  it('rejeita chave incorreta', () => {
    const envelope = cryptoLib.encryptBuffer(Buffer.from('dados'), PASSPHRASE);
    assert.throws(() => cryptoLib.decryptBuffer(envelope, 'outra-senha-qualquer-123'), /chave incorreta ou arquivo corrompido/);
  });

  it('rejeita envelope corrompido', () => {
    const envelope = cryptoLib.encryptBuffer(Buffer.from('dados importantes'), PASSPHRASE);
    envelope[envelope.length - 1] ^= 0xff;
    assert.throws(() => cryptoLib.decryptBuffer(envelope, PASSPHRASE), /chave incorreta ou arquivo corrompido/);
  });

  it('rejeita arquivo que não é envelope do SADEN', () => {
    assert.throws(() => cryptoLib.decryptBuffer(Buffer.from('SADENBK1'), PASSPHRASE), /truncado/);
    assert.throws(
      () => cryptoLib.decryptBuffer(Buffer.alloc(64, 1), PASSPHRASE),
      /não é um backup criptografado/
    );
  });

  it('exige passphrase com tamanho mínimo', () => {
    assert.throws(() => cryptoLib.encryptBuffer(Buffer.from('x'), 'curta'), /mínimo 12/);
  });

  it('checksum é estável e muda com o conteúdo', () => {
    const a = cryptoLib.checksumBuffer(Buffer.from('a'));
    const b = cryptoLib.checksumBuffer(Buffer.from('b'));
    assert.equal(a.length, 64);
    assert.notEqual(a, b);
  });
});

describe('manifesto e estados de saúde', () => {
  let dir;
  before(() => {
    fs.mkdirSync(TMP, { recursive: true });
    freshDb();
    dir = tempDir('manifest-test');
  });

  it('sem manifesto → missing', () => {
    assert.equal(manifestLib.assess({ outDir: dir }).status, 'missing');
  });

  it('backup recente → ok', () => {
    const result = backup.createBackup({ dbPath: DB_PATH, outDir: dir, retention: 5 });
    const health = manifestLib.assess({ outDir: dir });
    assert.equal(health.status, 'ok');
    assert.equal(health.detail, 'backup_recente');
    assert.equal(result.manifest.sha256, result.sha256);
    assert.ok(fs.existsSync(manifestLib.manifestPathFor(result.file)));
  });

  it('backup antigo → stale', () => {
    const health = manifestLib.assess({ outDir: dir, now: Date.now() + 40 * 3600 * 1000 });
    assert.equal(health.status, 'stale');
  });

  it('tentativa falha depois do sucesso → failed', () => {
    manifestLib.recordAttempt(dir, { status: 'failed', error: 'disco cheio' });
    const health = manifestLib.assess({ outDir: dir });
    assert.equal(health.status, 'failed');
    assert.match(health.detail, /disco cheio/);
  });

  it('arquivo removido → invalid', () => {
    const dir2 = tempDir('manifest-invalid');
    const result = backup.createBackup({ dbPath: DB_PATH, outDir: dir2, retention: 5 });
    fs.rmSync(result.file);
    assert.equal(manifestLib.assess({ outDir: dir2 }).status, 'invalid');
  });
});

describe('restore drill', () => {
  let dir;
  before(() => {
    dir = tempDir('drill-test');
    backup.createBackup({ dbPath: DB_PATH, outDir: dir, retention: 5 });
  });

  it('restaura e valida o backup mais recente', () => {
    const result = drill.drillLocal(dir);
    assert.equal(result.ok, true);
    assert.ok(result.counts.users >= 1);
    assert.ok(result.counts.alerts >= 1);
  });

  it('não deixa banco temporário para trás', () => {
    const before = fs.readdirSync(os.tmpdir()).filter((name) => name.startsWith('saden-drill-')).length;
    drill.drillLocal(dir);
    const after = fs.readdirSync(os.tmpdir()).filter((name) => name.startsWith('saden-drill-')).length;
    assert.equal(after, before);
  });

  it('detecta backup corrompido e cai para o próximo válido', () => {
    const dir2 = tempDir('drill-corrupt');
    const first = backup.createBackup({ dbPath: DB_PATH, outDir: dir2, date: new Date('2026-11-10T10:00:00'), retention: 5 });
    backup.createBackup({ dbPath: DB_PATH, outDir: dir2, date: new Date('2026-11-11T10:00:00'), retention: 5 });
    // Corrompe o mais recente, mantendo o anterior íntegro.
    const newest = backup.listBackups(dir2)[0];
    fs.writeFileSync(newest.path, 'corrompido');
    const result = drill.drillLocal(dir2);
    assert.equal(result.ok, true, 'drill deve usar o backup anterior');
    assert.equal(result.attempts[0].ok, false);
    assert.ok(fs.existsSync(first.file), 'backup antigo preservado');
  });

  it('falha quando todos os candidatos estão corrompidos', () => {
    const dir3 = tempDir('drill-all-bad');
    const result = backup.createBackup({ dbPath: DB_PATH, outDir: dir3, retention: 5 });
    fs.writeFileSync(result.file, 'lixo');
    const drillResult = drill.drillLocal(dir3);
    assert.equal(drillResult.ok, false);
    assert.match(drillResult.error, /falharam/);
  });
});

describe('transporte off-site', () => {
  let dir;
  let backupFile;

  before(() => {
    dir = tempDir('offsite-src');
    const result = backup.createBackup({ dbPath: DB_PATH, outDir: dir, retention: 5 });
    backupFile = result.file;
  });

  it('desabilitado sem configuração', () => {
    const cfg = offsite.config({});
    assert.equal(cfg.enabled, false);
    assert.equal(offsite.createTransport(cfg), null);
  });

  it('envia cifrado para diretório espelhado e confirma tamanho', async () => {
    const mirror = tempDir('offsite-mirror');
    const cfg = offsite.config({ SADEN_OFFSITE_MODE: 'dir', SADEN_OFFSITE_DIR: mirror, SADEN_BACKUP_PASSPHRASE: PASSPHRASE });
    const sent = await offsite.push({ file: backupFile, cfg });
    assert.equal(sent.status, 'ok');
    assert.equal(sent.encrypted, true);

    const stored = path.join(mirror, sent.key);
    const raw = fs.readFileSync(stored);
    assert.ok(raw.subarray(0, 8).equals(cryptoLib.MAGIC), 'objeto remoto é cifrado');
    assert.ok(!raw.includes(Buffer.from('SQLite format 3')), 'banco não sobe em claro');
  });

  it('recupera com a chave correta e falha com a errada', async () => {
    const mirror = tempDir('offsite-pull');
    const cfg = offsite.config({ SADEN_OFFSITE_MODE: 'dir', SADEN_OFFSITE_DIR: mirror, SADEN_BACKUP_PASSPHRASE: PASSPHRASE });
    const sent = await offsite.push({ file: backupFile, cfg });

    const out = path.join(TMP, 'restored-from-offsite.db');
    const pulled = await offsite.pull({ key: sent.key, outPath: out, cfg });
    assert.equal(pulled.sha256, cryptoLib.checksumFile(out));
    assert.equal(backup.validateBackup(out).integrity, 'ok');

    const wrong = { ...cfg, passphrase: 'chave-errada-mas-longa-123' };
    assert.rejects(() => offsite.pull({ key: sent.key, outPath: path.join(TMP, 'nope.db'), cfg: wrong }), /chave incorreta/);
    assert.ok(!fs.existsSync(path.join(TMP, 'nope.db')), 'não grava arquivo parcial em falha de chave');
  });

  it('aplica retenção remota mantendo os mais recentes', async () => {
    const mirror = tempDir('offsite-retention');
    const cfg = offsite.config({ SADEN_OFFSITE_MODE: 'dir', SADEN_OFFSITE_DIR: mirror, SADEN_BACKUP_PASSPHRASE: PASSPHRASE });
    for (let i = 0; i < 4; i++) {
      const f = path.join(dir, `saden-2026111${i}-100000.db`);
      fs.copyFileSync(backupFile, f);
      await offsite.push({ file: f, cfg });
    }
    const pruned = await offsite.prune({ keep: 2, cfg });
    assert.equal(pruned.removed.length, 2);
    assert.equal(fs.readdirSync(mirror).filter((n) => n.endsWith('.enc')).length, 2);
  });

  it('destino indisponível não lança e não marca sucesso', async () => {
    const mirror = tempDir('offsite-down');
    const cfg = offsite.config({ SADEN_OFFSITE_MODE: 'dir', SADEN_OFFSITE_DIR: mirror, SADEN_BACKUP_PASSPHRASE: PASSPHRASE });
    const transport = offsite.createTransport(cfg);
    transport.put = async () => {
      throw new Error('ECONNREFUSED');
    };
    const sent = await offsite.push({ file: backupFile, cfg, transport });
    assert.equal(sent.status, 'error');
    assert.equal(sent.reason, 'destino_indisponivel');
  });

  it('arquivo remoto incompleto é detectado pelo HEAD', async () => {
    const mirror = tempDir('offsite-truncated');
    const cfg = offsite.config({ SADEN_OFFSITE_MODE: 'dir', SADEN_OFFSITE_DIR: mirror, SADEN_BACKUP_PASSPHRASE: PASSPHRASE });
    const transport = offsite.createTransport(cfg);
    const realHead = transport.head;
    transport.head = async () => ({ size: 3 });
    const sent = await offsite.push({ file: backupFile, cfg, transport });
    transport.head = realHead;
    assert.equal(sent.status, 'error');
    assert.equal(sent.reason, 'tamanho_remoto_divergente');
  });
});

describe('transporte S3 (assinatura)', () => {
  let server;
  let received;
  let base;

  before(async () => {
    received = [];
    server = await new Promise((resolve) => {
      const s = http.createServer((req, res) => {
        received.push({ method: req.method, url: req.url, auth: req.headers.authorization, date: req.headers['x-amz-date'], hash: req.headers['x-amz-content-sha256'] });
        res.writeHead(200, { 'content-length': '2' }).end('ok');
      });
      s.listen(0, '127.0.0.1', () => resolve(s));
    });
    base = `http://127.0.0.1:${server.address().port}`;
  });

  after(() => new Promise((resolve) => server.close(resolve)));

  it('assina com SigV4 e usa caminho path-style', async () => {
    const cfg = offsite.config({
      SADEN_OFFSITE_MODE: 's3',
      SADEN_S3_ENDPOINT: base,
      SADEN_S3_BUCKET: 'balde',
      SADEN_S3_ACCESS_KEY: 'AKIA',
      SADEN_S3_SECRET_KEY: 'segredo',
      SADEN_BACKUP_PASSPHRASE: PASSPHRASE,
    });
    const transport = offsite.createTransport(cfg);
    await transport.put('teste.db.enc', Buffer.from('x'));
    const last = received[received.length - 1];
    assert.equal(last.method, 'PUT');
    assert.match(last.url, /^\/balde\/saden\/backups\/teste\.db\.enc$/);
    assert.match(last.auth, /^AWS4-HMAC-SHA256 Credential=AKIA\/\d{8}\/us-east-1\/s3\/aws4_request/);
    assert.match(last.auth, /SignedHeaders=/);
    assert.match(last.auth, /Signature=[0-9a-f]{64}/);
    assert.equal(last.hash.length, 64);
  });

  it('não inclui a chave secreta na requisição', async () => {
    const last = received[received.length - 1];
    assert.ok(!JSON.stringify(last).includes('segredo'));
  });
});

describe('monitor do backup', () => {
  it('usa identificador próprio e avisa início, sucesso e falha', async () => {
    const paths = [];
    const server = await new Promise((resolve) => {
      const s = http.createServer((req, res) => {
        paths.push(req.url);
        res.writeHead(200).end('ok');
      });
      s.listen(0, '127.0.0.1', () => resolve(s));
    });
    const base = `http://127.0.0.1:${server.address().port}/ping/backup-uuid`;
    try {
      assert.equal((await monitor.ping('start', { base })).status, 'ok');
      assert.equal((await monitor.ping('success', { base })).status, 'ok');
      assert.equal((await monitor.ping('fail', { base })).status, 'ok');
      assert.deepEqual(paths, ['/ping/backup-uuid/start', '/ping/backup-uuid', '/ping/backup-uuid/fail']);
    } finally {
      await new Promise((resolve) => server.close(resolve));
    }
  });

  it('não vaza o token no descritor de log', () => {
    const described = monitor.describe({ status: 'error', code: 500, reason: 'http_error' });
    assert.equal(JSON.stringify(described).includes('uuid'), false);
    assert.equal(monitor.redact('https://hc-ping.com/segredo-123/start').includes('segredo'), false);
  });
});
