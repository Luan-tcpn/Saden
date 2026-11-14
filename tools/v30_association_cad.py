"""V3.0 — associação do déficit recalculado com a produtividade (D98).

O modelo preditivo (``v30_models_cad.py``) responde "o déficit novo prevê
melhor?". Esta tabela responde outra pergunta: **o coeficiente da associação
muda** quando o déficit é recalculado?

Para cada cultura e cada definição de déficit, estima-se o coeficiente *within*
(efeitos fixos de município e ano) com erro agrupado por bloco espacial, e o
p-valor de Holm é aplicado sobre a família de hipóteses declarada (3 culturas ×
5 definições). Nenhuma especificação é escolhida pelo p-valor.

Uso:
    python tools/v30_association_cad.py
"""

from __future__ import annotations

import csv
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "geospatial"))

import run_robustness as rr  # noqa: E402
from agroclimate import robust, spatial, spatial_inference  # noqa: E402

PROCESSED = os.path.join(ROOT, "geospatial", "data", "processed")
MANIFESTS = os.path.join(ROOT, "geospatial", "data", "manifests")
RECALC = os.path.join(PROCESSED, "v30_panel_cad.csv")
OUT = os.path.join(MANIFESTS, "v30_association_cad.json")

DEFINITIONS = {
    "deficit_hist": "hist_def_cad50",
    "deficit_corr50": "corr_def_v26_50",
    "deficit_cad60": "corr_def_cad_0_60",
    "deficit_cad100": "corr_def_cad_0_100",
    "deficit_cad200": "corr_def_cad_0_200",
}
CROPS = ("soja", "milho", "milho_2")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _num(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_rows() -> list[dict]:
    with open(RECALC, newline="", encoding="utf-8-sig") as handle:
        recalc = {
            (row["ibge_code"], row["crop"], row["safra"]): row
            for row in csv.DictReader(handle)
        }
    blocks = spatial.spatial_blocks(rr.load_municipalities(), 250.0)
    rows = []
    for row in rr.load_panel():
        if str(row.get("status")) != "paired_usable":
            continue
        if str(row.get("climate_source")) != "NASA-POWER":
            continue
        key = (str(row["ibge_code"]), str(row["crop"]), str(row.get("safra")))
        extra = recalc.get(key)
        if extra is None:
            continue
        year = row.get("harvest_year") or row.get("pam_reference_year")
        if year in (None, ""):
            continue
        entry = {
            "ibge_code": str(row["ibge_code"]),
            "crop": str(row["crop"]),
            "state": row.get("state"),
            "year": int(year),
            "yield_kg_ha": _num(row.get("yield_kg_ha")),
            "spatial_block": blocks.get(str(row["ibge_code"])),
        }
        if entry["yield_kg_ha"] is None or not entry["spatial_block"]:
            continue
        ok = True
        for name, column in DEFINITIONS.items():
            value = _num(extra.get(column))
            if value is None:
                ok = False
                break
            entry[name] = value
        if ok:
            rows.append(entry)
    return rows


def estimate(rows, variable, block_key="spatial_block"):
    prepared = spatial_inference.within_data(rows, variable)
    if prepared.get("status") != "ok":
        return {"status": prepared.get("status")}
    blocks = [str(r.get(block_key) or "") for r in prepared["rows"]]
    result = spatial_inference.clustered_within_inference(
        prepared, {"bloco_espacial": blocks}, correction=robust.CR1
    )
    scheme = result.get("schemes", {}).get("bloco_espacial", {})
    if scheme.get("status") != "ok":
        return {"status": scheme.get("status")}
    return {
        "status": "ok",
        "coefficient": result["coefficient"],
        "std_error": scheme["std_error"],
        "t_statistic": scheme["t_statistic"],
        "p_value": scheme["p_value"],
        "n": result["n"],
        "n_clusters": scheme["n_clusters"],
        "deficit_mean": float(np.mean([r[variable] for r in prepared["rows"]])),
        "deficit_sd": float(np.std([r[variable] for r in prepared["rows"]])),
    }


def main() -> int:
    rows = load_rows()
    by_crop: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_crop[row["crop"]].append(row)
    print(f"linhas: {len(rows)}", flush=True)

    payload = {
        "generated_at": _now(),
        "method": (
            "Coeficiente within (FE municipio + ano) do deficit sobre "
            "produtividade, erro agrupado por bloco espacial (CR1), p de Holm "
            "sobre a familia de 15 hipoteses (3 culturas x 5 definicoes)."
        ),
        "family_size": 3 * len(DEFINITIONS),
        "crops": {},
    }
    p_values: dict[str, float] = {}
    for crop in CROPS:
        payload["crops"][crop] = {}
        for name in DEFINITIONS:
            result = estimate(by_crop.get(crop, []), name)
            payload["crops"][crop][name] = result
            if result.get("status") == "ok" and result.get("p_value") is not None:
                p_values[f"{crop}|{name}"] = float(result["p_value"])
    adjusted = robust.holm_adjust(p_values)
    for key, value in adjusted.items():
        crop, name = key.split("|")
        payload["crops"][crop][name]["p_holm"] = value
    payload["n_tests"] = len(p_values)
    payload["n_survive_holm"] = sum(1 for v in adjusted.values() if v < 0.05)

    with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
        handle.write("\n")

    print(f"{'cultura':<8}{'definição':<17}{'coef':>12}{'t':>9}{'p':>9}{'p_holm':>10}"
          f"{'média':>10}{'sd':>9}")
    for crop in CROPS:
        for name in DEFINITIONS:
            entry = payload["crops"][crop][name]
            if entry.get("status") != "ok":
                print(f"{crop:<8}{name:<17}{entry.get('status')}")
                continue
            print(
                f"{crop:<8}{name:<17}{entry['coefficient']:>12.4f}"
                f"{entry['t_statistic']:>9.2f}{entry['p_value']:>9.4f}"
                f"{entry['p_holm']:>10.4f}{entry['deficit_mean']:>10.1f}"
                f"{entry['deficit_sd']:>9.1f}"
            )
    print(f"\nsobrevivem a Holm: {payload['n_survive_holm']} de {payload['n_tests']}")
    print(f"manifesto: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
