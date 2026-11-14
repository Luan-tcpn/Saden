"""V3.4 — sensibilidades do contraste regional.

Todas as variantes usam os **mesmos modelos ajustados** (M2 e M2+bloco hídrico,
protocolo V3.3); muda apenas a regra de agrupamento, o suporte ou o peso. Isso
isola a sensibilidade do desenho, não da especificação.

Variantes (fixadas no pré-registro §7):
1. classificação primária (Sul = MRS1; Cerrado = MRS3∪4);
2. Cerrado restrito a MRS 3;
3. Cerrado sem MT;
4. Sul ∪ MRS 2 (pior caso de má atribuição);
5. agrupamento por região edafoclimática (101/102/103 vs 401/402);
6. D dentro de decis de déficit (suporte comum);
7. ponderação: observação, município, UF.

Uso: python tools/v34_regional_sensitivity.py
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

import v31_models as base  # noqa: E402
import v33_functional_form as v33  # noqa: E402
import v34_regional_contrast as v34  # noqa: E402

MANIFESTS = os.path.join(ROOT, "geospatial", "data", "manifests")
OUT = os.path.join(MANIFESTS, "v34_regional_sensitivity.json")
CROPS = ("milho", "soja", "milho_2")


def _delta(err_wb: np.ndarray, err_m2: np.ndarray, mask: np.ndarray) -> float | None:
    if not mask.any():
        return None
    return float(err_wb[mask].mean() - err_m2[mask].mean())


def _weighted_delta(err_wb, err_m2, group_a, group_b, weight_by) -> dict[str, Any]:
    """D com ponderação por observação, município ou UF."""
    out: dict[str, Any] = {}
    for label in ("observation", "municipality", "uf"):
        if label == "observation":
            d_a = _delta(err_wb, err_m2, group_a)
            d_b = _delta(err_wb, err_m2, group_b)
        else:
            # média das médias dentro de cada unidade
            units = weight_by[label]
            d_a = _mean_of_units(err_wb, err_m2, group_a, units)
            d_b = _mean_of_units(err_wb, err_m2, group_b, units)
        out[label] = {
            "delta_a": d_a,
            "delta_b": d_b,
            "D": (d_a - d_b) if (d_a is not None and d_b is not None) else None,
        }
    return out


def _mean_of_units(err_wb, err_m2, mask, units) -> float | None:
    subset = np.unique(units[mask])
    if subset.size == 0:
        return None
    values = []
    for unit in subset.tolist():
        inside = mask & (units == unit)
        if inside.any():
            values.append(float(err_wb[inside].mean() - err_m2[inside].mean()))
    return float(np.mean(values)) if values else None


def main() -> int:
    started = time.time()
    data = base.load_rows()
    data.pop("__dropped__", None)
    water = v33.load_water()
    groups = v34.load_groups()
    payload: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "note": (
            "mesmos modelos da V3.3; muda apenas agrupamento, suporte ou peso. "
            "Nenhuma variante substitui a classificacao primaria."
        ),
        "crops": {},
    }
    for crop in CROPS:
        rows = v34.build_rows(crop, data, water, groups)
        print(f"=== {crop}: {len(rows)} linhas ===", flush=True)
        m2 = v33._run(rows, v33.MODELS["M2"], 1, 300)
        wb = v33._run(rows, v33.MODELS["M2_WB_plus"], 1, 300)
        err_m2 = np.asarray(m2["row_abs_errors"]["TE"])
        err_wb = np.asarray(wb["row_abs_errors"]["TE"])
        codes = m2["row_codes"]
        years_raw = m2["row_years_raw"]
        # chave (município, ano): um município-ano é único, então o valor de
        # déficit de cada linha de teste é o daquele ano — não o de um ano
        # arbitrário do município.
        pair_info = {
            (row["ibge_code"], str(row["year"])): row for row in rows
        }
        info = {row["ibge_code"]: row for row in rows}
        aligned = [pair_info.get((c, y), {}) for c, y in zip(codes.tolist(), years_raw.tolist())]
        macro = np.array([item.get("macroregion", "") for item in aligned])
        state = np.array([item.get("state", "") for item in aligned])
        edafo = np.array([item.get("edapho_region", "") for item in aligned])
        deficit = np.array(
            [item.get("wb_deficit", np.nan) if item else np.nan for item in aligned],
            dtype="float64",
        )
        missing = int(np.isnan(deficit).sum())
        print(f"  linhas de teste sem déficit alinhado: {missing}", flush=True)
        units = {"municipality": codes, "uf": state}

        entry: dict[str, Any] = {"n": int(err_m2.size), "variants": {}}

        definitions = {
            "primaria": (np.isin(macro, ["1"]), np.isin(macro, ["3", "4"])),
            "cerrado_restrito_mrs3": (np.isin(macro, ["1"]), np.isin(macro, ["3"])),
            "cerrado_sem_mt": (
                np.isin(macro, ["1"]),
                np.isin(macro, ["3", "4"]) & (state != "MT"),
            ),
            "sul_com_transicao": (np.isin(macro, ["1", "2"]), np.isin(macro, ["3", "4"])),
            "edafoclimatica": (
                np.isin(edafo, ["101", "102", "103"]),
                np.isin(edafo, ["401", "402"]),
            ),
        }
        for name, (group_a, group_b) in definitions.items():
            if not group_a.any() or not group_b.any():
                entry["variants"][name] = {"status": "empty_group"}
                continue
            entry["variants"][name] = _weighted_delta(err_wb, err_m2, group_a, group_b, units)
            item = entry["variants"][name]
            print(
                "  %-24s D(obs)=%s D(muni)=%s D(uf)=%s"
                % (
                    name,
                    _fmt(item["observation"]["D"]),
                    _fmt(item["municipality"]["D"]),
                    _fmt(item["uf"]["D"]),
                ),
                flush=True,
            )

        # suporte comum: decis do déficit agrupado
        sul = np.isin(macro, ["1"])
        cerrado = np.isin(macro, ["3", "4"])
        valid = np.isfinite(deficit)
        deciles: dict[str, Any] = {}
        if valid.sum() > 100:
            edges = np.nanquantile(deficit[valid], np.linspace(0, 1, 11))
            for index in range(10):
                low, high = edges[index], edges[index + 1]
                inside = valid & (deficit >= low) & (deficit <= high)
                deciles[f"d{index}"] = {
                    "range_mm": [float(low), float(high)],
                    "n_sul": int((inside & sul).sum()),
                    "n_cerrado": int((inside & cerrado).sum()),
                    "delta_sul": _delta(err_wb, err_m2, inside & sul),
                    "delta_cerrado": _delta(err_wb, err_m2, inside & cerrado),
                    "D": (
                        _delta(err_wb, err_m2, inside & sul)
                        - _delta(err_wb, err_m2, inside & cerrado)
                        if (inside & sul).any() and (inside & cerrado).any()
                        else None
                    ),
                }
        entry["deficit_deciles"] = deciles
        print("  decis de déficit (D por decil):")
        for key, value in deciles.items():
            print(
                "    %-4s [%6.1f, %6.1f] n_sul=%4d n_cer=%4d D=%s"
                % (
                    key,
                    value["range_mm"][0],
                    value["range_mm"][1],
                    value["n_sul"],
                    value["n_cerrado"],
                    _fmt(value["D"]),
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


def _fmt(value) -> str:
    return "None" if value is None else f"{value:+.1f}"


if __name__ == "__main__":
    raise SystemExit(main())
