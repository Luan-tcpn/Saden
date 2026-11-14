# V3.2 — MASTER STATUS

**Versão:** V3.2 — inclinações climáticas heterogêneas por UF
**Branch:** `v3/uf-heterogeneous-climate-slopes`
**Commit-base:** `345b22e02b78447c94f0e6d5b316c3916d918283` (V3.1)
**Estado:** **concluída**

## Marcos verificados no início

| marco | valor confirmado |
|---|---|
| `main` / `archive/v1-final` / tag `v1-final` | `3f7ad33bc18c5a8e8e050bbc7817f5078488d625` |
| V3.0 | `40fd6aa226d1374964c8804adf614cf4747094d3` |
| V3.1 | `345b22e02b78447c94f0e6d5b316c3916d918283` |
| árvore de trabalho | limpa, sincronizada com `origin` |
| stash | vazio |
| bundle V3.1 | 16.658.052 B, SHA-256 `88A66B39…406AA82`, 32 refs, *okay* |
| bundle V3.0 | presente, 16.601.458 B |

## Commits da V3.2

| commit | conteúdo |
|---|---|
| `c9db008` | inclinações heterogêneas por UF, inferência UF×ano, D104–D107 |

**Bundle:** `SADEN_V3_2_RECOVERY_2026-11-14`, criado **fora** do repositório. O
`BUNDLE_INFO.txt` dessa pasta registra tamanho, SHA-256, número de refs e o
commit final — informação que não pode estar dentro do próprio commit.

## Resultado central

**A heterogeneidade de inclinações não está estabelecida.** Família
confirmatória de 6 testes globais (3 culturas × 2 variáveis), Holm: **1
rejeição** (milho 2ª × temperatura, p = 0,0019 → 0,0113). Nenhum contraste
individual por UF sobrevive ao Holm.

**Correção metodológica (D104):** a unidade de dependência para regressores
climáticos é **UF×ano**, não o bloco espacial de 250 km. F da soja para
precipitação: 8,74 (p ≈ 0) com agrupamento por bloco, 1,13 (p = 0,36) com
agrupamento duplo UF×ano + município.

| cultura | M2 comum | HET-FE | HET-PP | nível |
|---|---:|---:|---:|---|
| soja | **592,2** | 599,0 | 603,1 | **D** |
| milho | 1.688,6 | 1.578,3 | 1.610,9 | **C** |
| milho 2ª | **1.272,4** | 1.285,0 | 1.278,5 | **B** |

MAE em kg/ha, TE. M2 comum reproduz a V3.1 exatamente.

## Testes

| item | valor |
|---|---|
| suíte offline | **410/410** |
| novos testes V3.2 | 17 |
| `compileall` | limpo |
| números do relatório conferidos contra manifests | **39/39** |

## Bloqueios

* 4–6 UFs: modelo hierárquico completo não identificável (D106).
* ERA5-Land (sem credencial CDS) e CHIRPS/ARCO (DNS) — inalterados.
* Nenhuma generalização nacional.

## Próxima ação

Ver `NEXT_ACTIONS.md`: prioridade 1 é o teste conjunto da **forma funcional
hídrica** (déficit + graus-dia) com teste global pré-registrado; prioridade 2 é
revisar, sob a D104, quais p-valores de associação da V2.7–V3.1 sobrevivem.
