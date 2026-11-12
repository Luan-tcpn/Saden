#!/usr/bin/env python
"""CLI da V2.4 — escala espacial, calendário ZARC e referência municipal.

    geospatial\\.venv\\Scripts\\python.exe geospatial\\run_scale.py zarc
    geospatial\\.venv\\Scripts\\python.exe geospatial\\run_scale.py mapbiomas
    geospatial\\.venv\\Scripts\\python.exe geospatial\\run_scale.py municipal
    geospatial\\.venv\\Scripts\\python.exe geospatial\\run_scale.py reference

Os subcomandos usam rede. A suíte offline (`geospatial/tests`) é independente.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agri import config as agri_config  # noqa: E402
from agri import zarc as zarc_mod  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
MANIFEST_DIR = os.path.join(DATA_DIR, "manifests")
ARTIFACTS_DIR = os.path.join(HERE, "artifacts", "scale")

MUNICIPALITY = agri_config.MUNICIPALITY["ibge_code"]
BBOX_MUNICIPAL = [-56.1167, -13.6661, -55.0851, -11.7216]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(data: Any, path: str) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, default=str)
    return path


def _sha256(path: str) -> str:
    import hashlib

    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ------------------------------------------------------------------- ZARC


def cmd_zarc(args: argparse.Namespace) -> dict[str, Any]:
    """Adquire e normaliza o calendário ZARC (janelas oficiais de plantio)."""
    metadata = zarc_mod.package_metadata()
    acquisitions: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for safra in args.safras:
        resource = zarc_mod.resource_for_safra(metadata, safra)
        if resource is None:
            failures.append({"safra": safra, "error": "recurso CSV não localizado no catálogo"})
            continue
        raw_path = os.path.join(RAW_DIR, "zarc", f"tabua_risco_{safra.replace('/', '-')}.csv")
        filtered_path = os.path.join(
            PROCESSED_DIR, "zarc", f"zarc_sorriso_{safra.replace('/', '-')}.csv"
        )
        try:
            acquisition = zarc_mod.download_and_filter(
                resource, raw_path, filtered_path, municipality="Sorriso", uf="MT"
            )
        except Exception as exc:  # noqa: BLE001 - rede
            failures.append({"safra": safra, "error": f"{type(exc).__name__}: {exc}"})
            continue
        acquisition["raw_path_versioned"] = False
        acquisition["filtered_sha256"] = _sha256(filtered_path)
        acquisitions.append(acquisition)
        rows.extend(zarc_mod.normalize_rows(filtered_path, resource, metadata))

    output = os.path.join(PROCESSED_DIR, "zarc_planting_windows.csv")
    zarc_mod.write_normalized(rows, output)

    payload = {
        "generated_at": _now(),
        "institution": "MAPA",
        "dataset": metadata.get("title"),
        "dataset_id": metadata.get("id"),
        "dataset_page": metadata.get("dataset_page"),
        "license": metadata.get("license_title"),
        "metadata_modified": metadata.get("metadata_modified"),
        "municipality": {"ibge_code": MUNICIPALITY, "name": "Sorriso", "uf": "MT"},
        "safras_requested": args.safras,
        "safras_acquired": [a["resource_name"] for a in acquisitions],
        "acquisitions": acquisitions,
        "failures": failures,
        "records": len(rows),
        "records_by_safra": {},
        "records_by_cultura": {},
        "portarias": sorted({r["portaria"] for r in rows if r.get("portaria")}),
        "output_csv": os.path.relpath(output, HERE).replace("\\", "/"),
        "output_sha256": _sha256(output),
        "nature": (
            "Janelas recomendadas de plantio por risco (ZARC). Não são datas "
            "observadas de plantio nem medições de produtividade."
        ),
        "produtividade_field_note": (
            "O campo 'Produtividade' do ZARC é um código de classe de "
            "produtividade (referência técnica), não kg/ha."
        ),
    }
    for row in rows:
        payload["records_by_safra"][row["safra"]] = payload["records_by_safra"].get(row["safra"], 0) + 1
        payload["records_by_cultura"][str(row["cultura"])] = (
            payload["records_by_cultura"].get(str(row["cultura"]), 0) + 1
        )
    path = _write_json(payload, os.path.join(MANIFEST_DIR, "zarc_calendar_manifest.json"))
    return {
        "ok": True,
        "manifest": path,
        "csv": payload["output_csv"],
        "records": payload["records"],
        "safras_acquired": len(payload["safras_acquired"]),
        "failures": failures,
        "by_cultura": payload["records_by_cultura"],
    }


# ------------------------------------------------------------- MapBiomas


def cmd_mapbiomas(args: argparse.Namespace) -> dict[str, Any]:
    """Investiga as rotas oficiais do MapBiomas (GCS e GEE) para a área de estudo."""
    import urllib.error
    import urllib.request

    gcs_base = (
        "https://storage.googleapis.com/mapbiomas-public/initiatives/brasil/lulc_10m/"
        "collection4/coverage/brazil_coverage/brazil_coverage-col4_10m_{year}.tif"
    )
    probes: list[dict[str, Any]] = []
    for year in args.years:
        url = gcs_base.format(year=year)
        request = urllib.request.Request(url, headers={"User-Agent": "SADEN-V2.4/0.1"})
        try:
            request.get_method = lambda: "HEAD"  # type: ignore[method-assign]
            with urllib.request.urlopen(request, timeout=60) as response:
                probes.append(
                    {
                        "year": year,
                        "url": url,
                        "status": response.status,
                        "content_length": response.headers.get("Content-Length"),
                        "content_type": response.headers.get("Content-Type"),
                        "accept_ranges": response.headers.get("Accept-Ranges"),
                    }
                )
        except urllib.error.HTTPError as exc:
            probes.append(
                {
                    "year": year,
                    "url": url,
                    "status": exc.code,
                    "error": exc.reason,
                }
            )
        except Exception as exc:  # noqa: BLE001
            probes.append({"year": year, "url": url, "status": -1, "error": type(exc).__name__})

    gee_asset = "projects/mapbiomas-public/assets/brazil/lulc_10m/collection4/mapbiomas_10m_collection4_coverage_v1"
    payload = {
        "generated_at": _now(),
        "gcs_probes": probes,
        "gee_asset": {
            "id": gee_asset,
            "access": "requer conta Google Earth Engine (não configurada neste ambiente)",
            "status": "bloqueado_por_acesso",
            "procedure": (
                "Acesso manual legítimo: conta GEE institucional, "
                "Image.load('" + gee_asset + "') e exportação por AOI/município."
            ),
        },
        "worldcover_reference": {
            "status": "adquirido na V2.3 (ESA WorldCover 10 m, classes 10..100)",
            "role": "referência complementar preservada",
        },
    }
    path = _write_json(payload, os.path.join(MANIFEST_DIR, "mapbiomas_access_report.json"))
    return {"ok": True, "report": path, "gcs_probes": probes}


def _write_rows_csv(rows: list[dict[str, Any]], path: str) -> str:
    import csv as _csv

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = _csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


# ------------------------------------------------------------- municipal


def cmd_municipal(args: argparse.Namespace) -> dict[str, Any]:
    """NDVI municipal sobre a área agrícola (processamento por blocos)."""
    import numpy as np

    from historical import landuse as lu
    from historical import municipal as muni
    from historical import radiometry as radio
    from historical import series as series_mod
    from s2_poc import config, network, read

    network.configure_tls()
    from pystac_client import Client

    monthly_csv = os.path.join(PROCESSED_DIR, "sentinel2_historical_monthly.csv")
    monthly = series_mod.read_monthly_csv(monthly_csv)
    observed = [r for r in monthly if r.get("status") == "observed"]

    # uma data de referência por ano (mes com menor obstrução) ou um mês fixo
    by_year: dict[str, list[dict[str, Any]]] = {}
    for row in observed:
        by_year.setdefault(str(row["month"])[:4], []).append(row)
    reference: list[dict[str, Any]] = []
    for year in sorted(by_year):
        candidates = by_year[year]
        if args.month:
            fixed = [r for r in candidates if str(r["month"])[5:7] == args.month]
            candidates = fixed or candidates
        else:
            candidates = sorted(
                candidates, key=lambda r: float(r.get("obstruction_fraction") or 1.0)
            )
        reference.append(candidates[0])
    if args.max_dates:
        reference = reference[: args.max_dates]

    grid = muni.municipality_grid()
    blocks = muni.grid_blocks(grid, n_blocks=args.blocks)
    estimate = muni.estimate_operation(grid, n_dates=len(reference))
    _write_json(estimate, os.path.join(MANIFEST_DIR, "municipal_operation_estimate.json"))

    # máscara agrícola (WorldCover) calculada POR BLOCO (memória limitada)
    mask_cache: dict[tuple[int, int, int], np.ndarray] = {}
    mask_reports: list[dict[str, Any]] = []
    for mask_year in args.mask_years:
        agricultural_cells = 0
        for index, block in enumerate(blocks):
            key = (mask_year, block["row_off"], block["col_off"])
            if key not in mask_cache:
                bbox = lu.block_bounds_wgs84(grid, block)
                payload = lu.read_worldcover_block(mask_year, bbox)
                subgrid = lu.block_subgrid(grid, block)
                mask_cache[key] = lu.cropland_grid_mask(payload["data"], payload["meta"], subgrid)
            agricultural_cells += int(np.count_nonzero(mask_cache[key]))
        mask_reports.append(
            {
                "year": mask_year,
                "agricultural_cells_20m": agricultural_cells,
                "fraction": agricultural_cells / (grid["width"] * grid["height"]),
            }
        )
    primary_mask_year = str(args.mask_years[0])

    client = Client.open(config.STAC_URL)
    rows: list[dict[str, Any]] = []
    for entry in reference:
        month = str(entry["month"])
        date = str(entry.get("datetime") or "")[:10]
        item = None
        item_xf = None
        for collection in (radio.COLLECTION_C1, radio.COLLECTION_ORIGINAL):
            found = list(
                client.search(
                    collections=[collection],
                    ids=[str(entry["item_id"])],
                    limit=5,
                ).items()
            )
            if found:
                item = found[0]
                break
        if item is None:
            continue
        # o município de Sorriso atravessa os tiles 21LXG (norte) e 21LXF (sul):
        # a mesma data é buscada no tile complementar para completar a cobertura
        if date:
            for collection in (radio.COLLECTION_C1, radio.COLLECTION_ORIGINAL):
                for candidate in client.search(
                    collections=[collection],
                    bbox=BBOX_MUNICIPAL,
                    datetime=f"{date}T00:00:00Z/{date}T23:59:59Z",
                    limit=20,
                ).items():
                    from historical import pcatalog

                    if pcatalog.tile_code(candidate) == "MGRS-21LXF":
                        item_xf = candidate
                        break
                if item_xf is not None:
                    break
        profile = radio.item_radiometry(
            item,
            radio.COLLECTION_C1
            if str(entry["item_id"]).startswith("S2") and "_T21LXG_" in str(entry["item_id"])
            else radio.COLLECTION_ORIGINAL,
        )
        accumulators = []
        for block in blocks:
            red = muni.read_block(
                series_mod.asset_href_for(item, "red"),
                grid,
                block,
                resampling=read.Resampling.average,
                nodata=np.nan,
                dtype="float32",
            )
            nir = muni.read_block(
                series_mod.asset_href_for(item, "nir"),
                grid,
                block,
                resampling=read.Resampling.average,
                nodata=np.nan,
                dtype="float32",
            )
            scl = muni.read_block(
                series_mod.asset_href_for(item, "scl"),
                grid,
                block,
                resampling=read.Resampling.nearest,
                nodata=0,
                dtype="uint8",
            )
            if item_xf is not None:
                red_xf = muni.read_block(
                    series_mod.asset_href_for(item_xf, "red"),
                    grid,
                    block,
                    resampling=read.Resampling.average,
                    nodata=np.nan,
                    dtype="float32",
                )
                nir_xf = muni.read_block(
                    series_mod.asset_href_for(item_xf, "nir"),
                    grid,
                    block,
                    resampling=read.Resampling.average,
                    nodata=np.nan,
                    dtype="float32",
                )
                scl_xf = muni.read_block(
                    series_mod.asset_href_for(item_xf, "scl"),
                    grid,
                    block,
                    resampling=read.Resampling.nearest,
                    nodata=0,
                    dtype="uint8",
                )
                # mosaico determinístico: primeiro válido vence (21LXG > 21LXF)
                gap = ~np.isfinite(red) | (scl == 0)
                red = np.where(gap, red_xf, red)
                nir = np.where(gap, nir_xf, nir)
                scl = np.where(gap, scl_xf, scl)
            ndvi = muni.ndvi_from_reflectance(
                red, nir, float(profile["scale"]), float(profile["offset"])
            )
            valid = muni.scl_keep(scl) & np.isfinite(ndvi)
            agri = mask_cache.get(
                (int(primary_mask_year), block["row_off"], block["col_off"])
            )
            if agri is None:
                continue
            accumulators.append(muni.accumulate_ndvi(ndvi, valid, agri))
        merged = muni.merge_accumulators(accumulators)
        rows.append(
            {
                "month": month,
                "year": str(month)[:4],
                "item_id": str(entry["item_id"]),
                "catalog": entry.get("catalog"),
                "baseline": entry.get("baseline"),
                "radiometry_profile": profile["profile"],
                "mask_year": primary_mask_year,
                "agricultural_pixels": merged["count"],
                "ndvi_mean": merged["mean"],
                "ndvi_std": merged["std"],
                "ndvi_p05": merged["quantiles"].get("p05"),
                "ndvi_p25": merged["quantiles"].get("p25"),
                "ndvi_p50": merged["quantiles"].get("p50"),
                "ndvi_p75": merged["quantiles"].get("p75"),
                "ndvi_p95": merged["quantiles"].get("p95"),
                "blocks": len(blocks),
            }
        )
        print(
            f"[municipal] {month} {entry['item_id']}: pixels agrícolas="
            f"{merged['count']} NDVI={merged['mean']}"
        )
        # persistência incremental: uma data concluída já fica registrada
        csv_path = os.path.join(PROCESSED_DIR, "municipal_ndvi_agriculture.csv")
        _write_rows_csv(rows, csv_path)

    csv_path = os.path.join(PROCESSED_DIR, "municipal_ndvi_agriculture.csv")
    if rows:
        _write_rows_csv(rows, csv_path)

    payload = {
        "generated_at": _now(),
        "municipality": MUNICIPALITY,
        "grid": {
            "crs": muni.MUNICIPAL_CRS,
            "res": grid["res"],
            "width": grid["width"],
            "height": grid["height"],
            "transform": list(grid["transform"])[:6],
            "municipality_bbox_wgs84": grid["municipality_bbox_wgs84"],
        },
        "blocks": len(blocks),
        "estimate": estimate,
        "masks": mask_reports,
        "primary_mask_year": primary_mask_year,
        "dates_processed": len(rows),
        "csv": os.path.relpath(csv_path, HERE).replace("\\", "/") if rows else None,
        "limitations": [
            "Máscara agrícola do ESA WorldCover (2020 e 2021): não cobre 2017–2019 "
            "nem 2022–2025.",
            "Processamento por blocos: estatística agregada, sem raster municipal.",
        ],
    }
    path = _write_json(payload, os.path.join(MANIFEST_DIR, "municipal_ndvi_report.json"))
    return {
        "ok": True,
        "report": path,
        "dates_processed": len(rows),
        "csv": payload["csv"],
        "estimate": estimate,
        "masks": mask_reports,
    }


# --------------------------------------------------------------- CONAB SUTIN


def cmd_sutin(args: argparse.Namespace) -> dict[str, Any]:
    """Adquire os polígonos de produção da CONAB (SUTIN) para o município."""
    from agri import conab_sutin as sutin

    layers = sutin.list_layers(uf=args.uf)
    acquired: list[dict[str, Any]] = []
    for layer in layers:
        name = layer["name"]
        if args.layer and args.layer.lower() not in name.lower():
            continue
        try:
            result = sutin.get_features(name, bbox=args.bbox)
        except Exception as exc:  # noqa: BLE001 - rede
            acquired.append({"layer": name, "status": "erro", "error": str(exc)[:200]})
            continue
        slug = name.replace("wp_geote:", "").replace("/", "-")
        geojson_path = os.path.join(
            PROCESSED_DIR, "conab_sutin", f"{slug}.geojson"
        )
        csv_path = os.path.join(PROCESSED_DIR, "conab_sutin", f"{slug}.csv")
        sutin.write_geojson(result, geojson_path)
        sutin.write_csv(result, csv_path)
        summary = sutin.summarize(result["features"])
        acquired.append(
            {
                "layer": name,
                "status": "ok",
                "total_features": result["total_features"],
                "returned_features": result["returned_features"],
                "summary": summary,
                "geojson": os.path.relpath(geojson_path, HERE).replace("\\", "/"),
                "csv": os.path.relpath(csv_path, HERE).replace("\\", "/"),
                "url": result["url"],
                "attributes": sutin.FEATURE_PROPERTIES,
                "has_productivity_attribute": False,
            }
        )
        print(
            f"[sutin] {name}: {result['returned_features']} feições | "
            f"área {summary['total_area_ha']} ha"
        )

    payload = {
        "generated_at": _now(),
        "institution": "CONAB",
        "application": sutin.APP,
        "geoserver_wfs": sutin.WFS,
        "geoserver_wms": sutin.WMS,
        "uf_filter": args.uf,
        "bbox": args.bbox,
        "layers_available": len(layers),
        "layers": layers,
        "acquired": acquired,
        "productivity_attribute": (
            "As camadas trazem AREA_HA (área da feição) e identificadores de "
            "município/cultura/safra — não há campo de produtividade (kg/ha)."
        ),
        "license_note": (
            "Acesso público à aplicação oficial; termos de uso específicos de "
            "cada conjunto não obtidos — registrado como pendência (D48)."
        ),
    }
    path = _write_json(payload, os.path.join(MANIFEST_DIR, "conab_sutin_report.json"))
    return {
        "ok": True,
        "report": path,
        "layers_available": len(layers),
        "acquired": [
            {"layer": a["layer"], "features": a.get("returned_features")}
            for a in acquired
        ],
    }


# ---------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="SADEN V2.4 — escala espacial, calendário ZARC e referência municipal"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_zarc = sub.add_parser("zarc", help="adquire e normaliza o calendário ZARC")
    p_zarc.add_argument(
        "--safras",
        nargs="+",
        default=list(zarc_mod.SAFRAS.keys()),
        help="safras a adquirir (ex.: 2023/2024)",
    )
    p_zarc.set_defaults(func=cmd_zarc)

    p_mb = sub.add_parser("mapbiomas", help="investiga as rotas oficiais do MapBiomas")
    p_mb.add_argument("--years", type=int, nargs="+", default=[2017, 2020, 2025])
    p_mb.set_defaults(func=cmd_mapbiomas)

    p_su = sub.add_parser("sutin", help="polígonos de produção da CONAB (SUTIN)")
    p_su.add_argument("--uf", default="MT")
    p_su.add_argument(
        "--bbox",
        type=float,
        nargs=4,
        default=[-55.75, -12.85, -55.45, -12.60],
        help="bbox de recorte (Sorriso e entorno)",
    )
    p_su.add_argument("--layer", default=None, help="filtro por nome de camada")
    p_su.set_defaults(func=cmd_sutin)

    p_mu = sub.add_parser("municipal", help="NDVI municipal sobre a área agrícola")
    p_mu.add_argument("--blocks", type=int, default=16)
    p_mu.add_argument("--max-dates", type=int, default=0, help="0 = uma data por ano")
    p_mu.add_argument("--mask-years", type=int, nargs="+", default=[2020, 2021])
    p_mu.add_argument(
        "--month", default=None, help="mês fixo (MM) para comparação sazonal entre anos"
    )
    p_mu.set_defaults(func=cmd_municipal)

    args = parser.parse_args(argv)
    try:
        result = args.func(args)
    except Exception as exc:  # noqa: BLE001 - CLI falha com mensagem clara
        print(
            json.dumps(
                {"ok": False, "error": type(exc).__name__, "message": str(exc)},
                ensure_ascii=False,
            )
        )
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
