# SADEN V2.9 — Status da execução

> Etapa: **V2.9 — Regionalização agroclimática, heterogeneidade espacial do
> milho, CAD e classes de ciclo ZARC**. Atualizado em: 2026-11-14.

## Objetivo

Determinar **quanto da capacidade explicativa e preditiva vem das variáveis
agroclimáticas, quanto vem das diferenças regionais e espaciais, e em quais
culturas o resultado é generalizável**.

## Identificação da linha

| Item | Valor |
|---|---|
| Repositório | `C:\Users\luanf\OneDrive\Área de Trabalho\Saden_AgroClima` |
| Branch | `v2/regional-agroclimatic-robustness` (base `a36e6be` = V2.8) |
| V2.8 preservada | `v2/temporal-spatial-generalization` em `a36e6be`, publicada |
| Bundle V2.8 | `..\SADEN_V2_8_RECOVERY_2026-11-14\`, SHA-256 `73297BAB…46890AA8`, *okay*, 26 refs |
| V1 / `main` | `3f7ad33` (tag `v1-final`) — intactas |
| Suíte de referência | **338/338** ao abrir a V2.9 |
| Suíte atual | **364/364** |

## Estado das fases

| Fase | Item | Estado |
|---|---|---|
| 0 | Auditoria, bundle, branch, suíte de referência | **concluída** |
| 1 | Auditoria da equalização da V2.8 | **concluída** (D90) |
| 2 | Modelo regional de referência e valor incremental do clima | **concluída** (D91) |
| 3 | Heterogeneidade espacial do milho e escala do bloco | **concluída** (D92) |
| 4 | CAD: estratégia, piloto, amostra estratificada, balanço | **concluída** (D93) |
| 5 | Dicionário ZARC e teste de interação por classe | **concluída** (D94) |
| 6 | Cobertura territorial | **concluída** (D95) |
| 7 | Síntese científica | **concluída** |
| 8 | Validação final, bundle e publicação | **em curso** |

## Achados centrais

1. **Equalização:** a V2.8 era global, não por célula (TE 5.401 linhas em
   média, 11/25 células abaixo do alvo). Com equalização estrita, MAEs mudam
   em ≤ 5,1 kg/ha e os efeitos ficam nos mesmos ICs — a conclusão se sustenta.
2. **Valor incremental do clima (M2−M1):** na soja só existe com o ano
   compartilhado (−13,3 em SS, −19,2 em SE; −6,3 n.s. em TE); a família
   hídrica **piora** em TS/TE (+26,3 e +20,5). No milho 2ª safra a família
   meteorológica acrescenta nos quatro braços (TE −267,2).
3. **Milho e o bloco:** efeito −170,8 a 250 km, concentrado em PR (+421), BA
   (+291) e MS (+171); ~0 em GO/MT e negativo em RS — heterogeneidade dentro
   da UF. A 150 km o efeito é −47,1; a 600 km há só 14–15 blocos (poder baixo).
4. **ZARC:** dicionário oficial obtido (20/21/22 = Grupo I/II/III; não é
   cultivar). O teste formal **retira** a "inversão de sinal" da temperatura
   na soja (p=0,38); o déficit difere (p=0,003).
5. **CAD:** `scaleFactor=0.2` reduz o volume 60× (450 m); piloto valida contra
   a amostra de 90 m da V2.7 (112–201 mm, mediana 161,5). Amostra entregue:
   **120 municípios** (20 por UF), CAD 0–100 de 116,2 a 205,4 mm (mediana
   162,9), com medianas por UF de 138,5 (MS) a 194,7 (RS).
6. **Balanço hídrico com a CAD do próprio município:** razão do déficit
   (oficial/50 mm) mediana 0,875, **p10 0,407**, com **13,6%** dos
   município-anos em que o déficit é eliminado e desvio entre municípios de
   0,36. O reescalonamento **não é uniforme** — logo a escolha da CAD altera
   o padrão transversal do déficit e não apenas a sua escala.

## Manifestos

`v29_equalization_audit.json` · `v29_nested_models.json` ·
`v29_block_scale.json` · `v29_zarc_dictionary.json` ·
`v29_cycle_interaction.json` · `v29_coverage.json` · `v29_cad_expansion.json`
(parcial) · `v29_cad_stratified.json` · `v29_cad_balance_panel.json`.

## Próxima ação executável

Concluir a amostra estratificada de CAD, rodar o balanço hídrico por município,
preencher os números de CAD/cobertura no relatório e publicar.

## Bloqueios

- Cobertura completa de CAD: ~5 h de requisições (plano validado; retomável).
- Profundidade radicular por cultura: sem fonte cultivar-específica.
- ERA5-Land: credencial CDS ausente (D83). CHIRPS/ARCO: sem DNS.
