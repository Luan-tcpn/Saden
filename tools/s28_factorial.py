"""V2.8 — fatorial espaço × tempo e controle de tamanho (D87).

Responde à pergunta central da V2.8: a inversão da soja no P5 decorre da
**ausência do ano compartilhado**, da **redução do treino** ou de
**mudança de composição**?

O desenho é um fatorial 2×2 (espaço × tempo) sobre a mesma grade de dobras
do P5. O conjunto de teste é idêntico em todos os braços (cada linha é
prevista exatamente uma vez), de modo que as MAEs são comparáveis. O braço
``SE`` reproduz o P3 e o braço ``TE`` reproduz o P5 — verificado por teste.

Uso:
    python tools/s28_factorial.py            # grade completa
    python tools/s28_factorial.py --quick    # só soja, família B
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, timezone

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "geospatial"))

import run_robustness as rr  # noqa: E402
from agroclimate import generalization as gen  # noqa: E402

OUT_JSON = os.path.join(
    ROOT, "geospatial", "data", "manifests", "v28_factorial.json"
)
OUT_CSV = os.path.join(
    ROOT, "geospatial", "data", "manifests", "v28_factorial.csv"
)

CROPS = ("soja", "milho", "milho_2")
FAMILIES = ("B_meteorologicos", "C_thermal", "D_hidricos")
LEARNING_FRACTIONS = (0.4, 0.55, 0.7, 0.85)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value):
    """Remove arrays internos e campos privados antes de serializar."""
    if isinstance(value, dict):
        return {
            key: _clean(item)
            for key, item in value.items()
            if not key.startswith("_") and key not in ("test_blocks", "test_years")
        }
    if isinstance(value, (list, tuple)):
        return [_clean(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    return value


def _row(crop, family, config, arm, entry):
    return {
        "crop": crop,
        "family": family,
        "config": config,
        "arm": arm,
        "train_size_mean": round(entry.get("train_size_mean", 0.0), 1),
        "mae_modelo": round(entry["model"]["mae_kg_ha"], 4),
        "mae_baseline": round(entry["baseline"]["mae_kg_ha"], 4),
        "gain_percent": round(entry["gain_percent"], 4),
        "n": entry["model"]["n"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--block-km", type=float, default=250.0)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()

    crops = ("soja",) if args.quick else CROPS
    families = ("B_meteorologicos",) if args.quick else FAMILIES

    os.environ["SADEN_V27_BLOCK_KM"] = str(args.block_km)
    rows = rr.prepare(rr.load_panel())
    manifest: dict = {
        "generated_at": _now(),
        "seed": rr.SEED,
        "block_km": args.block_km,
        "method": (
            "Fatorial 2x2 espaco x tempo sobre a grade de dobras do P5, com "
            "controle de tamanho por reamostragem estratificada por bloco. "
            "SS=espaco e tempo compartilhados; SE=espaco separado (P3); "
            "TS=tempo separado; TE=ambos (P5). Teste identico nos 4 bracos."
        ),
        "crops": {},
    }
    csv_rows: list[dict] = []
    started = time.time()
    for crop in crops:
        subset = [r for r in rows if r["crop"] == crop]
        if not subset:
            continue
        crop_out: dict = {"n_rows": len(subset), "families": {}}
        for family in families:
            variables = rr.MODELS[family]
            full = gen.factorial_holdout(
                subset, variables, seed=rr.SEED, n_boot=1000
            )
            equal = gen.factorial_holdout(
                subset,
                variables,
                seed=rr.SEED,
                size_fraction=0.64,
                n_repeats=args.repeats,
                n_boot=1000,
            )
            curve = {}
            for fraction in LEARNING_FRACTIONS:
                curve[str(fraction)] = gen.factorial_holdout(
                    subset,
                    variables,
                    seed=rr.SEED,
                    size_fraction=fraction,
                    n_repeats=3,
                    n_boot=200,
                )
            crop_out["families"][family] = {
                "variables": list(variables),
                "full": _clean(full),
                "equal_size_0.64": _clean(equal),
                "learning_curve": _clean(curve),
            }
            for arm, entry in full.get("arms", {}).items():
                if entry.get("status") == "ok":
                    csv_rows.append(_row(crop, family, "full", arm, entry))
            for arm, entry in equal.get("arms", {}).items():
                if entry.get("status") == "ok":
                    csv_rows.append(_row(crop, family, "equal_0.64", arm, entry))
            for fraction, result in curve.items():
                for arm, entry in result.get("arms", {}).items():
                    if entry.get("status") == "ok":
                        csv_rows.append(
                            _row(crop, family, f"size_{fraction}", arm, entry)
                        )
            arms = full.get("arms", {})
            print(
                f"{crop:<8} {family:<16} full: "
                + " ".join(
                    f"{a}={arms[a]['model']['mae_kg_ha']:.1f}"
                    for a in ("SS", "SE", "TS", "TE")
                    if arms.get(a, {}).get("status") == "ok"
                ),
                flush=True,
            )
        manifest["crops"][crop] = crop_out
    manifest["elapsed_s"] = round(time.time() - started, 1)
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2, default=str)
        handle.write("\n")
    fields = [
        "crop",
        "family",
        "config",
        "arm",
        "train_size_mean",
        "mae_modelo",
        "mae_baseline",
        "gain_percent",
        "n",
    ]
    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in csv_rows:
            writer.writerow(row)
    print(f"manifesto: {OUT_JSON} ({manifest['elapsed_s']} s)")
    print(f"planilha : {OUT_CSV} ({len(csv_rows)} linhas)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
