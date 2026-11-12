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
import numpy as np
from collections import defaultdict
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


def cmd_eligible(args: argparse.Namespace) -> dict[str, Any]:
    """Municipios **elegiveis** para o painel (criterios de D69).

    Os criterios sao fixados **antes** da analise estatistica e nao dependem
    de clima nem de correlacao:

    1. rendimento medio **observado** (PAM) positivo em pelo menos
       ``--min-years`` dos anos da janela;
    2. area colhida positiva em pelo menos um ano;
    3. geometria municipal oficial disponivel;
    4. pelo menos uma estacao do INMET dentro do municipio ou a ate
       ``--max-distance`` km (para a via observacional).

    Cada municipio entra com o registro do motivo; a exclusao tambem e
    registrada.
    """
    pam_records = _read_csv(os.path.join(PROCESSED, "pam_panel.csv"))
    municipalities = _read_csv(os.path.join(PROCESSED, "panel_municipalities.csv"))
    selection = {
        row["ibge_code"]: row
        for row in _read_csv(os.path.join(PROCESSED, "panel_station_selection.csv"))
    }
    years = [str(y) for y in range(args.start_year, args.end_year + 1)]
    products = {"40124": "soja", "40122": "milho"}

    yields: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
    areas: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
    for record in pam_records:
        crop = products.get(str(record.get("crop_code")))
        if not crop:
            continue
        if record.get("observation_status") != "observed":
            continue
        value = record.get("value_normalized")
        if value in (None, ""):
            continue
        try:
            number = float(value)
        except ValueError:
            continue
        key = (str(record.get("geography_code")), crop)
        year = str(record.get("reference_year"))
        if record.get("variable_normalized") == "rendimento_medio_kg_ha" and number > 0:
            yields[key][year] = number
        elif record.get("variable_normalized") == "area_colhida_ha" and number > 0:
            areas[key][year] = number

    rows: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for muni in municipalities:
        code = muni["ibge_code"]
        station = selection.get(code)
        for crop in ("soja", "milho"):
            reasons: list[str] = []
            series = yields.get((code, crop), {})
            if len(series) < args.min_years:
                reasons.append(
                    f"anos com rendimento observado positivo ({len(series)}) < {args.min_years}"
                )
            if not areas.get((code, crop)):
                reasons.append("sem area colhida positiva")
            if not station or station.get("selection_method") == "none":
                reasons.append("sem estacao do INMET dentro do limite")
            if not muni.get("centroid_lat"):
                reasons.append("sem centroide")
            record = {
                "ibge_code": code,
                "municipality": muni["municipality"],
                "state": muni["state"],
                "crop": crop,
                "years_with_yield": len(series),
                "years_total": len(years),
                "area_positive_years": len(areas.get((code, crop), {})),
                "station_code": (station or {}).get("station_code"),
                "station_selection": (station or {}).get("selection_method"),
                "station_distance_km": (station or {}).get("distance_km"),
                "eligible": not reasons,
                "exclusion_reason": "; ".join(reasons),
            }
            if reasons:
                excluded.append(record)
            else:
                rows.append(record)
    path = _write_csv(
        rows, os.path.join(PROCESSED, "panel_eligible_municipalities.csv")
    )
    excluded_path = _write_csv(
        excluded, os.path.join(PROCESSED, "panel_excluded_municipalities.csv")
    )
    by_crop: dict[str, int] = {}
    for row in rows:
        by_crop[str(row["crop"])] = by_crop.get(str(row["crop"]), 0) + 1
    report = _write_json(
        {
            "generated_at": _now(),
            "criteria": {
                "min_years_with_observed_positive_yield": args.min_years,
                "window_years": years,
                "require_positive_harvested_area": True,
                "require_municipality_geometry": True,
                "require_inmet_station": True,
                "note": (
                    "Criterios fixados antes da analise estatistica; nao "
                    "dependem de clima nem de correlacao com o rendimento."
                ),
            },
            "eligible_rows": len(rows),
            "eligible_by_crop": by_crop,
            "distinct_municipalities": len({r["ibge_code"] for r in rows}),
            "excluded_rows": len(excluded),
            "csv": os.path.relpath(path, HERE).replace("\\", "/"),
            "excluded_csv": os.path.relpath(excluded_path, HERE).replace("\\", "/"),
        },
        os.path.join(MANIFESTS, "panel_eligibility.json"),
    )
    return {
        "ok": True,
        "report": report,
        "eligible_rows": len(rows),
        "eligible_by_crop": by_crop,
        "distinct_municipalities": len({r["ibge_code"] for r in rows}),
    }


