'use strict';

// Healthcheck do serviço de backup (Release 1.2.2).
//
// Não basta o processo estar vivo: o container só é saudável se existir um
// backup **validado e recente**. Um container que roda há dias sem produzir
// backup é exatamente o caso que isto precisa reprovar.

const path = require('path');
const manifest = require('../src/backup/manifest');

const outDir =
  process.env.SADEN_BACKUP_DIR || path.join(__dirname, '..', '..', 'data', 'backups');
const maxAgeHours = Number(process.env.SADEN_BACKUP_MAX_AGE_HOURS) || manifest.DEFAULT_MAX_AGE_HOURS;

const result = manifest.assess({ outDir, maxAgeHours });
const healthy = result.status === 'ok';

const payload = {
  at: new Date().toISOString(),
  kind: 'backup-health',
  status: result.status,
  detail: result.detail,
  last_ok_at: result.last_ok_at,
  age_hours: result.age_ms == null ? null : Number((result.age_ms / 3600000).toFixed(1)),
  max_age_hours: maxAgeHours,
};

// stdout é lido pelo Docker nos logs; o código de saída é o veredito.
process.stdout.write(`${JSON.stringify(payload)}\n`);
process.exit(healthy ? 0 : 1);
