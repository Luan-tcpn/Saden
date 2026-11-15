'use strict';

// Envio off-site dos backups (Release 1.2.2).
//
// Dois transportes, mesma interface:
//   dir  — diretório espelhado (testes e simulação de desastre local)
//   s3   — destino compatível com S3 (Backblaze B2, Cloudflare R2, MinIO, AWS)
//
// Regras que não mudam entre transportes:
// - só envia **depois** de o backup local estar validado;
// - cifra antes de sair do host (src/backup/crypto.js);
// - confirma o objeto remoto (tamanho) antes de declarar sucesso;
// - sem credenciais, tudo fica desabilitado e o backup local segue normal;
// - nenhuma chave ou URL assinada é logada.

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const { encryptBuffer, decryptBuffer, checksumBuffer } = require('./crypto');

/* ------------------------------- configuração ------------------------------ */

function config(env = process.env) {
  const mode = String(env.SADEN_OFFSITE_MODE || '').trim().toLowerCase();
  const common = {
    encrypted: String(env.SADEN_BACKUP_ENCRYPT || '1') !== '0',
    retention: Number(env.SADEN_OFFSITE_RETENTION) || 14,
    passphrase: env.SADEN_BACKUP_PASSPHRASE || '',
  };

  if (!mode || mode === 'disabled' || mode === 'none') {
    return { mode: 'disabled', enabled: false, ...common };
  }

  if (mode === 'dir') {
    const dir = String(env.SADEN_OFFSITE_DIR || '').trim();
    return { mode: dir ? 'dir' : 'disabled', enabled: Boolean(dir), dir, ...common };
  }

  if (mode === 's3') {
    const bucket = String(env.SADEN_S3_BUCKET || '').trim();
    const endpoint = String(env.SADEN_S3_ENDPOINT || '').trim();
    const accessKey = String(env.SADEN_S3_ACCESS_KEY || '').trim();
    const secretKey = String(env.SADEN_S3_SECRET_KEY || '').trim();
    const enabled = Boolean(bucket && endpoint && accessKey && secretKey);
    return {
      mode: enabled ? 's3' : 'disabled',
      enabled,
      bucket,
      endpoint,
      region: String(env.SADEN_S3_REGION || 'us-east-1').trim(),
      accessKey,
      secretKey,
      prefix: String(env.SADEN_S3_PREFIX || 'saden/backups').replace(/^\/+|\/+$/g, ''),
      ...common,
    };
  }

  return { mode: 'disabled', enabled: false, ...common };
}

/* --------------------------------- dir ------------------------------------- */

function dirTransport(dir) {
  fs.mkdirSync(dir, { recursive: true });
  const resolve = (key) => {
    const safe = path.basename(String(key));
    if (safe !== key) throw new Error('nome de objeto inválido');
    return path.join(dir, safe);
  };
  return {
    name: 'dir',
    async put(key, buffer) {
      fs.writeFileSync(resolve(key), buffer, { mode: 0o600 });
    },
    async get(key) {
      return fs.readFileSync(resolve(key));
    },
    async head(key) {
      try {
        return { size: fs.statSync(resolve(key)).size };
      } catch {
        return null;
      }
    },
    async list() {
      if (!fs.existsSync(dir)) return [];
      return fs
        .readdirSync(dir)
        .filter((name) => name.endsWith('.enc'))
        .map((name) => ({ key: name, size: fs.statSync(resolve(name)).size }))
        .sort((a, b) => b.key.localeCompare(a.key));
    },
    async remove(key) {
      fs.rmSync(resolve(key), { force: true });
    },
  };
}

/* ---------------------------------- S3 ------------------------------------- */

function hmac(key, data) {
  return crypto.createHmac('sha256', key).update(data).digest();
}

function sha256Hex(data) {
  return crypto.createHash('sha256').update(data).digest('hex');
}

