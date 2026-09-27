# SADEN v1.1 — Matriz de Decisão (segunda opinião → veredito)

> Origem das sugestões: `segunda opnião.txt` (pasta Área de Trabalho, 940 linhas) = FONTE DE HIPÓTESES, não especificação.
> Vereditos possíveis: IMPLEMENTAR · INVESTIGAR · ADIAR · REJEITAR · JÁ IMPLEMENTADO · JÁ RESOLVIDO.
> Data da classificação: 2026-09-27. Reclassificar só com evidência nova.

## Forecast / modelos

| Sugestão | Problema | Evidência | Viabilidade | Esforço | Risco | Teste | Resultado | Decisão | Status |
|---|---|---|---|---|---|---|---|---|---|
| ARIMA como challenger | Ridge pode não captar autocorrelação | **E2+E3 mediram: AR(p)+AIC vence Ridge na val one-step 5/5 e no recursivo H=7/14/30 5/5; JS×Python idênticos; 69/69 testes** | Alta (implementado em JS puro, sem deps) | Médio | Baixo (isolado, Ridge intacta, sem rota) | E3 feito | **APROVADO como challenger; Ridge segue champion** | **D37** | Feito (E3); D38 decidiu exposição opt-in `?model=ar` (implementada em E4, 77/77) |
| SARIMA/ETS | Sazonalidade explícita | Sazonalidade não demonstrada na série | Média | Médio | Médio (complexidade) | Idem + análise ACF/estacionariedade | — | INVESTIGAR | Aberto, após ARIMA |
| Regressão multivariada (clima/PTAX) | Features exógenas podem ajudar | Clima/PTAX hoje são contexto, não features; risco de leakage | Média | Alto (pareamento temporal/espacial) | Alto (leakage) | Gate: "estaria disponível na origem?" | — | INVESTIGAR | Aberto, com gate D35 |
| Prophet | Sazonalidade pronta | Dependência nova, benefício não demonstrado | Baixa | Médio | Médio (manutenção) | Só se ARIMA/ETS falharem | — | ADIAR | Adiado |
| LSTM / RF / XGBoost | "Parecer mais IA" | Série curta (~252 pregões), sem features tabulares ricas | Baixa | Alto | Alto (overfitting) | — | — | ADIAR | Adiado (D28 já adiou RF/GBM) |
| Ensemble Ridge+challengers | Combinar erros complementares | Nenhum challenger validado ainda | — | — | Alto (pesos arbitrários) | Só após ≥1 challenger validado, pesos por validação | — | REJEITAR (por ora) | Rejeitado até haver challenger válido |
| MAPE 8–10% / 6–8% como meta | Números da segunda opinião | Nunca medidos no SADEN | — | — | Alto (falsa promessa) | — | — | REJEITAR | Proibido adotar como verdade |

## Regionalização

| Sugestão | Problema | Evidência | Viabilidade | Esforço | Risco | Teste | Resultado | Decisão | Status |
|---|---|---|---|---|---|---|---|---|---|
| Mesorregião (137) + tabelas `mesorregions`/`commodity_prices_regional` | Preço regional real | D26: CONAB reCAPTCHA, PGPAF 403, CEPEA Cloudflare, ANTT sem API — nenhuma fonte automatizável | Baixa (hoje) | Alto | Alto (proxy rotulado de real) | Investigar fonte antes de schema | — | INVESTIGAR (fonte primeiro) | Aberto; schema SÓ após fonte real |
| Microclima por coordenada | Clima granular | Open-Meteo por lat/lon JÁ funciona | Alta | Baixo | Baixo | — | — | JÁ IMPLEMENTADO | Feito (weather por coords) |
| Yahoo × IBGE = preço regional | Proxy sem observação | Seria estimativa derivada, não preço | — | — | Crítico (desonestidade metodológica) | — | — | REJEITAR | Rejeitado; se um dia existir proxy, rotular DERIVED |

## Testes / qualidade

| Sugestão | Problema | Evidência | Viabilidade | Esforço | Risco | Teste | Resultado | Decisão | Status |
|---|---|---|---|---|---|---|---|---|---|
| Cobertura c8 | Cobertura não medida | **Medida em 2026-09-27: 88,51% linhas · 74,75% branches · 86,91% funcs (suíte completa, c8 efêmero via npx)** | Alta | Nulo (sem dependência nova) | Nenhum | `V1_1_AUDIT.md` A2 | Meta 70%+ superada | JÁ MEDIDO | Feito (sem `c8` no package.json, pelo dependency gate) |
| Teste de carga k6/Artillery | Capacidade desconhecida | Só medições exploratórias (D12) | Média | Médio | Baixo | Concorrência/latência/throughput locais | — | ADIAR | Adiado (após forecast/regionalização) |
| Testes cache/TTL | Cobertura de cache | Cache KV + hit de rota testados em E1 (2026-09-27, 51/51) | Alta | Baixo | Nenhum | `api.test.js` (miss/hit/expiração/sobrescrita + hit de rota) | PASS | JÁ IMPLEMENTADO | Feito |
| Testes timeout/fonte fora do ar | Resiliência | http.test cobre timeout unitário; rota com upstream morto sem seam (sem DI proposital) | Alta | Baixo | Baixo | http.test (502) + NOT RUN de rota em `V1_1_AUDIT.md` A6 | Parcial | JÁ IMPLEMENTADO (parcial) | Feito o possível sem DI |
| Testes dados inválidos | Robustez de entrada | validate.js + coords existem | Alta | Baixo | Baixo | commodity 404 (3 rotas), 422 série curta (E1), coords/range/places/alerts inválidos | PASS | JÁ IMPLEMENTADO | Feito (E1 fechou o 422) |
| joi/zod | Validação "padrão" | validate.js próprio passa 48/48 | Média | Médio | Médio (migração) | — | — | REJEITAR | Rejeitado (solução atual adequada) |
| Timeout Yahoo 12s → 15s | Suposta lentidão | Testes live passam com 12s | — | — | Baixo | — | — | REJEITAR | Rejeitado (sem evidência de problema) |
| Backoff + circuit breaker | Retry atual é linear 600ms | withRetry 3× existe e funciona | Média | Médio | Médio | — | — | INVESTIGAR | Aberto (backoff exponencial avaliável) |

