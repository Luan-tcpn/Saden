# Consolidação — estado da análise de poder

**Data:** 2026-11-14
Código: `tools/analysis/statistical_power.py`
Relatório: `docs/statistics/STATISTICAL_POWER_AND_MDE_REPORT.md`

---

## Antes

Nenhuma análise formal de poder. Discussões sobre "amostra pequena" e "poucos
clusters" eram qualitativas e não convertidas em efeito mínimo detectável.

## Desenho real usado na análise

| cultura | linhas | municípios | anos | clusters UF×ano | obs/cluster |
|---|---:|---:|---:|---:|---:|
| soja | 12.517 | 1.732 | 8 | 48 | 260,8 |
| milho | 12.013 | 1.645 | 8 | 56 | 214,5 |
| milho 2ª | 5.677 | 1.071 | 9 | 41 | 138,5 |

O MDE parte do **erro-padrão agrupado estimado**, nunca do N de linhas.

## MDE (kg/ha por unidade)

| exposição | soja | milho | milho 2ª |
|---|---:|---:|---:|
| déficit (por mm) | **1,14** | 2,11 | 3,36 |
| precipitação (por mm) | 0,60 | 1,50 | 3,21 |
| ET0 (por mm) | 1,33 | 2,62 | 3,71 |
| graus-dia (por °C·dia) | 0,49 | 1,03 | 0,92 |
| calor extremo (por dia) | 12,0 | 17,3 | 22,3 |
| temperatura (por °C) | **202,8** | **303,1** | **433,5** |

## Calibração do teste

| cultura | erro tipo I observado | poder no MDE 80% |
|---|---:|---:|
| soja | **7,8%** | 88,3% |
| milho | **6,0%** | 91,5% |
| milho 2ª | **10,3%** | 94,0% |

400 réplicas por cultura, com o componente de cluster sorteado **em cada
réplica**. Nominal era 5%. **O teste é liberal** (D125).

## Conclusão de desenho mais importante

| cenário | fator no erro-padrão |
|---|---:|
| dobrar municípios | **0,996 – 0,998** |
| quintuplicar municípios | **0,987 – 0,996** |
| anos 9 → 15 | **0,775** |
| UFs 7 → 10 | **0,837 – 0,841** |

Os clusters já têm 139–261 municípios. Com ICC de 0,18–0,28, **acrescentar
municípios quase não reduz o erro** (D126). Estende a série ou acrescenta UFs —
e MG se justifica por acrescentar clusters, não por volume.

## Efeito sobre leituras anteriores

| resultado | leitura revisada |
|---|---|
| temperatura/graus-dia nulos | **inconclusivo por poder**, MDE proibitivo |
| heterogeneidade por UF não demonstrada | inconclusivo por poder |
| bloco hídrico sem ganho (V3.3) | inconclusivo para modelos maiores |
| contraste regional (V3.4) | **não identificado**, não é poder |
| contraste dentro de SP (V3.5) | inconclusivo por poder |
| déficit × soja significativo | associação, não causal, com p liberal |

## Erros cometidos durante a construção (registrados)

1. Broadcasting `y - coluna*escalar` gerava matriz n×n.
2. Componente de cluster sorteado uma única vez → viés fixo → resultados
   degenerados (tipo I = 0, poder binário). Detectado porque 0 rejeições em 400
   réplicas é praticamente impossível sob H0.
3. Assinatura de `design_scenarios` incompatível com os testes.

## Limitações

1. MDE por exposição isolada; modelos multivariados diferem.
2. Ruído simulado gaussiano; cauda real mais pesada aumentaria o erro tipo I.
3. Não há poder para **previsão**, só para associação.
