"""V3.5 — aquisição de São Paulo pela cadeia existente.

Não cria pipeline paralelo: reutiliza as mesmas funções usadas para os seis
estados.

* municípios e geometria: ``agroclimate.boundaries`` (shapes oficiais do IBGE),
  com os **mesmos campos** de ``run_agroclimate.py municipalities``;
* clima diário: ``agroclimate.gridded.fetch_point("nasa_power")`` +
  ``normalize_nasa_power``, mesma janela 2016–2025;
* produtividade: ``agri.pam_panel.fetch_state_municipalities`` +
  ``fetch_state_pam`` (SIDRA 5457, mesmos produtos e variáveis);
* janela agrícola: ``agri.zarc_panel.fetch_panel``;
* painel: ``agroclimate.panel.build_panel`` com o mesmo perfil de solo e método
  de ET0 da V2.6–V3.4.

O painel histórico **não é tocado**: os seis estados ficam em
``panel_municipalities_v34.csv`` (snapshot) e o painel expandido é escrito em
arquivos novos.

Uso:
    python tools/v35_acquire_sp.py --stage municipalities
    python tools/v35_acquire_sp.py --stage climate
    python tools/v35_acquire_sp.py --stage productivity
    python tools/v35_acquire_sp.py --stage panel
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "geospatial"))

from agroclimate import boundaries, gridded, panel  # noqa: E402
from agri import pam_panel, zarc_panel  # noqa: E402

PROCESSED = os.path.join(ROOT, "geospatial", "data", "processed")
MANIFESTS = os.path.join(ROOT, "geospatial", "data", "manifests")
EXTERNAL = os.path.join(ROOT, "geospatial", "data", "external")

LEGACY_MUNICIPALITIES = os.path.join(PROCESSED, "panel_municipalities.csv")
LEGACY_SNAPSHOT = os.path.join(PROCESSED, "panel_municipalities_v34.csv")
SP_MUNICIPALITIES = os.path.join(PROCESSED, "panel_municipalities_sp.csv")
V35_MUNICIPALITIES = os.path.join(PROCESSED, "panel_municipalities_v35.csv")
SP_CLIMATE = os.path.join(PROCESSED, "climate_daily_sp.csv")
SP_PAM = os.path.join(PROCESSED, "pam_panel_sp.csv")
SP_ZARC = os.path.join(PROCESSED, "zarc_panel_sp.csv")
SP_PANEL = os.path.join(PROCESSED, "panel_sp_v35.csv")
CLIMATE_CACHE = os.path.join(EXTERNAL, "sp_climate_cache")
OUT_STATUS = os.path.join(MANIFESTS, "v35_sp_acquisition.json")

START_YEAR = 2016
END_YEAR = 2025
BOUNDARY_YEAR = 2025
SOIL_PROFILE = "tipo2_medio"
ET_METHOD = "fao56_penman_monteith"
WORKERS = 4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read(path: str) -> list[dict[str, str]]:
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _write(rows: list[dict[str, Any]], path: str) -> str:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with open(path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return path


def _sha(path: str) -> str | None:
    if not os.path.exists(path):
        return None
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def _load_status() -> dict[str, Any]:
    if os.path.exists(OUT_STATUS):
        return json.load(open(OUT_STATUS, encoding="utf-8"))
    return {"generated_at": _now(), "stages": {}}


def _save_status(payload: dict[str, Any]) -> None:
    payload["updated_at"] = _now()
    with open(OUT_STATUS, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
        handle.write("\n")


# --------------------------------------------------------------- municípios


def stage_municipalities(status: dict[str, Any]) -> dict[str, Any]:
    from shapely.geometry import shape

    legacy = _read(LEGACY_MUNICIPALITIES)
    if not legacy:
        raise SystemExit("painel de municípios ausente")
    if not os.path.exists(LEGACY_SNAPSHOT):
        _write(legacy, LEGACY_SNAPSHOT)
        print(f"snapshot do painel histórico: {LEGACY_SNAPSHOT}")

    features = boundaries.municipality_features("SP", year=BOUNDARY_YEAR)
    sp_geojson = boundaries.write_geojson(
        features, os.path.join(PROCESSED, "panel_municipalities_sp.geojson")
    )
    rows: list[dict[str, Any]] = []
    for feature in features:
        props = feature["properties"]
        geometry = shape(feature["geometry"])
        centroid = geometry.centroid
        bounds = geometry.bounds
        rows.append(
            {
                "ibge_code": props["ibge_code"],
                "municipality": props["municipality"],
                "state": "SP",
                "region": None,
                "centroid_lat": centroid.y,
                "centroid_lon": centroid.x,
                "area_km2": round(geometry.area * 111.32 ** 2, 2),
                "bbox_min_lon": round(bounds[0], 6),
                "bbox_min_lat": round(bounds[1], 6),
                "bbox_max_lon": round(bounds[2], 6),
                "bbox_max_lat": round(bounds[3], 6),
                "elevation_m": None,
            }
        )
    rows.sort(key=lambda row: row["ibge_code"])
    codes = [row["ibge_code"] for row in rows]
    assert len(codes) == len(set(codes)), "código IBGE duplicado em SP"
    assert all(code.startswith("35") for code in codes), "código fora da UF 35"
    legacy_codes = {row["ibge_code"] for row in legacy}
    assert not (set(codes) & legacy_codes), "SP colide com códigos já existentes"

    _write(rows, SP_MUNICIPALITIES)
    combined = sorted(legacy + rows, key=lambda row: row["ibge_code"])
    _write(combined, V35_MUNICIPALITIES)

    entry = {
        "sp_municipalities": len(rows),
        "legacy_municipalities": len(legacy),
        "combined_municipalities": len(combined),
        "sp_municipalities_sha256": _sha(SP_MUNICIPALITIES),
        "v35_municipalities_sha256": _sha(V35_MUNICIPALITIES),
        "legacy_snapshot_sha256": _sha(LEGACY_SNAPSHOT),
        "boundary_source": "IBGE — malhas municipais (geoftp)",
        "boundary_year": BOUNDARY_YEAR,
        "sp_geojson": sp_geojson,
        "legacy_rows_unchanged": True,
    }
    print(
        f"[municipios] SP: {len(rows)} municípios; painel v3.5: {len(combined)}"
    )
    return entry


# -------------------------------------------------------------------- clima


def _fetch_one(code: str, latitude: float, longitude: float) -> tuple[str, list[dict]]:
    cache_path = os.path.join(CLIMATE_CACHE, f"{code}.json")
    if os.path.exists(cache_path) and os.path.getsize(cache_path) > 1000:
        with open(cache_path, encoding="utf-8") as handle:
            return code, json.load(handle)
    start = f"{START_YEAR}-01-01"
    end = f"{END_YEAR}-12-31"
    series = gridded.fetch_point(latitude, longitude, start, end, source="nasa_power")
    os.makedirs(CLIMATE_CACHE, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(series, handle)
    return code, series


def stage_climate(status: dict[str, Any]) -> dict[str, Any]:
    municipalities = _read(SP_MUNICIPALITIES)
    if not municipalities:
        raise SystemExit("rode --stage municipalities antes")
    collected: dict[str, list[dict]] = {}
    failures: list[dict[str, str]] = []
    started = time.time()
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {
            pool.submit(
                _fetch_one,
                row["ibge_code"],
                float(row["centroid_lat"]),
                float(row["centroid_lon"]),
            ): row["ibge_code"]
            for row in municipalities
        }
        for index, future in enumerate(as_completed(futures), start=1):
            code = futures[future]
            try:
                got, series = future.result()
                collected[got] = series
            except Exception as error:  # noqa: BLE001 - registrar e seguir
                failures.append({"ibge_code": code, "error": str(error)[:200]})
            if index % 50 == 0:
                print(
                    f"[clima] {index}/{len(futures)} ({time.time()-started:.0f}s, "
                    f"{len(failures)} falhas)",
                    flush=True,
                )
    rows: list[dict[str, Any]] = []
    for code in sorted(collected):
        for record in collected[code]:
            merged = {"ibge_code": code}
            merged.update(record)
            rows.append(merged)
    _write(rows, SP_CLIMATE)
    entry = {
        "municipalities_requested": len(municipalities),
        "municipalities_with_climate": len(collected),
        "failures": failures[:20],
        "n_failures": len(failures),
        "n_rows": len(rows),
        "start_year": START_YEAR,
        "end_year": END_YEAR,
        "source": "NASA POWER (comunidade AG), endpoint temporal/daily/point",
        "elapsed_s": round(time.time() - started, 1),
        "sha256": _sha(SP_CLIMATE),
    }
    print(f"[clima] {len(collected)} municípios, {len(rows)} linhas")
    return entry


# ------------------------------------------------------------ produtividade


def stage_productivity(status: dict[str, Any]) -> dict[str, Any]:
    municipalities = _read(SP_MUNICIPALITIES)
    if not municipalities:
        raise SystemExit("rode --stage municipalities antes")
    total = len(municipalities)
    years = list(range(2017, 2026))
    munis = [
        {"ibge_code": row["ibge_code"], "municipality": row["municipality"], "state": "SP"}
        for row in municipalities
    ]
    # a API do SIDRA não aceita 645 localidades em uma URL; lotes de 200
    records: list[dict[str, Any]] = []
    batch_size = 200
    for index in range(0, total, batch_size):
        chunk = munis[index : index + batch_size]
        result = pam_panel.fetch_state_pam("SP", chunk, years)
        records.extend(result["records"])
        print(f"[pam] lote {index//batch_size + 1}: {result['n_records']} registros", flush=True)
    _write(records, SP_PAM)
    yields = [r for r in records if r.get("variable_normalized") == "rendimento_medio_kg_ha"]
    entry = {
        "municipalities": total,
        "years": years,
        "n_records": len(records),
        "n_yield_records": len(yields),
        "sha256": _sha(SP_PAM),
        "source": "IBGE/SIDRA tabela 5457 (PAM), produtos soja 40124 e milho 40122",
    }
    print(f"[pam] {len(records)} registros ({len(yields)} de rendimento)")
    return entry


# --------------------------------------------------------------------- zarc


def stage_zarc(status: dict[str, Any]) -> dict[str, Any]:
    municipalities = _read(SP_MUNICIPALITIES)
    if not municipalities:
        raise SystemExit("rode --stage municipalities antes")
    codes = [row["ibge_code"] for row in municipalities]
    rows = zarc_panel.fetch_panel(codes, progress=print)
    _write(rows, SP_ZARC)
    entry = {
        "municipalities": len(codes),
        "n_rows": len(rows),
        "sha256": _sha(SP_ZARC),
        "source": "MAPA/ZARC — tábua de risco por município, cultura e safra",
    }
    print(f"[zarc] {len(rows)} linhas de janela")
    return entry


# -------------------------------------------------------------------- painel


def stage_panel(status: dict[str, Any]) -> dict[str, Any]:
    municipalities = {row["ibge_code"]: row for row in _read(SP_MUNICIPALITIES)}
    pam_rows = _read(SP_PAM)
    zarc_rows = _read(SP_ZARC)
    climate_rows = _read(SP_CLIMATE)
    if not (municipalities and pam_rows and zarc_rows and climate_rows):
        raise SystemExit("etapas anteriores incompletas")
    series: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in climate_rows:
        series.setdefault((row["ibge_code"], row.get("source", "NASA-POWER")), []).append(row)
    panel_rows = panel.build_panel(
        pam_rows,
        zarc_rows,
        series,
        municipalities,
        soil_profile_key=SOIL_PROFILE,
        et_method=ET_METHOD,
        min_coverage=0.60,
    )
    _write(panel_rows, SP_PANEL)
    usable = [row for row in panel_rows if row.get("status") == "paired_usable"]
    by_crop: dict[str, int] = {}
    for row in usable:
        by_crop[row["crop"]] = by_crop.get(row.get("crop"), 0) + 1
    entry = {
        "n_rows": len(panel_rows),
        "n_paired_usable": len(usable),
        "by_crop_paired_usable": by_crop,
        "soil_profile": SOIL_PROFILE,
        "et_method": ET_METHOD,
        "min_coverage": 0.60,
        "sha256": _sha(SP_PANEL),
    }
    print(f"[painel] {len(panel_rows)} linhas; utilizáveis {len(usable)} {by_crop}")
    return entry


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--stage",
        required=True,
        choices=("municipalities", "climate", "productivity", "zarc", "panel"),
    )
    args = parser.parse_args()
    status = _load_status()
    handlers = {
        "municipalities": stage_municipalities,
        "climate": stage_climate,
        "productivity": stage_productivity,
        "zarc": stage_zarc,
        "panel": stage_panel,
    }
    entry = handlers[args.stage](status)
    status["stages"][args.stage] = entry
    _save_status(status)
    print(json.dumps(entry, ensure_ascii=False, indent=2, default=str)[:2000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
