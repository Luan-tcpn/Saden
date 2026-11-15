'use strict';

// Backup verificável do SQLite (Release 1.2.1).
//
// Por que não `cp`: o SADEN roda em WAL, com web e worker escrevendo. Copiar o
// arquivo principal pode capturar uma página em trânsito. `VACUUM INTO` produz
// um banco consistente a partir de uma transação de leitura.
//
// Garantias:
// - o backup só recebe o nome final depois de validado (nada de arquivo
//   incompleto parecendo bom);
// - `PRAGMA integrity_check` + tabelas obrigatórias + contagens;
// - retenção só remove depois que o novo backup foi validado;
// - falha não destrói backups anteriores;
// - log em JSON sem caminhos sensíveis de terceiros e sem dados de usuário.

const fs = require('fs');
const path = require('path');
const Database = require('better-sqlite3');
const cryptoLib = require('../src/backup/crypto');
const manifestLib = require('../src/backup/manifest');
const offsite = require('../src/backup/offsite');
const monitor = require('../src/worker/monitor');

// Tabelas que precisam existir em qualquer backup válido do SADEN.
// Nota: o projeto não mantém tabela de migrações — o schema é aplicado por DDL
// idempotente (`CREATE TABLE IF NOT EXISTS`) em `db.js`. A validação usa a
// presença das tabelas centrais como impressão digital do schema.
const TABLES = ['users', 'alerts', 'alert_events', 'price_observations', 'series_state'];

const DEFAULT_RETENTION = 14;

function timestamp(date = new Date()) {
  const pad = (n) => String(n).padStart(2, '0');
  return (
    `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}-` +
    `${pad(date.getHours())}${pad(date.getMinutes())}${pad(date.getSeconds())}`
  );
}

function log(entry) {
  process.stdout.write(`${JSON.stringify({ at: new Date().toISOString(), ...entry })}\n`);
}

/** Valida um arquivo de backup. Lança com motivo claro quando inválido. */
function validateBackup(file, { expectData = true } = {}) {
  if (!fs.existsSync(file)) throw new Error('arquivo de backup não existe');
  const size = fs.statSync(file).size;
  if (size === 0) throw new Error('arquivo de backup vazio');

  let db;
  try {
    db = new Database(file, { readonly: true, fileMustExist: true });
  } catch (error) {
    throw new Error(`não é um banco SQLite legível: ${error.message}`);
  }

  try {
    let integrity;
    let present;
    try {
      integrity = db.pragma('integrity_check', { simple: true });
      present = new Set(
        db.prepare("SELECT name FROM sqlite_master WHERE type = 'table'").all().map((row) => row.name)
      );
    } catch (error) {
      // better-sqlite3 abre qualquer arquivo; o erro real aparece na primeira
      // leitura. Aqui ele fica com a mesma mensagem do caso de abertura.
      throw new Error(`não é um banco SQLite legível: ${error.message}`);
    }

    if (integrity !== 'ok') throw new Error(`integrity_check falhou: ${integrity}`);

    const missing = TABLES.filter((table) => !present.has(table));
    if (missing.length) throw new Error(`tabelas ausentes: ${missing.join(', ')}`);

    const counts = {
      users: db.prepare('SELECT COUNT(*) n FROM users').get().n,
      alerts: db.prepare('SELECT COUNT(*) n FROM alerts').get().n,
      events: db.prepare('SELECT COUNT(*) n FROM alert_events').get().n,
      observations: db.prepare('SELECT COUNT(*) n FROM price_observations').get().n,
    };
    if (expectData && counts.users === 0 && counts.observations === 0) {
      // Banco vazio é válido (instalação nova), mas merece registro.
      return { ok: true, size, counts, integrity, empty: true };
    }

    return { ok: true, size, counts, integrity, empty: false };
  } finally {
    db.close();
  }
}

