"""V3.5 — extensão do mapeamento regional para São Paulo.

Mesma fonte congelada da V3.4 (planilha oficial MAPA/ZARC, SHA-256
``91126b6b…7458c84``), mesmo parser, mesma normalização de nomes. A única
diferença é que SP passa a ser incluído.

Regra de ouro: as linhas dos seis estados têm de ser **idênticas** às da V3.4 —
o script verifica isso linha a linha e aborta se houver divergência.

Uso: python tools/v35_region_mapping.py
"""

from __future__ import annotations

import csv
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

import v34_region_mapping as mapping  # noqa: E402

PROCESSED = os.path.join(ROOT, "geospatial", "data", "processed")
MANIFESTS = os.path.join(ROOT, "geospatial", "data", "manifests")

V34 = os.path.join(PROCESSED, "municipality_region_mapping.csv")
V35 = os.path.join(PROCESSED, "municipality_region_mapping_v35.csv")
OUT = os.path.join(MANIFESTS, "v35_region_mapping.json")
SP_PANEL = os.path.join(PROCESSED, "v35_panel_windows.csv")

STATES_V35 = ("PR", "RS", "MS", "MT", "GO", "BA", "SP")


def main() -> int:
    rows = mapping.read_rows()
    lookup = {(row["uf"], row["municipality_key"]): row for row in rows}

    registries: dict[str, list[dict[str, str]]] = defaultdict(list)
    with open(
        os.path.join(PROCESSED, "panel_municipalities_v35.csv"),
        newline="",
        encoding="utf-8-sig",
    ) as handle:
        for row in csv.DictReader(handle):
            if str(row.get("state")) in STATES_V35:
                registries[str(row["state"])].append(row)

    joined: list[dict[str, Any]] = []
    unmatched: list[dict[str, str]] = []
    for uf, members in sorted(registries.items()):
        for row in members:
            key = mapping.normalize(row.get("municipality") or "")
            found = lookup.get((uf, key))
            if found is None:
                unmatched.append({"uf": uf, "municipality": str(row.get("municipality"))})
                continue
            joined.append(
                {
                    "ibge_code": str(row["ibge_code"]),
                    "municipality": row.get("municipality"),
                    "uf": uf,
                    "edapho_region": found["edapho_region"],
                    "macroregion": found["macroregion"],
                }
            )
    joined.sort(key=lambda row: row["ibge_code"])

    # --- verificação de não regressão nos seis estados ----------------------
    legacy: dict[str, dict[str, str]] = {}
    with open(V34, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            legacy[str(row["ibge_code"])] = row
    divergences = []
    for row in joined:
        if row["uf"] == "SP":
            continue
        previous = legacy.get(row["ibge_code"])
        if previous is None:
            divergences.append({"ibge_code": row["ibge_code"], "issue": "ausente na V3.4"})
            continue
        if (
            previous["edapho_region"] != row["edapho_region"]
            or previous["macroregion"] != row["macroregion"]
        ):
            divergences.append(
                {
                    "ibge_code": row["ibge_code"],
                    "issue": "classificação divergente",
                    "v34": [previous["edapho_region"], previous["macroregion"]],
                    "v35": [row["edapho_region"], row["macroregion"]],
                }
            )
    if divergences:
        raise SystemExit(f"divergência nos seis estados: {divergences[:5]}")

    with open(V35, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["ibge_code", "municipality", "uf", "edapho_region", "macroregion"],
        )
        writer.writeheader()
        writer.writerows(joined)

    # --- distribuição em SP -------------------------------------------------
    sp = [row for row in joined if row["uf"] == "SP"]
    by_macro_registry = Counter(row["macroregion"] for row in sp)
    by_macro_edafo = Counter(
        f"MRS{row['macroregion']}/RE{row['edapho_region']}" for row in sp
    )

    # distribuição por cultura, no painel analítico
    codes_by_macro = {row["ibge_code"]: row["macroregion"] for row in sp}
    muni_by_crop_macro: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    rows_by_crop: dict[str, Counter] = defaultdict(Counter)
    # ``status``/``crop`` vivem no painel base de SP, não no arquivo de janelas
    with open(
        os.path.join(PROCESSED, "panel_sp_v35.csv"), newline="", encoding="utf-8-sig"
    ) as handle:
        for row in csv.DictReader(handle):
            if str(row.get("status")) != "paired_usable":
                continue
            code = str(row["ibge_code"])
            macro = codes_by_macro.get(code)
            if macro is None:
                continue
            crop = str(row["crop"])
            rows_by_crop[crop][macro] += 1
            muni_by_crop_macro[crop][macro].add(code)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "normative": "IN SPA/MAPA 1/2021 (anexo atualizado pelas Portarias 387/2023 e 281/2025)",
            "xlsx_sha256": json.load(
                open(os.path.join(MANIFESTS, "v34_region_mapping.json"), encoding="utf-8")
            )["source"]["xlsx_sha256"],
            "frozen_in": "V3.4 (D112)",
        },
        "joined": {"n": len(joined), "unmatched": len(unmatched), "unmatched_examples": unmatched[:10]},
        "legacy_six_states_unchanged": True,
        "sp": {
            "n_municipalities": len(sp),
            "by_macroregion": dict(sorted(by_macro_registry.items())),
            "by_macroregion_edapho": dict(sorted(by_macro_edafo.items())),
            "municipalities_by_crop": {
                crop: {macro: len(codes) for macro, codes in sorted(groups.items())}
                for crop, groups in sorted(muni_by_crop_macro.items())
            },
            "rows_by_crop": {
                crop: dict(sorted(counter.items()))
                for crop, counter in sorted(rows_by_crop.items())
            },
        },
    }
    with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
        handle.write("\n")

    print(json.dumps(payload["sp"], ensure_ascii=False, indent=2))
    print(f"mapeamento v3.5: {V35} ({len(joined)} municípios)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
