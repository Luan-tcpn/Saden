'use strict';

// Envelope de criptografia dos backups off-site (Release 1.2.2).
//
// Por que não só copiar o arquivo: o destino remoto está fora do controle do
// SADEN. O backup contém e-mails, hashes de senha e histórico de alertas.
// Aqui o arquivo é cifrado **antes** de sair do host.
//
// Formato (tudo binário, sem JSON no envelope):
//   "SADENBK1"  8 bytes   identificação de versão
//   salt       16 bytes   scrypt
//   iv         12 bytes   AES-GCM
//   tag        16 bytes   autenticação GCM
//   ciphertext  N bytes
//
// A chave deriva de uma passphrase (scrypt, N=2^14) e **nunca** é gravada junto
// do backup. Perder a passphrase = perder a cópia remota; a cópia local continua
// aberta e é a rede de segurança.

const crypto = require('crypto');
const fs = require('fs');

const MAGIC = Buffer.from('SADENBK1', 'ascii');
const SALT_LEN = 16;
const IV_LEN = 12;
const TAG_LEN = 16;
const KEY_LEN = 32;
const SCRYPT = { N: 16384, r: 8, p: 1, maxmem: 64 * 1024 * 1024 };

function deriveKey(passphrase, salt) {
  if (!passphrase || String(passphrase).length < 12) {
    throw new Error('passphrase de backup ausente ou curta (mínimo 12 caracteres)');
  }
  return crypto.scryptSync(String(passphrase), salt, KEY_LEN, SCRYPT);
}

/** Cifra um Buffer. Retorna o envelope completo. */
function encryptBuffer(plain, passphrase) {
  if (!Buffer.isBuffer(plain)) throw new Error('conteúdo deve ser Buffer');
  const salt = crypto.randomBytes(SALT_LEN);
  const iv = crypto.randomBytes(IV_LEN);
  const key = deriveKey(passphrase, salt);
  const cipher = crypto.createCipheriv('aes-256-gcm', key, iv);
  const ciphertext = Buffer.concat([cipher.update(plain), cipher.final()]);
  const tag = cipher.getAuthTag();
  key.fill(0);
  return Buffer.concat([MAGIC, salt, iv, tag, ciphertext]);
}

/** Decifra um envelope. Lança em chave errada ou arquivo corrompido. */
function decryptBuffer(envelope, passphrase) {
  if (!Buffer.isBuffer(envelope)) throw new Error('envelope deve ser Buffer');
  if (envelope.length < MAGIC.length + SALT_LEN + IV_LEN + TAG_LEN) {
    throw new Error('envelope truncado');
  }
  if (!envelope.subarray(0, MAGIC.length).equals(MAGIC)) {
    throw new Error('não é um backup criptografado do SADEN');
  }
  let offset = MAGIC.length;
  const salt = envelope.subarray(offset, (offset += SALT_LEN));
  const iv = envelope.subarray(offset, (offset += IV_LEN));
  const tag = envelope.subarray(offset, (offset += TAG_LEN));
  const ciphertext = envelope.subarray(offset);

  const key = deriveKey(passphrase, salt);
  try {
    const decipher = crypto.createDecipheriv('aes-256-gcm', key, iv);
    decipher.setAuthTag(tag);
    return Buffer.concat([decipher.update(ciphertext), decipher.final()]);
  } catch (error) {
    // GCM não distingue chave errada de conteúdo alterado — e não deve.
    throw new Error('falha ao decifrar: chave incorreta ou arquivo corrompido');
  } finally {
    key.fill(0);
  }
}

function encryptFile(inputPath, outputPath, passphrase) {
  const plain = fs.readFileSync(inputPath);
  const envelope = encryptBuffer(plain, passphrase);
  fs.writeFileSync(outputPath, envelope, { mode: 0o600 });
  return { bytes: envelope.length, plainBytes: plain.length };
}

function decryptFile(inputPath, outputPath, passphrase) {
  const envelope = fs.readFileSync(inputPath);
  const plain = decryptBuffer(envelope, passphrase);
  fs.writeFileSync(outputPath, plain, { mode: 0o600 });
  return { bytes: plain.length };
}

function checksumFile(filePath) {
  const hash = crypto.createHash('sha256');
  const fd = fs.openSync(filePath, 'r');
  const buffer = Buffer.allocUnsafe(1024 * 1024);
  try {
    let read;
    while ((read = fs.readSync(fd, buffer, 0, buffer.length, null)) > 0) {
      hash.update(buffer.subarray(0, read));
    }
  } finally {
    fs.closeSync(fd);
  }
  return hash.digest('hex');
}

function checksumBuffer(buffer) {
  return crypto.createHash('sha256').update(buffer).digest('hex');
}

module.exports = {
  MAGIC,
  encryptBuffer,
  decryptBuffer,
  encryptFile,
  decryptFile,
  checksumFile,
  checksumBuffer,
  deriveKey,
};
