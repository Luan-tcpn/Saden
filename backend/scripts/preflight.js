'use strict';

// Preflight de runtime (fechamento operacional da v1.2.0).
//
// Por que existe: `npm start` com um Node fora da linha suportada falhava com
// `ERR_DLOPEN_FAILED` / `NODE_MODULE_VERSION` vindo de dentro do binário nativo
// do better-sqlite3 — mensagem que não diz o que fazer. Aqui a falha é
// detectada antes, com diagnóstico e comando exato.
//
// Roda como `prestart`, `predev` e `pretest`.

const path = require('path');
const fs = require('fs');

const SUPPORTED_MAJOR = 22;
const SUPPORTED_ABI = '127';

/**
 * Decide se o runtime é aceitável. Função pura para poder ser testada sem
 * trocar o Node da máquina.
 * @returns {{ok: boolean, reason: string|null, detail: object}}
 */
function checkRuntime({ major, abi }) {
  if (Number(major) !== SUPPORTED_MAJOR) {
    return {
      ok: false,
      reason: 'unsupported_node',
      detail: { expectedMajor: SUPPORTED_MAJOR, expectedAbi: SUPPORTED_ABI, major, abi },
    };
  }
  return { ok: true, reason: null, detail: { expectedMajor: SUPPORTED_MAJOR, expectedAbi: SUPPORTED_ABI, major, abi } };
}

function isAbiError(message) {
  return /NODE_MODULE_VERSION|ERR_DLOPEN_FAILED|was compiled against a different/i.test(String(message || ''));
}

function instructions(lines) {
  // eslint-disable-next-line no-console
  for (const line of lines) console.error('  ' + line);
}

function run() {
  const major = Number(process.versions.node.split('.')[0]);
  const abi = process.versions.modules;
  const verdict = checkRuntime({ major, abi });

  if (!verdict.ok) {
    console.error('');
    console.error(`  [SADEN] Node.js ${process.version} não é suportado por este projeto.`);
    instructions([
      'Este projeto usa um módulo nativo (better-sqlite3) e foi padronizado em Node 22.',
      `Node atual: ${process.versions.node} (ABI ${abi}) · esperado: ${SUPPORTED_MAJOR} (ABI ${SUPPORTED_ABI}).`,
      '',
      'Como corrigir:',
      '  nvm use                    # lê o .nvmrc (22.14.0)',
      '  cd backend && npm ci       # reinstala o binário para a ABI correta',
      '',
      'Não rode `npm rebuild` com o Node errado: o binário seria recompilado para a ABI errada.',
    ]);
    console.error('');
    process.exit(1);
  }

  const modulePath = path.join(__dirname, '..', 'node_modules', 'better-sqlite3');
  if (!fs.existsSync(modulePath)) {
    console.error('');
    console.error('  [SADEN] Dependências não instaladas.');
    instructions(['Rode: cd backend && npm ci']);
    console.error('');
    process.exit(1);
  }

  try {
    // eslint-disable-next-line global-require
    const Database = require('better-sqlite3');
    const db = new Database(':memory:');
    db.exec('CREATE TABLE preflight(a INTEGER)');
    db.close();
  } catch (error) {
    console.error('');
    if (isAbiError(error.message)) {
      console.error('  [SADEN] Módulo nativo incompatível com este runtime (ABI).');
      instructions([
        `Node atual: ${process.versions.node} (ABI ${abi}).`,
        'O binário do better-sqlite3 foi compilado para outra ABI.',
        '',
        'Como corrigir:',
        '  nvm use                    # Node 22',
        '  cd backend && npm ci       # reinstala o binário para a ABI correta',
      ]);
    } else {
      console.error('  [SADEN] Falha ao carregar better-sqlite3.');
      instructions([String(error.message).split('\n')[0], 'Rode: cd backend && npm ci']);
    }
    console.error('');
    process.exit(1);
  }

  // eslint-disable-next-line no-console
  console.log(`[SADEN] runtime ok: Node ${process.version} (ABI ${abi})`);
}

if (require.main === module) run();

module.exports = { checkRuntime, isAbiError, SUPPORTED_MAJOR, SUPPORTED_ABI };
