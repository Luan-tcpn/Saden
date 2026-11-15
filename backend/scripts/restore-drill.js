'use strict';

// Restore drill (Release 1.2.2).
//
// Um backup "íntegro" só prova que o arquivo abre. Aqui o arquivo é restaurado
// de verdade num diretório temporário, aberto, verificado e descartado. Se o
// mais recente falhar, o drill tenta os anteriores e registra o resultado —
// nunca toca no banco de produção.
//
// uso:
//   node scripts/restore-drill.js [--out-dir <dir>] [--db <origem>] [--keep]
//   node scripts/restore-drill.js --from-offsite <chave.enc>

const fs = require('fs');
const os = require('os');
const path = require('path');
const Database = require('better-sqlite3');
const cryptoLib = require('../src/backup/crypto');
const manifestLib = require('../src/backup/manifest');
const offsite = require('../src/backup/offsite');

const TABLES = ['users', 'alerts', 'alert_events', 'price_observations', 'series_state'];

function verifyDatabase(file) {
  const db = new Database(file, { readonly: true, fileMustExist: true });
  try {
    const integrity = db.pragma('integrity_check', { simple: true });
    const present = new Set(
      db.prepare("SELECT name FROM sqlite_master WHERE type = 'table'").all().map((row) => row.name)
    );
    const missing = TABLES.filter((table) => !present.has(table));
    const counts = {
      users: db.prepare('SELECT COUNT(*) n FROM users').get().n,
      alerts: db.prepare('SELECT COUNT(*) n FROM alerts').get().n,
      events: db.prepare('SELECT COUNT(*) n FROM alert_events').get().n,
      observations: db.prepare('SELECT COUNT(*) n FROM price_observations').get().n,
    };
    return { integrity, missing, counts };
  } finally {
    db.close();
  }
}

function candidates(outDir) {
  const items = manifestLib.listManifests(outDir);
  return items
    .map(({ manifest }) => manifest)
    .filter((manifest) => manifest && manifest.status === 'ok')
    .map((manifest) => ({ ...manifest, path: path.join(outDir, manifest.file) }))
    .filter((manifest) => fs.existsSync(manifest.path));
}

/** Executa o drill sobre um arquivo. Nunca altera a origem. */
function drill(file, { checksum } = {}) {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'saden-drill-'));
  const copy = path.join(tmpDir, 'drill.db');
  try {
    fs.copyFileSync(file, copy);
    if (checksum) {
      const actual = cryptoLib.checksumFile(copy);
      if (actual !== checksum) throw new Error('checksum divergente');
    }
    const result = verifyDatabase(copy);
    if (result.integrity !== 'ok') throw new Error(`integrity_check: ${result.integrity}`);
    if (result.missing.length) throw new Error(`tabelas ausentes: ${result.missing.join(', ')}`);
    return { ok: true, counts: result.counts, integrity: result.integrity };
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
}

/** Tenta os backups mais recentes, do mais novo para o mais antigo. */
function drillLocal(outDir, { maxAttempts = 3 } = {}) {
  const list = candidates(outDir);
  if (!list.length) return { ok: false, error: 'nenhum backup válido', attempts: 0 };
  const attempts = [];
  for (const item of list.slice(0, maxAttempts)) {
    try {
      const result = drill(item.path, { checksum: item.sha256 });
      attempts.push({ file: item.file, ok: true });
      return { ok: true, file: item.file, counts: result.counts, attempts };
    } catch (error) {
      attempts.push({ file: item.file, ok: false, error: error.message });
    }
  }
  return { ok: false, error: 'todos os backups testados falharam', attempts };
}

async function drillOffsite(key, cfg = offsite.config()) {
  const transport = offsite.createTransport(cfg);
  if (!transport) throw new Error('off-site desabilitado');
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'saden-offsite-'));
  const restored = path.join(tmpDir, 'restored.db');
  try {
    const pulled = await offsite.pull({ key, outPath: restored, cfg, transport, expectedSha256: sha256 });
    const result = drill(restored);
    return { ...result, bytes: pulled.bytes, sha256: pulled.sha256, envelope_sha256: pulled.envelopeSha256 };
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
}

async function main() {
  const argv = process.argv.slice(2);
  const opt = (name) => {
    const i = argv.indexOf(name);
    return i >= 0 ? argv[i + 1] : null;
  };
  const outDir = opt('--out-dir') || process.env.SADEN_BACKUP_DIR || path.join(__dirname, '..', '..', 'data', 'backups');

  try {
    if (opt('--from-offsite')) {
      const result = await drillOffsite(opt('--from-offsite'), { sha256: opt('--sha256') });
      process.stdout.write(`${JSON.stringify({ at: new Date().toISOString(), event: 'drill_offsite', ...result })}\n`);
      process.exitCode = result.ok ? 0 : 1;
      return;
    }
    const result = drillLocal(outDir);
    process.stdout.write(
      `${JSON.stringify({ at: new Date().toISOString(), event: 'drill_local', ...result, out_dir: path.basename(outDir) })}\n`
    );
    process.exitCode = result.ok ? 0 : 1;
  } catch (error) {
    process.stdout.write(`${JSON.stringify({ at: new Date().toISOString(), event: 'drill_failed', error: error.message })}\n`);
    process.exitCode = 1;
  }
}

if (require.main === module) main();

module.exports = { drill, drillLocal, drillOffsite, verifyDatabase, candidates };
