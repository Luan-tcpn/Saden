# SADEN — Contexto e roadmap da V2

> Status: **V2.1 EXECUTADA EM BRANCH ISOLADA** (2026-11-11). A PoC Sentinel-2
> rodou com 4 cenas reais L2A e está documentada em
> `docs/V2_EXECUTION_STATUS.md`. A V1 permanece congelada (D40) e intocada.
> Este documento mantém o roteiro, os riscos e os critérios; decisões formais
> ficam em `docs/DECISIONS.md` (D41).
> Data: 2026-11-11.

## 1. Ponto de partida real (V1)

- Previsão com metodologia única **Ridge**; `?model=ridge` é apenas alias
  legado e qualquer outro valor retorna HTTP 400.
- AR(p) foi avaliado como challenger e **retirado do produto**; resultados
  históricos permanecem em `docs/FORECAST_EVALUATION.md`.
- Histórico experimental em `model_runs` preservado, sem migração.
- Gates da V1: 65/65 testes, smoke 9/9, E2E 57/57, Docker validado.
- Limitações vigentes: referência internacional (não preço físico regional),
  modelo univariado, série ~1 ano, intervalo gaussiano sem cobertura empírica,
  sem TLS/SMTP real/monitoramento/teste de carga, instância única.

## 2. Regra de entrada na V2

A V2 só começa se **todas** as condições abaixo forem verdadeiras:

1. Existe uma decisão nova registrada em `docs/DECISIONS.md` (D41+), com
   problema, alternativas, custo e critério de aceite.
2. A V1 está reproduzível: `npm test`, smoke e E2E verdes na árvore limpa.
3. O escopo escolhido tem evidência de valor (uso real, banca/orientador ou
   requisito técnico concreto), não apenas desejo de novidade.
4. Há tempo e ambiente para validar de verdade (Docker, navegador, fonte
   externa) — sem declarar concluído o que não foi executado.
5. `SADEN-TCC` continua intocado; mudanças ficam neste repositório.

## 3. Trilhas candidatas (prioridade proposta, não compromisso)

### T1 — Robustez operacional (maior valor por risco)
- TLS/reverse proxy, backup automatizado com verificação, logs com retenção,
  healthcheck externo e alerta de falha.
- Critério de aceite: reinício sem perda, restauração testada, health monitorado.
- Risco: ambiente de deploy inexistente; exige decisão de hospedagem.
- Dependência: definição do alvo (máquina local, VPS, serviço gerenciado).

### T2 — Observabilidade e desempenho
- Medir latência real por endpoint e custo de forecast sob carga; cache de
  forecast **somente se** a medição justificar (D12).
- Critério de aceite: números antes/depois, sem regressão funcional.
- Risco: otimização prematura; benchmark mal desenhado.
- Dependência: script de carga reproduzível e ambiente estável.

### T3 — Dados regionais (alto valor acadêmico, alta dependência externa)
- CEPEA (contratação), CONAB (CAPTCHA), IMEA (licença parcial-MT), B3 (futuros).
- Critério de aceite: contrato/autorização + fonte documentada + série
  comparável + declaração de nível (nacional/regional).
- Risco: custo, licença e instabilidade; scraping não autorizado é proibido.
- Dependência: convênio ou autorização formal; sem isso, trilha bloqueada.

### T4 — Modelagem (somente com protocolo experimental)
- Reavaliar challengers (SARIMA/ETS/ensemble) **fora do produto**, com mesmo
  split, mesmas métricas, teste intocado e decisão explícita de entrada.
- Critério de aceite: ganho consistente e reprodutível, com validação
  multi-horizonte e limite de complexidade.
- Risco: overfitting em ~1 ano de série; `val_n` pequeno; comparação injusta.
- Dependência: mais dados históricos e/ou fonte regional (T3).

### T5 — Experiência e acessibilidade
- Auditoria WCAG básica, navegação por teclado, contraste, estados de erro.
- Critério de aceite: checklist verificável + E2E ampliado.
- Risco: alegações de conformidade sem auditoria formal (evitar).
- Dependência: escopo e ferramenta de auditoria definidos.

## 4. Fora de escopo por padrão

- Reescrever a arquitetura (microsserviços, Python, ORM) sem necessidade medida.
- Trocar a metodologia do produto sem decisão e sem avaliação.
- Scraping de CEPEA/CONAB ou proxy de dados não autorizados.
- Prometer MAPE futuro, "production-ready" ou cobertura do intervalo.
- Apagar histórico de experimentos (`model_runs`/`forecasts`).

## 5. Critérios de saída (definition of done)

