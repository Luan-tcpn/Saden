"""CLI da V2.6 — base agroclimática e painel multi-municipal.

Comandos
--------

``stations``
    Inventário de estações do INMET e seleção por município.
``municipalities``
    Lista de municípios (IBGE) com centroide e geometria.
``climate``
    Aquisição das séries diárias (INMET e/ou reanálises) por município.
``quality``
    Auditoria de qualidade das séries diárias.
``pam``
    Aquisição da PAM (SIDRA 5457) por UF.
``zarc``
    ZARC (MAPA) por município, em streaming.
``panel``
    Montagem do painel agroclimático × produtividade.
``validate``
    Comparação entre fontes (INMET × reanálise).
``analyse``
    Análise exploratória do painel (baselines e validação temporal).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

DATA = os.path.join(HERE, "data")
PROCESSED = os.path.join(DATA, "processed")
MANIFESTS = os.path.join(DATA, "manifests")
RAW = os.path.join(DATA, "raw")

from agroclimate import gridded, inmet, panel, quality, stations  # noqa: E402
from agri import pam_panel, zarc_panel  # noqa: E402

PANEL_YEARS = list(range(2017, 2026))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(payload: Any, path: str) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return path


def _read_csv(path: str) -> list[dict[str, Any]]:
    if not os.path.exists(path):
        return []
    import csv

    with open(path, newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _write_csv(rows, path: str) -> str:
    import csv

    rows = list(rows)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with open(path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


# --------------------------------------------------------------- municípios


def _municipality_geometry(code: str, retries: int = 3) -> Any:
    """Geometria municipal (EPSG:4326) via API do IBGE."""
    import gzip
    import json
    import time
    import urllib.request

    url = (
        "https://servicodados.ibge.gov.br/api/v1/malhas/municipios/"
        f"{code}?formato=application/vnd.geo+json&qualidade=minima"
    )
    last: Exception | None = None
    for attempt in range(retries):
        request = urllib.request.Request(
            url, headers={"User-Agent": "SADEN-V2.6/0.1 (investigacao academica)"}
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                raw = response.read()
            if raw[:2] == b"\x1f\x8b":
                raw = gzip.decompress(raw)
            payload = json.loads(raw.decode("utf-8"))
            from shapely.geometry import shape

            return shape(payload)
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(1.5 * (attempt + 1))
    print(f"[municipios] {code}: geometria indisponivel ({last})")
    return None


def cmd_municipalities(args: argparse.Namespace) -> dict[str, Any]:
    """Municípios das UFs candidatas, com centroide e geometria.

    As malhas vêm do shapefile oficial do IBGE (servidor ``geoftp``), baixado
    uma vez por UF; a API de malhas do IBGE responde com *timeout* neste
    ambiente.
    """
    from shapely.geometry import shape

    from agroclimate import boundaries

    features: list[dict[str, Any]] = []
    for state in args.states:
        features.extend(
            boundaries.municipality_features(state, year=args.boundary_year)
        )
        print(f"[municipios] {state}: malhas carregadas")
    geojson_path = boundaries.write_geojson(
        features, os.path.join(PROCESSED, "panel_municipalities.geojson")
    )

    out: list[dict[str, Any]] = []
    for feature in features:
        props = feature["properties"]
        geometry = shape(feature["geometry"])
        centroid = geometry.centroid
        bounds = geometry.bounds
        out.append(
            {
                "ibge_code": props["ibge_code"],
                "municipality": props["municipality"],
                "state": props["state"],
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
    out.sort(key=lambda r: r["ibge_code"])
    path = _write_csv(out, os.path.join(PROCESSED, "panel_municipalities.csv"))
    return {
        "ok": True,
        "csv": os.path.relpath(path, HERE).replace("\\", "/"),
        "geojson": os.path.relpath(geojson_path, HERE).replace("\\", "/"),
        "municipalities": len(out),
        "states": args.states,
        "boundary_year": args.boundary_year,
    }


# ------------------------------------------------------------------stations


def cmd_stations(args: argparse.Namespace) -> dict[str, Any]:
    """Inventário de estações do INMET e seleção por município."""
    catalog = stations.fetch_station_catalog()
    rows = [station.to_dict() for station in catalog]
    catalog_path = _write_csv(
        rows, os.path.join(PROCESSED, "inmet_station_catalog.csv")
    )
    municipalities = _read_csv(os.path.join(PROCESSED, "panel_municipalities.csv"))
    selected: list[dict[str, Any]] = []
    geojson_path = os.path.join(PROCESSED, "panel_municipalities.geojson")
    if municipalities and os.path.exists(geojson_path):
        from shapely.geometry import shape

        with open(geojson_path, encoding="utf-8") as handle:
            features = json.load(handle).get("features", [])
        geometries = {
            str(f["properties"]["ibge_code"]): shape(f["geometry"])
            for f in features
        }
        prepared = []
        for muni in municipalities:
            item = dict(muni)
            item["geometry"] = geometries.get(str(muni["ibge_code"]))
            prepared.append(item)
        selected = stations.select_stations_for_municipalities(catalog, prepared)
    selected_path = _write_csv(
        selected, os.path.join(PROCESSED, "panel_station_selection.csv")
    )
    manifest = {
        "generated_at": _now(),
        "source": stations.STATIONS_URL,
        "n_stations": len(catalog),
        "n_operational": sum(1 for s in catalog if s.is_operating),
        "by_state": {
            state: sum(1 for s in catalog if s.state == state)
            for state in sorted({s.state for s in catalog})
        },
        "catalog_csv": os.path.relpath(catalog_path, HERE).replace("\\", "/"),
        "selection_csv": os.path.relpath(selected_path, HERE).replace("\\", "/"),
        "selection_rules": {
            "priority": [
                "inside_municipality",
                "nearest_within_threshold",
                "none",
            ],
            "max_distance_km": stations.MAX_STATION_DISTANCE_KM,
            "far_distance_km": stations.FAR_STATION_DISTANCE_KM,
        },
    }
    path = _write_json(manifest, os.path.join(MANIFESTS, "inmet_stations.json"))
    return {
        "ok": True,
        "report": path,
        "n_stations": len(catalog),
        "n_selected": len(selected),
    }


# -------------------------------------------------------------------climate


def cmd_climate(args: argparse.Namespace) -> dict[str, Any]:
    """Aquisição das séries climáticas diárias por município."""
    municipalities = _read_csv(os.path.join(PROCESSED, "panel_municipalities.csv"))
    if not municipalities:
        return {"ok": False, "error": "rode 'municipalities' antes"}
    selection = {
        row["ibge_code"]: row
        for row in _read_csv(os.path.join(PROCESSED, "panel_station_selection.csv"))
    }
    years = list(range(args.start_year, args.end_year + 1))
    out_rows: list[dict[str, Any]] = []
    manifest: dict[str, Any] = {
        "generated_at": _now(),
        "sources": {},
        "municipalities": len(municipalities),
        "years": years,
    }
    for source in args.sources:
        name = "inmet" if source == "inmet" else source
        if source == "inmet":
            if not selection:
                print("[clima] sem selecao de estacoes: pulando INMET")
                continue
            for muni in municipalities:
                row = selection.get(muni["ibge_code"])
                if not row or not row.get("station_code"):
                    continue
                code = row["station_code"]
                for year in years:
                    station_file = inmet.fetch_station_year(year, code)
                    if station_file is None:
                        continue
                    for record in inmet.to_daily_records(station_file):
                        record["ibge_code"] = muni["ibge_code"]
                        record["station_code"] = code
                        record["station_name"] = row.get("station_name")
                        record["distance_km"] = row.get("distance_km")
                        record["selection_method"] = row.get("selection_method")
                        out_rows.append(record)
                print(f"[clima] INMET {muni['municipality']} ({code})")
        else:
            for muni in municipalities:
                if muni.get("centroid_lat") is None:
                    continue
                try:
                    records = gridded.fetch_point(
                        float(muni["centroid_lat"]),
                        float(muni["centroid_lon"]),
                        f"{years[0]}-01-01",
                        f"{years[-1]}-12-31",
                        source=source,
                    )
                except Exception as exc:  # noqa: BLE001
                    print(f"[clima] {source} {muni['municipality']}: {exc}")
                    continue
                for record in records:
                    record["ibge_code"] = muni["ibge_code"]
                    out_rows.append(record)
                print(f"[clima] {source} {muni['municipality']}: {len(records)} dias")
    path = _write_csv(out_rows, os.path.join(PROCESSED, "climate_daily.csv"))
    manifest["sources"] = {
        "n_records": len(out_rows),
        "csv": os.path.relpath(path, HERE).replace("\\", "/"),
    }
    report = _write_json(manifest, os.path.join(MANIFESTS, "climate_daily.json"))
    return {"ok": True, "report": report, "n_records": len(out_rows)}


# -------------------------------------------------------------------quality


def cmd_quality(args: argparse.Namespace) -> dict[str, Any]:
    """Auditoria de qualidade das séries diárias."""
    rows = _read_csv(os.path.join(PROCESSED, "climate_daily.csv"))
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        key = (str(row.get("ibge_code")), str(row.get("source")))
        grouped.setdefault(key, []).append(row)
    reports: list[dict[str, Any]] = []
    cleaned: list[dict[str, Any]] = []
    for (code, source), series in sorted(grouped.items()):
        audit = quality.audit_series(series)
        for record in audit["records"]:
            record["ibge_code"] = code
            cleaned.append(record)
        reports.append(
            {
                "ibge_code": code,
                "source": source,
                "n_records": audit["n_records"],
                "n_unique_days": audit["n_unique_days"],
                "duplicate_dates": audit["duplicate_dates"],
                "invalid_counts": audit["invalid_counts"],
                "missing_counts": audit["missing_counts"],
                "coverage": audit["coverage"],
                "n_discontinuities": audit["n_discontinuities"],
                "discontinuities": audit["discontinuities"][:20],
            }
        )
    path = _write_csv(cleaned, os.path.join(PROCESSED, "climate_daily_audited.csv"))
    report_path = _write_json(
        {
            "generated_at": _now(),
            "n_series": len(reports),
            "rules": {
                "physical_ranges": quality.PHYSICAL_RANGES,
                "discontinuity_gap_days": quality.DISCONTINUITY_GAP_DAYS,
                "min_coverage": quality.MIN_COVERAGE,
                "note": (
                    "Ausencias nunca viram zero; valores fora da faixa fisica "
                    "sao marcados e preservados em raw_<variavel>."
                ),
            },
            "series": reports,
            "csv": os.path.relpath(path, HERE).replace("\\", "/"),
        },
        os.path.join(MANIFESTS, "climate_quality.json"),
    )
    return {"ok": True, "report": report_path, "n_series": len(reports)}


# -----------------------------------------------------------------------pam


def cmd_pam(args: argparse.Namespace) -> dict[str, Any]:
    """Aquisição da PAM (SIDRA 5457) por UF."""
    records: list[dict[str, Any]] = []
    manifest: dict[str, Any] = {"generated_at": _now(), "states": {}}
    for state in args.states:
        municipalities = pam_panel.fetch_state_municipalities(state)
        result = pam_panel.fetch_state_pam(
            state, municipalities, list(range(args.start_year, args.end_year + 1))
        )
        records.extend(result["records"])
        manifest["states"][state] = {
            "n_municipalities": len(municipalities),
            "n_records": result["n_records"],
            "url": result["url"],
        }
        print(f"[pam] {state}: {result['n_records']} registros")
    path = _write_csv(records, os.path.join(PROCESSED, "pam_panel.csv"))
    manifest["n_records"] = len(records)
    manifest["csv"] = os.path.relpath(path, HERE).replace("\\", "/")
    report = _write_json(manifest, os.path.join(MANIFESTS, "pam_panel.json"))
    return {"ok": True, "report": report, "n_records": len(records)}


# ----------------------------------------------------------------------zarc


def cmd_zarc(args: argparse.Namespace) -> dict[str, Any]:
    """ZARC (MAPA) por município."""
    municipalities = _read_csv(os.path.join(PROCESSED, "panel_municipalities.csv"))
    codes = [m["ibge_code"] for m in municipalities]
    rows = zarc_panel.fetch_panel(codes, progress=print)
    path = _write_csv(rows, os.path.join(PROCESSED, "zarc_panel.csv"))
    report = _write_json(
        {
            "generated_at": _now(),
            "source": zarc_panel.CKAN_PACKAGE,
            "n_municipalities": len(codes),
            "n_records": len(rows),
            "safras": sorted({str(r.get("safra")) for r in rows}),
            "csv": os.path.relpath(path, HERE).replace("\\", "/"),
        },
        os.path.join(MANIFESTS, "zarc_panel.json"),
    )
    return {"ok": True, "report": report, "n_records": len(rows)}


# ---------------------------------------------------------------------panel


def cmd_panel(args: argparse.Namespace) -> dict[str, Any]:
    """Montagem do painel agroclimático × produtividade."""
    municipalities = {
        row["ibge_code"]: row
        for row in _read_csv(os.path.join(PROCESSED, "panel_municipalities.csv"))
    }
    pam_records = _read_csv(os.path.join(PROCESSED, "pam_panel.csv"))
    zarc_rows = _read_csv(os.path.join(PROCESSED, "zarc_panel.csv"))
    climate_rows = _read_csv(os.path.join(PROCESSED, "climate_daily_audited.csv"))
    if not climate_rows:
        climate_rows = _read_csv(os.path.join(PROCESSED, "climate_daily.csv"))
    series: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in climate_rows:
        key = (str(row.get("ibge_code")), str(row.get("source")))
        series.setdefault(key, []).append(row)
    rows = panel.build_panel(
        pam_records,
        zarc_rows,
        series,
        municipalities,
        soil_profile_key=args.soil_profile,
        et_method=args.et_method,
        min_coverage=args.min_coverage,
    )
    path = _write_csv(
        rows, os.path.join(PROCESSED, "agroclimatic_productivity_panel.csv")
    )
    usable = [r for r in rows if r.get("status") == "paired_usable"]
    by_crop: dict[str, int] = {}
    for row in usable:
        by_crop[str(row.get("crop"))] = by_crop.get(str(row.get("crop")), 0) + 1
    report = _write_json(
        {
            "generated_at": _now(),
            "rows": len(rows),
            "paired_usable": len(usable),
            "usable_by_crop": by_crop,
            "soil_profile": args.soil_profile,
            "et_method": args.et_method,
            "min_coverage": args.min_coverage,
            "csv": os.path.relpath(path, HERE).replace("\\", "/"),
        },
        os.path.join(MANIFESTS, "agroclimatic_panel.json"),
    )
    return {
        "ok": True,
        "report": report,
        "rows": len(rows),
        "paired_usable": len(usable),
        "usable_by_crop": by_crop,
    }


# ------------------------------------------------------------------validate


def cmd_validate(args: argparse.Namespace) -> dict[str, Any]:
    """Comparação entre a observação de estação e as reanálises."""
    import numpy as np

    rows = _read_csv(os.path.join(PROCESSED, "climate_daily_audited.csv"))
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        key = (str(row.get("ibge_code")), str(row.get("source")))
        grouped.setdefault(key, []).append(row)
    by_code: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for (code, source), series in grouped.items():
        by_code.setdefault(code, {})[source] = series

    comparisons: list[dict[str, Any]] = []
    for code, sources in sorted(by_code.items()):
        if "inmet" not in sources:
            continue
        station = {
            str(r["date"]): r for r in sources["inmet"] if r.get("date")
        }
        for source, series in sorted(sources.items()):
            if source == "inmet":
                continue
            pairs_t: list[tuple[float, float]] = []
            pairs_p: list[tuple[float, float]] = []
            for record in series:
                day = str(record.get("date"))
                reference = station.get(day)
                if reference is None:
                    continue
                a = reference.get("temp_media_c")
                b = record.get("temp_media_c")
                if a not in (None, "") and b not in (None, ""):
                    pairs_t.append((float(a), float(b)))
                a = reference.get("precip_mm")
                b = record.get("precip_mm")
                if a not in (None, "") and b not in (None, ""):
                    pairs_p.append((float(a), float(b)))
            if not pairs_t and not pairs_p:
                continue
            item: dict[str, Any] = {
                "ibge_code": code,
                "gridded_source": source,
                "n_temperature_pairs": len(pairs_t),
                "n_precip_pairs": len(pairs_p),
            }
            if pairs_t:
                x = np.array([p[0] for p in pairs_t])
                y = np.array([p[1] for p in pairs_t])
                item.update(
                    {
                        "temp_bias": float(y.mean() - x.mean()),
                        "temp_mae": float(np.mean(np.abs(y - x))),
                        "temp_rmse": float(np.sqrt(np.mean((y - x) ** 2))),
                        "temp_correlation": (
                            float(np.corrcoef(x, y)[0, 1]) if len(x) > 2 else None
                        ),
                    }
                )
            if pairs_p:
                x = np.array([p[0] for p in pairs_p])
                y = np.array([p[1] for p in pairs_p])
                item.update(
                    {
                        "precip_bias": float(y.mean() - x.mean()),
                        "precip_mae": float(np.mean(np.abs(y - x))),
                        "precip_rmse": float(np.sqrt(np.mean((y - x) ** 2))),
                        "precip_correlation": (
                            float(np.corrcoef(x, y)[0, 1]) if len(x) > 2 else None
                        ),
                        "precip_total_station": float(x.sum()),
                        "precip_total_gridded": float(y.sum()),
                    }
                )
            comparisons.append(item)
    report = _write_json(
        {
            "generated_at": _now(),
            "n_comparisons": len(comparisons),
            "note": (
                "Comparacao entre uma estacao pontual e uma celula de "
                "reanálise (~9 km a 0,25°): equivalencia NAO e esperada; "
                "as diferencas sao de escala, nao de erro."
            ),
            "comparisons": comparisons,
        },
        os.path.join(MANIFESTS, "climate_source_comparison.json"),
    )
    return {"ok": True, "report": report, "n_comparisons": len(comparisons)}


# ------------------------------------------------------------------main


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SADEN V2.6 — base agroclimática")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("municipalities", help="municípios do painel (IBGE)")
    p.add_argument("--states", nargs="+", default=["MT"])
    p.add_argument("--boundary-year", type=int, default=2025)
    p.set_defaults(func=cmd_municipalities)

    p = sub.add_parser("stations", help="inventário de estações do INMET")
    p.set_defaults(func=cmd_stations)

    p = sub.add_parser("climate", help="aquisição das séries climáticas")
    p.add_argument("--sources", nargs="+", default=["era5_land", "era5"])
    p.add_argument("--start-year", type=int, default=2016)
    p.add_argument("--end-year", type=int, default=2025)
    p.set_defaults(func=cmd_climate)

    p = sub.add_parser("quality", help="auditoria de qualidade")
    p.set_defaults(func=cmd_quality)

    p = sub.add_parser("pam", help="PAM (SIDRA 5457) por UF")
    p.add_argument("--states", nargs="+", default=["MT"])
    p.add_argument("--start-year", type=int, default=2017)
    p.add_argument("--end-year", type=int, default=2025)
    p.set_defaults(func=cmd_pam)

    p = sub.add_parser("zarc", help="ZARC (MAPA) por município")
    p.set_defaults(func=cmd_zarc)

    p = sub.add_parser("panel", help="painel agroclimático × produtividade")
    p.add_argument("--soil-profile", default="tipo2_medio")
    p.add_argument("--et-method", default="fao56_penman_monteith")
    p.add_argument("--min-coverage", type=float, default=0.60)
    p.set_defaults(func=cmd_panel)

    p = sub.add_parser("validate", help="comparação entre fontes climáticas")
    p.set_defaults(func=cmd_validate)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = args.func(args)
    except Exception as exc:  # noqa: BLE001
        import traceback

        traceback.print_exc()
        print(json.dumps({"ok": False, "error": type(exc).__name__, "message": str(exc)},
                         ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
