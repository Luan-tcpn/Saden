# SADEN V2.7 — Recuperação

> Procedimento para retomar a V2.7 a partir de qualquer ponto, inclusive
> após interrupção por limite de uso do modelo, queda de energia ou
> reinstalação da máquina.

## 1. Estado mínimo para retomar

| Item | Onde |
|---|---|
| Checkpoints | `docs/execution/v2.7/` (7 arquivos) |
| Decisões D76+ | `docs/execution/v2.7/DECISIONS_V2_7.md` e `docs/DECISIONS.md` |
| Evidências | `docs/execution/v2.7/EVIDENCE_MATRIX.md` |
| Manifests (verdade numérica) | `geospatial/data/manifests/v27_*.json` / `.csv` |
| Código novo | `geospatial/agroclimate/{robust,spatial,spatial_inference,phenology,soil}.py`, `geospatial/run_robustness.py` |
| Scripts de experimento | `tools/{calibrate_wild_bootstrap,validate_v27_stats,s27_wcs_probe,s27_cad_metadata,s27_cad_sample,s27_phenology_window}.py` |

## 2. Ambiente

```powershell
cd "C:\Users\luanf\OneDrive\Área de Trabalho\Saden_AgroClima"
& geospatial\.venv\Scripts\python.exe -c "import sys; print(sys.version)"
```

* Interpretador correto: **`geospatial\.venv\Scripts\python.exe`** (Python
  3.12.10). O Python do sistema **não** tem as dependências e produz
  `ModuleNotFoundError` — erro já observado nesta execução.
* Dependências: numpy 2.5.4, pandas 2.2.3, rasterio 1.4.3, shapely 2.1.2,
  pytest 9.2.0. **scipy não é necessário** (toda a estatística é NumPy
  puro) e `requirements.txt` **não** foi alterado.
* Caminho com acento ("Área de Trabalho"): o GDAL/schannel exige
  `network.configure_tls()`; o rasterio está fixado em 1.4.3.

## 3. Testes

```powershell
# offline
& geospatial\.venv\Scripts\python.exe -m unittest discover -s geospatial\tests -t geospatial
# externos (opt-in)
$env:SADEN_EXTERNAL_TESTS="1"
& geospatial\.venv\Scripts\python.exe -m unittest discover -s geospatial\tests_external -t geospatial
```

Referência da V2.7: **318/318** offline e **10/10** externos.

## 4. Reprodução dos experimentos

Todos os experimentos são **retomáveis** (grava incrementalmente e retoma
a partir do manifesto existente).

```powershell
# 1. calibração do bootstrap wild (longa; ~75 min em 84 casos)
& geospatial\.venv\Scripts\python.exe tools\calibrate_wild_bootstrap.py
# 2. inferência robusta (efeitos fixos + Conley + bootstrap + Holm)
& geospatial\.venv\Scripts\python.exe geospatial\run_robustness.py infer --block-km 250 --null-policy auto
# 3. validação territorial por blocos espaciais (P1-P5; ~2 h nas 3 culturas)
& geospatial\.venv\Scripts\python.exe geospatial\run_robustness.py spatial --block-km 250
# 4. dependência espacial (correlograma; manifesto v27_spatial_dependence.*)
& geospatial\.venv\Scripts\python.exe geospatial\run_robustness.py dependence
# 5. diagnóstico dos grupos de agrupamento
& geospatial\.venv\Scripts\python.exe geospatial\run_robustness.py diagnose
# 6. validação das implementações estatísticas
& geospatial\.venv\Scripts\python.exe tools\validate_v27_stats.py
# 7. experimento fenológico
& geospatial\.venv\Scripts\python.exe tools\s27_phenology_window.py --sample 250
# 8. CAD (exige rede; sondagem + amostra)
& geospatial\.venv\Scripts\python.exe tools\s27_cad_sample.py --sample 10 --window-deg 0.2
```

> `spatial` grava o manifesto **por cultura**, ao final de cada uma: se for
> interrompido, as culturas já concluídas estão no arquivo. O comando é o
> mais caro (≈2 h no total) porque cada predição refaz a regressão sobre o
> conjunto de treino.

## 5. Onde os artefatos grandes estão

* `geospatial/data/processed/climate_daily.csv` — 1.076,9 MB (**fora do Git**).
* `geospatial/data/processed/agroclimatic_productivity_panel.csv` — 27,3 MB
  (**fora do Git**).
* `geospatial/data/manifests/v27_*` — versionados (pequenos).
* `geospatial/data/processed/embrapa_solos_wcs_capabilities.xml` — resposta
  bruta do WCS (fora do Git).
* `tmp/v27_*.py` e `tmp/v27_*.npy` — scripts e caches da sessão anterior
  (fora do Git; **não apagar** antes de a consolidação final).

## 6. Se a execução for interrompida

1. **Não** usar `git reset --hard` nem `git clean -fd`: há alterações não
   commitadas que precisam ser preservadas.
2. Reexecutar o comando do experimento correspondente: ele **retoma** a
   partir do manifesto gravado.
3. Se um manifesto estiver truncado (interrupção no meio da escrita),
   apagá-lo **apenas** para aquele experimento e reexecutá-lo — o script
   reconstrói tudo do zero de forma determinística (semente fixa).
4. Conferir `docs/execution/v2.7/MASTER_STATUS.md` para saber exatamente
   em que fase a execução parou.

## 7. Recuperação Git

```powershell
git status --short --branch
git log --oneline v2/agroclimatic-productivity-panel..HEAD
git bundle verify "..\SADEN_V2_7_RECOVERY_2026-11-14\saden-v2-7-final-2026-11-14.bundle"
```

Bundles anteriores (V2.3–V2.6) são **somente leitura** e não devem ser
movidos, sobrescritos ou excluídos.

## 8. Fontes externas e limites

| Fonte | Limite | Conduta |
|---|---|---|
| NASA POWER / INMET | — | já baixados; **não** reexecutar |
| WCS Embrapa Solos | 1 janela por município/camada | timeout 180 s; até 2 tentativas; espera crescente |
| CDS (ERA5-Land) | credencial ausente | **não** criar conta, **não** pedir credencial |
| CHIRPS / ARCO | DNS ausente | **não** repetir sem mudança de rede |

Erros transitórios (429/5xx): respeitar `Retry-After`, no máximo **2
tentativas adicionais**. Suspender a fonte se persistir.
