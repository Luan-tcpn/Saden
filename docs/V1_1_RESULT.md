# SADEN v1.1 — Registro final da evolução (2026-09-27)

> Todos os números abaixo foram medidos nesta árvore. Sem metas retroativas.

## 1. Objetivo da v1.1

Preservar a v1.0.0 e adicionar somente melhorias comprovadas: challenger de
forecast validado, testes faltantes, backup operacional e documentação
recuperada — sem reescrita, sem proxy regional, sem resultado inventado.

## 2. Estado inicial

v1.0.0 (`9218e01`): 48/48 testes, E2E 53/53 (validação registrada), Ridge
champion, preço = referência internacional declarada, `docs/` restaurado.

## 3. Principais evoluções (ciclos E1–E4, G6, D39, backup, E2E)

- E1: cache KV/TTL, hit de rota, 422 série curta → 51/51.
- E2: investigação AR(p)+AIC (réplica validada contra `model_runs`).
- E3: `arService.js` + `linalg.js`, gate de leakage, avaliação recursiva → 69/69.
- E4/D38: `?model=ar` opt-in, `persistRun` partilhado, CSV por modelo → 77/77.
- G6: nenhuma fonte regional integrável (CONAB CAPTCHA, CEPEA paga, IMEA parcial, B3 futuros).
- D39: seletor Ridge/AR no dashboard → E2E 57/57.
- Backup: `scripts/backup.js` + rotina → 80/80.

## 4. Decisões D35–D39

D35 regras Champion/Challenger; D36 correção docs; D37 GO condicional + resultado
(AR aprovado challenger, Ridge champion); D38 exposição opt-in + resultado;
D39 seletor mínimo + resultado. Ordem cronológica verificada, sem duplicadas.

## 5–7. Forecasting e exposição

Ridge travada e intacta em comportamento. AR(p)+AIC (p∈1..8 por AIC no treino,
mesma série/split/métricas): vence Ridge no one-step e no recursivo H=7/14/30
nas 5 commodities (ex.: café rec-H7 136,6 vs 445,9). H30 absoluto fraco nos dois.
Exposição: `GET /api/forecast/:key?model=ar` + seletor na UI (default Ridge);
persistência `ar(order=N)` sem migração; CSV identifica o modelo.

## 8. Regionalização (G6)

Nenhuma fonte adequada para integração neste momento. Price Reference Engine
inalterado (só `nacional` populado). Proxy Yahoo×IBGE proibido e não utilizado.

## 9. Qualidade e testes

| Suíte | Resultado | Data |
|---|---|---|
| `npm test` | 80/80, 14 suítes (inclui 2 live) | 2026-09-27 |
| cobertura c8 (efêmero) | 88,51% linhas · 74,75% branches · 86,91% funcs | 2026-09-27 |
| smoke | 8/8 + `?model=ar` e 400 ao vivo | 2026-09-27 |
| E2E Round 2 | 57/57 (53 + 4 D39), Edge headless, pageErrors 0 | 2026-09-27 |

## 10. Segurança

bcrypt cost 10, JWT 12h + fail-fast, rate-limit auth, SQL parametrizado,
`esc()` no frontend, CSV anti-injeção, `model` em allowlist, erros sem
vazamento. Express 4 com 3 moderadas (risco aceito, D10). CSRF n/a (Bearer).

## 11. Backup

`node scripts/backup.js` (cópia online, retenção 7, `tmp/backups/`),
restauração documentada, `integrity_check` ok em backup real.
**NÃO VALIDADO EM DOCKER** (backup em container seria efêmero sem volume dedicado).

## 12. E2E e lição operacional

E2E-R2 OK pós-todas as mudanças. Incidente: servidor órfão pré-edit serviu HTML
obsoleto (detectado por divergência de bytes 26597 vs 26887); regra: antes de
E2E, confirmar PID/porta/versão servida. Headed Edge falha 1 check de
geolocalização (prompt vs negação — ambiente, não regressão).

## 13. Docker

