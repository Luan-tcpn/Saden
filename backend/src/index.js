'use strict';

const path = require('path');
const express = require('express');
const cors = require('cors');
const config = require('./config');
const { connect } = require('./db');
const { errorHandler } = require('./utils/errors');

const app = express();
app.disable('x-powered-by');
// Endurecimento básico sem dependências (compatível com Leaflet/Chart.js via CDN).
app.use((req, res, next) => {
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('Referrer-Policy', 'strict-origin-when-cross-origin');
  res.setHeader('X-Frame-Options', 'SAMEORIGIN');
  res.setHeader(
    'Content-Security-Policy',
    [
      "default-src 'self'",
      "script-src 'self' https://unpkg.com https://cdn.jsdelivr.net",
      "style-src 'self' https://unpkg.com",
      'img-src \'self\' data: https://unpkg.com https://tile.openstreetmap.org https://server.arcgisonline.com https://*.arcgisonline.com',
      "connect-src 'self'",
      "frame-ancestors 'self'",
      "object-src 'none'",
      "base-uri 'self'",
    ].join('; ')
  );
  next();
});
app.use(cors({ origin: config.frontendOrigin }));
app.use(express.json({ limit: '256kb' }));

// Log simples de requisições (sem segredos).
app.use((req, res, next) => {
  const t = Date.now();
  res.on('finish', () => {
    // eslint-disable-next-line no-console
    console.log(
      JSON.stringify({ level: 'info', method: req.method, path: req.originalUrl, status: res.statusCode, ms: Date.now() - t })
    );
  });
  next();
});

app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', service: 'saden-backend', time: new Date().toISOString() });
});

app.use('/api/auth', require('./routes/auth'));
app.use('/api/commodities', require('./routes/commodities'));
app.use('/api/prices', require('./routes/prices'));
app.use('/api/weather', require('./routes/weather'));
app.use('/api/geo', require('./routes/geo'));
app.use('/api/forecast', require('./routes/forecast'));
app.use('/api/alerts', require('./routes/alerts'));
app.use('/api/places', require('./routes/places'));
app.use('/api/landcover', require('./routes/landcover'));
app.use('/api/reports', require('./routes/reports'));

app.get('/api/sources', (req, res) => {
  const rows = connect().prepare('SELECT key, name, base_url, docs_url, kind, status, notes FROM data_sources').all();
  res.json({ sources: rows });
});

// Frontend estático servido pelo próprio backend (deploy único, porta única).
// Sem cache HTTP (no-store): evita HTML/JS obsoleto em desenvolvimento e
// 304 falsos por granularidade de mtime; app pequeno, custo irrelevante (D33).
const frontendDir = path.join(__dirname, '..', '..', 'frontend');
app.use(
  express.static(frontendDir, {
    etag: false,
    lastModified: false,
    maxAge: 0,
    setHeaders: (res) => res.setHeader('Cache-Control', 'no-store'),
  })
);
app.get('*', (req, res, next) => {
  if (req.path.startsWith('/api/')) return next({ status: 404, message: 'Endpoint não encontrado' });
  res.sendFile(path.join(frontendDir, 'index.html'));
});

app.use(errorHandler);

if (require.main === module) {
  connect();
  app.listen(config.port, () => {
    // eslint-disable-next-line no-console
    console.log(`SADEN backend+frontend em http://localhost:${config.port}`);
  });
}

module.exports = app;
