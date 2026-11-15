# SADEN — imagem de produção da Release Candidate (Node 22, SQLite preservado).
FROM node:22-slim

ENV NODE_ENV=production

WORKDIR /app

# Dependências primeiro (cache de layer); sem devDependencies (testes usam node --test built-in).
COPY backend/package.json backend/package-lock.json ./backend/
RUN cd backend && npm ci --omit=dev --no-audit --no-fund

# Código (frontend já é estático servido pelo backend; sem build).
COPY backend ./backend
COPY frontend ./frontend
COPY .env.example ./.env.example
COPY docs ./docs
COPY README.md ./README.md

# Diretórios de runtime com dono não-root. `/app/backups` precisa existir **na
# imagem**: um volume nomeado vazio herda o dono do diretório de montagem. Sem
# isso, o volume nasce root e o `node` (uid 1000) não consegue escrever o backup.
RUN mkdir -p data tmp/mail-outbox logs backups && chown -R node:node /app
USER node

EXPOSE 3001

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:3001/api/health').then(r=>{if(!r.ok)process.exit(1)}).catch(()=>process.exit(1))"

CMD ["node", "backend/src/index.js"]