Uma trilha só é considerada concluída quando:

- implementação revisada e sem segredos no diff;
- testes novos cobrindo o comportamento (sem reduzir a suíte existente);
- smoke/E2E executados quando houver superfície de UI/API;
- Docker revalidado quando o artefato mudar;
- documentação atualizada com números reais e limitações honestas;
- tag/release apenas com push e evidência confirmados.

## 6. Perguntas abertas

1. Qual é o alvo real de execução (local, VPS, PaaS)? Sem isso, T1 fica abstrata.
2. Existe orçamento/convênio para CEPEA ou autorização IMEA? Se não, T3 para.
3. Há série histórica maior disponível para reduzir o risco de T4? De onde?
4. Qual nível de disponibilidade é exigido pela banca/uso real?
5. Quem opera backup/restauração e com qual frequência?
6. A acessibilidade precisa de laudo formal ou de checklist técnico?
7. Qual o critério objetivo para "V2 pronta" (data, demonstração, publicação)?

## 7. Riscos transversais

| Risco | Impacto | Mitigação |
|---|---|---|
| Escopo inflado | V2 nunca fecha | uma trilha por vez, com critério de aceite |
| Fonte externa instável | dados faltando | cache, 502 honesto, fallback declarado |
| Série curta | modelo frágil | não prometer precisão; avaliar fora do produto |
| Deploy sem TLS | credenciais expostas | T1 antes de qualquer uso real |
| Histórico perdido | perda de auditabilidade | backups + proibição de migração destrutiva |
| Docs divergirem do código | perda de confiança | atualizar docs no mesmo commit |

## 8. Regras de honestidade (herdadas da V1)

- Nada de números inventados, fontes fictícias ou resultados extrapolados.
- Docker/push/release só com execução real e evidência.
- Separar sempre FATO / INTERPRETAÇÃO / LIMITAÇÃO / POSSÍVEL IMPACTO.
- `SADEN-TCC` é somente leitura; o autor decide o que levar ao texto acadêmico.

## 9. Primeiro passo sugerido (quando autorizado)

Escolher **uma** trilha, escrever D41 com problema/alternativas/custo/critério,
e só então abrir branch. Sem decisão registrada, a V2 permanece não iniciada.

## 10. O que foi realmente feito na V2.1

### 10.1 PoC (branch `v2/geospatial-foundation`)

- **Branch:** `v2/geospatial-foundation`, derivada de `v1-final` (`3f7ad33`).
  Nenhum merge em `main`; tag e branches de arquivo intactas.
- **Trilha escolhida:** dados geoespaciais (T3), escopo mínimo — Sentinel-2
  L2A, uma janela técnica, um pipeline local.
- **Fonte:** Earth Search / Element 84, coleção `sentinel-2-c1-l2a`, acesso
  anônimo e gratuito.
- **AOI:** Sorriso-MT (IBGE `5107925`) + janela de `0,10° × 0,10°`. Recorte
  técnico, não talhão.
- **Produto:** NDVI/EVI/NDMI em grade comum de 20 m (`EPSG:32721`), máscara
  SCL conservadora, 4 cenas reais (jun–set/2025), GeoTIFFs + CSV + PNG +
  manifesto JSON com checksums.
- **Testes:** 30/30 sintéticos offline; V1 revalidada em 65/65.

### 10.2 Validação V2.1 (branch `v2/geospatial-validation`)

- **Branch:** `v2/geospatial-validation` (derivada da fundação), com checkpoint
  imutável da PoC na tag `v2-poc-sentinel2` e bundle de segurança verificado.
- **A — reprodução/auditoria:** PoC reexecutada em diretório separado; grade
  idêntica e diferença **0,0** em todas as estatísticas; auditoria radiométrica
  confirma escala/offset do metadado e do COG, sem dupla aplicação.
- **B — máscara SCL:** Perfil A (histórico) × Perfil B (exclui 2 e 6)
  comparados quantitativa e visualmente; efeito ≤ 0,18% na média do NDVI.
  Decisão **D43**: A na reprodução da PoC, B como padrão da V2.1.
- **C — geometria:** limite municipal oficial do IBGE validado (9.293,47 km²);
  bbox histórica tem **0,51 km² fora** do município; três AOIs diferenciadas;
  custo do município inteiro estimado (23,2 M px/banda) e não executado.
  Decisão **D42**.
- **D — mosaico:** dois tiles do mesmo `datatake` (2023-06-20), regra
  `first_valid_wins`, mapa de origem por pixel; diferença na sobreposição com
  correlação 0,99999 nos índices. Decisão **D44**.
