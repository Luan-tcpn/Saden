"""V2.9 — diagnóstico de cobertura e interseção entre fontes (D95).

Responde "quantas observações do painel têm, ao mesmo tempo, clima,
produtividade, classe de ciclo e CAD?" — sem somar coberturas de fontes
diferentes como se fossem a mesma população.

Uso:
    python tools/s29_coverage.py
"""

from __future__ import annotations

import csv
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "geospatial"))

from agroclimate import cycle  # noqa: E402

PROCESSED = os.path.join(ROOT, "geospatial", "data", "processed")
MANIFESTS = os.path.join(ROOT, "geospatial", "data", "manifests")
OUT = os.path.join(MANIFESTS, "v29_coverage.json")
CAD_MANIFEST = os.path.join(MANIFESTS, "v29_cad_expansion.json")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_panel_rows():
    path = os.path.join(PROCESSED, "agroclimatic_productivity_panel.csv")
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            if str(row.get("status")) != "paired_usable":
                continue
            if str(row.get("climate_source")) != "NASA-POWER":
                continue
            rows.append(row)
    return rows


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Cobertura e interseção de fontes.")
    parser.add_argument("--cad", default=CAD_MANIFEST)
    args = parser.parse_args()

    import run_robustness as rr

    rows = load_panel_rows()
    prepared = rr.prepare(rr.load_panel())
    blocks_by_crop: dict[str, int] = {}
    for row in prepared:
        code = str(row["crop"])
        if code not in blocks_by_crop:
            blocks_by_crop[code] = 0
    for crop in blocks_by_crop:
        blocks_by_crop[crop] = len(
            {
                str(r.get("spatial_block"))
                for r in prepared
                if str(r["crop"]) == crop and r.get("spatial_block")
            }
        )
    cad = {}
    if os.path.exists(args.cad):
        cad = {
            str(r["ibge_code"]): r
            for r in json.load(open(args.cad, encoding="utf-8"))["municipalities"]
            if r.get("cad_0_100_pixels")
        }

    per_crop: dict[str, dict] = {}
    by_crop: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_crop[str(row["crop"])].append(row)
    for crop, subset in by_crop.items():
        states = Counter(str(r.get("state")) for r in subset)
        years = Counter(str(r.get("harvest_year") or r.get("pam_reference_year")) for r in subset)
        cycles = Counter(str(r.get("zarc_cycle")) for r in subset)
        with_cad = [r for r in subset if str(r["ibge_code"]) in cad]
        per_crop[crop] = {
            "rows": len(subset),
            "municipalities": len({str(r["ibge_code"]) for r in subset}),
            "blocks": blocks_by_crop.get(crop, 0),
            "states": dict(states.most_common()),
            "years": dict(sorted(years.items())),
            "cycles": {
                cycle.class_label(code) + f" ({code})": count
                for code, count in cycles.most_common()
            },
            "rows_with_cad": len(with_cad),
            "municipalities_with_cad": len({str(r["ibge_code"]) for r in with_cad}),
            "state_share": {
                state: count / len(subset) for state, count in states.most_common()
            },
        }

    payload = {
        "generated_at": _now(),
        "note": (
            "Coberturas medidas na MESMA população (linhas paired_usable de "
            "NASA POWER). A CAD foi coletada para todos os municípios do "
            "painel; 'rows_with_cad' é a interseção efetiva."
        ),
        "panel": {
            "rows": len(rows),
            "municipalities": len({str(r["ibge_code"]) for r in rows}),
            "crops": sorted(by_crop),
        },
        "cad": {
            "municipalities_collected": len(cad),
            "coverage_of_panel_municipalities": (
                len(cad) / len({str(r["ibge_code"]) for r in rows}) if rows else None
            ),
            "cad_0_100_mm_range": (
                [
                    min(r["cad_0_100_pixels"]["median"] for r in cad.values()),
                    max(r["cad_0_100_pixels"]["median"] for r in cad.values()),
                ]
                if cad
                else None
            ),
        },
        "per_crop": per_crop,
        "gaps": {
            "states_not_in_panel": ["AC", "AL", "AM", "AP", "CE", "DF", "ES", "MA",
                                    "MG", "PA", "PB", "PE", "PI", "RJ", "RN", "RO",
                                    "RR", "SC", "SE", "SP", "TO"],
            "note": (
                "O painel cobre 5-6 UFs; a expansão nacional exigiria "
                "diagnóstico de representatividade por bioma e sistema "
                "produtivo, não apenas mais linhas."
            ),
        },
    }
    with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
        handle.write("\n")
    for crop, entry in per_crop.items():
        print(
            f"{crop:<8} rows={entry['rows']:<6} munis={entry['municipalities']:<5} "
            f"blocks={entry['blocks']:<4} UFs={len(entry['states'])} "
            f"CAD rows={entry['rows_with_cad']}"
        )
    print(f"CAD coletada: {len(cad)} municípios; manifesto: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
