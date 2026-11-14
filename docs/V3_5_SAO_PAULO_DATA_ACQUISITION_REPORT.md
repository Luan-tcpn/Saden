# SADEN V3.5 — Relatório de aquisição de dados de São Paulo

**Data:** 2026-11-14 · Manifesto: `geospatial/data/manifests/v35_sp_acquisition.json`

---

## 1. Princípio

SP entrou pela **cadeia existente**, não por um pipeline paralelo:

| etapa | componente reutilizado |
|---|---|
| municípios e geometria | `agroclimate.boundaries.municipality_features` (malhas IBGE, ano 2025) |
| clima diário | `agroclimate.gridded.fetch_point("nasa_power")` + `normalize_nasa_power` |
| produtividade | `agri.pam_panel.fetch_state_municipalities` + `fetch_state_pam` (SIDRA 5457) |
| janela agrícola | `agri.zarc_panel.fetch_panel` |
| CAD | `tools/v30_cad_acquire.py` (WCS, `scaleFactor=0.2`, máscara do polígono) |
| painel | `agroclimate.panel.build_panel` (mesmo perfil de solo e método de ET0) |
| janela corrigida e descritores | `v31_rebuild_panel._aggregate` + `v33_water_variables._descriptors` |

## 2. Fontes e identificação

| fonte | produto | período | unidades | licença |
|---|---|---|---|---|
| IBGE — malhas municipais (geoftp) | geometria, centróide, área, bbox | 2025 | — | aberta |
| NASA POWER (comunidade AG) | clima diário | 2016–2025 | °C, mm, MJ/m², %, km/h, kPa | aberta |
| IBGE/SIDRA tabela 5457 (PAM) | área, quantidade, rendimento | 2017–2025 | ha, t, kg/ha | aberta |
| MAPA/ZARC — tábua de risco | janela de semeadura por cultura, solo, ciclo | 2005/06–2026/27 | meses/decêndios | aberta |
| Embrapa Solos (GeoInfo WCS) | água disponível por camada | estático | mm | **CC BY-NC 3.0 BR** |

## 3. Volumes adquiridos

| etapa | resultado | hash SHA-256 (início) |
|---|---|---|
| municípios | **645** (todos com código iniciando em `35`) | `8a1c1486…` |
| clima | **645/645 municípios, 0 falhas**, 2.356.185 linhas | `3b0f874f…` |
| produtividade | 46.440 registros (11.610 de rendimento) | `da10560a…` |
| ZARC | 1.082.148 linhas de janela (10 safras) | `2e00bf54…` |
| CAD | **584 municípios** com estatística por profundidade | `v35_cad_polygon_sp.json` |
| painel base | 19.608 linhas, **10.805 utilizáveis** | — |

O clima levou 430 s com 4 workers e **nenhuma falha**. O download é cacheado por
município (`data/external/sp_climate_cache/`, fora do Git) e a reexecução usa o
cache (~35 s).

## 4. Cobertura por cultura

| cultura | linhas utilizáveis | municípios | anos |
|---|---:|---:|---:|
| soja | 3.633 | 507 | 8 |
| milho | 4.397 | 582 | 8 |
| milho 2ª | 2.775 | 566 | 9 |

## 5. Funil de elegibilidade

| etapa | municípios |
|---|---:|
| SP no IBGE | 645 |
| com classificação MRS | 643 |
| com CAD | 584 |
| com painel utilizável | 582 |

**63 municípios de SP não entram no painel analítico.** Das 8.803 linhas
excluídas no painel base de SP, os motivos medidos são:

| motivo | linhas |
|---|---:|
| sem rendimento observado do IBGE/PAM | 4.569 |
| dias climáticos na janela = 0 (< 30) | 4.150 |
| cobertura climática na janela < 0,60 | 156 (somando as faixas) |

Nenhum valor foi imputado. "Dias climáticos na janela = 0" indica safra sem
janela ZARC aplicável àquele município/cultura — não falha de aquisição (o clima
tem 3.653 dias para todos os 645 municípios).

## 6. Qualidade

* **Duplicidade**: 0 códigos IBGE repetidos; 0 colisões com os seis estados.
* **Unidade de produtividade**: `kg/ha`, a mesma do painel histórico; o campo
  `yield_unit_original` guarda a unidade da fonte.
* **Área**: usa-se **área colhida** (não plantada) para o rendimento, como no
  painel histórico.
* **Clima**: 3.653 dias por município (2016-01-01 a 2025-12-31), mesma janela dos
  seis estados; 0 municípios com falha.
* **Janela ZARC**: contrato corrigido da V3.1 (primeiro dia do primeiro mês ao
  último dia do último mês); nenhuma janela genérica por cultura.
* **CAD**: mesma fonte, mesma resolução (`~460 m`), mesma máscara de polígono;
  média, mediana, desvio e percentis por profundidade.
* **Nada sintético**: nenhuma interpolação de produtividade, nenhum preenchimento
  de ano ausente.

## 7. Limitações

1. **Milho 2ª safra**: a PAM publica o **total anual** de milho (1ª + 2ª); o
   painel marca essas linhas como `retrospective_mask` e
   `semantic_compatibility = incompativel`. Isso já era verdade nos seis estados
   e não muda com SP.
2. **CAD não cobre os 645**: 584 têm estatística; os demais não têm linha
   analítica utilizável, então não entram na modelagem.
3. **Clima de uma única fonte** (NASA POWER). ERA5-Land e CHIRPS continuam
   bloqueados (credencial / DNS).
4. **Participação na produção nacional não é estimada**: ver relatório de
   cobertura.

## 8. Reprodutibilidade

```
python tools/v35_acquire_sp.py --stage municipalities
python tools/v35_acquire_sp.py --stage climate       # 430 s na primeira vez
python tools/v35_acquire_sp.py --stage productivity
python tools/v35_acquire_sp.py --stage zarc
python tools/v30_cad_acquire.py --states SP \
    --municipalities geospatial/data/processed/panel_municipalities_sp.csv \
    --geojson geospatial/data/processed/panel_municipalities_sp.geojson \
    --panel geospatial/data/processed/panel_sp_v35.csv \
    --out geospatial/data/manifests/v35_cad_polygon_sp.json
python tools/v35_acquire_sp.py --stage panel
python tools/v35_region_mapping.py
python tools/v35_build_windows.py
```

O painel histórico **não é tocado**: `panel_municipalities_v34.csv` é o snapshot
congelado dos seis estados e `v31_panel_windows.csv` permanece intacto.

## 9. Erros de execução registrados

1. **Corrida no arquivo de status**: as etapas rodaram em paralelo e a escrita de
   `v35_sp_acquisition.json` sobrescreveu a entrada de clima. Corrigido
   reexecutando a etapa (cache → 35 s).
2. **Painel de SP sem latitude/longitude**: o painel base não carrega centróide;
   a primeira execução gerou 0 linhas de janela. Corrigido com junção por
   `ibge_code` ao cadastro municipal — 10.805 linhas geradas.
3. **`tools/v35_region_mapping.py`**: `Counter.add` inexistente, mascarado por um
   manifesto antigo em disco. Corrigido e reexecutado com verificação de que as
   linhas dos seis estados permanecem idênticas às da V3.4.
