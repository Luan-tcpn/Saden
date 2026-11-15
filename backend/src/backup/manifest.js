'use strict';

// Manifesto e estado de saúde dos backups (Release 1.2.2).
//
// Cada backup tem um sidecar `<nome>.json` gravado **depois** de o banco ser
// validado e renomeado. O manifesto é a fonte de verdade para o healthcheck:
// arquivo existir não basta, precisa ter manifesto com `status: ok`.
//
// Estados (usados pelo container e pela API):
//   ok       — último backup validado e recente
//   stale    — último válido passou da janela (24 h + tolerância)
//   failed   — a última tentativa falhou (existe registro, mas sem sucesso novo)
//   invalid  — manifesto existe, mas o arquivo não confere
//   missing  — nenhum backup conhecido

const fs = require('fs');
const path = require('path');

const MANIFEST_VERSION = 1;
const DEFAULT_MAX_AGE_HOURS = 30; // 24 h de ciclo + 6 h de tolerância

function manifestPathFor(file) {
  return file.replace(/\.db$/, '') + '.json';
}

function writeManifest(file, payload) {
  const target = manifestPathFor(file);
  const manifest = {
    version: MANIFEST_VERSION,
    file: path.basename(file),
    ...payload,
    written_at: new Date().toISOString(),
  };
  fs.writeFileSync(target, `${JSON.stringify(manifest, null, 2)}\n`, { mode: 0o600 });
  return manifest;
}

function readManifest(file) {
  const target = manifestPathFor(file);
  try {
    return JSON.parse(fs.readFileSync(target, 'utf8'));
  } catch {
    return null;
  }
}

function listManifests(outDir) {
  if (!fs.existsSync(outDir)) return [];
  return fs
    .readdirSync(outDir)
    .filter((name) => /^saden-\d{8}-\d{6}\.json$/.test(name))
    .map((name) => ({ path: path.join(outDir, name), manifest: JSON.parse(fs.readFileSync(path.join(outDir, name), 'utf8')) }))
    .sort((a, b) => b.manifest.file.localeCompare(a.manifest.file));
}

/** Registra a última tentativa (sucesso ou falha) sem criar arquivo falso. */
function recordAttempt(outDir, { status, error = null, file = null, at = new Date().toISOString() }) {
  const target = path.join(outDir, '.last-attempt.json');
  const payload = { status, error, file, at };
  try {
    fs.mkdirSync(outDir, { recursive: true });
    fs.writeFileSync(target, `${JSON.stringify(payload, null, 2)}\n`, { mode: 0o600 });
  } catch {
    /* registro é auxiliar: não pode derrubar o backup */
  }
  return payload;
}

function readAttempt(outDir) {
  try {
    return JSON.parse(fs.readFileSync(path.join(outDir, '.last-attempt.json'), 'utf8'));
  } catch {
    return null;
  }
}

/**
 * Avalia a saúde a partir do manifesto mais recente.
 * @returns {{status:string, age_ms:number|null, detail:string, last_ok_at:string|null}}
 */
function assess({ outDir, now = Date.now(), maxAgeHours = DEFAULT_MAX_AGE_HOURS } = {}) {
  const maxAgeMs = maxAgeHours * 3600 * 1000;
  let items;
  try {
    items = listManifests(outDir);
  } catch {
    return { status: 'missing', age_ms: null, detail: 'diretorio_ilegivel', last_ok_at: null };
  }
  if (!items.length) return { status: 'missing', age_ms: null, detail: 'sem_manifesto', last_ok_at: null };

  const latest = items[0].manifest;
  const latestPath = path.join(outDir, latest.file);
  const exists = fs.existsSync(latestPath);
  const age = latest.created_at ? now - new Date(latest.created_at).getTime() : null;

  // Uma tentativa que falhou depois do último sucesso é informação operacional:
  // o container não pode parecer saudável só porque ontem deu certo.
  const attempt = readAttempt(outDir);
  const attemptNewer =
    attempt && attempt.status !== 'ok' && (!latest.created_at || new Date(attempt.at) > new Date(latest.created_at));

  if (latest.status !== 'ok') {
    return { status: 'failed', age_ms: age, detail: latest.error || 'ultima_tentativa_falhou', last_ok_at: latest.created_at || null };
  }
  if (attemptNewer) {
    return { status: 'failed', age_ms: age, detail: attempt.error || 'ultima_tentativa_falhou', last_ok_at: latest.created_at };
  }
  if (!exists) {
    return { status: 'invalid', age_ms: age, detail: 'arquivo_ausente', last_ok_at: null };
  }
  const size = fs.statSync(latestPath).size;
  if (latest.size != null && size !== latest.size) {
    return { status: 'invalid', age_ms: age, detail: 'tamanho_divergente', last_ok_at: null };
  }
  if (age == null || age > maxAgeMs) {
    return { status: 'stale', age_ms: age, detail: 'backup_atrasado', last_ok_at: latest.created_at || null };
  }
  return { status: 'ok', age_ms: age, detail: 'backup_recente', last_ok_at: latest.created_at };
}

module.exports = {
  MANIFEST_VERSION,
  DEFAULT_MAX_AGE_HOURS,
  manifestPathFor,
  writeManifest,
  readManifest,
  listManifests,
  recordAttempt,
  readAttempt,
  assess,
};
