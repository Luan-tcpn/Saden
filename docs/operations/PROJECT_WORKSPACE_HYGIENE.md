# Higiene do workspace — `.commandcode` e arquivos não versionados

Auditoria feita em 2026-11-15, sobre `main` = `1b6dc49`.

---

## 1. `.commandcode`

### O que existe (verificado no sistema de arquivos)

```text
.commandcode/
└── taste/
    ├── taste.md              0 bytes    (índice de categorias, vazio)
    ├── coding/taste.md     556 bytes
    └── workflow/taste.md  1992 bytes
```

Três arquivos Markdown, nenhum binário, nenhum cache, nenhuma sessão, nenhum
token ou credencial. Não há `plans/`, `sessions/`, `cache/` ou logs.

### Função comprovada

São arquivos de **preferências aprendidas** ("taste") que o Command Code Desktop
mantém por projeto: convenções de código e de fluxo de trabalho que o assistente
passa a seguir. O conteúdo é gerado/atualizado automaticamente pela ferramenta a
partir das interações — não é configuração escrita à mão para o produto.

Classificação: **estado local do ambiente**, com valor apenas para esta máquina e
este usuário. Não contém instruções compartilháveis que afetem o runtime do SADEN.

### Situação no Git (comprovada)

| verificação | comando | resultado |
|---|---|---|
| está versionado? | `git ls-files .commandcode` | **nada** (0 arquivos) |
| está ignorado? | `git check-ignore -v .commandcode` | **não** — sem regra |
| aparece no status? | `git status` | sim, como `?? .commandcode/` |

Ou seja: não polui o histórico, mas aparece como pendência em todo `git status`.

### Decisão

**Manter no disco, ignorar no Git.** A pasta continua existindo e o Command Code
Desktop segue funcionando normalmente; ela apenas deixa de aparecer como alteração
pendente. Nada foi movido, copiado ou apagado.

Justificativa para `.gitignore` (e não `.git/info/exclude`): qualquer colaborador
que use o mesmo assistente teria a mesma pasta com conteúdo pessoal. Ignorar no
`.gitignore` evita que alguém a comite por acidente.

---

## 2. Outros diretórios não versionados

| caminho | o que é | decisão |
|---|---|---|
| `geospatial/` | artefatos da linha de pesquisa geoespacial (dados/manifests) | **não versionar** — pesquisa, não runtime; preservado no disco |
| `tools/` | scripts de pesquisa (`calibrate_wild_bootstrap.py`, `validate_v27_stats.py`, `__pycache__`) | **não versionar** — idem |
| `tmp/` | caches, bancos de teste, capturas de tela | já ignorado por `tmp/*` |
| `data/` | banco SQLite de trabalho | ignorado por `data/*.db*` |

Esses diretórios existem porque o repositório serviu à linha de pesquisa V2/V3
antes da productização. Eles **não** fazem parte da aplicação e não são usados em
runtime. Não foram removidos: são trabalho histórico e a remoção exigiria decisão
do responsável.

---

## 3. O que foi versionado nesta etapa

| caminho | motivo |
|---|---|
| `site-institucional/` | entrega institucional estática |
| `docs/operations/PROJECT_WORKSPACE_HYGIENE.md` | este documento |
| `.gitignore` | regra para `.commandcode/` |

Nenhum segredo, bundle, banco, cache ou artefato de pesquisa entrou no commit.

---

## 4. Verificação pós-mudança

| item | estado |
|---|---|
| `.commandcode` acessível pelo aplicativo | sim (não foi tocada) |
| `git status` limpo de ruído | sim |
| segredos no repositório | nenhum |
| aplicação funcional | inalterada — nenhum arquivo de `backend/` ou `frontend/` foi modificado |