- **E — série 2023–2025:** série mensal exploratória sobre a AOI de validação,
  seleção por fração obstruída sobre a AOI e lacunas explícitas (D45).
- **Testes:** 95/95 sintéticos offline; suíte de rede separada e opt-in (4/4 OK).
- **Fora de escopo (continua fora):** UI, dashboard, endpoint, integração de
  índices ao produto, modelo de preço/produtividade, outros satélites,
  serviços pagos.

Relatório técnico completo (com FATO/INTERPRETAÇÃO/LIMITAÇÃO por seção):
`docs/V2_1_VALIDATION_REPORT.md`. Estado operacional:
`docs/V2_EXECUTION_STATUS.md`. Números, arquivos, limitações e comandos
estão também em `geospatial/README.md`. Não há conclusão agronômica: os
índices descrevem reflectância em recortes geográficos.

### 10.3 V2.2 — base observada de produtividade (branch `v2/agricultural-productivity-data`)

- **Branch:** `v2/agricultural-productivity-data` (derivada de
  `v2/geospatial-validation` / `e1d7f30`); V1 e V2.1 intocadas.
- **Fontes investigar:** IBGE/SIDRA (PAM, tabela 5457 — municipal, 1974–2025,
  observada, sem chave) e CONAB (Boletim de Safras — **estadual**, estimada e
  revisada). SIGS/`api.conab.gov.br` (DNS) e `dados.gov.br` (401) bloqueados
  e registrados.
- **Dados obtidos:** 4.472 registros PAM de Sorriso (2013–2025) + 444 da
  CONAB (MT, safras 23/24–25/26) = **4.916 observações normalizadas**,
  com valor/unidade originais preservados, natureza e escopo explícitos.
- **Qualidade:** 0 erros, 19 avisos (revisões entre boletins; dupla contagem
  agregado × componente), 5.866 achados informativos.
- **Compatibilidade espacial:** AOI = **0,4654%** do município → IBGE = **B
  (contextual)**, CONAB = **C**; nenhuma fonte oficial na escala da AOI.
- **Compatibilidade temporal:** IBGE 2023–2025 (**n = 3**), CONAB 3 safras,
  Sentinel-2 mensal com 2 lacunas preservadas; sem calendário validado.
- **Culturas-piloto:** soja e milho (exatas); algodão condicionado (caroço ×
  pluma); café e trigo descartados (produção municipal zero). Decisões
  **D46–D49**.
- **Veredito do portão:** **CAMINHO 2** — há base real e auditável, mas só em
  escala municipal/estadual; a V2.3, se autorizada, deve ser exploratória e
  municipal, com n ≥ 10 anos.
- **Fora de escopo (continua fora):** modelo de produtividade, integração ao
  Ridge, UI/dashboard, API pública de produtividade.

Relatório: `geospatial/reports/V2_2_PRODUCTIVITY_DATA_COMPATIBILITY.md`.

### 10.4 V2.3 — estudo exploratório municipal (branch `v2/agricultural-productivity-exploratory`)

- **Branch:** derivada de `v2/agricultural-productivity-data` (`775d57b`); V1,
  V2.1 e V2.2 intocadas; bundle da V2.3 verificado.
- **Harmonização radiométrica (D50):** C1 e coleção original são
  **numericamente idênticas** com as conveções de DN corretas — 6 pares de
  datas (2018–2025) com diferença de NDVI **0,0** e correlação **1,0**. O
  pipeline da V2.1 permanece intacto (perfil histórico separado).
- **Série histórica 2017–2025** na grade da V2.1 (20 m, Perfil B, seleção por
  obstrução, lacunas preservadas).
- **Uso do solo (D51):** MapBiomas **bloqueado** (download suspenso; via GEE);
  ESA WorldCover adquirido → AOI **77,6% (2020) / 81,2% (2021)** de lavoura.
- **Calendário (D52):** SISZARC sem DNS; nenhuma janela fenológica inventada;
  agregação por ano civil com ressalva.
- **Portão (D53):** modelagem exploratória só com **≥ 9 pares anuais por
  cultura**; abaixo disso, descrição e correlação exploratória.
- Testes: **165/165** offline. Relatório:
  `geospatial/reports/V2_3_EXPLORATORY_PRODUCTIVITY_STUDY.md`.

### 10.5 V2.4 — escala espacial, calendário ZARC e referências agrícolas (branch `v2/agricultural-scale-harmonization`)