# -------------------------------------------------------------------climate


def cmd_climate(args: argparse.Namespace) -> dict[str, Any]:
    """Aquisição das séries climáticas diárias por município.

    O conjunto de municípios é o dos **elegíveis** (critérios de D69), para
    não requerer dados climáticos de municípios que não entram no painel.
    """
    from concurrent.futures import ThreadPoolExecutor

    municipalities = _read_csv(os.path.join(PROCESSED, "panel_municipalities.csv"))
    if not municipalities:
        return {"ok": False, "error": "rode 'municipalities' antes"}
    eligible_path = os.path.join(PROCESSED, "panel_eligible_municipalities.csv")
    if os.path.exists(eligible_path):
        eligible = {r["ibge_code"] for r in _read_csv(eligible_path)}
        municipalities = [m for m in municipalities if m["ibge_code"] in eligible]
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

    # --- reanálises (uma requisição por município e por fonte) ------------
    # O paralelismo é **por fonte**: o NASA POWER e o Open-Meteo têm limites
    # de requisições (HTTP 429 sob carga alta) e não toleram a mesma carga.
    source_workers = {
        "nasa_power": max(1, args.workers // 2),
        "era5_land": max(1, args.workers // 2),
        "era5": max(1, args.workers // 2),
    }
    climate_csv = os.path.join(PROCESSED, "climate_daily.csv")
    existing = _read_csv(climate_csv)
    for source in args.sources:
        if source == "inmet":
            continue
        done_codes = {
            str(r.get("ibge_code"))
            for r in existing
            if str(r.get("source")) == source
        }
        pending = [m for m in municipalities if m["ibge_code"] not in done_codes]
        if not pending:
            print(f"[clima] {source}: ja concluido")
            continue
        collected: list[dict[str, Any]] = []
        attempt = 0
        while pending and attempt < 4:
            attempt += 1

            def fetch_gridded(muni):
                try:
                    records = gridded.fetch_point(
                        float(muni["centroid_lat"]),
                        float(muni["centroid_lon"]),
                        f"{years[0]}-01-01",
                        f"{years[-1]}-12-31",
                        source=source,
                    )
                except Exception as exc:  # noqa: BLE001
                    return muni, [], str(exc)
                return muni, records, None

            failed: list[tuple[dict[str, Any], str]] = []
            done = 0
            workers = source_workers.get(source, args.workers)
            with ThreadPoolExecutor(max_workers=workers) as pool:
                for muni, records, error in pool.map(fetch_gridded, pending):
                    done += 1
                    if error:
                        failed.append((muni, error))
                        continue
                    for record in records:
                        record["ibge_code"] = muni["ibge_code"]
                    collected.extend(records)
                    if done % 200 == 0:
                        print(f"[clima] {source}: {done}/{len(pending)}")
                        _write_csv(existing + collected, climate_csv)
            print(
                f"[clima] {source}: {done} municipios na tentativa {attempt} "
                f"({len(failed)} falhas)"
            )
            # persiste o progresso a cada fonte/tentativa
            existing = existing + collected
            _write_csv(existing, climate_csv)
            collected = []
            pending = [muni for muni, _err in failed]
            if pending:
                print(f"[clima] {source}: repetindo {len(pending)} municipios")
        manifest["sources"][source] = {
            "n_failed": len(pending),
        }
    out_rows = existing

    # --- estação do INMET -------------------------------------------------
    # O INMET é a base de **observação** e de **verificação independente**.
    # A aquisição completa (1.622 municípios x 10 anos) é longa; por isso o
    # escopo é configurável e o progresso é persistido a cada lote, para
    # que uma interrupção não perca o trabalho feito.
    if "inmet" in args.sources:
        inmet_rows: list[dict[str, Any]] = []
        failures = 0
        targets = []
        for muni in municipalities:
            row = selection.get(muni["ibge_code"])
            if not row or not row.get("station_code"):
                continue
            if args.inmet_scope == "inside" and row.get("selection_method") != "inside_municipality":
                continue
            targets.append((muni, row))
        if args.inmet_limit:
            targets = targets[: args.inmet_limit]
        print(f"[clima] INMET: {len(targets)} municipios (escopo={args.inmet_scope})")

        def fetch_inmet(item):
            muni, row = item
            code = row["station_code"]
            records_out: list[dict[str, Any]] = []
            failed = 0
            for year in years:
                try:
                    station_file = inmet.fetch_station_year(year, code)
                    if station_file is None:
                        continue
                    for record in inmet.to_daily_records(station_file):
                        record["ibge_code"] = muni["ibge_code"]
                        record["station_code"] = code
                        record["station_name"] = row.get("station_name")
                        record["distance_km"] = row.get("distance_km")
                        record["selection_method"] = row.get("selection_method")
                        records_out.append(record)
                except Exception as exc:  # noqa: BLE001
                    failed += 1
                    print(
                        f"[clima] INMET {muni['municipality']} ({code}) {year}: {exc}"
                    )
            return records_out, failed

        from concurrent.futures import ThreadPoolExecutor

        done = 0
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            for records_out, failed in pool.map(fetch_inmet, targets):
                inmet_rows.extend(records_out)
                failures += failed
                done += 1
                if done % 25 == 0:
                    print(f"[clima] INMET: {done}/{len(targets)} municipios")
                    # persiste o progresso: uma interrupção não perde o feito
                    _write_csv(existing + inmet_rows, climate_csv)
        out_rows.extend(inmet_rows)
        manifest["sources"]["inmet"] = {
            "n_records": len(inmet_rows),
            "n_failures": failures,
            "n_municipalities": len(targets),
            "scope": args.inmet_scope,
        }

    path = _write_csv(out_rows, os.path.join(PROCESSED, "climate_daily.csv"))
    manifest["sources"]["total"] = {"n_records": len(out_rows)}
    manifest["csv"] = os.path.relpath(path, HERE).replace("\\", "/")
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
        source = str(row.get("source") or "").strip().lower()
        key = (str(row.get("ibge_code")), source)
        grouped.setdefault(key, []).append(row)
    by_code: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for (code, source), series in grouped.items():
        by_code.setdefault(code, {})[source] = series

    comparisons: list[dict[str, Any]] = []
    for code, sources in sorted(by_code.items()):
        station = {
            str(r["date"]): r for r in sources.get("inmet", []) if r.get("date")
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


def cmd_analyse(args: argparse.Namespace) -> dict[str, Any]:
    """Análise exploratória do painel (baselines, validação temporal e territorial)."""
    from agroclimate import analysis

    dataset = _read_csv(
        os.path.join(PROCESSED, "agroclimatic_productivity_panel.csv")
    )
    if not dataset:
        return {"ok": False, "error": "painel ausente; rode 'panel' antes"}
    # A análise principal usa **uma** fonte climática por linha. A base
    # reanalisada cobre todos os municípios; a via de observação (INMET) é um
    # subconjunto usado como verificação independente (D75).
    if args.climate_source:
        before = len(dataset)
        dataset = [
            row for row in dataset
            if str(row.get("climate_source") or "").strip().lower()
            == args.climate_source.strip().lower()
        ]
        print(
            f"[analyse] fonte '{args.climate_source}': "
            f"{len(dataset)} de {before} linhas"
        )
    rows = analysis.prepare_rows(dataset)
    by_crop: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_crop[str(row["crop"])].append(row)

    results: dict[str, Any] = {"generated_at": _now(), "crops": {}}
    p_values: dict[str, float] = {}
    for crop, crop_rows in sorted(by_crop.items()):
        item: dict[str, Any] = {"n_observations": len(crop_rows)}
        item["n_municipalities"] = len({r["ibge_code"] for r in crop_rows})
        item["n_years"] = len({r["year"] for r in crop_rows})
        # ---_descritiva por variável ------------------------------------------------
        descriptive: dict[str, Any] = {}
        for variable in (
            "precip_acumulada_mm",
            "temp_media_c",
            "degree_days_total",
            "deficiency_total_mm",
            "excess_total_mm",
            "et0_total_mm",
        ):
            values = [
                float(r[variable]) for r in crop_rows if r.get(variable) is not None
            ]
            if not values:
                continue
            descriptive[variable] = {
                "n": len(values),
                "mean": float(np.mean(values)),
                "sd": float(np.std(values, ddof=1)) if len(values) > 1 else None,
                "min": float(np.min(values)),
                "max": float(np.max(values)),
            }
        item["descriptive"] = descriptive

        # ---_correlações marginais --------------------------------------------------
        correlations: dict[str, Any] = {}
        for variable in (
            "precip_acumulada_mm",
            "temp_media_c",
            "degree_days_total",
            "deficiency_total_mm",
            "excess_total_mm",
            "et0_total_mm",
        ):
            pairs = [
                (float(r[variable]), float(r["yield_kg_ha"]))
                for r in crop_rows
                if r.get(variable) is not None
            ]
            if len(pairs) < 4:
                continue
            xs = [p[0] for p in pairs]
            ys = [p[1] for p in pairs]
            correlations[variable] = {
                "n": len(pairs),
                "pearson_r": analysis.pearson(xs, ys),
                "spearman_rho": analysis.spearman(xs, ys),
                "permutation_p": analysis.permutation_p(
                    xs, ys, permutations=args.permutations
                ),
            }
            if correlations[variable]["permutation_p"] is not None:
                p_values[f"{crop}|{variable}"] = correlations[variable]["permutation_p"]
        item["correlations"] = correlations

        # ---_modelos pré-declarados --------------------------------------------------
        models: dict[str, Any] = {}
        for name, variables in analysis.MODELS.items():
            if not variables:
                continue
            wf = analysis.walk_forward(
                crop_rows, variables=variables, min_train=args.min_train,
                crop_filter=crop,
            )
            th = analysis.territorial_holdout(
                crop_rows, variables=variables, n_folds=args.folds, crop_filter=crop
            )
            models[name] = {
                "variables": list(variables),
                "walk_forward": {
                    "status": wf.get("status"),
                    "n_predictions": wf.get("n_predictions"),
                    "models": wf.get("models"),
                    "best_by_mae": wf.get("best_by_mae"),
                },
                "territorial_holdout": {
                    "status": th.get("status"),
                    "n_predictions": th.get("n_predictions"),
                    "models": th.get("models"),
                    "best_by_mae": th.get("best_by_mae"),
                },
            }
        item["models"] = models

        # ---_painel com efeitos fixos ------------------------------------------------
        fixed: dict[str, Any] = {}
        for variable in (
            "precip_acumulada_mm",
            "degree_days_total",
            "deficiency_total_mm",
            "temp_media_c",
        ):
            fixed[variable] = analysis.fixed_effects(crop_rows, variable, crop_filter=crop)
        item["fixed_effects"] = fixed
        results["crops"][crop] = item

    corrected = analysis.holm_correction(p_values)
    results["holm"] = corrected
    results["protocol"] = {
        "models": {k: list(v) for k, v in analysis.MODELS.items()},
        "min_train": args.min_train,
        "folds": args.folds,
        "permutations": args.permutations,
        "note": (
            "Modelos e validações fixados antes da análise; nenhum algoritmo "
            "complexo; erros-padrão agrupados por município no painel de "
            "efeitos fixos."
        ),
    }
    path = _write_json(
        results,
        os.path.join(MANIFESTS, f"agroclimatic_analysis{args.out_suffix}.json"),
    )
    summary_path = _write_csv(
        _analysis_summary_rows(results),
        os.path.join(MANIFESTS, f"agroclimatic_analysis{args.out_suffix}.csv"),
    )
    return {
        "ok": True,
        "report": path,
        "summary_csv": os.path.relpath(summary_path, HERE).replace("\\", "/"),
        "crops": {
            crop: {
                "n_observations": item["n_observations"],
                "n_municipalities": item["n_municipalities"],
                "n_years": item["n_years"],
            }
            for crop, item in results["crops"].items()
        },
    }


def _analysis_summary_rows(results: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for crop, item in results.get("crops", {}).items():
        for variable, stats in (item.get("correlations") or {}).items():
            rows.append(
                {
                    "crop": crop,
                    "kind": "correlacao",
                    "variable": variable,
                    "n": stats.get("n"),
                    "pearson_r": stats.get("pearson_r"),
                    "spearman_rho": stats.get("spearman_rho"),
                    "permutation_p": stats.get("permutation_p"),
                    "holm_p": results.get("holm", {}).get(f"{crop}|{variable}"),
                }
            )
        for name, model in (item.get("models") or {}).items():
            for experiment in ("walk_forward", "territorial_holdout"):
                block = model.get(experiment) or {}
                for metric, values in (block.get("models") or {}).items():
                    rows.append(
                        {
                            "crop": crop,
                            "kind": f"{experiment}:{name}",
                            "variable": metric,
                            "n": values.get("n_predictions"),
                            "mae_kg_ha": values.get("mae_kg_ha"),
                            "rmse_kg_ha": values.get("rmse_kg_ha"),
                        }
                    )
        for variable, block in (item.get("fixed_effects") or {}).items():
            rows.append(
                {
                    "crop": crop,
                    "kind": "efeitos_fixos",
                    "variable": variable,
                    "n": block.get("n"),
                    "coefficient": block.get("coefficient"),
                    "std_error_clustered": block.get("std_error_clustered"),
                    "t_statistic": block.get("t_statistic"),
                }
            )
    return rows


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

    p = sub.add_parser("eligible", help="municípios elegíveis do painel (D69)")
    p.add_argument("--min-years", type=int, default=7)
    p.add_argument("--start-year", type=int, default=2017)
    p.add_argument("--end-year", type=int, default=2025)
    p.set_defaults(func=cmd_eligible)

    p = sub.add_parser("climate", help="aquisição das séries climáticas")
    p.add_argument("--sources", nargs="+", default=["nasa_power", "era5_land", "era5"])
    p.add_argument("--start-year", type=int, default=2016)
    p.add_argument("--end-year", type=int, default=2025)
    p.add_argument("--workers", type=int, default=6)
    p.add_argument(
        "--inmet-scope",
        choices=("all", "inside"),
        default="inside",
        help="'inside': apenas municípios com estação dentro do município",
    )
    p.add_argument("--inmet-limit", type=int, default=0, help="0 = sem limite")
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

    p = sub.add_parser("analyse", help="análise exploratória do painel")
    p.add_argument("--min-train", type=int, default=5)
    p.add_argument("--folds", type=int, default=5)
    p.add_argument("--permutations", type=int, default=5000)
    p.add_argument(
        "--climate-source",
        default="NASA-POWER",
        help="fonte climática da análise principal (vazio = todas)",
    )
    p.add_argument("--out-suffix", default="", help="sufixo do nome do manifesto")
    p.set_defaults(func=cmd_analyse)

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
