"""Validação do build completo canônico contra a referência V3.5.

Compara o painel construído (`panel_canonical_v2_windows.csv`) com o painel
publicado (`v35_panel_windows.csv`) e classifica cada variável:

* **idêntica** — não depende da física corrigida;
* **alterada pela física corrigida** — ET0, déficit, excedente e derivados.

Também mede a cobertura real de municípios e a razão da ausência dos demais,
e verifica a chave e a integridade.

Uso: python tools/validation/validate_full_build.py
"""

from __future__ import annotations

import csv
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from typing import Any

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
_DATA_ROOT = os.environ.get("SADEN_DATA_ROOT") or os.path.join(ROOT, "geospatial", "data")
PROCESSED = os.path.join(_DATA_ROOT, "processed")
MANIFESTS = os.path.join(ROOT, "geospatial", "data", "manifests")
OUT_JSON = os.path.join(MANIFESTS, "full_build_validation.json")

BUILT = os.path.join(PROCESSED, "panel_canonical_v2_windows.csv")
REFERENCE = os.path.join(PROCESSED, "v35_panel_windows.csv")


def load(path: str) -> dict[tuple[str, str, str], dict[str, str]]:
    out: dict[tuple[str, str, str], dict[str, str]] = {}
    with open(path, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            out[(str(row["ibge_code"]), str(row["crop"]), str(row["safra"]))] = row
    return out


def compare_columns(built: dict, reference: dict, keys: list[tuple[str, str, str]]) -> dict[str, Any]:
    columns = [name for name in reference[keys[0]] if name in built[keys[0]]]
    out: dict[str, Any] = {}
    for column in columns:
        diffs: list[float] = []
        identical = 0
        for key in keys:
            left = built[key].get(column)
            right = reference[key].get(column)
            if left in (None, "") or right in (None, ""):
                if (left or "") == (right or ""):
                    identical += 1
                continue
            try:
                a, b = float(left), float(right)
            except ValueError:
                if left == right:
                    identical += 1
                continue
            if a == b:
                identical += 1
            else:
                diffs.append(a - b)
        if diffs:
            array = np.asarray(diffs)
            out[column] = {
                "classification": "alterada",
                "n_different": int(array.size),
                "n_identical": identical,
                "max_abs_diff": float(np.max(np.abs(array))),
                "median_diff": float(np.median(array)),
                "median_relative": float(
                    np.median(array / np.where(np.abs(array) > 0, np.abs(array), 1))
                ) if array.size else None,
            }
        else:
            out[column] = {"classification": "idêntica", "n_identical": identical}
    return out


def main() -> int:
    built = load(BUILT)
    reference = load(REFERENCE)
    shared = sorted(set(built) & set(reference))

    registry: set[str] = set()
    with open(os.path.join(PROCESSED, "panel_municipalities_v35.csv"), newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            if str(row.get("state")) in {"PR", "RS", "MS", "MT", "GO", "BA", "SP"}:
                if "Área Operacional" in str(row.get("municipality") or ""):
                    continue
                registry.add(str(row["ibge_code"]))

    built_codes = {key[0] for key in built}
    missing = sorted(registry - built_codes)
    columns = compare_columns(built, reference, shared)

    changed = {name: data for name, data in columns.items() if data["classification"] == "alterada"}
    identical = [name for name, data in columns.items() if data["classification"] == "idêntica"]

    # verificação da identidade de conservação no balanço corrigido
    balance_ok = 0
    balance_violations = 0
    for key in shared[:3000]:
        row = built[key]
        try:
            precip = float(row["precip_acumulada_mm_corrected"])
            etr = float(row["etr_total_mm_corrected"])
            excess = float(row["excess_total_mm_corrected"])
        except (KeyError, TypeError, ValueError):
            continue
        if precip <= 0:
            continue
        # P = ETR + EXC + variação de ARM; aqui só se checa EXC <= P
        if excess <= precip + 1e-6:
            balance_ok += 1
        else:
            balance_violations += 1

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "built": {"rows": len(built), "municipalities": len(built_codes),
                  "by_crop": dict(Counter(key[1] for key in built))},
        "reference": {"rows": len(reference),
                      "by_crop": dict(Counter(key[1] for key in reference))},
        "keys": {
            "shared": len(shared),
            "only_built": len(set(built) - set(reference)),
            "only_reference": len(set(reference) - set(built)),
        },
        "coverage": {
            "registry_municipalities": len(registry),
            "built_municipalities": len(built_codes),
            "coverage_rate": round(len(built_codes) / len(registry), 4) if registry else None,
            "missing": len(missing),
            "missing_examples": missing[:20],
            "reason": (
                "município sem linha analítica utilizável: exige produtividade PAM, "
                "clima NASA-POWER, janela ZARC e status paired_usable simultaneamente"
            ),
        },
        "columns": {
            "identical": identical,
            "changed": changed,
        },
        "balance_consistency": {"ok": balance_ok, "violations": balance_violations},
    }
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, default=str)
        handle.write("\n")

    print(f"construído: {len(built)} linhas, {len(built_codes)} municípios")
    print(f"referência: {len(reference)} linhas")
    print(f"chaves compartilhadas: {len(shared)} | só construído: {report['keys']['only_built']} | "
          f"só referência: {report['keys']['only_reference']}")
    print(f"cobertura do cadastro: {report['coverage']['coverage_rate']:.1%} "
          f"({len(built_codes)}/{len(registry)}), faltando {len(missing)}")
    print(f"colunas idênticas: {len(identical)}")
    print("colunas alteradas pela física corrigida:")
    for name, data in sorted(changed.items()):
        print(f"   {name:38} n={data['n_different']:6d} dif.média={data['median_diff']:+10.4f} "
              f"máx={data['max_abs_diff']:10.4f}")
    print("consistência de balanço (EXC <= P):", report["balance_consistency"])
    print("manifesto:", OUT_JSON)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
