'use strict';
// Backup online do SQLite do SADEN (operacional, aditivo, reversível).
// Uso: node scripts/backup.js [destDir]  (padrão: tmp/backups)
// - Respeita DATABASE_PATH (absoluto ou relativo à raiz do projeto).
// - Usa Database#backup (cópia online consistente, inclui WAL; sem travar escrita).
// - Mantém os 7 backups mais recentes, remove os antigos.
// - Restauração: parar o backend e copiar o arquivo de volta para data/saden.db
//   (ver README, seção Persistência). NÃO versionar backups (tmp/ é ignorado).
// - Sem D-number: tooling operacional, não muda arquitetura nem API.
const fs = require('fs');
const path = require('path');
const Database = require(path.join(__dirname, '..', 'backend', 'node_modules', 'better-sqlite3'));

const ROOT = path.join(__dirname, '..');
const KEEP_DEFAULT = 7;

function resolveDbPath() {
  const raw = process.env.DATABASE_PATH || 'data/saden.db';
  return path.isAbsolute(raw) ? raw : path.join(ROOT, raw);
}

function defaultDestDir() {
  return path.join(ROOT, 'tmp', 'backups');
}

function stamp(date = new Date()) {
  return date.toISOString().replace(/[-:]/g, '').slice(0, 15); // AAAAMMDDTHHMMSS
}

function listBackups(destDir) {
  if (!fs.existsSync(destDir)) return [];
  return fs
    .readdirSync(destDir)
    .filter((f) => /^saden-\d{8}T\d{6}\.db$/.test(f))
    .sort()
    .map((f) => path.join(destDir, f));
}

async function backup(dbPath = resolveDbPath(), destDir = defaultDestDir(), keep = KEEP_DEFAULT) {
  if (!fs.existsSync(dbPath)) {
    throw Object.assign(new Error(`Banco não encontrado: ${dbPath}`), { status: 1 });
  }
  fs.mkdirSync(destDir, { recursive: true });
  const file = path.join(destDir, `saden-${stamp()}.db`);
  // better-sqlite3 backup() retorna Promise (cópia online consistente, inclui WAL).
  const handle = new Database(dbPath, { readonly: true });
  try {
    await handle.backup(file);
  } finally {
    handle.close();
  }
  const kept = listBackups(destDir);
  const removed = kept.length > keep ? kept.slice(0, kept.length - keep) : [];
  for (const f of removed) fs.unlinkSync(f);
  const stat = fs.statSync(file);
  return { file, bytes: stat.size, kept: listBackups(destDir), removed };
}

if (require.main === module) {
  const destDir = process.argv[2] ? path.resolve(process.argv[2]) : defaultDestDir();
  backup(resolveDbPath(), destDir, KEEP_DEFAULT).then(
    (out) => console.log(JSON.stringify({ ok: true, file: out.file, bytes: out.bytes, kept: out.kept.length })),
    (e) => {
      console.error(JSON.stringify({ ok: false, message: e.message }));
      process.exit(1);
    }
  );
}

module.exports = { backup, listBackups, resolveDbPath, defaultDestDir, KEEP_DEFAULT };
