'use strict';

// Abstração de envio de e-mail para recuperação de senha.
//
// Estado real (2026-09-08): SEM provedor SMTP configurado. O envio grava a
// mensagem num outbox local (`tmp/mail-outbox/*.json`) e registra log —
// suficiente para desenvolvimento/teste e para demonstrar o fluxo completo.
// Para produção, configure as variáveis SMTP_* (.env.example) e implemente o
// transporte em `sendViaSmtp()` — o restante do fluxo (token, expiração, uso
// único) já é real e não muda. NUNCA afirmar que e-mails foram entregues
// quando só o outbox foi gravado.
const fs = require('fs');
const path = require('path');
const config = require('../config');

function outboxDir() {
  const root = path.join(__dirname, '..', '..', '..');
  const dir = process.env.MAIL_OUTBOX_DIR || path.join(root, 'tmp', 'mail-outbox');
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

function resetLink(token) {
  const base = (config.frontendOrigin || 'http://localhost:3001').replace(/\/$/, '');
  return `${base}/reset?token=${encodeURIComponent(token)}`;
}

async function sendPasswordReset({ to, name, token }) {
  const link = resetLink(token);
  const message = {
    to,
    subject: 'SADEN — redefinição de senha',
    text: `Olá ${name}. Para redefinir sua senha, acesse o link abaixo (válido por 1 hora, uso único):\n${link}\nSe você não solicitou, ignore esta mensagem.`,
    link,
    created_at: new Date().toISOString(),
    transport: 'dev-outbox',
  };
  if (process.env.SMTP_HOST) {
    return sendViaSmtp(message);
  }
  const file = path.join(outboxDir(), `${Date.now()}-${Math.random().toString(36).slice(2)}.json`);
  fs.writeFileSync(file, JSON.stringify(message, null, 1));
  // eslint-disable-next-line no-console
  console.log(JSON.stringify({ level: 'info', kind: 'mail-outbox', to, file }));
  return { queued: true, transport: 'dev-outbox', file };
}

// Gancho de produção: lançar erro claro até haver transporte real.
async function sendViaSmtp() {
  throw Object.assign(new Error('Transporte SMTP não implementado — configure o provedor (ver .env.example)'), {
    status: 501,
  });
}

module.exports = { sendPasswordReset, resetLink, outboxDir };