- **Calendário oficial (D54)**: ZARC do MAPA (`dados.agricultura.gov.br`,
  CC-BY) — 11 safras, **1.408 registros de Sorriso**, 23 culturas, janelas por
  decêndio/solo/ciclo e portaria de origem.
- **Produtividade submunicipal (D56)**: **não existe** em fonte pública
  reproduzível. A CONAB SUTIN entrega **área** por feição (submunicipal), sem
  produtividade; MapBiomas GCS 403, GEE exige conta; IMEA 500; SIGS/INCRA sem
  DNS.
- **Escala municipal (D57)**: indicador NDVI agregado por 16 blocos sobre a
  área agrícola (WorldCover 40) e o polígono do município, com mosaico de dois
  tiles; piloto 2017-03 → 11.999.215 pixels agrícolas (≈4.800 km²), NDVI médio
  0,5668 (AOI 43,26 km²: 0,5282).
- **Referência espacial e agronômica separadas (D55)**.
- Testes: **181/181** offline. Relatórios: `geospatial/reports/V2_4_*.md`.

### 10.6 V2.5 — pareamento sazonal, integração espacial e reavaliação (branch `v2/seasonal-spatial-pairing`)

- **Branch:** derivada de `v2/agricultural-scale-harmonization` (`ba3fa5a`);
  V1, V2.1, V2.2, V2.3 e V2.4 intocadas; sem merge em `main`; bundle de
  recuperação verificado (SHA-256 `84FE004E…56DCE`).
- **Série municipal concluída (D59, D65):** 47 meses (jan/fev/set–dez de
  2017–2025 — todos os meses observados da série de referência que caiem nas
  janelas agrícolas) × 4 variantes de máscara = **188 linhas**, com
  proveniência completa (cena, tile, perfil radiométrico, cobertura válida,
  fração obstruída, quantis). Reprocessamento incremental → **SHA-256
  idêntico**, **0 duplicatas**.
- **Correção do ZARC (D62, D63):** o campo `decendios_com_risco` é **textual**
  (`baixo`/`medio`/`alto`) — a leitura da V2.4 produzia janelas **vazias**; e a
  âncora de ano dos decêndios 1–12 é o **segundo** ano da safra. Verificado por
  um critério objetivo: a portaria que publica a recomendação precede o
  início da janela (165 violações → **0**). Regra oficial de decêndios: 3 por
  mês (1–10, 11–20, 21–fim), com fevereiro e bissextos.
- **Janela recomendada:** risco **≤ 20%** (muito baixo ou baixo — critério
  oficial do MAPA) e **modal** entre as combinações oficiais de solo/ciclo;
  desempate determinístico e independente do rendimento.
- **Relação safra → PAM (D60):** regra principal = **ano de colheita**
  (`safra_fin`); alternativa = ano de plantio. Milho 1ª e 2ª safras **separados**
  — a PAM publica o **total do ano**, incompatibilidade declarada; a 2ª ficou
  com n = 3 (não avaliável).
- **Dataset pareado (D64):** 228 linhas em **duas fatias** — `zarc_sazonal`
  (janela oficial) e `ano_civil_v23` (**réplica da V2.3**, verificada par a
  par com diferença máxima **1,1·10⁻¹⁶**). n efetivo = **anos com
  rendimento**: soja 8, milho 8, milho 2ª 3 (sazonal); 9/9 (ano civil).
- **Estatística (D61):** Pearson, Spearman, permutação (5.000, semente fixa),
  IC 95% por bootstrap, **correção de Holm** (32 testes), correlação
  detrendizada e walk-forward com os mesmos baselines da V2.3, **alinhado nos
  mesmos anos de teste** (2023–2025).
- **Resultado — CAMINHO B:** mudar a escala **reduz** a correlação (soja
  0,432 → 0,302; milho 0,200 → −0,015) e mudar a janela também (soja
  0,432 → 0,372; milho 0,200 → −0,455). Nenhum dos 32 testes é significativo
  após Holm (p = 1,000) e o modelo com NDVI **não** supera a média histórica
  em nenhuma das 8 configurações. **A hipótese da V2.4 está refutada.**
- **Representatividade:** a AOI subestima o NDVI municipal em **+0,037**
  (V2.4 estimava +0,039); a diferença média **anual** varia de −0,0002
  (2018) a +0,0775 (2022) — **não é estável**. Sensibilidade à máscara:
  desprezível (4 variantes → resultados praticamente idênticos).
- **Correções de engenharia reais** encontradas na auditoria (8): máscara
  booleana comparada com `== 40`; `transform` do WorldCover não ajustado à
  janela; leitura sem validação (janelas vazias); topo do bloco; `NaN` no
  acumulador; risco textual do ZARC; âncora de ano; e `walk_forward` calculando
  os baselines sobre o **indicador** em vez do **rendimento**.
