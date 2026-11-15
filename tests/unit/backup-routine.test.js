'use strict';

const { describe, it, before, after } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.join(__dirname, '..', '..');
const TMP = path.join(ROOT, 'tmp');
const DB_PATH = path.join(TMP, 'test-backup-routine.db');
process.env.DATABASE_PATH = DB_PATH;

const backup = require('../../backend/scripts/backup');

function freshDb() {
  try {
    fs.unlinkSync(DB_PATH);
  } catch {
    /* primeiro run */
  }
  const db = require('../../backend/src/db');
  db.connect();
  const conn = db.connect();
  conn.prepare("INSERT INTO users(name, email, password_hash) VALUES('Teste','b@t.local','x')").run();
  conn
    .prepare(
      "INSERT INTO alerts(user_id, commodity_key, kind, condition, series_id, threshold, active, status) VALUES(1,'soja','price','price_above','yahoo:ZS=F:brl:sc60',1,1,'active')"
    )
    .run();
  return conn;
}

describe('rotina de backup', () => {
  let outDir;

  before(() => {
    fs.mkdirSync(TMP, { recursive: true });
    freshDb();
    outDir = path.join(TMP, 'backups-test');
    fs.rmSync(outDir, { recursive: true, force: true });
  });

  after(() => {
    fs.rmSync(outDir, { recursive: true, force: true });
  });

  it('gera backup válido com as contagens do banco', () => {
    const result = backup.createBackup({ dbPath: DB_PATH, outDir, date: new Date('2026-11-14T10:00:00') });
    assert.equal(result.ok, true);
    assert.ok(fs.existsSync(result.file));
    assert.equal(result.integrity, 'ok');
    assert.equal(result.counts.users, 1);
    assert.equal(result.counts.alerts, 1);
    assert.ok(result.size > 0);
    assert.match(result.name, /^saden-20261114-100000\.db$/);
  });

  it('o backup pode ser aberto e lido como banco independente', () => {
    const items = backup.listBackups(outDir);
    const verification = backup.validateBackup(items[0].path);
    assert.equal(verification.counts.alerts, 1);
    assert.equal(verification.integrity, 'ok');
  });

  it('recusa arquivo inválido com motivo claro', () => {
    const bogus = path.join(TMP, 'bogus-backup.db');
    fs.writeFileSync(bogus, 'isto nao e sqlite');
    assert.throws(() => backup.validateBackup(bogus), /não é um banco SQLite legível/);
    fs.rmSync(bogus, { force: true });
  });

  it('arquivo vazio é rejeitado', () => {
    const empty = path.join(TMP, 'empty-backup.db');
    fs.writeFileSync(empty, '');
    assert.throws(() => backup.validateBackup(empty), /vazio/);
    fs.rmSync(empty, { force: true });
  });

  it('não deixa arquivo parcial quando a origem não é um banco', () => {
    const notDb = path.join(TMP, 'origem-invalida.db');
    fs.writeFileSync(notDb, 'lixo');
    const before = backup.listBackups(outDir).length;
    assert.throws(() => backup.createBackup({ dbPath: notDb, outDir }), /VACUUM INTO falhou/);
    const partials = fs.readdirSync(outDir).filter((name) => name.includes('.partial'));
    assert.equal(partials.length, 0, 'nenhum arquivo parcial deve restar');
    assert.equal(backup.listBackups(outDir).length, before, 'backups antigos intactos');
    fs.rmSync(notDb, { force: true });
  });

  it('aplica retenção sem apagar o backup novo', () => {
    const dir = path.join(TMP, 'backups-retention');
    fs.rmSync(dir, { recursive: true, force: true });
    const stamps = ['2026-11-10T10:00:00', '2026-11-11T10:00:00', '2026-11-12T10:00:00'];
    for (const stamp of stamps) {
      backup.createBackup({ dbPath: DB_PATH, outDir: dir, date: new Date(stamp), retention: 10 });
    }
    const before = backup.listBackups(dir);
    assert.equal(before.length, 3);

    const result = backup.createBackup({
      dbPath: DB_PATH,
      outDir: dir,
      date: new Date('2026-11-13T10:00:00'),
      retention: 2,
    });
    const after = backup.listBackups(dir);
    assert.equal(after.length, 2);
    assert.equal(after[0].name, 'saden-20261113-100000.db');
    assert.ok(after.some((item) => item.name === result.name));
    assert.equal(result.removed.length, 2);
    fs.rmSync(dir, { recursive: true, force: true });
  });

  it('falha no backup novo não remove os antigos', () => {
    const dir = path.join(TMP, 'backups-falha');
    fs.rmSync(dir, { recursive: true, force: true });
    backup.createBackup({ dbPath: DB_PATH, outDir: dir, date: new Date('2026-11-12T10:00:00'), retention: 1 });
    const before = backup.listBackups(dir).map((item) => item.name);

    const notDb = path.join(TMP, 'origem-invalida-2.db');
    fs.writeFileSync(notDb, 'lixo');
    assert.throws(() => backup.createBackup({ dbPath: notDb, outDir: dir, retention: 1 }));
    const after = backup.listBackups(dir).map((item) => item.name);
    assert.deepEqual(after, before);
    fs.rmSync(notDb, { force: true });
    fs.rmSync(dir, { recursive: true, force: true });
  });

  // Achado da auditoria v1.2.2: dois backups no mesmo segundo compartilhavam o
  // arquivo parcial e um apagava o do outro. O parcial agora é único por
  // processo; a colisão de nome final é detectada sem sobrescrever nada.
  it('dois backups no mesmo segundo não se destroem', () => {
    const dir = path.join(TMP, 'backups-colisao');
    fs.rmSync(dir, { recursive: true, force: true });
    const when = new Date('2026-05-05T10:00:00');
    const first = backup.createBackup({ dbPath: DB_PATH, outDir: dir, date: when });
    assert.throws(
      () => backup.createBackup({ dbPath: DB_PATH, outDir: dir, date: when }),
      /já existe backup com este carimbo de tempo/
    );
    assert.ok(fs.existsSync(first.file), 'o primeiro backup permanece');
    assert.equal(backup.validateBackup(first.file).integrity, 'ok');
    const restos = fs.readdirSync(dir).filter((name) => name.includes('.partial'));
    assert.deepEqual(restos, [], 'nenhum arquivo parcial abandonado');
    fs.rmSync(dir, { recursive: true, force: true });
  });

  it('backup é consistente enquanto outra conexão escreve (WAL)', async () => {
    const writer = require('../../backend/src/db').connect();
    let running = true;
    const writes = (async () => {
      let i = 0;
      while (running) {
        writer
          .prepare("INSERT INTO price_observations(commodity_key, data_date, price_usd, fx_rate, price_brl, unit_br, provider) VALUES('soja', ?, 1, 5, 5, 'R$/sc 60kg', 'teste')")
          .run(`2026-01-${String((i % 28) + 1).padStart(2, '0')}x${i++}`);
        await new Promise((resolve) => setImmediate(resolve));
      }
    })();

    const result = backup.createBackup({ dbPath: DB_PATH, outDir, date: new Date('2026-11-14T11:00:00') });
    running = false;
    await writes;
    assert.equal(result.integrity, 'ok');
    assert.equal(backup.validateBackup(result.file).ok, true);
  });
});