function encodeRfc3986(value) {
  return encodeURIComponent(value).replace(/[!'()*]/g, (c) => `%${c.charCodeAt(0).toString(16).toUpperCase()}`);
}

/** Assinatura SigV4 mínima para PUT/GET/HEAD/DELETE em bucket path-style. */
function signV4({ method, url, payloadHash, accessKey, secretKey, region, extraHeaders = {} }) {
  const u = new URL(url);
  const now = new Date();
  const stamp = now.toISOString().replace(/[:-]|\.\d{3}/g, '');
  const date = stamp.slice(0, 8);

  const headers = {
    host: u.host,
    'x-amz-content-sha256': payloadHash,
    'x-amz-date': stamp,
    ...extraHeaders,
  };
  const sortedKeys = Object.keys(headers)
    .map((k) => k.toLowerCase())
    .sort();
  const canonicalHeaders = sortedKeys.map((k) => `${k}:${String(headers[k]).trim()}\n`).join('');
  const signedHeaders = sortedKeys.join(';');
  const canonicalUri = u.pathname.split('/').map(encodeRfc3986).join('/').replace(/%2F/g, '/');
  const canonicalQuery = [...u.searchParams.entries()]
    .sort(([a], [b]) => (a === b ? 0 : a < b ? -1 : 1))
    .map(([k, v]) => `${encodeRfc3986(k)}=${encodeRfc3986(v)}`)
    .join('&');

  const canonicalRequest = [
    method,
    canonicalUri,
    canonicalQuery,
    canonicalHeaders,
    signedHeaders,
    payloadHash,
  ].join('\n');

  const scope = `${date}/${region}/s3/aws4_request`;
  const stringToSign = ['AWS4-HMAC-SHA256', stamp, scope, sha256Hex(canonicalRequest)].join('\n');
  const kDate = hmac(`AWS4${secretKey}`, date);
  const kRegion = hmac(kDate, region);
  const kService = hmac(kRegion, 's3');
  const kSigning = hmac(kService, 'aws4_request');
  const signature = crypto.createHmac('sha256', kSigning).update(stringToSign).digest('hex');

  return {
    ...headers,
    Authorization: `AWS4-HMAC-SHA256 Credential=${accessKey}/${scope}, SignedHeaders=${signedHeaders}, Signature=${signature}`,
  };
}

function s3Transport(cfg) {
  const endpoint = cfg.endpoint.replace(/\/+$/, '');
  const objectKey = (key) => [cfg.prefix, String(key)].filter(Boolean).join('/');
  const objectUrl = (key) =>
    `${endpoint}/${encodeRfc3986(cfg.bucket)}/${objectKey(key).split('/').map(encodeRfc3986).join('/')}`;

  const request = async (method, key, body) => {
    const url = objectUrl(key);
    const payload = body || Buffer.alloc(0);
    const headers = signV4({
      method,
      url,
      payloadHash: sha256Hex(payload),
      accessKey: cfg.accessKey,
      secretKey: cfg.secretKey,
      region: cfg.region,
    });
    const response = await fetch(url, {
      method,
      headers,
      body: method === 'GET' || method === 'HEAD' ? undefined : payload,
      signal: AbortSignal.timeout(30000),
    });
    return response;
  };

  const listPrefix = async () => {
    // Listagem v2 simples; usada só para retenção.
    const url =
      `${endpoint}/${encodeRfc3986(cfg.bucket)}?list-type=2&prefix=${encodeRfc3986(cfg.prefix + '/')}`;
    const headers = signV4({
      method: 'GET',
      url,
      payloadHash: sha256Hex(Buffer.alloc(0)),
      accessKey: cfg.accessKey,
      secretKey: cfg.secretKey,
      region: cfg.region,
    });
    const response = await fetch(url, { headers, signal: AbortSignal.timeout(30000) });
    if (!response.ok) throw new Error(`listagem S3 falhou (${response.status})`);
    const xml = await response.text();
    const keys = [...xml.matchAll(/<Key>([^<]+)<\/Key>/g)].map((m) => m[1]);
    return keys
      .filter((k) => k.endsWith('.enc'))
      .map((k) => ({ key: k.split('/').pop(), size: 0 }))
      .sort((a, b) => b.key.localeCompare(a.key));
  };

  return {
    name: 's3',
    async put(key, buffer) {
      const response = await request('PUT', key, buffer);
      if (!response.ok) throw new Error(`upload S3 falhou (${response.status})`);
    },
    async get(key) {
      const response = await request('GET', key);
      if (!response.ok) throw new Error(`download S3 falhou (${response.status})`);
      return Buffer.from(await response.arrayBuffer());
    },
    async head(key) {
      const response = await request('HEAD', key);
      if (response.status === 404) return null;
      if (!response.ok) throw new Error(`HEAD S3 falhou (${response.status})`);
      return { size: Number(response.headers.get('content-length') || 0) };
    },
    async list() {
      return listPrefix();
    },
    async remove(key) {
      const response = await request('DELETE', key);
      if (!response.ok && response.status !== 404) throw new Error(`DELETE S3 falhou (${response.status})`);
    },
  };
}

function createTransport(cfg) {
  if (!cfg.enabled) return null;
  if (cfg.mode === 'dir') return dirTransport(cfg.dir);
  if (cfg.mode === 's3') return s3Transport(cfg);
  return null;
}

/* -------------------------------- operações -------------------------------- */

/**
 * Envia um backup local já validado. Cifra, envia, confirma tamanho remoto.
 * Nunca lança por falha de destino: retorna `{status:'error'}`.
 */
async function push({ file, cfg = config(), transport = createTransport(cfg) } = {}) {
  if (!transport) return { status: 'disabled', key: null, reason: 'offsite_desabilitado' };
  const name = `${path.basename(file)}.enc`;
  try {
    const plain = fs.readFileSync(file);
    const envelope = cfg.encrypted ? encryptBuffer(plain, cfg.passphrase) : plain;
    await transport.put(name, envelope);

    const remote = await transport.head(name);
    if (!remote || remote.size !== envelope.length) {
      return { status: 'error', key: name, reason: 'tamanho_remoto_divergente' };
    }
    return {
      status: 'ok',
      key: name,
      bytes: envelope.length,
      sha256: checksumBuffer(envelope),
      encrypted: cfg.encrypted,
      transport: transport.name,
    };
  } catch (error) {
    return { status: 'error', key: name, reason: classify(error) };
  }
}

/** Baixa e (se necessário) decifra um objeto remoto para `outPath`. */
async function pull({ key, outPath, cfg = config(), transport = createTransport(cfg) } = {}) {
  const envelope = await transport.get(key);
  const plain = cfg.encrypted ? decryptBuffer(envelope, cfg.passphrase) : envelope;
  fs.writeFileSync(outPath, plain, { mode: 0o600 });
  return { bytes: plain.length, sha256: checksumBuffer(plain) };
}

/** Mantém apenas os `keep` objetos mais recentes. Nunca remove antes de listar. */
async function prune({ keep = 14, cfg = config(), transport = createTransport(cfg) } = {}) {
  if (!transport) return { status: 'disabled', removed: [] };
  const items = await transport.list();
  const limit = Number.isFinite(keep) && keep > 0 ? Math.floor(keep) : 14;
  const removed = [];
  for (const item of items.slice(limit)) {
    try {
      await transport.remove(item.key);
      removed.push(item.key);
    } catch {
      /* não falha a operação inteira por um objeto */
    }
  }
  return { status: 'ok', total: items.length, removed };
}

function classify(error) {
  const message = String((error && error.message) || '');
  if (/timeout|aborted/i.test(message)) return 'timeout';
  if (/401|403|SignatureDoesNotMatch|AccessDenied/i.test(message)) return 'credenciais_invalidas';
  if (/ENOTFOUND|EAI_AGAIN|ECONNREFUSED/i.test(message)) return 'destino_indisponivel';
  return 'erro_offsite';
}

module.exports = {
  config,
  createTransport,
  dirTransport,
  s3Transport,
  signV4,
  push,
  pull,
  prune,
  classify,
};
