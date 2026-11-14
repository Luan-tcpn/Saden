"""V3.5 — janela corrigida (V3.1) e descritores hídricos (V3.3) para São Paulo.

Reutiliza as **funções de cálculo** já validadas — ``_window_records`` e
``_aggregate`` (V3.1) e ``_descriptors`` (V3.3) — apontando-as para os arquivos
de SP. O painel histórico não é recalculado: as linhas dos seis estados vêm de
``v31_panel_windows.csv`` e ``v33_water_variables.csv``, preservadas intactas.

Saídas (novas, sem sobrescrever nada):
* ``v35_sp_windows.csv``   — as mesmas colunas de janela de ``v31_panel_windows.csv``
* ``v35_sp_water.csv``     — as mesmas colunas de ``v33_water_variables.csv``
* ``v35_panel_windows.csv``— histórico + SP (painel expandido de trabalho)
* ``v35_water_variables.csv`` — idem para os descritores

Uso: python tools/v35_build_windows.py
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "geospatial"))
sys.path.insert(0, HERE)

from agroclimate import cycle  # noqa: E402
from agroclimate import evapotranspiration as et_module  # noqa: E402
from agroclimate import thermal  # noqa: E402
from agroclimate import water_balance as wb_module  # noqa: E402

import v31_rebuild_panel as rb  # noqa: E402
import v33_water_variables as wv  # noqa: E402

PROCESSED = os.path.join(ROOT, "geospatial", "data", "processed")
MANIFESTS = os.path.join(ROOT, "geospatial", "data", "manifests")

SP_PANEL = os.path.join(PROCESSED, "panel_sp_v35.csv")
SP_CLIMATE = os.path.join(PROCESSED, "climate_daily_sp.csv")
SP_CAD = os.path.join(MANIFESTS, "v35_cad_polygon_sp.json")
LEGACY_CAD = os.path.join(MANIFESTS, "v30_cad_polygon.json")

OUT_SP_WINDOWS = os.path.join(PROCESSED, "v35_sp_windows.csv")
OUT_SP_WATER = os.path.join(PROCESSED, "v35_sp_water.csv")
OUT_PANEL = os.path.join(PROCESSED, "v35_panel_windows.csv")
OUT_WATER = os.path.join(PROCESSED, "v35_water_variables.csv")
OUT_JSON = os.path.join(MANIFESTS, "v35_sp_windows.json")

LEGACY_PANEL = os.path.join(PROCESSED, "v31_panel_windows.csv")
LEGACY_WATER = os.path.join(PROCESSED, "v33_water_variables.csv")

CAD_SCENARIOS = {"cad_0_60": 60, "cad_0_100": 100, "cad_0_200": 200}
PROFILE_BY_CROP = {"soja": "soja_gilmore", "milho": "milho_embrapa", "milho_2": "milho_embrapa"}


def _num(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_cad() -> dict[str, dict[str, float]]:
    merged: dict[str, dict[str, float]] = {}
    for path in (LEGACY_CAD, SP_CAD):
        if not os.path.exists(path):
            continue
        payload = json.load(open(path, encoding="utf-8"))
        for code, entry in payload.get("municipalities", {}).items():
            merged[code] = {
                name: entry.get(f"{name}_mm") for name in CAD_SCENARIOS
            }
    return merged


def load_sp_rows() -> list[dict[str, Any]]:
    """Linhas analíticas de SP, com o centróide do cadastro municipal.

    O painel base não carrega latitude/longitude; o centróide vem de
    ``panel_municipalities_sp.csv`` (mesma fonte de geometria do painel).
    """
    coordinates: dict[str, tuple[float, float]] = {}
    with open(
        os.path.join(PROCESSED, "panel_municipalities_sp.csv"),
        newline="",
        encoding="utf-8-sig",
    ) as handle:
        for row in csv.DictReader(handle):
            lat = _num(row.get("centroid_lat"))
            lon = _num(row.get("centroid_lon"))
            if lat is not None and lon is not None:
                coordinates[str(row["ibge_code"])] = (lat, lon)

    rows: list[dict[str, Any]] = []
    missing_coordinates = 0
    with open(SP_PANEL, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            if str(row.get("status")) != "paired_usable":
                continue
            if str(row.get("climate_source")) != "NASA-POWER":
                continue
            months = [m for m in str(row.get("zarc_window_months") or "").split(";") if m]
            if not months:
                continue
            code = str(row["ibge_code"])
            position = coordinates.get(code)
            if position is None:
                missing_coordinates += 1
                continue
            rows.append(
                {
                    "ibge_code": code,
                    "crop": str(row["crop"]),
                    "safra": str(row.get("safra")),
                    "months": months,
                    "state": row.get("state"),
                    "zarc_cycle": str(row.get("zarc_cycle") or ""),
                    "harvest_year": row.get("harvest_year"),
                    "yield_kg_ha": _num(row.get("yield_kg_ha")),
                    "latitude": position[0],
                    "longitude": position[1],
                }
            )
    if missing_coordinates:
        print(f"[aviso] {missing_coordinates} linhas sem centróide")
    return rows


def load_sp_climate(codes: list[str]):
    index = {code: i for i, code in enumerate(codes)}
    path = SP_CLIMATE
    dates: list[str] = []
    day_index: dict[str, int] = {}
    capacity = 4000
    fields = rb.FIELDS
    matrices = {
        field: np.full((len(codes), capacity), np.nan, dtype="float32") for field in fields
    }
    with open(path, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            code = str(row.get("ibge_code") or "")
            if code not in index:
                continue
            day = str(row.get("date"))
            slot = day_index.get(day)
            if slot is None:
                slot = len(dates)
                if slot >= capacity:
                    capacity *= 2
                    for field in fields:
                        padded = np.full((len(codes), capacity), np.nan, dtype="float32")
                        padded[:, :slot] = matrices[field][:, :slot]
                        matrices[field] = padded
                day_index[day] = slot
                dates.append(day)
            position = index[code]
            for field in fields:
                value = _num(row.get(field))
                if value is not None:
                    matrices[field][position, slot] = value
    n_days = len(dates)
    for field in fields:
        matrices[field] = matrices[field][:, :n_days]
    return matrices, dates


def build() -> tuple[list[dict], list[dict], dict[str, Any]]:
    started = time.time()
    rows = load_sp_rows()
    codes = sorted({row["ibge_code"] for row in rows})
    cad = load_cad()
    print(f"linhas SP: {len(rows)}; municípios: {len(codes)}", flush=True)
    matrices, dates = load_sp_climate(codes)
    index = {code: i for i, code in enumerate(codes)}
    print(f"dias de clima SP: {len(dates)} ({time.time()-started:.0f}s)", flush=True)

    window_rows: list[dict[str, Any]] = []
    water_rows: list[dict[str, Any]] = []
    for row in rows:
        position = index[row["ibge_code"]]
        latitude = row["latitude"]
        if latitude is None:
            continue
        day_arrays = {field: matrices[field][position] for field in rb.FIELDS}
        profile = thermal.PROFILES.get(PROFILE_BY_CROP.get(row["crop"], ""))
        windows = {}
        for label, corrected in (("legacy", False), ("corrected", True)):
            start, end = cycle.window_bounds(row["months"], corrected=corrected)
            windows[label] = [i for i, d in enumerate(dates) if start <= d <= end]
        record: dict[str, Any] = {
            "ibge_code": row["ibge_code"],
            "crop": row["crop"],
            "safra": row["safra"],
            "state": row["state"],
            "zarc_cycle": row["zarc_cycle"],
            "harvest_year": row["harvest_year"],
            "yield_kg_ha": row["yield_kg_ha"],
            "months": ";".join(row["months"]),
            "n_months_listed": len(row["months"]),
            "latitude": latitude,
            "longitude": row["longitude"],
        }
        for label, days in windows.items():
            if len(days) < 30:
                continue
            records = rb._window_records(dates, day_arrays, None, days, latitude)
            aggregate = rb._aggregate(records, profile, latitude, cad_mm=50.0, with_balance=True)
            for key, value in aggregate.items():
                record[f"{key}_{label}"] = value
        corrected_days = windows["corrected"]
        if len(corrected_days) >= 30:
            records = rb._window_records(dates, day_arrays, None, corrected_days, latitude)
            for name in CAD_SCENARIOS:
                capacity = cad.get(row["ibge_code"], {}).get(name)
                if not capacity:
                    continue
                aggregate = rb._aggregate(
                    records, profile, latitude, cad_mm=float(capacity), with_balance=True
                )
                record[f"deficiency_{name}"] = aggregate.get("deficiency_total_mm")
                record[f"excess_{name}"] = aggregate.get("excess_total_mm")
                record[f"cad_{name}_mm"] = float(capacity)
        window_rows.append(record)

        # descritores de estresse (mesma função da V3.3)
        if len(corrected_days) < 30:
            continue
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
        for label, depth in wv.CAD_LABELS.items():
            if depth is None:
                capacity = 50.0
            else:
                capacity = cad.get(row["ibge_code"], {}).get(label)
                if not capacity:
                    continue
            balance = wb_module.sequential_water_balance(monthly, cad_mm=float(capacity))
            entry = wv._descriptors(balance, float(capacity))
            water = {
                "ibge_code": row["ibge_code"],
                "crop": row["crop"],
                "safra": row["safra"],
                "state": row["state"],
                "harvest_year": row["harvest_year"],
                "yield_kg_ha": row["yield_kg_ha"],
                "scenario": label,
            }
            water.update(entry)
            water_rows.append(water)

    summary = {
        "n_rows_panel": len(rows),
        "n_municipalities": len(codes),
        "n_window_rows": len(window_rows),
        "n_water_rows": len(water_rows),
        "n_codes_with_cad": sum(1 for code in codes if cad.get(code, {}).get("cad_0_100")),
        "elapsed_s": round(time.time() - started, 1),
    }
    return window_rows, water_rows, summary


def _write(rows: list[dict[str, Any]], path: str, fields: list[str] | None = None) -> None:
    if fields is None:
        fields = []
        for row in rows:
            for key in row:
                if key not in fields:
                    fields.append(key)
    with open(path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def merge(legacy_path: str, extra_rows: list[dict[str, Any]], out_path: str) -> dict[str, Any]:
    with open(legacy_path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        legacy_fields = list(reader.fieldnames or [])
        legacy_rows = list(reader)
    extra_fields = []
    for row in extra_rows:
        for key in row:
            if key not in extra_fields:
                extra_fields.append(key)
    fields = legacy_fields + [f for f in extra_fields if f not in legacy_fields]
    for row in extra_rows:
        for key in legacy_fields:
            row.setdefault(key, "")
    _write(legacy_rows + extra_rows, out_path, fields)
    return {
        "legacy_rows": len(legacy_rows),
        "extra_rows": len(extra_rows),
        "total_rows": len(legacy_rows) + len(extra_rows),
        "n_columns": len(fields),
    }


def main() -> int:
    window_rows, water_rows, summary = build()
    _write(window_rows, OUT_SP_WINDOWS)
    _write(water_rows, OUT_SP_WATER)
    merged_window = merge(LEGACY_PANEL, window_rows, OUT_PANEL)
    merged_water = merge(LEGACY_WATER, water_rows, OUT_WATER)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sp": summary,
        "merged_panel": merged_window,
        "merged_water": merged_water,
        "legacy_panel_untouched": LEGACY_PANEL,
        "definition": (
            "janela corrigida da V3.1 (D100) e descritores da V3.3 aplicados às "
            "linhas de SP; as linhas históricas são copiadas sem recálculo"
        ),
    }
    with open(OUT_JSON, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
        handle.write("\n")
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
