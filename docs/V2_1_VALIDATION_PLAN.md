# SADEN V2.1 — Plano de validação geoespacial (checkpoint A–E)

> Branch: `v2/geospatial-validation` (derivada de `v2/geospatial-foundation`,
> commit `2e5b3ef`). Checkpoint imutável da PoC: tag anotada
> `v2-poc-sentinel2`. V1 intocada (`3f7ad33`, tag `v1-final`).
> Bundle de segurança: `..\SADEN_V2_1_RECOVERY_2026-11-11\saden-v2-1-start-2026-11-11.bundle`
> (2.435.845 bytes, SHA-256 `74727C33…B1274`, `git bundle verify` OK).
> Data: 2026-11-11.

## 1. Estado real de partida (verificado)

| Item | Estado |
|---|---|
| `main` / `v1-final` / `archive/v1-final` | `3f7ad33` local e remoto; tag objeto `e62a5372` |
| `v2/geospatial-foundation` | `2e5b3ef`, sincronizada com `origin` |
| Árvore de trabalho | limpa antes do início da missão |
| PoC | 4 cenas L2A, 12 GeoTIFFs, CSV, 4 PNG, manifestos em `geospatial/artifacts/` |
| Testes offline da PoC | 30/30 |
| V1 backend | 65/65 (revalidado na missão anterior) |

## 2. Arquivos envolvidos

| Responsabilidade | Arquivo atual |
|---|---|
| Parâmetros STAC/AOI/bandas/máscara | `geospatial/s2_poc/config.py` |
| Malha IBGE e janela técnica | `geospatial/s2_poc/aoi.py` |
| Busca/STAC e seleção mensal | `geospatial/s2_poc/stac_search.py` |
| Leitura remota, grade, reamostragem, GeoTIFF | `geospatial/s2_poc/read.py` |
| Escala/offset, máscara SCL, índices, estatísticas | `geospatial/s2_poc/indices.py` |
| Orquestração/CSV/manifesto | `geospatial/s2_poc/pipeline.py` |
| Prévia PNG | `geospatial/s2_poc/render.py` |
| CLI | `geospatial/run_poc.py` |
| Testes | `geospatial/tests/` |

## 3. Riscos identificados (e tratamento)

1. **Comentário de SCL incorreto.** O código da PoC rotulava a classe 2 como
   “vegetação muito baixa/solo”. A tabela oficial (Copernicus Data Space)
   define `2 = Dark Area Pixels`. O comportamento (manter 2) não será alterado
   silenciosamente: será comparado e documentado (Checkpoint B).
2. **Licença declarada no STAC.** A coleção `sentinel-2-c1-l2a` declara
   `license: proprietary`, embora o Registry of Open Data on AWS afirme
   “free, full and open” e o acesso seja anônimo. Registrar as duas fontes,
   sem afirmar licença única.
3. **Offset radiométrico.** Baselines 2023–2025 observados: 05.09, 05.10 e
   05.11. Todos ≥ 04.00, com `scale=0.0001`, `offset=-0.1` nos metadados.
   `rasterio.read()` devolve DN uint16 bruto; a escala **não** é aplicada
   automaticamente. Qualquer baseline < 04.00 deve **bloquear** o asset.
4. **Bbox histórica não está inteiramente no município.** Medição preliminar:
   120,16 km² de bbox, 119,65 km² dentro (99,58%). O centroide não basta; a
   interseção será calculada e documentada.
5. **Custo do município inteiro.** 9.293 km² a 20 m ≈ 23,2 milhões de
   pixels/banda (~93 MB float32 por banda e por data). Processar o município
   em 36 meses é inviável e desnecessário: usar AOIs de validação.
6. **Dois tiles.** `21LXG` e `21LXF` se sobrepõem em faixa de ~0,094° de
   latitude. Uma AOI de 0,06° centrada em `(-55.6009, -12.7039)` está dentro
   do município e é coberta **inteiramente pelos dois tiles** → caso real para
   mosaico e medida de diferença na sobreposição.