- Testes: **213/213** offline (33 novos da V2.5). Relatórios:
  `geospatial/reports/V2_5_SEASONAL_SPATIAL_PAIRING.md` e
  `geospatial/reports/V2_5_ADVISOR_SUMMARY.md`.
- **Nada foi integrado** ao Ridge de preços, à API ou à interface (D40, D41).

### 10.7 V2.6 — base agroclimática e painel multi-municipal (branch `v2/agroclimatic-productivity-panel`)

- **Encerramento do NDVI (D66):** a hipótese do NDVI como variável de
  produtividade foi **encerrada** com protocolo; os indicadores Sentinel-2
  permanecem como material de pesquisa e referência geoespacial.
- **Fontes meteorológicas (D67):** INMET (668 estações; séries diárias por
  **HTTP Range** — 808 kB lidos por estação/ano), NASA POWER (MERRA-2 + CERES,
  base reanalisada do painel), ERA5-Land e ERA5 via Open-Meteo (**parcial**:
  HTTP 429 sob uso intensivo), CHIRPS e ARCO **bloqueados** (sem DNS), CDS
  **exige chave de conta** (não criada). Toda linha carrega `source_type`
  (`station_observation` / `reanalysis`).
- **Métodos agroclimáticos (D68):** graus-dia com **perfis por cultura**
  (soja de Ometto 1981 com Tb = 14 °C; soja de Gilmore & Rogers 1958 com
  Tb = 10 °C; milho da Embrapa Milho e Sorgo com Tmax ≤ 30 °C e Tmin ≥ 10 °C);
  ET0 pelo FAO-56 Penman-Monteith (vento de 10 m → 2 m pelo coeficiente 0,4),
  Thornthwaite (1948) e Hargreaves-Samani, cada um **identificado**; balanço
  hídrico de Thornthwaite & Mather (1955) com CAD por perfis de solo
  documentados (50 mm do MAPA como principal).
- **Janela descontígua (D73):** nas culturas de ciclo curto do Nordeste, usa-se
  o **bloco contíguo de maior duração** da janela oficial; os meses do bloco
  secundário são descartados, não agregados.
- **Painel (D69):** 1.622 municípios elegíveis (produção observada em ≥ 7 dos
  9 anos, área positiva, geometria e estação a até 80 km) → 2.780 pares
  município-cultura; painel final de **19.402 observações utilizáveis**
  (soja 1.225 municípios, milho 1.063, milho 2ª 505).
- **Resultado (D70):** p ajustado (Holm) = **0,0036** para as variáveis
  agroclimáticas — contra **1,000** do NDVI na V2.5. O **déficit hídrico** é
  o sinal mais forte (t ≈ −17). Na **validação temporal** a média histórica
  vence; na **validação territorial** (municípios inteiros) o modelo com clima
  vence nas 6 combinações (ganho de 1,7% a 6,3%). O mesmo padrão aparece na
  **via de observação do INMET** (146 municípios de soja): é validação
  independente da reanálise.
- **Comparação INMET × reanálise (D75):** temperatura r = 0,854 (viés
  +0,37 °C); precipitação r = 0,602 com subestimação de ~8% — viés conhecido
  do MERRA-2 em trópicos, não erro de implementação.
- **Artefatos grandes fora do Git (D74).**
- Testes: **262/262** offline. Relatórios: `geospatial/reports/V2_6_*.md`.

## 11. Próximos passos propostos (não iniciados)

1. Revisar a V2.1 com orientador antes de ampliar escopo.
2. **V2.2 — feita** (base observada de produtividade + compatibilidade):
   ver §10.3 e o relatório
   `geospatial/reports/V2_2_PRODUCTIVITY_DATA_COMPATIBILITY.md`.
3. **V2.3 (condicional)** — só com os pré-requisitos do portão de decisão:
   ampliar a série Sentinel-2 para 2017–2025 (n ≥ 9–10), validar o calendário
   fenológico em fonte oficial, identificar o uso do solo na AOI e fixar a
   variável-alvo (rendimento médio municipal). Escopo: estudo **exploratório
   na escala municipal**; não é validação da AOI.
4. **V2.4** — avaliar se variáveis agronômicas ajudam a previsão de preço,
   com protocolo experimental, Ridge como baseline obrigatório e teste
   intocado.
5. Robustez operacional da V1 (TLS, SMTP, backup, monitoramento) segue como
   trilha independente de maior valor para produção.