function listBackups(outDir) {
  if (!fs.existsSync(outDir)) return [];
  return fs
    .readdirSync(outDir)
    .filter((name) => /^saden-\d{8}-\d{6}\.db$/.test(name))
    .map((name) => {
      const full = path.join(outDir, name);
      return { name, path: full, size: fs.statSync(full).size, mtimeMs: fs.statSync(full).mtimeMs };
    })
    .sort((a, b) => b.name.localeCompare(a.name));
}

/**
 * Cria um backup. Retorna descritor; lança em falha (após limpar o parcial).
 */
function createBackup({
  dbPath,
  outDir,
  retention = DEFAULT_RETENTION,
  date = new Date(),
  keepPartialOnError = false,
} = {}) {
  if (!dbPath || !fs.existsSync(dbPath)) throw new Error(`banco não encontrado: ${dbPath || '(vazio)'}`);
  fs.mkdirSync(outDir, { recursive: true });

  const base = `saden-${timestamp(date)}`;
  const target = path.join(outDir, `${base}.db`);
  // Parcial único por processo: dois backups iniciados no mesmo segundo não
  // podem compartilhar o mesmo arquivo temporário. Sem isso, um processo apaga
  // o parcial do outro (`rmSync` inicial) e o backup alheio falha com EBUSY.
  const partial = path.join(outDir, `.${base}.${process.pid}-${Math.random().toString(36).slice(2, 8)}.partial.db`);

  // Um arquivo parcial nunca é sobrescrito silenciosamente.
  if (fs.existsSync(target)) throw new Error('já existe backup com este carimbo de tempo');

  fs.rmSync(partial, { force: true });
  const source = new Database(dbPath, { readonly: true, fileMustExist: true });
  try {
    source.prepare('VACUUM INTO ?').run(partial);
  } catch (error) {
    source.close();
    if (!keepPartialOnError) fs.rmSync(partial, { force: true });
    throw new Error(`VACUUM INTO falhou: ${error.message}`);
  }
  source.close();

  let validation;
  try {
    validation = validateBackup(partial);
  } catch (error) {
    fs.rmSync(partial, { force: true });
    throw new Error(`backup inválido, descartado: ${error.message}`);
  }

  // Só agora o arquivo passa a existir com o nome definitivo.
  fs.renameSync(partial, target);
  const stored = fs.statSync(target);
  if (stored.size !== validation.size) {
    throw new Error('tamanho divergente após renomear');
  }

  // Checksum e manifesto: o healthcheck confia no manifesto, não na existência
  // do arquivo. Ambos são gravados antes de qualquer poda.
  const sha256 = cryptoLib.checksumFile(target);
  const manifest = manifestLib.writeManifest(target, {
    status: 'ok',
    created_at: date.toISOString(),
    size: stored.size,
    sha256,
    counts: validation.counts,
    integrity: validation.integrity,
    source: path.basename(dbPath),
  });

  const removed = prune(outDir, retention, target);
  return {
    ok: true,
    file: target,
    name: path.basename(target),
    size: stored.size,
    sha256,
    counts: validation.counts,
    integrity: validation.integrity,
    manifest,
    retention,
    removed,
  };
}

/** Remove os backups mais antigos (e o manifesto correspondente). */
function prune(outDir, keep, protectedPath) {
  const retention = Number.isFinite(keep) && keep > 0 ? Math.floor(keep) : DEFAULT_RETENTION;
  const backups = listBackups(outDir);
  const removed = [];
  if (backups.length <= retention) return removed;

  const losers = backups.slice(retention);
  for (const item of losers) {
    if (protectedPath && item.path === protectedPath) continue;
    try {
      fs.rmSync(item.path);
      fs.rmSync(manifestLib.manifestPathFor(item.path), { force: true });
      removed.push(item.name);
    } catch {
      // Falha ao remover não invalida o backup recém-criado.
    }
  }
  return removed;
}

/**
 * Envia o backup recém-validado para o destino off-site, se configurado.
 * Falha do destino não desfaz nem invalida o backup local.
 */
