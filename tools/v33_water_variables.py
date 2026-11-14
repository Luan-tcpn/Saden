"""V3.3 — descritores do balanço hídrico além do déficit acumulado.

A V3.2 encontrou sinais exploratórios de heterogeneidade no milho para déficit,
graus-dia e calor, mas não para precipitação e temperatura brutas. A hipótese da
V3.3 é que a **forma funcional** está incompleta: intensidade acumulada não
descreve duração, timing nem intensidade relativa do estresse.

Este script produz, para a janela corrigida (D100) e os mesmos cenários de CAD
da V3.0/V3.1, os descritores que o painel ainda não tem:

* ``deficit_months`` — meses da janela com déficit (DEF > 0);
* ``stress_share`` — fração da janela em estresse;
* ``max_consecutive_deficit_months`` — maior sequência contínua em estresse;
* ``storage_min_mm`` — menor armazenamento de água no solo;
* ``etr_over_etp`` — ETR/ETP acumulados (índice relativo de atendimento da
  demanda; equivalente conceitual ao WRSI);
* ``deficit_over_etp`` — déficit normalizado pela demanda atmosférica;
* ``months_to_first_stress`` — posição do primeiro mês com déficit na janela.

A granularidade é **mensal**, que é o que o balanço sequencial de
Thornthwaite–Mather implementado no projeto oferece. Nenhuma duração em dias é
inventada: os dados diários existem, mas o balanço sequencial de armazenamento
não é diário.

Uso: python tools/v33_water_variables.py
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "geospatial"))
sys.path.insert(0, HERE)

from agroclimate import cycle  # noqa: E402
from agroclimate import evapotranspiration as et_module  # noqa: E402
from agroclimate import water_balance as wb_module  # noqa: E402

import v31_rebuild_panel as rebuild  # noqa: E402  (reuso, sem duplicar logica)

PROCESSED = os.path.join(ROOT, "geospatial", "data", "processed")
MANIFESTS = os.path.join(ROOT, "geospatial", "data", "manifests")
OUT_CSV = os.path.join(PROCESSED, "v33_water_variables.csv")
OUT_JSON = os.path.join(MANIFESTS, "v33_water_variables.json")

CAD_LABELS = {
    "cad50": None,
    "cad_0_60": 60,
    "cad_0_100": 100,
    "cad_0_200": 200,
}


def _descriptors(balance, cad_mm: float) -> dict:
    """Descritores temporais do balanço (delegado à biblioteca)."""
    descriptors = wb_module.stress_descriptors(balance)
    valid = [row for row in balance if row.get("status") == "ok"]
    if not valid:
        return {"status": "no_valid_months", "cad_mm": cad_mm}
    deficit_total = sum(float(row.get("def_mm") or 0.0) for row in valid)
    return {
        "status": "ok",
        "cad_mm": cad_mm,
        "deficit_total_mm": deficit_total,
        "etp_total_mm": sum(float(row.get("etp_mm") or 0.0) for row in valid),
        "etr_total_mm": sum(float(row.get("etr_mm") or 0.0) for row in valid),
        **{key: value for key, value in descriptors.items() if key != "months"},
        "months": descriptors["months"],
    }


def main() -> int:
    started = time.time()
    rows = rebuild.load_panel_rows()
    codes = sorted({row["ibge_code"] for row in rows})
    cad = rebuild.load_cad()
    centroids = rebuild.load_centroids()
    print(f"linhas: {len(rows)}; municipios: {len(codes)}", flush=True)
    matrices, dates, _ = rebuild.load_climate(codes)
    print(f"dias de clima: {len(dates)} ({time.time()-started:.0f}s)", flush=True)

    by_code: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_code[row["ibge_code"]].append(row)

    output: list[dict] = []
    for position, code in enumerate(codes):
        latitude = centroids.get(code)
        if latitude is None:
            continue
        day_arrays = {field: matrices[field][position] for field in rebuild.FIELDS}
        for row in by_code[code]:
            start, end = cycle.window_bounds(row["months"], corrected=True)
            days = [i for i, d in enumerate(dates) if start <= d <= end]
            if len(days) < 30:
                continue
            records = rebuild._window_records(dates, day_arrays, None, days, latitude)
            series = et_module.daily_et0_series(
                [
                    {
                        "date": r["date"],
                        "temp_max_c": r["temp_max_c"],
                        "temp_min_c": r["temp_min_c"],
                        "temp_media_c": r["temp_media_c"],
                        "radiacao_mj_m2": r["radiacao_mj_m2"],
                        "vento_kmh": r["vento_kmh"],
                        "umidade_rel_pct": r["umidade_rel_pct"],
                        "pressao_kpa": r["pressao_kpa"],
                    }
                    for r in records
                ],
                float(latitude),
                method="fao56_penman_monteith",
                elevation_m=None,
            )
            precip = {r["date"]: r["precip_mm"] for r in records}
            for item in series:
                item["precip_mm"] = precip.get(str(item.get("date")))
            monthly = wb_module.daily_to_monthly(series)
            base = {
                "ibge_code": code,
                "crop": row["crop"],
                "safra": row["safra"],
                "state": row["state"],
                "harvest_year": row["harvest_year"],
                "yield_kg_ha": row["yield_kg_ha"],
                "n_window_days": len(days),
            }
            capacity_default = 50.0
            for label, depth in CAD_LABELS.items():
                if depth is None:
                    capacity = capacity_default
                else:
                    capacity = cad.get(code, {}).get(label)
                    if not capacity:
                        continue
                balance = wb_module.sequential_water_balance(
                    monthly, cad_mm=float(capacity)
                )
                descriptors = _descriptors(balance, float(capacity))
                record = dict(base)
                record["scenario"] = label
                record.update(descriptors)
                output.append(record)
        if (position + 1) % 300 == 0:
            print(f"  {position+1}/{len(codes)} municipios", flush=True)

    fields: list[str] = []
    for record in output:
        for key in record:
            if key not in fields:
                fields.append(key)
    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(output)

    by_scenario: dict[str, dict] = {}
    for label in CAD_LABELS:
        subset = [r for r in output if r["scenario"] == label and r.get("status") == "ok"]
        if not subset:
            continue
        by_scenario[label] = {
            "n": len(subset),
            "median_months": float(np.median([r["months"] for r in subset])),
            "median_deficit_months": float(np.median([r["deficit_months"] for r in subset])),
            "median_stress_share": float(np.median([r["stress_share"] for r in subset])),
            "median_max_consecutive": float(
                np.median([r["max_consecutive_deficit_months"] for r in subset])
            ),
            "share_all_months_stressed": float(
                np.mean([1.0 if r["deficit_months"] == r["months"] else 0.0 for r in subset])
            ),
            "share_no_stress": float(
                np.mean([1.0 if r["deficit_months"] == 0 else 0.0 for r in subset])
            ),
            "median_etr_over_etp": float(np.median([r["etr_over_etp"] for r in subset])),
            "median_deficit_total_mm": float(
                np.median([r["deficit_total_mm"] for r in subset])
            ),
            "median_storage_min_mm": float(
                np.median([r["storage_min_mm"] for r in subset])
            ),
        }

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "definition": (
            "descritores mensais do balanco sequencial de Thornthwaite-Mather na "
            "janela ZARC corrigida; nenhuma duracao em dias e inventada"
        ),
        "granularity": "mensal (o balanco sequencial implementado e mensal)",
        "n_rows": len(output),
        "scenarios": by_scenario,
        "elapsed_s": round(time.time() - started, 1),
    }
    with open(OUT_JSON, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
        handle.write("\n")
    print(json.dumps(by_scenario, ensure_ascii=False, indent=2))
    print(f"painel: {OUT_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
