# V3.3 — REGISTRO DE AUDITORIA DE INFERÊNCIA

Gerado por `tools/v33_write_audit_register.py` a partir de `geospatial/data/manifests/v33_inference_audit.json`. Não editar à mão: os números vêm do manifesto.

## Cenários

* **C1** — dados historicos + agrupamento por bloco (base das familias historicas)
* **C2** — mesmos dados e coeficiente + agrupamento duplo UFxano+municipio
* **C3** — reanalise com janela corrigida (separada; nao e efeito de inferencia)

## Resumo por família

| família | hipóteses | reprodução (dif. máx.) | histórico | auditado (UF×ano + município) |
|---|---:|---|---|---|
| F1_v27 (V2.7 — efeitos fixos por variável meteorológica) | 21 | 1.48e-06 | 10 brutos / 4 Holm | 4 brutos / 0 Holm |
| F2_v30 (V3.0 — déficit sob cinco definições) | 15 | 3.55e-15 | 10 Holm de 15 | 9 brutos / 8 Holm |
| F3_v29_interaction (V2.9 — interação por grupo de ciclo) | 9 | 9.19e-08 | 2 brutos / 1 Holm | 0 brutos / 0 Holm |

## V2.7 — efeitos fixos por variável meteorológica

Fonte histórica: `v27_robust_inference.json`. Reprodução do coeficiente: diferença máxima 1.48e-06 em 21 hipóteses.

| cultura | variável | coef. | SE bloco | SE UF | SE UF×ano | SE duplo | p bloco | p duplo | Holm bloco | Holm duplo | classificação |
|---|---|---:|---:|---:|---:|---:|---|---|---|---|---|
| milho_2 | deficiency_total_mm | -0.742 | 0.438 | 0.140 | 0.995 | 1.011 | 0.1009 | 0.4686 | 1.0000 | 1.0000 | **sem_evidencia_em_nenhum** |
| milho_2 | degree_days_total | -0.127 | 0.239 | 0.066 | 0.154 | 0.157 | 0.5986 | 0.4240 | 1.0000 | 1.0000 | **sem_evidencia_em_nenhum** |
| milho_2 | et0_total_mm | 0.064 | 0.593 | 0.415 | 0.741 | 0.749 | 0.9154 | 0.9330 | 1.0000 | 1.0000 | **sem_evidencia_em_nenhum** |
| milho_2 | excess_total_mm | -0.124 | 0.671 | 0.633 | 1.123 | 1.123 | 0.8543 | 0.9126 | 1.0000 | 1.0000 | **sem_evidencia_em_nenhum** |
| milho_2 | extreme_heat_days | -4.685 | 3.739 | 1.987 | 6.007 | 6.114 | 0.2203 | 0.4493 | 1.0000 | 1.0000 | **sem_evidencia_em_nenhum** |
| milho_2 | precip_acumulada_mm | 0.197 | 0.474 | 0.428 | 0.844 | 0.846 | 0.6812 | 0.8176 | 1.0000 | 1.0000 | **sem_evidencia_em_nenhum** |
| milho_2 | temp_media_c | -83.476 | 85.595 | 85.461 | 122.453 | 123.049 | 0.3375 | 0.5026 | 1.0000 | 1.0000 | **sem_evidencia_em_nenhum** |
| milho | deficiency_total_mm | -3.039 | 1.025 | 1.260 | 0.979 | 0.981 | 0.0047 | 0.0033 | 0.0785 | 0.0688 | **mantida_apenas_bruta** |
| milho | degree_days_total | -0.338 | 0.345 | 0.425 | 0.362 | 0.365 | 0.3322 | 0.3596 | 1.0000 | 1.0000 | **sem_evidencia_em_nenhum** |
| milho | et0_total_mm | -2.492 | 0.466 | 0.515 | 1.045 | 1.047 | 2.42e-06 | 0.0214 | 5.08e-05 | 0.4062 | **mantida_apenas_bruta** |
| milho | excess_total_mm | 0.734 | 0.318 | 0.224 | 0.624 | 0.623 | 0.0253 | 0.2445 | 0.3037 | 1.0000 | **nao_sustentada** |
| milho | extreme_heat_days | -19.195 | 6.459 | 7.843 | 7.767 | 7.770 | 0.0046 | 0.0172 | 0.0785 | 0.3435 | **mantida_apenas_bruta** |
| milho | precip_acumulada_mm | 0.975 | 0.350 | 0.348 | 0.594 | 0.593 | 0.0076 | 0.1069 | 0.1066 | 1.0000 | **nao_sustentada** |
| milho | temp_media_c | -182.665 | 47.808 | 72.445 | 95.018 | 95.012 | 3.82e-04 | 0.0606 | 0.0069 | 1.0000 | **enfraquecida** |
| soja | deficiency_total_mm | -1.260 | 0.240 | 0.221 | 0.581 | 0.581 | 4.08e-06 | 0.0361 | 8.16e-05 | 0.6506 | **mantida_apenas_bruta** |
| soja | degree_days_total | 0.246 | 0.160 | 0.250 | 0.193 | 0.194 | 0.1300 | 0.2111 | 1.0000 | 1.0000 | **sem_evidencia_em_nenhum** |
| soja | et0_total_mm | 0.049 | 0.386 | 0.661 | 0.584 | 0.584 | 0.9006 | 0.9341 | 1.0000 | 1.0000 | **sem_evidencia_em_nenhum** |
| soja | excess_total_mm | 0.464 | 0.335 | 0.310 | 0.495 | 0.495 | 0.1729 | 0.3538 | 1.0000 | 1.0000 | **sem_evidencia_em_nenhum** |
| soja | extreme_heat_days | -4.403 | 1.719 | 1.992 | 4.936 | 4.935 | 0.0138 | 0.3777 | 0.1797 | 1.0000 | **nao_sustentada** |
| soja | precip_acumulada_mm | 0.581 | 0.197 | 0.160 | 0.312 | 0.312 | 0.0050 | 0.0705 | 0.0785 | 1.0000 | **enfraquecida** |
| soja | temp_media_c | -92.789 | 20.477 | 37.853 | 68.845 | 68.755 | 4.30e-05 | 0.1849 | 8.17e-04 | 1.0000 | **nao_sustentada** |

