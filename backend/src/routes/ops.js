'use strict';

// Saúde e operação (Release 2).
//
// Dois níveis, deliberadamente separados:
// - `/api/health/worker`: público e mínimo, para healthcheck de container.
//   Diz se o worker está vivo e quando rodou por último; nada sensível.
// - `/api/ops/status`: restrito ao operador (SADEN_ADMIN_EMAILS). Traz execuções,
//   fontes, métricas e últimas falhas.

const express = require('express');
const { connect } = require('../db');
const { requireAuth } = require('../middleware/auth');
const { requireAdmin } = require('../middleware/admin');
const { requireString } = require('../utils/validate');
const { badRequest } = require('../utils/errors');
const health = require('../worker/health');
const runner = require('../worker/runner');

const router = express.Router();

router.get('/health/worker', (req, res, next) => {
  try {
    const status = health.status();
    // 200 = processo vivo (mesmo com falha de fonte recente); 503 = parado ou
    // sem heartbeat. Um monitor externo alerta pelo código HTTP.
    const code = status.status === 'ok' || status.status === 'degraded' ? 200 : 503;
    res.status(code).json({
      status: status.status,
      alive: status.alive,
      reason: status.reason,
      last_run_at: status.last_run ? status.last_run.started_at : null,
      last_success_at: status.last_success_at,
      since_last_success_ms: status.since_last_success_ms,
      consecutive_failures: status.consecutive_failures,
      next_run_at: status.next_run_at,
      heartbeat_age_ms: status.heartbeat_age_ms,
    });
  } catch (error) {
    next(error);
  }
});

router.get('/ops/status', requireAuth, requireAdmin, (req, res, next) => {
  try {
    const db = connect();
    const users = db.prepare('SELECT COUNT(*) n FROM users').get().n;
    const alerts = db.prepare('SELECT status, COUNT(*) n FROM alerts GROUP BY status').all();
    const events = db.prepare("SELECT COUNT(*) n FROM alert_events WHERE event_type = 'trigger'").get().n;
    const unread = db
      .prepare("SELECT COUNT(*) n FROM alert_events WHERE event_type = 'trigger' AND read_at IS NULL")
      .get().n;
    const feedback = db.prepare('SELECT COUNT(*) n FROM feedback').get().n;
    res.json({
      worker: health.status(),
      sources: health.sources(),
      metrics: runner.metrics({ windowDays: 7 }),
      runs: health.lastRuns(10),
      product: {
        users,
        alerts_by_status: Object.fromEntries(alerts.map((row) => [row.status, row.n])),
        trigger_events: events,
        unread_events: unread,
        feedback_items: feedback,
      },
      retention: {
        worker_runs_kept: health.RUNS_KEEP,
        note: 'Execuções antigas são podadas; alertas, eventos e séries são preservados.',
      },
    });
  } catch (error) {
    next(error);
  }
});

// Feedback simples do usuário: sem dados pessoais adicionais, sem serviço externo.
const FEEDBACK_KINDS = ['problem', 'suggestion', 'usefulness', 'difficulty'];
router.get('/feedback/kinds', (req, res) => res.json({ kinds: FEEDBACK_KINDS }));

router.post('/feedback', requireAuth, (req, res, next) => {
  try {
    const body = req.body || {};
    const kind = requireString(body.kind, 'kind', { min: 3, max: 20 });
    if (!FEEDBACK_KINDS.includes(kind)) throw badRequest(`kind deve ser um de: ${FEEDBACK_KINDS.join(', ')}`);
    const message = requireString(body.message, 'message', { min: 3, max: 1000 });
    const context = body.context && typeof body.context === 'object' ? body.context : null;
    const info = connect()
      .prepare('INSERT INTO feedback(user_id, kind, message, context_json) VALUES(?, ?, ?, ?)')
      .run(req.user.id, kind, message, context ? JSON.stringify(context).slice(0, 2000) : null);
    res.status(201).json({ feedback: { id: Number(info.lastInsertRowid), kind, created: true } });
  } catch (error) {
    next(error);
  }
});

module.exports = router;
