'use strict';

// Verificação ponta a ponta do off-site (Release 1.2.3).
//
// Roda o ciclo completo contra o destino configurado e prova, ou não, que a
// cópia remota é restaurável. É o teste obrigatório antes de confiar no off-site.
//
// uso:
//   node backend/scripts/offsite-verify.js [--db data/saden.db] [--work-dir /tmp/x]
//
// Só grava em diretório temporário; não toca no banco de produção.
// Sai com código 1 se qualquer etapa falhar.

const fs = require('fs');
const os = require('os');
const path = require('path');
const backup = require('./backup');
const offsite = require('../src/backup/offsite');
const drill = require('./restore-drill');

function opt(argv, name) {
  const i = argv.indexOf(name);
  return i >= 0 ? argv[i + 1] : null;
}

async function main() {
  const argv = process.argv.slice(2);
  const dbPath = opt(argv, '--db') || process.env.DATABASE_PATH || path.join(__dirname, '..', '..', 'data', 'saden.db');
  const workDir = fs.mkdtempSync(path.join(os.tmpdir(), 'saden-offsite-verify-'));
  const steps = [];
  const cfg = offsite.config();

  const record = (name, ok, detail = null) => {
    steps.push({ step: name, ok, detail });
    if (!ok) throw Object.assign(new Error(`falhou: ${name}`), { steps });
  };

  try {
    if (!cfg.enabled) {
      record('configuracao', false, `off-site desabilitado (mode=${cfg.mode})`);
    }
    if (!cfg.encrypted) {
      record('criptografia', false, 'SADEN_BACKUP_ENCRYPT=0 — recusado para produção');
    }
    record('configuracao', true, { mode: cfg.mode, transport: cfg.mode, retention: cfg.retention });

    // 1. backup local validado
    const created = backup.createBackup({ dbPath, outDir: workDir, retention: 5 });
    record('backup_local', created.integrity === 'ok', { size: created.size, sha256: created.sha256.slice(0, 12) });

    // 2. upload
    const transport = offsite.createTransport(cfg);
    const sent = await offsite.push({ file: created.file, cfg, transport });
    record('upload', sent.status === 'ok', { bytes: sent.bytes, key_sha: String(sent.key).slice(-12) });

    // 3. download + checksum do envelope + decifra
    const pulled = await offsite.pull({
      key: sent.key,
      outPath: path.join(workDir, 'restored.db'),
      cfg,
      transport,
      expectedSha256: sent.sha256,
    });
    record('download_e_checksum', pulled.sha256 === created.sha256, { bytes: pulled.bytes });

    // 4. restauração verificada
    const restored = drill.drill(path.join(workDir, 'restored.db'), { checksum: created.sha256 });
    record('restauracao', restored.ok === true, { counts: restored.counts });

    // 5. chave errada deve falhar
    let rejected = false;
    try {
      await offsite.pull({
        key: sent.key,
        outPath: path.join(workDir, 'wrong.db'),
        cfg: { ...cfg, passphrase: 'chave-errada-de-proposito-999' },
        transport,
      });
    } catch {
      rejected = true;
    }
    record('chave_errada_rejeitada', rejected && !fs.existsSync(path.join(workDir, 'wrong.db')));

    // 6. checksum divergente deve falhar
    let checksumRejected = false;
    try {
      await offsite.pull({
        key: sent.key,
        outPath: path.join(workDir, 'bad-checksum.db'),
        cfg,
        transport,
        expectedSha256: 'a'.repeat(64),
      });
    } catch {
      checksumRejected = true;
    }
    record('checksum_divergente_rejeitado', checksumRejected);

    // 7. objeto inexistente deve falhar
    let missingRejected = false;
    try {
      await offsite.pull({ key: 'nao-existe-' + Date.now() + '.db.enc', outPath: path.join(workDir, 'x.db'), cfg, transport });
    } catch {
      missingRejected = true;
    }
    record('objeto_inexistente_rejeitado', missingRejected);

    process.stdout.write(
      `${JSON.stringify({ event: 'offsite_verify', ok: true, mode: cfg.mode, steps }, null, 2)}\n`
    );
  } catch (error) {
    process.stdout.write(
      `${JSON.stringify({ event: 'offsite_verify', ok: false, error: error.message, steps }, null, 2)}\n`
    );
    process.exitCode = 1;
  } finally {
    fs.rmSync(workDir, { recursive: true, force: true });
  }
}

if (require.main === module) main();

module.exports = { main };
