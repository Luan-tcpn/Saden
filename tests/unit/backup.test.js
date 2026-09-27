'use strict';

// Backup SQLite: nomeação, conteúdo restaurável e retenção. Hermético em
// tmp/ (não toca data/saden.db nem versiona nada).
const { describe, it, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');

const Database = require('../../backend/node_modules/better-sqlite3');
const { backup, listBackups } = require('../../scripts/backup');

let work;
let srcDb;

beforeEach(() => {
  work = fs.mkdtempSync(path.join(os.tmpdir(), 'saden-bkp-'));
  srcDb = path.join(work, 'orig.db');
  const db = new Database(srcDb);
  db.exec('CREATE TABLE t(id INTEGER PRIMARY KEY, v TEXT)');
  db.prepare("INSERT INTO t(v) VALUES('alpha'),('beta')").run();
  db.close();
});

afterEach(() => {
  fs.rmSync(work, { recursive: true, force: true });
});

describe('backup SQLite', () => {
  it('gera arquivo nomeado com conteúdo restaurável', async () => {
    const out = await backup(srcDb, work, 7);
    assert.match(path.basename(out.file), /^saden-\d{8}T\d{6}\.db$/);
    assert.ok(out.bytes > 0);
    const restored = new Database(out.file, { readonly: true });
    try {
      assert.deepEqual(
        restored.prepare('SELECT v FROM t ORDER BY id').all(),
        [{ v: 'alpha' }, { v: 'beta' }]
      );
    } finally {
      restored.close();
    }
  });

  it('retenção mantém os N mais recentes', async () => {
    for (let i = 1; i <= 5; i++) {
      fs.writeFileSync(path.join(work, `saden-2020010${i}T000000.db`), 'x');
    }
    const out = await backup(srcDb, work, 3);
    const kept = listBackups(work).map((f) => path.basename(f));
    assert.equal(kept.length, 3);
    assert.ok(kept.includes(path.basename(out.file)), 'backup atual preservado');
    assert.ok(!kept.some((f) => f.startsWith('saden-20200101') || f.startsWith('saden-20200102')));
  });

  it('banco inexistente → erro honesto', async () => {
    await assert.rejects(() => backup(path.join(work, 'nao-existe.db'), work, 3), /não encontrado/);
  });
});