## Segurança / operação

| Sugestão | Problema | Evidência | Viabilidade | Esforço | Risco | Teste | Resultado | Decisão | Status |
|---|---|---|---|---|---|---|---|---|---|
| `esc()` anti-XSS | XSS em innerHTML | D20 implementou; auditoria 2026-09-27: strings externas escapadas, resto numérico | — | — | — | — | OK | JÁ IMPLEMENTADO | Feito |
| SRI nos CDNs | Integridade de CDN | D21 implementou | — | — | — | — | OK | JÁ IMPLEMENTADO | Feito |
| CSRF | Sessões via cookie | Auth usa `Authorization: Bearer`, sem cookies | — | — | — | — | N/A | REJEITAR | Rejeitado (não aplicável) |
| Validar FRONTEND_ORIGIN | CORS aberto | CORS configurável, instância única local | Média | Baixo | Baixo | — | — | INVESTIGAR | Aberto (baixa prioridade) |
| SMTP+TLS real | Outbox não é e-mail | D14 documentou; fora do escopo acadêmico | Baixa | Alto | Médio | — | — | ADIAR | Adiado |
| Logger pino/winston | Logging atual suficiente? | Logging atual NÃO auditado ainda | Média | Baixo | Baixo | Auditar antes | — | INVESTIGAR | Aberto (auditar primeiro) |
| Nginx + TLS Let's Encrypt | Produção real | Fora do escopo (RC acadêmica, D34) | Baixa | Alto | Médio | — | — | ADIAR | Adiado |
| Backup `data/saden.db` | Perda de dados | Volume persiste; sem rotina de backup | Alta | Baixo | Baixo | — | — | INVESTIGAR | Aberto (documentar rotina) |
| Restringir `/api/sources` | Catálogo público | Por desenho é público (landing cita fontes) | — | — | — | — | N/A | REJEITAR | Rejeitado (público por decisão) |

## Docs / DX / GitHub

| Sugestão | Problema | Evidência | Viabilidade | Esforço | Risco | Teste | Resultado | Decisão | Status |
|---|---|---|---|---|---|---|---|---|---|
| Corrigir `COPY docs` (build falhava) | docs ausente na árvore antiga | docs PRESENTE e versionado em 2026-09-27 | — | — | — | build pendente (daemon inativo) | Causa eliminada | JÁ RESOLVIDO | Feito (README atualizado) |
| OpenAPI/Swagger | Descoberta de API | Benefício não avaliado; risco de doc falsa | Média | Médio | Médio | Só se refletir rotas reais | — | ADIAR | Adiado |
| Diagrama Mermaid/draw.io | Visual da arquitetura | ARCHITECTURE.md textual existe | Alta | Baixo | Baixo | — | — | INVESTIGAR | Aberto (baixo custo) |
| setup.sh/batch | Onboarding | Fluxo PowerShell documentado e testado | Média | Baixo | Baixo | — | — | ADIAR | Adiado (fluxo atual funciona) |
| Troubleshooting porta/SSL/cache | Suporte | Sem evidência de dor recorrente | Média | Baixo | Baixo | — | — | ADIAR | Adiado |
| LICENSE | Sem licença declarada | Nenhum LICENSE na raiz (verificado) | Alta | Baixo | Baixo (decisão do autor) | — | — | INVESTIGAR | Aberto (autor decide) |
| Badges | Sinais de saúde | Exigem CI real; sem CI, badge mente | Baixa | Baixo | Médio (falsa confiança) | — | — | ADIAR | Adiado (até haver CI) |
| Descrição/topics GitHub | Descoberta | Metadados externos, sem controle aqui | — | — | — | — | — | ADIAR | Adiado (ação do autor) |
| SEO/OpenGraph/social sharing | Marketing | Baixa prioridade (sistema acadêmico com login) | — | — | — | — | — | ADIAR | Adiado |

## Código

| Sugestão | Problema | Evidência | Viabilidade | Esforço | Risco | Teste | Resultado | Decisão | Status |
|---|---|---|---|---|---|---|---|---|---|
| Centralizar conversão (fxService) | Duplicação | fxService JÁ centraliza | — | — | — | — | OK | JÁ IMPLEMENTADO | Feito |
| config.js p/ magic numbers | Números mágicos | TTLs/timeout/lambda centralizados em config + forecast | — | — | — | — | OK | JÁ IMPLEMENTADO | Feito (parcial; reauditar) |
| Documentar rotas | Descoberta | ARCHITECTURE.md documenta; OpenAPI adiado | — | — | — | — | OK | JÁ IMPLEMENTADO | Feito (parcial) |
| Skeleton loaders/spinners | UX de loading | Status inline contextuais (D22 dispensou toasts de propósito) | Média | Médio | Baixo | Só com benefício medido | — | ADIAR | Adiado |
| ARIA/contraste WCAG | Acessibilidade formal | D22: aria-live, teclado, foco; sem auditoria formal WCAG | Média | Médio | Baixo | Auditoria formal | — | INVESTIGAR | Aberto (sem alegar conformidade) |
