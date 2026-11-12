# SADEN V2.6 — Painel multi-municipal de produtividade e clima

> Branch: `v2/agroclimatic-productivity-panel`. Execução: 2026-11-12.
> Artefato principal: `geospatial/data/processed/agroclimatic_productivity_panel.csv`
> (35.894 linhas; 19.402 utilizáveis).
> Manifestos: `agroclimatic_panel.json`, `panel_eligibility.json`,
> `zarc_panel.json`, `pam_panel.json`.
> Decisões: D66–D72.

---

## 1. O problema que o painel resolve

**FATO.** A V2.5 trabalhou com **um município** (Sorriso/MT) e **8 anos**,
produzindo **n = 8 pares por cultura**. Esse tamanho de amostra não permite
separar o efeito do clima do efeito do ano, e não permite generalizar.

**FATO.** O alvo da PAM é **municipal**: o rendimento médio de um município
depende do clima **e** do portfolio de culturas, do solo, do manejo e da
tecnologia. Num único município, todas essas causas estão confundidas com o
clima.

**Decisão (D66, D69).** A V2.6 constrói um **painel de múltiplos municípios**
com variáveis agroclimáticas, para que a variação **transversal** (entre
municípios) e a variação **temporal** (entre anos) possam ser analisadas
separadamente.

---

## 2. Construção do painel

### 2.1 Cadeia de aquisição

```
IBGE localidades ──▶ malhas municipais (shapefile oficial, 1 por UF)
        │
        ├──▶ PAM/SIDRA 5457 (1 consulta por UF, 2 produtos, 4 variáveis, 9 anos)
        ├──▶ ZARC/MAPA   (11 safras nacionais em streaming, filtradas por geocódigo)
        └──▶ INMET        (668 estações; série diária por leitura HTTP Range)

        ▼
  climate_daily.csv ──▶ climate_daily_audited.csv (auditoria)
        ▼
  agroclimatic_productivity_panel.csv
```

### 2.2 O que cada fonte contribuiu

| Fonte | Volume | Papel |
|---|---:|---|
| PAM (SIDRA 5457) | 128.160 registros em 6 UFs | alvo de produtividade (rendimento, área, produção) |
| ZARC (MAPA) | **2.374.625** registros (11 safras × 1.622 municípios × solo × ciclo) | janela de plantio oficial por município, safra, cultura, solo, ciclo, risco e portaria |
| INMET | 668 estações catalogadas; séries diárias por estação | base de **observação** para validação independente |
| NASA POWER (MERRA-2) | 1.622 municípios × 10 anos × 3.653 dias | base **reanalisada** espacialmente consistente do painel |

**FATO.** O ZARC multi-municipal foi obtido **sem baixar e versionar** as
tabelas nacionais: cada safra (≈200 MB) é baixada em **streaming** e apenas
as linhas dos geocódigos solicitados são mantidas em memória. O filtro é pelo
**geocódigo IBGE**, não pelo nome do município — o filtro por nome da V2.4
produzia falso positivo.

---

## 3. Critérios de elegibilidade (fixados antes da análise)

**D69.** Um município entra no painel, para uma cultura, se:

1. tiver rendimento médio **observado** (PAM) positivo em **≥ 7 dos 9** anos de
   2017–2025;
2. tiver área colhida positiva em ≥ 1 ano;
3. tiver geometria municipal oficial disponível;
4. tiver ≥ 1 estação do INMET dentro do município ou a até 80 km.

**FATO.** 1.622 municípios distintos atingiram o critério → **2.780 pares
município-cultura elegíveis**. Motivos de exclusão estão registrados em
`panel_excluded_municipalities.csv`.

**FATO.** Os critérios **não** usam clima nem desempenho estatístico: são
critérios de **disponibilidade e consistência de dados**.

### 3.1 Distribuição territorial do painel final

| UF | Soja (obs) | Milho (obs) | Milho 2ª (obs) |municípios na amostra |
|---|---:|---:|---:|---:|
| MT | 911 | 997 | 353 | 142 |
| GO | 1.558 | 1.567 | 285 | 246 |
| MS | 586 | 552 | 428 | 79 |
| PR | 2.863 | 2.966 | 1.836 | 399 |
| RS | 2.966 | 1.428 | — | 499 |
| BA | — | 106 | — | 417 |
| **Total** | **8.884** | **7.616** | **2.902** | **1.782** |

**FATO.** A **Bahia** não tem soja nem milho no painel final: as janelas
oficiais do ZARC para as culturas de ciclo curto dortem (março–junho e/ou
outubro–dezembro) não atingiram a cobertura mínima de dados climáticos. É
uma limitação **da janela**, não da base meteorológica — e é coerente com a
agronomia: na Bahia o calendário de plantio é bimodal e não coincide com o
ciclo das culturas do Centro-Sul.

**FATO.** O milho 2ª safra aparece em **5** UFs (ausente no RS, onde a
recomendação do ZARC para a 2ª safra se sobrepõe à janela da 1ª).

---

## 4. Estrutura do painel

Cada linha é uma **observação** (município × cultura × safra × ano × fonte
climática) com 40+ campos:

