# Consolidação — teste de clone limpo

**Data:** 2026-11-14
**Ambiente:** diretório temporário isolado, fora do repositório e das caches.

---

## Procedimento

1. `git clone --no-hardlinks --single-branch --branch
   maintenance/technical-consolidation` a partir do repositório local.
2. `python -m venv` novo (Python 3.12.10).
3. `pip install -r geospatial/requirements.txt` — do zero, sem herdar nada.
4. Suíte completa, pipeline, replicação, auditoria.

## Inventário do clone

| item | valor |
|---|---:|
| arquivos | 537 |
| tamanho | 91,9 MB |
| painéis derivados | **ausentes** (não versionados) |
| `v35_panel_windows.csv` | ausente |
| `pam_panel.csv` | ausente |
| amostra canônica (204 linhas) | presente (versionada) |

## Níveis de sucesso

### Nível 1 — recuperação do código: **ATINGIDO**

| item | resultado |
|---|---|
| instalação | OK (Python 3.12.10, numpy 2.5.4, pandas 2.2.3) |
| **testes** | **479 passaram, 3 pularam, 0 falharam** |
| tempo | 27,2 s |

Os 3 pulos são testes que dependem de painéis derivados ausentes — comportamento
correto, não falha.

### Nível 2 — recuperação dos dados: **ATINGIDO POR DOCUMENTAÇÃO**

Cada entrada externa tem script de aquisição, fonte oficial e hash registrado em
manifesto. Os derivados (6,3 GB) não são redistribuíveis no bundle e foram
acessados via `SADEN_DATA_ROOT`.

### Nível 3 — reprodução do pipeline: **ATINGIDO (amostra)**

| item | resultado |
|---|---|
| municípios reconstruídos | 14 (7 UFs) |
| linhas de janela | 204 |
| comparadas com a referência V3.5 | 204 |
| **diferença máxima** | **0,000** |
| tempo | 39,8 s |

### Nível 4 — reprodução científica: **ATINGIDO**

| item | resultado |
|---|---|
| casos manuais da replicação | 8/8 |
| janelas reais comparadas | 36 |
| diferença máxima no déficit | 6,3 × 10⁻⁶ mm |
| defeito D124 reproduzido | sim (15 mm vs 5 mm) |
| auditoria PAM reproduzida | **números idênticos** |

## Defeito encontrado pelo teste

**`geospatial/requirements.txt` não declarava `pytest`.** O comando
`python -m pytest` falhava com `No module named pytest` em ambiente novo. Isto
significa que, até esta etapa, **o projeto não conseguia rodar a própria suíte
em uma máquina limpa** — a reprodutibilidade era do código, não do processo.

Corrigido: `pytest==9.2.0` declarado (R14).

## Caveat de integridade

O hash do manifesto `pam_quality_audit.json` **difere** entre o clone
(`B659D089…`) e o original (`A3FFA6D1…`), porque o arquivo embute `generated_at`
e tamanhos de arquivo em bytes. Os **números são idênticos**:

| campo | clone | original |
|---|---|---|
| células | 43.650 | 43.650 |
| duplicidades | 0 | 0 |
| flags | mesmas 5 classes e contagens | idem |
| impacto no painel | 27 de 30.207 | idem |

**Conclusão:** o manifesto serve como registro de proveniência, **não** como
verificação de integridade por hash. Ação 1.2 em `NEXT_ACTIONS.md`.

## O que o clone **não** prova

1. Que uma pessoa sem o ambiente original consiga **obter** os dados: a
   aquisição depende de APIs públicas que podem mudar.
2. Que o build completo de 2.425 municípios reproduz — só a amostra foi testada.
3. Que o bundle basta: os derivados ficaram fora dele por tamanho e licença.
