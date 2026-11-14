# Productização — próximas ações

**Data:** 2026-11-14

## Prioridade 1 — fechar a lacuna de monitoramento

### 1.1. Avaliação periódica real
Hoje só há avaliação quando o preço é atualizado por uma consulta. Para
monitorar de fato, é preciso um agendador persistente (cron do sistema, PM2,
Task Scheduler ou um serviço de fila) chamando
`node -e "require('./src/services/alertEngine')..."` ou um endpoint interno
protegido.

**Pré-requisitos**: lock para instância única; registro de execução; limite de
requisições à fonte; alerta de falha. Sem isso, não prometer tempo real.

### 1.2. E-mail de notificação
Só faz sentido depois de 1.1 e com SMTP real configurado. O `mailService` é
outbox de desenvolvimento — não é e-mail enviado.

## Prioridade 2 — melhorias de produto

### 2.1. Série física regional
Depende de fonte pública com API. CEPEA/CONAB seguem `blocked`. Alternativa:
parceria/planilha oficial publicada com URL estável.

### 2.2. Frescor por série
Hoje é 7 dias para todas. Se entrar uma série semanal ou mensal, o limite precisa
vir do catálogo, não de constante.

### 2.3. Histórico de eventos exportável
CSV dos disparos, coerente com o padrão de relatórios existente.

## Prioridade 3 — dívida técnica

### 3.1. `rain_above` residual
Existem registros legados possíveis em bancos reais. Migrar para "arquivado"
explícito na UI, ou removê-los depois de aviso.

### 3.2. Rate limit nos endpoints de alerta
Hoje herdado apenas no login. `POST /api/alerts/evaluate` dispara consultas à
fonte; convém limitar por usuário.

### 3.3. Teste E2E automatizado no CI
A validação de navegador foi manual (agent-browser). Converter o roteiro em
script versionado reduziria regressão de UI.

## Fora de escopo (não fazer agora)

- novos modelos agroclimáticos, MG, NDVI, previsão de safra;
- segundo recurso grande de produto;
- integração clima × preço sem evidência;
- dependências pagas.
