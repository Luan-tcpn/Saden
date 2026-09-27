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

Build/up/health **NOT RUN** (daemon inativo em todas as verificações de
2026-09-27). `Dockerfile`/`compose` íntegros por inspeção; `COPY docs`
consistente. Sem TLS/backup/monitoramento — nunca alegado como produção.

## 14. Limitações (vigentes)

Referência internacional (não físico regional); modelo univariado; clima fora
do modelo; série ~1 ano; val_n 33–35; intervalo gaussiano sem cobertura
empírica; H30 fraco bilateral; Land Cover visual; sem teste de carga; sem SMTP;
instância única.

## 15. Itens adiados (com fundamento)

SARIMA/ETS/MA/ensemble, Prophet/LSTM/RF/XGBoost, OpenAPI, carga k6, Python,
microsserviços, Nginx/TLS, badges/CI, SEO/social, UI comparativa além do seletor.

## 16. Estado final

**V1.1 STATUS: FUNCTIONALLY COMPLETE** (validação Docker pendente de ambiente —
registrada separadamente, não bloqueia o restante).

## 17. Evidências

Commits `9218e01`→`4a859f8` (+ este ciclo); `docs/FORECAST_EVALUATION.md`;
`docs/REGIONAL_INVESTIGATION.md`; suítes executadas (logs em `tmp/`, ignorados).

## 18. Próximos trabalhos possíveis (não iniciados)

Validação Docker; UI comparativa além do seletor; challengers SARIMA/ETS;
convênio CEPEA / autorização IMEA se surgirem; `V1_1_TCC_IMPACT.md` como ponte
para o autor atualizar o SADEN-TCC.