## V3.0 — déficit sob cinco definições

Fonte histórica: `v30_association_cad.json`. Reprodução do coeficiente: diferença máxima 3.55e-15 em 15 hipóteses.

| cultura | variável | coef. | SE bloco | SE UF | SE UF×ano | SE duplo | p bloco | p duplo | Holm bloco | Holm duplo | classificação |
|---|---|---:|---:|---:|---:|---:|---|---|---|---|---|
| milho_2 | deficit_cad100 | -0.165 | 0.513 | 0.658 | 0.899 | 0.910 | 0.7506 | 0.8575 | 1.0000 | 1.0000 | **sem_evidencia_em_nenhum** |
| milho_2 | deficit_cad200 | -0.432 | 0.979 | 0.879 | 1.373 | 1.399 | 0.6619 | 0.7592 | 1.0000 | 1.0000 | **sem_evidencia_em_nenhum** |
| milho_2 | deficit_cad60 | -0.438 | 0.493 | 0.526 | 0.846 | 0.859 | 0.3813 | 0.6133 | 1.0000 | 1.0000 | **sem_evidencia_em_nenhum** |
| milho_2 | deficit_corr50 | -0.555 | 0.547 | 0.511 | 0.893 | 0.904 | 0.3186 | 0.5439 | 1.0000 | 1.0000 | **sem_evidencia_em_nenhum** |
| milho_2 | deficit_hist | -0.742 | 0.438 | 0.140 | 0.995 | 1.011 | 0.1009 | 0.4686 | 0.5044 | 1.0000 | **sem_evidencia_em_nenhum** |
| milho | deficit_cad100 | -2.781 | 0.950 | 1.139 | 0.931 | 0.934 | 0.0052 | 0.0046 | 0.0423 | 0.0367 | **mantida** |
| milho | deficit_cad200 | -2.010 | 0.599 | 0.760 | 1.142 | 1.143 | 0.0016 | 0.0851 | 0.0156 | 0.5104 | **enfraquecida** |
| milho | deficit_cad60 | -2.605 | 0.907 | 0.964 | 0.829 | 0.832 | 0.0061 | 0.0030 | 0.0424 | 0.0330 | **mantida** |
| milho | deficit_corr50 | -2.437 | 0.863 | 0.889 | 0.758 | 0.761 | 0.0069 | 0.0024 | 0.0424 | 0.0294 | **mantida** |
| milho | deficit_hist | -3.039 | 1.025 | 1.260 | 0.979 | 0.981 | 0.0047 | 0.0033 | 0.0423 | 0.0330 | **mantida** |
| soja | deficit_cad100 | -2.318 | 0.296 | 0.372 | 0.557 | 0.558 | 6.13e-10 | 1.73e-04 | 7.97e-09 | 0.0023 | **mantida** |
| soja | deficit_cad200 | -2.285 | 0.385 | 0.647 | 0.729 | 0.728 | 3.84e-07 | 0.0032 | 4.61e-06 | 0.0330 | **mantida** |
| soja | deficit_cad60 | -2.403 | 0.301 | 0.376 | 0.471 | 0.472 | 3.47e-10 | 9.34e-06 | 4.86e-09 | 1.31e-04 | **mantida** |
| soja | deficit_corr50 | -2.448 | 0.294 | 0.391 | 0.401 | 0.402 | 1.19e-10 | 3.94e-07 | 1.78e-09 | 5.91e-06 | **mantida** |
| soja | deficit_hist | -1.260 | 0.240 | 0.221 | 0.581 | 0.581 | 4.08e-06 | 0.0361 | 4.49e-05 | 0.2530 | **mantida_apenas_bruta** |