async function ship(result, { cfg = offsite.config(), transport } = {}) {
  if (!cfg.enabled) return { status: 'disabled' };
  const sent = await offsite.push({ file: result.file, cfg, transport });
  if (sent.status !== 'ok') {
    manifestLib.writeManifest(result.file, {
      ...result.manifest,
      offsite: { status: 'error', reason: sent.reason, at: new Date().toISOString() },
    });
    return sent;
  }
  const pruned = await offsite.prune({ keep: cfg.retention, cfg, transport });
  manifestLib.writeManifest(result.file, {
    ...result.manifest,
    offsite: {
      status: 'ok',
      key: sent.key,
      bytes: sent.bytes,
      sha256: sent.sha256,
      encrypted: sent.encrypted,
      transport: sent.transport,
      pruned: pruned.removed || [],
      at: new Date().toISOString(),
    },
  });
  return sent;
}

function parseArgs(argv) {
  const args = { retention: Number(process.env.SADEN_BACKUP_RETENTION) || DEFAULT_RETENTION };
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '--db') args.dbPath = argv[++i];
    else if (arg === '--out-dir') args.outDir = argv[++i];
    else if (arg === '--retention') args.retention = Number(argv[++i]);
    else if (arg === '--verify') args.verify = argv[++i];
    else if (arg === '--list') args.list = true;
    else if (arg === '--no-offsite') args.noOffsite = true;
    else if (arg === '--help' || arg === '-h') args.help = true;
  }
  return args;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    console.log(
      [
        'uso: node scripts/backup.js [--db <arquivo>] [--out-dir <dir>] [--retention <n>] [--no-offsite]',
        '     node scripts/backup.js --verify <arquivo>',
        '     node scripts/backup.js --list --out-dir <dir>',
      ].join('\n')
    );
    return;
  }

  if (args.verify) {
    const result = validateBackup(args.verify);
    log({ event: 'backup_verified', file: path.basename(args.verify), ...result });
    return;
  }

  if (args.list) {
    const dir = args.outDir || process.env.SADEN_BACKUP_DIR || path.join(__dirname, '..', '..', 'data', 'backups');
    const items = listBackups(dir);
    log({ event: 'backup_list', count: items.length, items, health: manifestLib.assess({ outDir: dir }) });
    return;
  }

  const dbPath = args.dbPath || process.env.DATABASE_PATH || path.join(__dirname, '..', '..', 'data', 'saden.db');
  const outDir = args.outDir || process.env.SADEN_BACKUP_DIR || path.join(__dirname, '..', '..', 'data', 'backups');

  // Monitor próprio do backup: identificador **diferente** do worker.
  const monitorBase = process.env.SADEN_BACKUP_MONITOR_PING_URL || '';
  const started = await monitor.ping('start', { base: monitorBase });

  try {
    const result = createBackup({ dbPath, outDir, retention: args.retention });
    const sent = args.noOffsite ? { status: 'disabled' } : await ship(result);
    manifestLib.recordAttempt(outDir, { status: 'ok', file: result.name });

    // Sucesso só depois de: VACUUM, validação, checksum, manifesto e envio.
    const finished = await monitor.ping('success', { base: monitorBase });
    log({
      event: 'backup_ok',
      file: result.name,
      size: result.size,
      sha256: result.sha256,
      counts: result.counts,
      integrity: result.integrity,
      removed: result.removed,
      offsite: { status: sent.status, reason: sent.reason || null, encrypted: sent.encrypted || false },
      monitor: { start: monitor.describe(started), end: monitor.describe(finished) },
    });
  } catch (error) {
    manifestLib.recordAttempt(outDir, { status: 'failed', error: error.message });
    await monitor.ping('fail', { base: monitorBase });
    log({ event: 'backup_failed', error: error.message });
    process.exitCode = 1;
  }
}

if (require.main === module) main();

module.exports = {
  createBackup,
  validateBackup,
  listBackups,
  prune,
  ship,
  timestamp,
  TABLES,
  DEFAULT_RETENTION,
};