| Bloco | Campos |
|---|---|
| Identificação | `ibge_code`, `municipality`, `state`, `region`, `crop`, `crop_code`, `safra`, `harvest_year` |
| Produtividade | `yield_kg_ha`, `yield_unit_original`, `area_harvested_ha`, `quantity_produced_t`, `pam_source`, `pam_source_id`, `pam_observation_nature` |
| Clima | `climate_source`, `climate_source_type`, precipitação acumulada/média diária, dias com chuva/secos, temperatura média/máx/mín, radiação, umidade, vento, umidade do solo, cobertura |
| Derivados | `degree_days_total`, `degree_days_mean`, `degree_days_coverage`, `base_temperature_c`, `upper_temperature_c`, `thermal_profile`, `heat_wave_events`, `heat_wave_days`, `extreme_heat_days`, `warm_nights`, `et0_total_mm`, `etp_total_mm`, `etr_total_mm`, `deficiency_total_mm`, `excess_total_mm`, `storage_final_mm`, `et_method`, `soil_profile`, `cad_mm` |
| Calendário | `zarc_window_months`, `zarc_window_start/end`, `zarc_decends`, `zarc_soil`, `zarc_cycle`, `zarc_risk_max`, `zarc_portaria`, `zarc_official_combinations`, `zarc_distinct_windows`, `zarc_window_blocks`, `zarc_window_discarded_months` |
| Qualidade | `coverage`, `status`, `quality_flag`, `exclusion_reason`, `semantic_compatibility` |

**FATO.** As exclusões são 5,2% das linhas totais (35.894 → 19.402
utilizáveis) e cada uma tem o motivo registrado:

| Motivo | Linhas |
|---|---:|
| dias climáticos na janela < 30 (safra sem dado) | 9.235 |
| sem rendimento observado do IBGE/PAM | 3.859 |
| cobertura climática < 0,60 | ~570 |
| safras 2025/26 e 2026/27 (sem PAM ainda) | — |

**FATO.** O **n efetivo** é o número de observações município-ano-cultura
**com rendimento e clima**: 8.884 (soja), 7.616 (milho), 2.902 (milho 2ª).
As várias janelas do ZARC de um mesmo município-ano **não** criam observações
extras — apenas uma linha por (município, safra, cultura, fonte).

---

## 5. Limitações do painel

| Limitação | Consequência |
|---|---|
| **Janela do ZARC é proxy** | janela recomendada ≠ plantio observado; a exposição real ao clima é apenas uma aproximação |
| **Resolução da reanálise** | o NASA POWER interpola para o centroide a partir de ~0,5° × 0,625° (~55 km): municípios vizinhos compartilham informaçãoaltamente correlacionada → **pseudo-replicação espacial** |
| **Sem mapa de uso do solo anual** | mantido da V2.5 (MapBiomas bloqueado) |
| **Milho agregado na PAM** | o alvo é o total do ano; a incompatibilidade é declarada linha a linha (`semantic_compatibility`) |
| **Desbalanceamento** | nem todo município tem 9 anos; a estrutura desbalanceada foi preservada |
| **Valores extremos da PAM** | são oficiais e coerentes com quantidade ÷ área; mantidos |
| **Cobertura do ZARC ausente** | Bahia (ciclo curto) e milho 2ª no RS ficam fora |

**INTERPRETAÇÃO.** A pseudo-replicação espacial é a limitação mais relevante:
com ~55 km de resolução, dois municípios a 30 km de distância recebem valores
climáticos quase idênticos. Isso **não** invalida o painel — mas exige
erro-padrão **agrupado** (por município) e interpretações cuidadosas do
erro-padrão, e **impede** tratar as linhas como observações independentes.

---

## 6. Verificações de reprodutibilidade

**FATO.** Toda a cadeia é determinística e reexecutável:

| Verificação | Resultado |
|---|---|
| Geometrias: 1.782 municípios, 6 UFs | carregadas em 39 s do shapefile oficial |
| PAM: 6 UFs em uma consulta por UF | 128.160 registros em 55 s |
| ZARC: 11 safras nacionais | 2.374.625 registros em 8,7 min (streaming) |
| Estação do INMET (Sorriso 2019) | 8.760 linhas horárias em 2,8 s, com 3,2 MB lidos |
| Máscaras de solo | 3 perfis com CAD documentada |
| Painel final | 35.894 linhas, reprodutível do início ao fim |

**FATO.** Artefatos grandes (série diária, ZARC multi-municipal, PAM
multi-municipal, malhas) **não** são versionados: são regeráveis pelos
comandos de `run_agroclimate.py`, e o manifesto correspondente é versionado.

---

## 7. O que o painel habilita

**FATO.** O painel permite, pela primeira vez no projeto:

1. separar a variação **entre municípios** (que inclui solo, manejo e
   tecnologia) da variação **entre anos** (que inclui o clima);
2. testar a **transferência territorial** — treinar em um conjunto de
   municípios e testar em municípios **não vistos**;
3. corrigir o erro-padrão por **agrupamento**, em vez de tratar 19.402 linhas
   como independentes;
4. comparar variáveis agroclimáticas com baselines **na mesma amostra** em
   que o NDVI da V2.5 falhou.

**FATO.** Com 1.225 municípios de soja e 8 anos, o painel supera com folga o
limite de 15 municípios por cultura fixado na V2.6.