**VALIDADO em 2026-09-27** (daemon iniciado na hora; imagem `saden:rc` 394 MB):
build PASS → up PASS → healthcheck `healthy` → `/api/health` ok → frontend
26887 bytes com seletor → auth → forecast Ridge (milho, 7 pts) → `?model=ar`
(order=1 na janela ao vivo) → `model=xxx` 400 → down/up com recriação:
login persistiu (volume `./data`) → smoke 8/8 contra o container.
Backup: host CLI durante runtime ok (4,44 MB); `/app/tmp/backups` é efêmero
(probe sumiu na recriação) — backup suportado via host, não no container sem
volume dedicado. Outbox persiste (montado); `docs/` dentro da imagem.
Sem TLS/backup/monitoramento — nunca alegado como produção.

## 14. Limitações (vigentes)

Referência internacional (não físico regional); modelo univariado; clima fora
do modelo; série ~1 ano; val_n 33–35; intervalo gaussiano sem cobertura
empírica; H30 fraco bilateral; Land Cover visual; sem teste de carga; sem SMTP;
instância única.

## 15. Itens adiados (com fundamento)

SARIMA/ETS/MA/ensemble, Prophet/LSTM/RF/XGBoost, OpenAPI, carga k6, Python,
microsserviços, Nginx/TLS, badges/CI, SEO/social, UI comparativa além do seletor.

## 16. Estado final

**V1.1 STATUS: FUNCTIONALLY COMPLETE** (Docker validado em 2026-09-27 —
todos os gates, incluindo smoke 8/8 no container).

> Atualização 2026-11-11: este registro descreve a v1.1 histórica. A **V1
> final** congela a Ridge como metodologia única e retira o AR do produto
> (D40); ver seção 19.

## 17. Evidências

Commits `9218e01`→`4a859f8` (+ este ciclo); `docs/FORECAST_EVALUATION.md`;
`docs/REGIONAL_INVESTIGATION.md`; suítes executadas (logs em `tmp/`, ignorados).

## 18. Próximos trabalhos possíveis (não iniciados)

Validação Docker; UI comparativa além do seletor; challengers SARIMA/ETS;
convênio CEPEA / autorização IMEA se surgirem; `V1_1_TCC_IMPACT.md` como ponte
para o autor atualizar o SADEN-TCC.

---

# V1 FINAL — encerramento (2026-11-11, D40)

## 19. Escopo congelado

- Metodologia de previsão: **Ridge única** (pipeline, split 70/15/15, baselines,
  λ por validação e métricas inalterados).
- AR(p) **fora do produto**: `arService.js`, `olsBeta`, `#sel-model` e o
  parâmetro de modelo no frontend removidos. `?model=ridge` é alias legado;
  qualquer outro valor → **HTTP 400**.
- Histórico experimental preservado em `model_runs` (`ar(order=3)` n=5,
  `ar(order=1)` n=4), sem migração nem reinterpretação.

## 20. Evidência executada nesta árvore

| Verificação | Resultado |
|---|---|
| `npm test` | **65/65 PASS**, 9 suítes, 0 falhas, 7,06 s |
| smoke local | **9/9 PASS** (Ridge; `model=ar`→400) |
| E2E Edge headless/CDP | **57/57 PASS**, `pageErrors: []` |
| Docker | build OK; up `healthy`; auth; Ridge 200; `model=ar`→400; persistência down/up; smoke **9/9** no container |
| Backup | `tmp/backups/saden-20261111T170124.db`, 4.472.832 bytes |

## 21. O que NÃO foi feito (honestidade de escopo)

- Nenhuma funcionalidade de V2 implementada; `docs/CONTEXTO_V2.md` é apenas
  documental.
- Sem TLS, sem SMTP real, sem teste de carga, sem monitoramento, sem cobertura
  empírica do intervalo — nada disso foi alegado como pronto para produção.
- ARIMA (MA/sazonalidade), ensemble e fontes regionais seguem não implementados.

## 22. Situação

**V1 CONGELADA E VALIDADA NO AMBIENTE LOCAL** (tag `v1-final`), com escopo
declarado, testes verdes e Docker executado de fato. Produção real continua
exigindo TLS, backup operacional, monitoramento e avaliação de carga.
