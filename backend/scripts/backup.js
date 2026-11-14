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
  const partial = path.join(outDir, `.${base}.partial.db`);

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

  const removed = prune(outDir, retention, target);
  return {
    ok: true,
    file: target,
    name: path.basename(target),
    size: stored.size,
    counts: validation.counts,
    integrity: validation.integrity,
    retention,
    removed,
  };
}

/** Remove os backups mais antigos, preservando `keep` (inclui o recém-criado). */
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
      removed.push(item.name);
    } catch {
      // Falha ao remover não invalida o backup recém-criado.
    }
  }
  return removed;
}

function parseArgs(argv) {
  const args = { retention: Number(process.env.SADEN_BACKUP_RETENTION) || DEFAULT_RETENTION };
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '--db') args.dbPath = argv[++i];
    else if (arg === '--out-dir') args.outDir = argv[++i];
    else if (arg === '--retention') args.retention = Number(argv[++i]);
    else if (arg === '--verify') args.verify = argv[++i];
    else if (arg === '--list') args.list = args.outDir;
    else if (arg === '--help' || arg === '-h') args.help = true;
  }
  return args;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    console.log(
      [
        'uso: node scripts/backup.js [--db <arquivo>] [--out-dir <dir>] [--retention <n>]',
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
    log({ event: 'backup_list', count: listBackups(args.list).length, items: listBackups(args.list) });
    return;
  }

  const dbPath = args.dbPath || process.env.DATABASE_PATH || path.join(__dirname, '..', '..', 'data', 'saden.db');
  const outDir = args.outDir || process.env.SADEN_BACKUP_DIR || path.join(__dirname, '..', '..', 'data', 'backups');

  try {
    const result = createBackup({ dbPath, outDir, retention: args.retention });
    log({ event: 'backup_ok', ...result, file: path.basename(result.file) });
  } catch (error) {
    log({ event: 'backup_failed', error: error.message });
    process.exitCode = 1;
  }
}

if (require.main === module) main();

module.exports = { createBackup, validateBackup, listBackups, prune, timestamp, TABLES, DEFAULT_RETENTION };