## V2.9 — interações por grupo de ciclo

| cultura | variável | diferença de inclinação | SE bloco | SE duplo | p bloco | p duplo | p histórico |
|---|---|---:|---:|---:|---|---|---|
| milho_2 | deficiency_total_mm | -0.727 | 0.572 | 0.817 | 0.2140 | 0.3811 | 0.2140 |
| milho_2 | precip_acumulada_mm | 0.161 | 0.367 | 0.451 | 0.6636 | 0.7235 | 0.6636 |
| milho_2 | temp_media_c | 0.496 | 4.384 | 2.444 | 0.9107 | 0.8407 | 0.9107 |
| milho | deficiency_total_mm | -2.612 | 1.875 | 1.746 | 0.1701 | 0.1413 | 0.1701 |
| milho | precip_acumulada_mm | -1.017 | 0.496 | 0.559 | 0.0456 | 0.0750 | 0.0456 |
| milho | temp_media_c | -22.915 | 14.327 | 17.635 | 0.1163 | 0.2001 | 0.1163 |
| soja | deficiency_total_mm | -1.194 | 0.378 | 0.859 | 0.0028 | 0.1725 | 0.0028 |
| soja | precip_acumulada_mm | -0.075 | 0.165 | 0.226 | 0.6500 | 0.7407 | 0.6500 |
| soja | temp_media_c | -3.981 | 4.510 | 6.471 | 0.3821 | 0.5420 | 0.3821 |

## Classificações usadas

| rótulo | significado |
|---|---|
| `mantida` | significativa bruta **e** após Holm com agrupamento duplo |
| `mantida_apenas_bruta` | significativa bruta sob duplo, mas não após Holm |
| `enfraquecida` | significativa por bloco; p duplo entre 0,05 e 0,10 |
| `nao_sustentada` | significativa por bloco; p duplo ≥ 0,10 |
| `reforcada` | não significativa por bloco; significativa após Holm sob duplo |
| `sem_evidencia_em_nenhum` | não significativa em nenhum esquema |
| `nao_auditavel` | dados insuficientes para reestimar |

## Limitações do registro

* A auditoria isola o **agrupamento**; modelo, amostra e variável são os históricos.
* Para F1 e F3 as variáveis são as da janela **histórica** (`_legacy`), porque eram
  as usadas nas versões originais. Corrigir a janela é outro cenário (C3), tratado
  em V3.1/V3.3 e não aqui.
* A família de multiplicidade é a **original** de cada versão (21, 15 e 9), sem
  rearranjo retrospectivo.
* `p` do duplo usa CR1 com `t(G−1)`, `G = min(clusters UF×ano, municípios)`; com 31–48
  clusters UF×ano a aproximação é razoável, mas não exata.
