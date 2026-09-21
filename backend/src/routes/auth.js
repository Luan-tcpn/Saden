'use strict';

const crypto = require('crypto');
const express = require('express');
const bcrypt = require('bcryptjs');
const { connect } = require('../db');
const { signToken } = require('../middleware/auth');
const { isEmail, requireString } = require('../utils/validate');
const { badRequest, unauthorized } = require('../utils/errors');
const rateLimit = require('../middleware/rateLimit');
const mailService = require('../services/mailService');

const router = express.Router();

// Anti brute-force: 10 tentativas / 10min por IP em login e registro.
const authLimit = rateLimit({ windowMs: 10 * 60 * 1000, max: 10 });

router.post('/register', authLimit, (req, res, next) => {
  try {
    const name = requireString(req.body && req.body.name, 'name', { min: 2, max: 120 });
    const email = requireString(req.body && req.body.email, 'email', { max: 160 }).toLowerCase();
    const password = req.body && req.body.password;
    if (!isEmail(email)) throw badRequest('E-mail inválido');
    if (typeof password !== 'string' || password.length < 6 || password.length > 128) {
      throw badRequest('Senha deve ter entre 6 e 128 caracteres');
    }
    const exists = connect().prepare('SELECT id FROM users WHERE email = ?').get(email);
    if (exists) throw badRequest('E-mail já cadastrado');
    const hash = bcrypt.hashSync(password, 10);
    const info = connect()
      .prepare('INSERT INTO users(name, email, password_hash) VALUES(?, ?, ?)')
      .run(name, email, hash);
    const user = { id: info.lastInsertRowid, name, email };
    res.status(201).json({ user, token: signToken(user) });
  } catch (e) {
    next(e);
  }
});

router.post('/login', authLimit, (req, res, next) => {
  try {
    const email = requireString(req.body && req.body.email, 'email', { max: 160 }).toLowerCase();
    const password = req.body && req.body.password;
    if (!isEmail(email)) throw badRequest('E-mail inválido');
    if (typeof password !== 'string' || password.length === 0) throw badRequest('Senha obrigatória');
    const row = connect().prepare('SELECT * FROM users WHERE email = ?').get(email);
    if (!row || !bcrypt.compareSync(password, row.password_hash)) {
      throw unauthorized('Credenciais inválidas');
    }
    const user = { id: row.id, name: row.name, email: row.email };
    res.json({ user, token: signToken(user) });
  } catch (e) {
    next(e);
  }
});

router.get('/me', require('../middleware/auth').requireAuth, (req, res, next) => {
  try {
    const row = connect().prepare('SELECT id, name, email, created_at FROM users WHERE id = ?').get(req.user.id);
    if (!row) throw unauthorized('Usuário não encontrado');
    res.json({ user: row });
  } catch (e) {
    next(e);
  }
});

const RESET_TTL_MS = 60 * 60 * 1000; // 1 hora

function hashToken(token) {
  return crypto.createHash('sha256').update(String(token)).digest('hex');
}

// Recuperação: resposta sempre genérica (anti-enumeração de contas).
router.post('/forgot', authLimit, async (req, res, next) => {
  try {
    const email = requireString(req.body && req.body.email, 'email', { max: 160 }).toLowerCase();
    if (!isEmail(email)) throw badRequest('E-mail inválido');
    const done = { message: 'Se houver uma conta associada a este e-mail, enviaremos instruções para redefinição da senha.' };
    const user = connect().prepare('SELECT id, name, email FROM users WHERE email = ?').get(email);
    if (!user) return res.json(done);
    const token = crypto.randomBytes(32).toString('hex');
    const expires = new Date(Date.now() + RESET_TTL_MS).toISOString().replace('T', ' ').slice(0, 19);
    connect()
      .prepare('INSERT INTO password_resets(user_id, token_hash, expires_at) VALUES(?, ?, ?)')
      .run(user.id, hashToken(token), expires);
    try {
      await mailService.sendPasswordReset({ to: user.email, name: user.name, token });
    } catch (e) {
      // Falha de transporte não revela nada ao solicitante; segue mensagem genérica.
      // eslint-disable-next-line no-console
      console.error(JSON.stringify({ level: 'error', kind: 'mail', message: e.message }));
    }
    return res.json(done);
  } catch (e) {
    return next(e);
  }
});

function findValidReset(token) {
  if (typeof token !== 'string' || token.length < 32) return null;
  const wanted = hashToken(token);
  const rows = connect()
    .prepare("SELECT * FROM password_resets WHERE used_at IS NULL AND expires_at > datetime('now')")
    .all();
  for (const r of rows) {
    try {
      const a = Buffer.from(r.token_hash, 'hex');
      const b = Buffer.from(wanted, 'hex');
      if (a.length === b.length && crypto.timingSafeEqual(a, b)) return r;
    } catch {
      /* ignora linha malformada */
    }
  }
  return null;
}

router.post('/reset', authLimit, (req, res, next) => {
  try {
    const token = req.body && req.body.token;
    const password = req.body && req.body.password;
    if (typeof password !== 'string' || password.length < 6 || password.length > 128) {
      throw badRequest('Senha deve ter entre 6 e 128 caracteres');
    }
    const reset = findValidReset(token);
    if (!reset) throw badRequest('Link de recuperação inválido ou expirado');
    connect().prepare('UPDATE users SET password_hash = ? WHERE id = ?').run(bcrypt.hashSync(password, 10), reset.user_id);
    connect().prepare("UPDATE password_resets SET used_at = datetime('now') WHERE id = ?").run(reset.id);
    // Invalida outros tokens pendentes do usuário (uso único global).
    connect().prepare("UPDATE password_resets SET used_at = datetime('now') WHERE user_id = ? AND used_at IS NULL").run(reset.user_id);
    res.json({ message: 'Senha redefinida com sucesso. Faça login com a nova senha.' });
  } catch (e) {
    next(e);
  }
});

module.exports = router;
