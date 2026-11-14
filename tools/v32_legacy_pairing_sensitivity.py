"""V3.2 — sensibilidade da V3.1 ao esquema de reamostragem (D104).

As comparações preditivas da V3.1 usaram bootstrap por **bloco espacial**. Como
a V3.2 mostrou que a unidade de dependência dos regressores climáticos é UF×ano,
verifica-se aqui se as conclusões pareadas da V3.1 (janela corrigida vs janela
histórica) mudam quando a reamostragem é feita por UF×ano.

Não refaz nenhuma estimativa: reutiliza `v31_models.load_rows` e o mesmo
estimador, com as mesmas sementes, e só troca as unidades do bootstrap.

Uso: python tools/v32_legacy_pairing_sensitivity.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "geospatial"))
sys.path.insert(0, HERE)

import run_robustness as rr  # noqa: E402
from agroclimate import generalization as gen  # noqa: E402

import v31_models as base  # noqa: E402

MANIFESTS = os.path.join(ROOT, "geospatial", "data", "manifests")
OUT = os.path.join(MANIFESTS, "v32_v31_resampling_sensitivity.json")

PAIRS = (
    ("corrected_climate", "legacy_climate"),
    ("corrected_water_cad100", "corrected_climate"),
)


def main() -> int:
    started = time.time()
    data = base.load_rows()
    data.pop("__dropped__", None)
    payload: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "purpose": (
            "verificar se as conclusoes pareadas da V3.1 sobrevivem ao bootstrap "
            "por UFxano, unidade adotada na D104"
        ),
        "protocol": "identico a V3.1 (TE, per_cell, 3 repeticoes, semente rr.SEED); "
                    "muda apenas a unidade de reamostragem do IC",
        "crops": {},
    }
    for crop in ("soja", "milho", "milho_2"):
        rows = data.get(crop, [])
        print(f"=== {crop} ===", flush=True)
        kept = {}
        for name, variables in (
            ("legacy_climate", ("precip_legacy", "temp_legacy")),
            ("corrected_climate", ("precip_corrected", "temp_corrected")),
            ("corrected_water_cad100", ("deficit_cad100",)),
        ):
            usable = [r for r in rows if all(r.get(v) is not None for v in variables)]
            kept[name] = gen.factorial_holdout(
                usable,
                variables,
                seed=rr.SEED,
                n_repeats=3,
                n_boot=1000,
                variant="climate_plus_state",
                equalize="per_cell",
                keep_errors=True,
            )
        blocks = kept["corrected_climate"]["row_blocks"]
        state_years = np.array(
            [
                f"{s}||{y}"
                for s, y in zip(
                    kept["corrected_climate"]["row_states"].tolist(),
                    kept["corrected_climate"]["row_years"].tolist(),
                )
            ]
        )
        entry: dict[str, Any] = {"n_rows": len(rows), "pairs": {}}
        for left, right in PAIRS:
            a = np.asarray(kept[left]["row_abs_errors"]["TE"])
            b = np.asarray(kept[right]["row_abs_errors"]["TE"])
            if a.size != b.size:
                entry["pairs"][f"{left}_vs_{right}"] = {"status": "unaligned"}
                continue
            record: dict[str, Any] = {
                "delta_mae": float(np.mean(a) - np.mean(b)),
                "n": int(a.size),
            }
            for label, units in (("block", blocks), ("state_year", state_years)):
                interval = gen.block_bootstrap_difference(a, b, units, n_boot=1000)
                record[label] = {
                    "ci95": interval["ci95"],
                    "n_units": interval["n_blocks"],
                    "excludes_zero": bool(
                        interval["ci95"][0] > 0 or interval["ci95"][1] < 0
                    ),
                }
            entry["pairs"][f"{left}_vs_{right}"] = record
            print(
                "  %-34s delta=%+8.2f bloco[%8.1f,%8.1f]%s UFxano[%8.1f,%8.1f]%s"
                % (
                    f"{left} vs {right}",
                    record["delta_mae"],
                    record["block"]["ci95"][0],
                    record["block"]["ci95"][1],
                    "*" if record["block"]["excludes_zero"] else " ",
                    record["state_year"]["ci95"][0],
                    record["state_year"]["ci95"][1],
                    "*" if record["state_year"]["excludes_zero"] else " ",
                ),
                flush=True,
            )
        payload["crops"][crop] = entry
    payload["elapsed_s"] = round(time.time() - started, 1)
    with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
        handle.write("\n")
    print(f"manifesto: {OUT} ({payload['elapsed_s']} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