7. **Série temporal.** Meses sem cena utilizável serão marcados
   `no_usable_observation`; nenhum preenchimento/interpolação.

## 4. Desenho dos checkpoints

### A — Reprodução e auditoria

- Reexecutar a PoC em diretório separado (`artifacts/repro_poc/`), sem tocar
  nos resultados anteriores; comparar grade, contagens e estatísticas com o
  manifesto original; investigar diferenças.
- Auditar por item: baseline, datatake/órbita, nuvem, CRS, dtype, nodata,
  scale/offset, presença de escala no arquivo (`ds.scales`/`ds.offsets`) e
  ausência de dupla aplicação.
- Verificar `DN=0 → NaN` antes da escala e o `+1` do EVI em reflectância.

### B — Máscara SCL

- Perfil A (histórico): exclui `0,1,3,7,8,9,10,11`.
- Perfil B (restritivo): A + `2` + `6`.
- Perfil C: contagem por classe e contribuição de cada classe para os índices
  (diagnóstico, sem virar opção de produto).
- Métricas: contagem/percentual por classe, válidos, área estimada por pixel,
  distribuição (média, mediana, p5/p25/p75/p95, desvio, min/max), pixels que
  mudam de estado entre A e B, mapas de máscara.
- Decisão: manter A como referência se a evidência não justificar mudança;
  qualquer mudança exige justificativa escrita e reprodutível.

### C — Geometria municipal

- Malha IBGE `5107925`, qualidade `maxima` (2.689 vértices), versão/URL/data.
- Validar topologia, anel, área geodésica e em projeção de área igual.
- Três geometrias explícitas: município, AOI histórica (preservada), AOI de
  validação (0,06°, dentro do município e dos dois tiles).
- Quantificar bbox histórica: área total, dentro, fora, percentual.
- Estimar pixels/memória para o município inteiro e registrar limite
  operacional.

### D — Dois tiles

- Caso real: itens contemporâneos de `21LXG` e `21LXF` na mesma data/datatake.
- Mosaico determinístico: prioridade explícita (tile primário) e preenchimento
  de nodata pelo secundário; mapa de origem por pixel.
- Quantificar diferença na sobreposição (reflectância e índices) antes/depois;
  checar transform/resolução/CRS, lacunas e duplicação.
- Se não houver par contemporâneo, registrar bloqueio com evidências.

### E — Série 2023–2025

- Busca mensal (36 meses), até 4 candidatas por mês ordenadas por nuvem do
  tile; seleção pela **fração obstruída sobre a AOI** (classes SCL de nuvem/
  sombra/saturado/nodata), não só `eo:cloud_cover`.
- Processar com a máscara decidida em B; registrar baseline por cena.
- CSV mensal com `status`, IDs, datas, cobertura válida, estatísticas e
  metadados; meses sem observação ficam explicitamente vazios.
- Gráficos com lacunas reais (sem linha contínua sobre meses ausentes).

## 5. Testes

Offline (padrão, sem rede): fórmulas, escala/offset, baseline não suportada,
nodata/NaN/inf/denominador, perfis SCL, classes, alinhamento, reamostragem
categórica × contínua, interseção bbox×polígono, mosaico sintético com
sobreposição conhecida, seamline/nodata, meses ausentes, manifesto/SHA-256.

Externos (separados, opcionais): descoberta STAC, reprodução real, mosaico
real, série 2023–2025. Nunca chamados de “offline”.

## 6. Critérios de aceite

Os dez blocos da seção 12 do prompt mestre. Qualquer item dependente de
indisponibilidade externa será marcado **BLOQUEADO** com evidência, nunca
“aprovado”.

## 7. Limites de escopo (não fazer)

Sem UI, dashboard, endpoint, modelo de produtividade/preço, integração ao
Ridge, clima, SADEN-TCC ou processamento do município inteiro em alta
resolução. Nenhuma conclusão agronômica a partir de índices.
