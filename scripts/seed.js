'use strict';
// Seed de desenvolvimento: garante usuário demo + tabelas base.
// Uso: npm run seed (dentro de backend/). NÃO contém credenciais reais.
const path = require('path');
const bcrypt = require(path.join(__dirname, '..', 'backend', 'node_modules', 'bcryptjs'));
const { connect } = require('../backend/src/db');

const db = connect();
const email = 'demo@saden.local';
const exists = db.prepare('SELECT id FROM users WHERE email = ?').get(email);
if (!exists) {
  db.prepare('INSERT INTO users(name, email, password_hash) VALUES(?, ?, ?)').run(
    'Demo SADEN',
    email,
    bcrypt.hashSync('saden123', 10)
  );
  console.log('Usuário demo criado: demo@saden.local / saden123');
} else {
  console.log('Usuário demo já existe.');
}
const { commodities } = { commodities: db.prepare('SELECT key FROM commodities').all() };
console.log('Commodities:', commodities.map((c) => c.key).join(', '));
