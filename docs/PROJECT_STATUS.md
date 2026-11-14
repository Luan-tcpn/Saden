# SADEN — Estado do projeto

Atualizado em **2026-11-11** (V1 congelada; seções abaixo preservam o histórico de 2026-09-08). Legenda: DONE · PARTIAL · BROKEN · BLOCKED · NOT_STARTED.

> **V1 FINAL (2026-11-11)**: previsão com metodologia única **Ridge**; AR(p)
> retirado do produto (D40), com histórico experimental preservado. Suíte
> **65/65**, smoke **9/9** (local e container), E2E **57/57**, Docker validado.
> A V2 geoespacial começou em **branch isolada** (`v2/geospatial-foundation`),
> sem alterar `main` nem a tag `v1-final`. Estado real em
> `docs/V2_EXECUTION_STATUS.md`.

## Funcionalidades

| Item | Estado | Evidência |
|---|---|---|
| App inicia (backend+frontend porta 3001) | DONE | `GET /api/health` → ok; PID ativo |
| Arquitetura limpa (frontend↔backend separados) | DONE | `docs/ARCHITECTURE.md` |
| Banco SQLite + schema + seed | DONE | `backend/src/db.js`; tabelas criadas em `data/saden.db` |
| Auth (registro/login/sessão/proteção/logout) | DONE | testes integração 8/8; validado via curl |
| Preços reais (Yahoo + PTAX, cache, rastreio) | DONE | soja R$ 148,33/sc em 2026-09-08; teste LIVE passa |
| Clima real (Open-Meteo 7d + histórico) | DONE | teste LIVE passa; 7 dias Ribeirão Preto |
| Localização (IBGE + geocoding + âncora IBGE) | DONE | "Ribeirão Preto" → lat/lon + ibge 3543402 |
| Dashboard (filtros reais, histórico, métricas, comparação) | DONE | validado no navegador: KPIs, gráficos e troca de commodity funcionam |
| Mapa do Brasil (Leaflet OSM + Esri satélite, clique → dados) | DONE | validado: marcador + popup + painel com preço e clima reais; legenda adicionada |
| Pipeline previsão (Ridge única + 3 baselines, split temporal, intervalo) | DONE | soja: MAPE teste 1,95%, ridge vence baselines; `?model≠ridge`→400 (D40) |
| Avaliação de modelos (MAE/RMSE/MAPE treino/val/teste) | DONE | tabela no dashboard + payload |
| Relatórios (JSON + CSV + impressão/PDF) | DONE | validado via curl (265 linhas CSV milho) |
| Testes (8 unit + integração) | DONE | `npm test` 65/65 (9 suítes), smoke 9/9, E2E 57/57 (V1 final) |
| Segurança (bcrypt, JWT, validação, CORS, rate-limit, sem segredo no front) | DONE | 25/25 testes; audit: 3 moderadas com risco aceito (D10) |
| Performance/cache | DONE | warm ≤10ms/endpoint, dashboard 39ms; sem otimização especulativa (D12) |
| Refinamento visual | DONE | identidade agro validada desktop+mobile; a11y básica ok |
| Doc TCC (fontes, metodologia, limitações) | DONE | `docs/TCC.md` com resultados reais das 5 commodities |
| Landing pública + roteador (/login /register /reset) | DONE | E2E navegador: landing→cadastro→app→logout; ilustração SVG local |
| Recuperação de senha | DONE | token uso único 1h, resposta genérica, outbox dev; SMTP documentado como pendência externa |
| Localização robusta | DONE | cidade/rua/coords + autocomplete aplicável + reverse + Minha localização; E2E 20/20 |
| Aparência (light/dark/system) | DONE | persistente, gráficos adaptados, validado com reload |
| Responsividade 320–1440 | DONE | drawer mobile, tabelas com scroll, mapa e filtros adaptados; overflow 0 medido |
| Landing profissional (foto + narrativa + footer) | DONE | hero pivô/meteorologia, 7 seções, footer completo sem links falsos; light/dark/mobile validados |
| Logo satélite + favicon | DONE | SVG próprio (verde #2c5f3a preservado) em navbar/auth/app/landing/favicon |
| Refinamento estético landing | DONE | ritmo por superfícies, navbar centralizada, hero com fade, timeline, banda dados, footer integrado; frase removida |
| Segurança pós-auditoria (FASE A) | DONE | esc() anti-XSS global, CSP+headers, JWT fail-fast prod, município geocodificado, staleness discreto |
| Robustez (FASE B) | DONE | csvCell anti-fórmula, retenção reports/eventos 500, prune, SRI nos CDNs |
| A11y/UX (FASE C) | DONE | teclado no autocomplete, foco drawer, aria-live, Limpar filtros, intervalo explicado |
| Header integrado (FASE D) | DONE | transparente no topo, superfície sutil no scroll; validado claro/escuro/foto |
| Alertas MVP (FASE E) | DONE | price_below/above + rain_above, CRUD, check sob demanda, histórico, isolamento; E2E |
| Locais salvos + período + variação (F/G) | DONE | user_places no mapa, range allowlist, gráfico de variação %; E2E |
| NDVI (FASE H) | ESTUDO | viável via Sentinel-2/CDSE, bloqueado por credencial — docs/NDVI_STUDY.md |
| V1 recuperável (tag + branch + bundle + backup) | DONE | `docs/V1_RECOVERY.md`; bundle SHA-256 `DB2D8858…`; banco `integrity_check=ok` |
| V2.1 PoC Sentinel-2 (branch isolada) | DONE | 4 cenas L2A reais, NDVI/EVI/NDMI 20 m, 30/30 testes sintéticos — `docs/V2_EXECUTION_STATUS.md` |
| Testes | DONE | 65/65 (`npm test`), smoke 9/9, E2E navegador 57/57 (V1 final; histórico 44/44→53/53 da RC) |
| Preço territorial (engine + fallback) | DONE | hierarquia honesta (nacional populado; regional `unavailable` explícito); badge no dashboard |
| Frete | REFERÊNCIA | sem fonte estruturada; sem cálculo automático; link/manual na tabela de fontes |
| Mapa agrícola Land Cover | DONE | camada Sentinel-2 10m opcional + legenda PT + atribuição; sem ponto/% (identify exige credencial) |
| Consolidação (revalidação completa) | DONE | 48/48, smoke 8/8, E2E 44/44; XSS/headers/engine revalidados; CEPEA/IMEA rechecados e mantidos bloqueados |
| Valor (legenda compacta, relatório c/ local, Q&A banca) | DONE | E2E 46/46; Land Cover como auxiliar; nada reescrito |
| Contexto por tela (RC) | DONE | form completo em Dashboard/Mapa/Relatórios; resto limpo; coords exatas; E2E 53/53; overflow 0 |
| Roadmap granular | DONE | `docs/PROJECT_ROADMAP.md` é o plano oficial de execução |
| Auditoria final (P14→P19) | DONE | 29/29 testes, smoke 8/8, visual sem erros, docs coerentes — ver roadmap |

## V2.5 — Pareamento sazonal, integração espacial e reavaliação estatística (2026-11-12)

Branch: `v2/seasonal-spatial-pairing`. Relatórios:
`geospatial/reports/V2_5_SEASONAL_SPATIAL_PAIRING.md` e
`geospatial/reports/V2_5_ADVISOR_SUMMARY.md`. Decisões D58–D65.

| Item | Estado | Evidência |
|---|---|---|
| Série NDVI municipal mensal | DONE | `municipal_ndvi_monthly.csv`, 47 meses × 4 máscaras = 188 linhas; SHA-256 idêntico na reexecução; 0 duplicatas |
| Mosaico de tiles verificado | DONE | 47/47 meses com `21LXG` + `21LXF` (`first_valid_wins`, D44) |
| Perfil radiométrico por registro | DONE | 60 `original_pre_04_no_offset` + 52 `C1_harmonized`, identificados linha a linha |
| Máscara agrícola auditada | DONE | 4 variantes (`wc2020`/`wc2021`/`stable`/`broad`); `stable` = 12.498.721 px = 4.999,5 km² |
| Limitação temporal da máscara | DECLARED | `mask_year` + `mask_retrospective` em 100% das linhas (só há mapas de 2020 e 2021) |
| Regra oficial de decêndios | DONE | 3 por mês (1–10, 11–20, 21–fim); 36 decêndios testados, fevereiro e bissextos |
| Âncora de ano dos decêndios | CORRIGIDA | 165 violações da cronologia das portarias → **0** (D62) |
| Risco textual do ZARC | CORRIGIDO | `baixo`/`medio`/`alto` lidos corretamente; antes produzia janelas vazias |
| Janela recomendada | DONE | risco ≤ 20% (critério oficial do MAPA) + janela modal por safra (D63) |
| Correspondência safra → PAM | PARCIAL | regra = ano de colheita (`safra_fin`); textos das portarias ainda pendentes |
| Milho 1ª × 2ª safra | DONE | janelas separadas; 2ª ficou com n = 3 (incompatibilidade semântica declarada, D60) |
| Dataset pareado | DONE | `municipal_seasonal_productivity_dataset.csv`, 228 linhas, 2 fatias de pareamento |
| Réplica da V2.3 | VERIFICADA | diferença máxima 1,1·10⁻¹⁶ em 18 pares (D64) |
| n efetivo contabilizado | DONE | soja 8, milho 8, milho 2ª 3 (sazonal); 9/9 (ano civil) — anos com rendimento |
| Reavaliação estatística | DONE | Pearson, Spearman, permutação (5.000, semente fixa), IC bootstrap, Holm, detrendizado |
| Validação temporal alinhada | DONE | mesmos anos de teste (2023–2025) em todas as 8 configurações |
| Representatividade AOI × município | DONE | r = 0,972; diferença média +0,037 (não estável: −0,000 a +0,078 por ano) |
| Sensibilidade à máscara | DONE | 4 máscaras → resultados praticamente idênticos |
| Testes offline | DONE | **213/213** (33 novos da V2.5) |
| Integração ao Ridge / API / UI | NOT_STARTED | fora de escopo; não houve ganho (D53, D61) |
| Treino de modelo de produtividade | NOT_STARTED | gate metodológico não satisfeito |

**Resultado da V2.5 — CAMINHO B (base pareada válida, sem ganho do NDVI).**
A pergunta central ("a escala municipal e a janela agronômica oficial
produzem uma relação mais consistente?") tem resposta **negativa**: mudar a
escala reduz r (soja 0,432 → 0,302; milho 0,200 → −0,015) e mudar a janela
também (soja 0,432 → 0,372; milho 0,200 → −0,455). Nenhum dos 32 testes da
família é significativo após Holm (todos p = 1,000) e, na validação temporal
alinhada, o modelo com NDVI **não** supera a média histórica em nenhuma das 8
configurações.

## V2.6 — Base agroclimática e painel multi-municipal (2026-11-12)

Branch: `v2/agroclimatic-productivity-panel`. Relatórios:
`geospatial/reports/V2_6_AGROCLIMATIC_DATA_FOUNDATION.md`,
`V2_6_MULTIMUNICIPAL_PANEL.md`, `V2_6_AGROCLIMATIC_EXPLORATORY_ANALYSIS.md`,
`V2_6_ADVISOR_SUMMARY.md`. Decisões D66–D75.

| Item | Estado | Evidência |
|---|---|---|
| Encerramento da linha do NDVI | DONE | D66; indicadores Sentinel-2 preservados como referência |
| Inventário de estações do INMET | DONE | 668 estações; 294 municípios com estação dentro, 1.425 a até 80 km, 63 sem estação |
| Aquisição meteorológica real | DONE | INMET por HTTP Range (808 kB lidos por estação/ano); NASA POWER (MERRA-2) para 1.622 municípios |
| Qualidade das séries | DONE | 1.622 séries auditadas: cobertura 1,000, 0 duplicatas, 0 invalidos, 0 descontinuidades; ausente ≠ zero |
| ERA5-Land investigado | PARCIAL | via Open-Meteo (temperatura, umidade, solo); acesso nativo do CDS exige chave de conta |
| Extração municipal validada | DONE | 1.782 municípios de 6 UFs, malhas do shapefile oficial do IBGE (leitor próprio) |
| Painel de municípios | DONE | 1.622 elegíveis → 2.780 pares município-cultura |
| Critérios de inclusão documentados | DONE | D69 (produção em ≥ 7/9 anos, área positiva, geometria, estação) |
| PAM normalizado | DONE | 128.160 registros em 6 UFs (1 consulta por UF) |
| ZARC por município | DONE | 2.374.625 registros (11 safras) em streaming por geocódigo |
| Graus-dia por perfil de cultura | DONE | soja (Ometto; Gilmore & Rogers) e milho (Embrapa), com fonte e limitações |
| Balanço hídrico implementado | DONE | Thornthwaite & Mather (1955), CAD com perfis de solo documentados |
| Indicadores por cultura | DONE | precipitação, temperatura, graus-dia, calor, ET0, ETR, déficit/excedente, umidade do solo |
| Dataset agroclimático | DONE | 35.894 linhas, 19.402 utilizáveis (soja 8.884 / milho 7.616 / milho 2ª 2.902) |
| Análise exploratória | DONE | correlações com Holm (p = 0,0036), walk-forward temporal e holdout territorial, efeitos fixos com EP agrupado |
| Comparação INMET × reanálise | DONE | `climate_source_comparison.json` |
| Testes offline | DONE | **262/262** (49 novos da V2.6) |
| Integração ao Ridge / API / UI | NOT_STARTED | fora de escopo; ganho temporal não demonstrado |
| Treino de modelo complexo | NOT_STARTED | proibido nesta etapa (D70) |

**Resultado da V2.6 — CAMINHO A (painel viável, análise conclusiva).** As
variáveis agroclimáticas têm associação **significativa** com o rendimento
municipal (p Holm = 0,0036, contra 1,000 do NDVI na V2.5); o déficit hídrico
na janela de plantio é o sinal mais forte (t ≈ −17). **Na validação temporal o
clima não supera a média histórica**; **na validação territorial (municípios
inteiros) o modelo com clima vence** nas 6 combinações (ganho de 1,7% a 6,3%).

## Problemas conhecidos

1. Servidor roda como processo manual (`Start-Process`, PID volátil) — sem serviço/systemd.
2. `priceService` descarta pregões sem PTAX correspondente (raro; fim de semana) — comportamento intencional, contado em `fx_fallback_days`.
3. Previsão usa datas futuras em dias corridos (não só dias úteis) — declarado em `limitations`.
4. Validação visual P14 concluída (Edge headless + CDP): auth, dashboard, filtros, mapa interativo, relatório — zero erros console/rede. Evidências em `tmp/shots/`.
5. Comparação do dashboard dispara N chamadas `latest` (N+1) — candidato a endpoint único (P16).
6. Forecast recalcula a cada chamada (sem cache) — candidato a cache (P16).

## APIs

Ver `docs/API_SOURCES.md` e `GET /api/sources`. CEPEA/CONAB: BLOCKED (sem API pública).

## Ambiente

Node 22, `backend/node_modules` instalado, `.env` a partir de `.env.example`, banco em `data/saden.db`.
Servidor: `node backend/src/index.js` (ou `npm start` em `backend/`). Testes: `npm test` em `backend/`.
Smoke E2E: `node scripts/smoke-test.js`.

## Próximas prioridades (ver roadmap oficial)

1. Uso real de demonstração (apresentar; coletar feedback de orientador).
2. Endpoint único de comparação e cache de forecast somente se o uso justificar (D12).
3. Convênio de dados para preço físico regional (CEPEA/CONAB) como trabalho futuro.

## Fechamento da V1 (2026-11-11)

| Gate | Resultado |
|---|---|
| `npm test` | 65/65, 9 suítes, 0 falhas (~7,06 s) |
| smoke local | 9/9 (Ridge; `model=ar` → 400) |
| E2E Edge headless/CDP | 57/57, `pageErrors: []` |
| Docker | build, up healthy, auth, Ridge, 400, persistência down/up, smoke 9/9 |
| Backup | `tmp/backups/saden-20261111T170124.db` (4.472.832 bytes) |
| Histórico AR | preservado (`ar(order=3)` 5; `ar(order=1)` 4) | |

Escopo congelado: uma metodologia (Ridge), sem TLS/SMTP/carga/monitoramento —
não declarado pronto para produção. Próxima etapa possível: `docs/CONTEXTO_V2.md`.

## V2 geoespacial — branch isolada (2026-11-11, D41)

| Item | Estado | Evidência |
|---|---|---|
| Fonte pública Sentinel-2 L2A | DONE | Earth Search `sentinel-2-c1-l2a`, acesso anônimo |
| AOI com origem oficial | DONE | malha IBGE Sorriso-MT + janela técnica 0,10° |
| Aquisição/processamento real | DONE | 4 cenas (jun–set/2025), 12 GeoTIFFs, 1 grade 20 m |
| Máscara de nuvem/nodata | DONE | SCL conservadora; 99,94–99,96% válidos; 0 degenerados |
| Testes sintéticos offline | DONE | 30/30 (`unittest`, sem rede) |
| Série tabular + prévias + manifesto | DONE | CSV 12 linhas, 4 PNG, JSON com SHA-256 |
| Integração ao produto/UI | NOT_STARTED | fora do escopo desta missão |
| Modelo de produtividade/preço | NOT_STARTED | exige dados observados e protocolo próprio |

A V2.1 **não** conclui análise sazonal, produtividade ou melhoria de previsão.
Detalhes, números e limitações: `docs/V2_EXECUTION_STATUS.md` e
`geospatial/README.md`.

## V2.1 validação geoespacial — branch `v2/geospatial-validation` (2026-11-11, D42–D45)

| Item | Estado | Evidência |
|---|---|---|
| Reprodução da PoC | DONE | reexecutada em diretório separado; grade idêntica e delta 0,0 em todas as estatísticas |
| Auditoria radiométrica | DONE | baseline 05.09/05.10/05.11, `scale=0.0001`, `offset=-0.1` idênticos entre STAC e COG; sem dupla aplicação; baseline < 4.0 bloqueia o item |
| Comparação de máscaras SCL | DONE | Perfil A × B em 4 cenas reais + diagnóstico por classe; efeito ≤ 0,18% na média do NDVI; decisão D43 |
| Limite municipal oficial | DONE | IBGE `5107925` (qualidade `maxima`, 2.689 vértices, válida); 9.293,47 km²; bbox histórica com 0,51 km² **fora** do município |
| Mosaico de dois tiles | DONE | `21LXG`+`21LXF` do mesmo `datatake` (2023-06-20), regra `first_valid_wins`, mapa de origem por pixel; correlação ≥ 0,99999 |
| Série mensal 2023–2025 | DONE | 36 meses pesquisados, 34 observados, 2 lacunas justificadas; sem preenchimento; CSV + PNG com lacunas visíveis |
| Testes | DONE | **95/95** offline; testes de rede separados e opt-in (4/4 OK) |
| Integração ao produto/UI | NOT_STARTED | fora do escopo da missão |
| Modelo de produtividade/preço | NOT_STARTED | exige dados observados e protocolo próprio (V2.2+) |

Relatório técnico: `docs/V2_1_VALIDATION_REPORT.md`.

## V2.2 base observada de produtividade — branch `v2/agricultural-productivity-data` (2026-11-11, D46–D49)

| Item | Estado | Evidência |
|---|---|---|
| IBGE/SIDRA (PAM 5457) | DONE | 4.472 registros reais do município 5107925 (2013–2025), sem chave |
| CONAB (Boletim de Safras) | DONE (estadual) | 444 registros de MT, safras 23/24–25/26; estimativas revisadas |
| Bloqueios de acesso | DOCUMENTED | SIGS/`api.conab.gov.br` sem DNS; `dados.gov.br` HTTP 401 — não contornados |
| Base normalizada | DONE | 4.916 registros, 26 campos, valor/unidade originais preservados |
| Crosswalk de culturas | DONE | 5 commodities do SADEN mapeadas com classe (exact/equivalent/partial) |
| Qualidade | DONE | 0 erros, 19 avisos (revisões entre boletins; dupla contagem) |
| Compatibilidade espacial | DONE | AOI = 0,4654% do município → IBGE = B, CONAB = C; nenhuma fonte na escala da AOI |
| Compatibilidade temporal | DONE | IBGE n = 3 (2023–2025), CONAB 3 safras, Sentinel-2 34/36 meses |
| Testes | DONE | **137/137** offline; **10/10** externos opt-in |
| Modelo de produtividade / integração | NOT_STARTED | fora de escopo; exige autorização do portão de decisão |

Relatório: `geospatial/reports/V2_2_PRODUCTIVITY_DATA_COMPATIBILITY.md`.
Veredito do portão: **CAMINHO 2** (dados reais, escala municipal/estadual).

## V2.3 estudo exploratório municipal — branch `v2/agricultural-productivity-exploratory` (2026-11-11, D50–D53)

| Item | Estado | Evidência |
|---|---|---|
| Série Sentinel-2 histórica | DONE | 2017–2025 na grade da V2.1 (20 m, Perfil B, seleção por obstrução, lacunas preservadas) |
| Harmonização radiométrica | DONE | C1 × original: diferença de NDVI **0,0**, correlação **1,0** em 6 pares (2018–2025) — D50 |
| Uso do solo na AOI | PARTIAL | MapBiomas **bloqueado** (download suspenso; via GEE); ESA WorldCover → **77,6% (2020) / 81,2% (2021)** de lavoura — D51 |
| Calendário fenológico | BLOCKED | SISZARC/MAPA sem DNS; nenhuma janela inventada; agregação por ano civil — D52 |
| Rendimento-alvo | DONE | IBGE/PAM `rendimento_medio_kg_ha` (kg/ha), soja e milho, valores originais preservados |
| Conjunto pareado + estatísticas | DONE | `geospatial/data/processed/productivity_exploratory_dataset.csv` + p-valor por permutação e teste de tendência |
| Modelagem exploratória | CONDITIONAL | portão D53: **≥ 9 pares anuais por cultura**; abaixo disso, apenas descrição e correlação exploratória |
| Testes | DONE | **165/165** offline (70 novos da V2.3) |
| Integração ao produto/Ridge | NOT_STARTED | fora de escopo; requer aprovação do portão |

Relatório: `geospatial/reports/V2_3_EXPLORATORY_PRODUCTIVITY_STUDY.md`.

## V2.4 escala espacial e calendário oficial — branch `v2/agricultural-scale-harmonization` (2026-11-12, D54–D57)

| Item | Estado | Evidência |
|---|---|---|
| Calendário oficial (ZARC/MAPA) | DONE | 11 safras, 1.408 registros de Sorriso, 23 culturas, portaria de origem |
| Safra × ano PAM | DONE | 148 combinações com regra derivada + alternativa |
| Produtividade submunicipal | NONE (com evidência) | CONAB SUTIN traz área, não produtividade; MapBiomas 403/GEE; IMEA 500; SIGS/INCRA sem DNS |
| Referência submunicipal de área | DONE | CONAB SUTIN soja/MT 2021: 17 feições em Sorriso |
| Escala municipal do indicador | DONE | 16 blocos, mosaico de 2 tiles, recorte pelo polígono; piloto 2017-03: 0,5668 (AOI 0,5282) |
| Testes | DONE | **181/181** offline |
| Veredito | **CAMINHO B** | referência fina indisponível; escala municipal harmonizável |


## V2.7 - Robustez estatistica, validacao espacial e agronomia (2026-11-14)

| Item | Estado | Evidencia |
|---|---|---|
| Dependencia espacial caracterizada | DONE | r(T) = 0,8339 e r(P) = 0,6295 na banda de 400-425 km, em manifesto reproduzivel (`v27_spatial_dependence.json`); a limitacao "55 km" foi **refutada** (D76) |
| Inferencia agrupada (4 esquemas) + Conley + bootstrap wild + Holm | DONE | 12 familias de 21 hipoteses; 4/21 (bloco 250 km) a 13/21 (municipio) |
| Bootstrap wild calibrado por Monte Carlo | DONE | tamanho ~nominal para >= 10 grupos; **levemente** conservador com 5 (0,047; poder 53,5%) apos a grade recalculada; **dois defeitos reais corrigidos** (D79, D80, D85) |
| Politica de nulidade do bootstrap | DONE | as duas variantes sao reportadas; politica declarada (D81) |
| Janela fenologica de enchimento de graos | DONE | requisitos termicos publicados; 84 municipios, 1.027 linhas recalculadas (D78) |
| CAD territorial oficial | DONE | Embrapa Solos (Vasques et al. 2021), 90 m, CC BY-NC 3.0 BR; CAD 0-100 cm de 126 a 240 mm (D82) |
| Validacao territorial P1-P4 | DONE | reproduz a faixa da V2.6 (+1,35% a +6,36%); 132 valores de MAE identicos bit a bit |
| **Holdout espacial x temporal (P5)** | DONE | remove bloco **e** ano do treino (D86): soja **-3,30%**, milho +1,21% (hidrico +5,40%), milho 2a +16,92% |
| ERA5-Land nativo | BLOCKED | credencial CDS ausente; nenhuma conta criada, nenhuma credencial solicitada (D83) |
| Ampliacao do painel | ADIADA | decisao de escopo: a robustez estatistica precede a escala |
| Testes | DONE | **318/318** offline (262 da V2.6 + 56 da V2.7); 10/10 externos |
| Veredito | **CAMINHO A** | nenhuma integracao ao produto; a Ridge permanece unica na previsao de precos |

**Resultado cientifico central:** o ganho territorial da V2.6 depende do ano
compartilhado entre treino e teste. Por cultura: soja **nao robusto**
(inverte de sinal), milho **parcialmente robusto** (so as variaveis
hidricas resistem), milho 2a safra **robusto** no protocolo mais estrito.

Relatorio: `docs/V2_7_ROBUSTNESS_REPORT.md`. Checkpoints:
`docs/execution/v2.7/`. Decisoes D76-D86.
