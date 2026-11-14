'use strict';

// Lock persistente com lease (Release 2).
//
// Regra: só executa o job quem possui o lock. A aquisição é um **único
// statement** com ON CONFLICT — atômico no SQLite, sem race entre checar e
// escrever. Se a instância morrer, o lease expira e outra assume; se a instância
// estiver viva, o heartbeat renova o prazo.
//
// Por que não lock em memória: dois processos (web + worker, ou dois workers)
// não compartilham memória. Por que não Redis: uma linha em SQLite resolve, e a
// topologia suportada é um host com volume local (documentado).

const { connect } = require('../db');

function nowIso() {
  return new Date().toISOString();
}

function isoPlus(ms) {
  return new Date(Date.now() + ms).toISOString();
}

/**
 * Tenta adquirir o job. Atômico: ou a linha é nossa, ou não é.
 * @returns {{acquired: boolean, owner: string|null, expires_at: string|null, reason: string}}
 */
function acquire(jobKey, owner, ttlMs) {
  const db = connect();
  const now = nowIso();
  const expires = isoPlus(ttlMs);
  const info = db
    .prepare(
      `INSERT INTO worker_locks(job_key, owner, acquired_at, heartbeat_at, expires_at, status)
       VALUES(?, ?, ?, ?, ?, 'held')
       ON CONFLICT(job_key) DO UPDATE SET
         owner = excluded.owner,
         acquired_at = excluded.acquired_at,
         heartbeat_at = excluded.heartbeat_at,
         expires_at = excluded.expires_at,
         status = 'held'
       WHERE worker_locks.expires_at <= ? OR worker_locks.owner = ?`
    )
    .run(jobKey, owner, now, now, expires, now, owner);

  const row = db.prepare('SELECT * FROM worker_locks WHERE job_key = ?').get(jobKey);
  if (info.changes === 1 && row && row.owner === owner) {
    return { acquired: true, owner: row.owner, expires_at: row.expires_at, reason: 'acquired' };
  }
  return {
    acquired: false,
    owner: row ? row.owner : null,
    expires_at: row ? row.expires_at : null,
    reason: row ? 'held_by_other' : 'unknown',
  };
}

/** Renova o lease se ainda formos o dono. */
function heartbeat(jobKey, owner, ttlMs) {
  const info = connect()
    .prepare(
      `UPDATE worker_locks SET heartbeat_at = ?, expires_at = ?
        WHERE job_key = ? AND owner = ? AND status = 'held'`
    )
    .run(nowIso(), isoPlus(ttlMs), jobKey, owner);
  return info.changes === 1;
}

/** Libera o lock (fim do ciclo ou shutdown). */
function release(jobKey, owner) {
  const info = connect()
    .prepare("DELETE FROM worker_locks WHERE job_key = ? AND owner = ?")
    .run(jobKey, owner);
  return info.changes === 1;
}

/** Remove locks expirados (higiene; não é necessário para a corretude). */
function reapExpired() {
  return connect()
    .prepare("DELETE FROM worker_locks WHERE expires_at <= ? AND status = 'held'")
    .run(nowIso()).changes;
}

function info(jobKey) {
  const row = connect().prepare('SELECT * FROM worker_locks WHERE job_key = ?').get(jobKey);
  if (!row) return null;
  const expired = row.expires_at <= nowIso();
  return { ...row, expired, active: !expired };
}

module.exports = { acquire, heartbeat, release, reapExpired, info, nowIso };
