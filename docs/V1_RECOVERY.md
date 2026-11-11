# SADEN — Recuperação da V1 congelada

> Guia curto e operacional. Nenhum dado pesado, banco ou segredo é versionado
> aqui. Os arquivos de recuperação ficam **fora do repositório**, em
> `../SADEN_V1_RECOVERY_2026-11-11/` (manifesto completo:
> `README_RECUPERACAO_V1.md`).

## 1. Referências da V1

| Item | Valor |
|---|---|
| Commit congelado | `3f7ad33bc18c5a8e8e050bbc7817f5078488d625` |
| Tag anotada | `v1-final` (objeto `e62a5372e8bc69a87f642398681ed4df13d4fc54`) |
| Branch de arquivo | `archive/v1-final` |
| Bundle | `../SADEN_V1_RECOVERY_2026-11-11/saden-v1-final-2026-11-11.bundle` |
| SHA-256 do bundle | `DB2D8858D3D4C40D081C79B33FF241F34D25B55842CE1E219CE589F7C3F0BF8F` |
| Backup SQLite | `../SADEN_V1_RECOVERY_2026-11-11/db/saden-20261111T171823.db` |
| SHA-256 do backup | `1F3D1646FB56EEF77BEAEA7CD9987E4EEDF30A83E87404B3641BCB7FE731147D` |

> O bundle e o backup estão em armazenamento local (OneDrive). Isso **não**
> substitui backup offsite: copie para outra mídia/nuvem sob controle do autor.

## 2. Conferir que a V1 está intacta

```powershell
git fetch --tags origin
git rev-parse main
git rev-parse v1-final^{}
git rev-parse archive/v1-final
# esperado nos três: 3f7ad33bc18c5a8e8e050bbc7817f5078488d625
git ls-remote origin refs/heads/main refs/tags/v1-final "refs/tags/v1-final^{}"
```

## 3. Trabalhar a partir da V1 sem destruir nada

```powershell
# branch de trabalho derivada da tag (não mexe em main)
git switch -c recuperacao/v1-local v1-final
```

Nunca use `git reset --hard`, `git clean -fd`, `git tag -f` ou force push para
"consertar" ponteiros. Se algo divergir, investigue e registre.

## 4. Restaurar o bundle em um clone separado

```powershell
git clone C:\caminho\para\SADEN_V1_RECOVERY_2026-11-11\saden-v1-final-2026-11-11.bundle SADEN_V1_CLONE
cd SADEN_V1_CLONE
git tag --list                     # deve listar v1-final
git rev-parse v1-final^{}          # 3f7ad33...
```

## 5. Restaurar o banco (somente em recuperação real)

1. Pare o backend (`node backend/src/index.js`) — nunca copie com o banco aberto.
2. Renomeie o banco atual para `data/saden.db.antes-recuperacao-AAAAMMDD`.
3. Copie o `.db` de backup para `data/saden.db`.
4. Se existirem `saden.db-wal`/`saden.db-shm` antigos, mova-os junto.
5. Inicie o backend e confirme `GET /api/health`.
6. Gere um novo backup consistente: `node scripts/backup.js`.

> Restaurar backup descarta o que foi gravado depois dele. Use apenas em
> recuperação real, nunca como rotina.

## 6. Verificação do backup

O backup foi criado com `scripts/backup.js` (cópia online consistente) e
validado com `PRAGMA integrity_check` = `ok`, `quick_check` = `ok`,
15 tabelas, 887 `model_runs`, 12.159 `forecasts` e 9 linhas de histórico AR.

## 7. Limitações

- A V1 não é declarada pronta para produção: faltam TLS, SMTP real, backup
  automatizado, monitoramento e teste de carga.
- O GitHub Release `v1-final` depende de credencial `gh` já autenticada; se
  ausente, a tag, `main`, `archive/v1-final` e o bundle continuam válidos.
- O histórico AR no banco é registro experimental, não funcionalidade do
  produto (D40).
