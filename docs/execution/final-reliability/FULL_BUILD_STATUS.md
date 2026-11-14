# Fechamento — estado do build completo

**Data:** 2026-11-14
**Manifesto:** `geospatial/data/manifests/panel_canonical_build_v2.json`
**Validação:** `full_build_validation.json`
**Saídas:** `panel_canonical_v2_windows.csv`, `panel_canonical_v2_water.csv`

---

## 1. Execução

Build em **6 blocos** com prefixos próprios (nada sobrescrito), depois merge
validado:

| bloco | municípios | linhas de janela |
|---|---:|---:|
| c1 — BA, MS, MT, GO | 447 | 7.343 |
| c2 — RS | 455 | 4.394 |
| c3 — PR (metade A) | 197 | 3.893 |
| c4 — PR (metade B) | 197 | 3.772 |
| c5 — SP (metade A) | 292 | 5.404 |
| c6 — SP (metade B) | 292 | 5.401 |
| **total** | **1.880** | **30.207** |

Linhas de água: **120.828**. Chaves duplicadas: **0**. Problemas: **nenhum**.

Tempo: 101 s para o maior bloco; ~11 min de processamento no total.

## 2. Cobertura real

| item | valor |
|---|---:|
| municípios no cadastro (7 UFs, sem áreas operacionais) | 2.425 |
| municípios com linha analítica construída | **1.880** |
| cobertura | **77,5%** |
| faltando | 545 |

**Causa dos 545**: um município só entra no painel se tiver, simultaneamente,
produtividade PAM, clima NASA-POWER, janela ZARC e `status = paired_usable`.
Os ausentes são municípios sem produção declarada da cultura, sem estação/clima
disponível ou sem janela ZARC aplicável. **Nenhum dado foi inventado para atingir
2.425** — a contagem de municípios do cadastro não é meta de cobertura.

## 3. Comparação com V3.5

| verificação | resultado |
|---|---|
| chaves compartilhadas | **30.207 de 30.207** |
| chaves só no build novo | 0 |
| chaves só na referência | 0 |
| colunas idênticas | **37** |
| colunas alteradas pela física corrigida | 11 |
| consistência `EXC ≤ P` | 3.000 verificações, 0 violações |

Variáveis alteradas (mediana da diferença): ET0 +3,06 mm; déficit +1,07 mm;
ETR +2,78 mm; excedente −13,16 mm; cenários de CAD entre −0,68 e −12,66 mm.

**Mesma população, mesma chave, física diferente** — exatamente o esperado.

## 4. Proteções

- escrita atômica (`.tmp` + `os.replace`);
- **recusa de sobrescrita** sem `--force` (testado: levanta `FileExistsError`);
- prefixos por bloco, sem colisão;
- nenhum artefato V3.0/V3.5 tocado — verificado por hash.

## 5. Pintura de integridade

| arquivo | SHA-256 |
|---|---|
| `panel_canonical_v2_windows.csv` | `6a95581c6bc8e43f4f8766c89381e729ad8d27e1e61b13928dbf71ce98324092` |
| `panel_canonical_v2_water.csv` | ver `panel_canonical_build_v2.json` |
| conteúdo do manifesto | `a8329388f76dbb3ed6ef8e498411ba43f495883e8e61e46cbdb38e8fed4f5eab` |

## 6. Limitações

1. Não foi executado um build completo **com a física histórica** para comparação
   bit a bit em 30.207 linhas; a equivalência histórica foi provada em 14
   municípios na etapa anterior, e aqui a comparação é contra o painel V3.5 já
   publicado (mesma população).
2. O build usa os painéis base (`agroclimatic_productivity_panel.csv`,
   `panel_sp_v35.csv`) como entrada; não reexecuta a aquisição de PAM nem de ZARC.
3. Tempo de ~11 min é de máquina local; não há estimativa para outro hardware.
