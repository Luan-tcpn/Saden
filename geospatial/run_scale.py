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

    # recorte territorial: somente centros de célula dentro do polígono do município
    from agri.geometry_compat import municipality_geometry

    municipality_geom = municipality_geometry()
    municipality_cells = muni.municipality_mask(grid, municipality_geom)
    municipality_fraction = float(municipality_cells.mean())

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
            inside = municipality_cells[
                block["row_off"] : block["row_off"] + block["height"],
                block["col_off"] : block["col_off"] + block["width"],
            ]
            accumulators.append(muni.accumulate_ndvi(ndvi, valid, agri & inside))
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
        "municipality_cells_20m": int(np.count_nonzero(municipality_cells)),
        "municipality_fraction_of_bbox": municipality_fraction,
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


# ------------------------------------------------- relação safra × ano PAM


def cmd_relation(args: argparse.Namespace) -> dict[str, Any]:
    """Tabela de correspondência entre safra ZARC e ano de referência da PAM.

    Regra **derivada** (não é uma afirmação do IBGE): a safra ZARC ``Y/Y+1``
    tem plantio no ano Y (soja e milho 1ª, out–dez) ou no ano Y+1 (milho 2ª,
    jan–fev) e, portanto, colheita **no ano civil Y+1**. A PAM referencia o ano
    civil da produção/colheita → candidata principal: **Y+1**. A alternativa
    (ano de plantio, Y) é preservada com confiança menor.
    """
    import csv as _csv
    import statistics

    zarc_csv = os.path.join(PROCESSED_DIR, "zarc_planting_windows.csv")
    with open(zarc_csv, newline="", encoding="utf-8-sig") as handle:
        rows = list(_csv.DictReader(handle))

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault((row["safra"], str(row["cultura"])), []).append(row)

    output: list[dict[str, Any]] = []
    for (safra, cultura), items in sorted(grouped.items()):
        ini = int(str(safra).split("/")[0])
        years = sorted({r["safra_ini"] for r in items})
        janelas = sorted({r["janela_base"] for r in items if r["janela_base"]})
        datas_ini = sorted(r["janela_inicio_data"] for r in items if r["janela_inicio_data"])
        datas_fim = sorted(r["janela_fim_data"] for r in items if r["janela_fim_data"])
        planting_year = int(years[0]) if years else ini
        harvest_year = planting_year + 1
        second_safra = "2ª" in str(cultura)
        output.append(
            {
                "safra": safra,
                "cultura": cultura,
                "segunda_safra": second_safra,
                "combinacoes_grupo_solo_ciclo": len(items),
                "janelas_distintas": ";".join(janelas),
                "plantio_inicio": datas_ini[0] if datas_ini else None,
                "plantio_fim": datas_fim[-1] if datas_fim else None,
                "ano_de_plantio": planting_year,
                "ano_de_colheita_estimado": harvest_year,
                "pam_ano_candidato_principal": harvest_year,
                "pam_ano_candidato_alternativo": planting_year,
                "confianca": "media" if second_safra else "media_alta",
                "portarias": ";".join(sorted({r["portaria"] for r in items if r["portaria"]})),
                "natureza": "regra_derivada_do_calendario_zarc",
                "observacao": (
                    "A correspondência safra→ano da PAM é DERIVADA (colheita no ano "
                    "civil seguinte); deve ser confirmada com a documentação da "
                    "portaria e do calendário de semeadura antes de uso analítico."
                ),
            }
        )

    csv_path = os.path.join(PROCESSED_DIR, "zarc_pam_year_relation.csv")
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = _csv.DictWriter(handle, fieldnames=list(output[0].keys()))
        writer.writeheader()
        for row in output:
            writer.writerow(row)

    payload = {
        "generated_at": _now(),
        "rows": len(output),
        "csv": os.path.relpath(csv_path, HERE).replace("\\", "/"),
        "rule": (
            "Safra Y/Y+1 → ano de referência PAM = Y+1 (ano de colheita), com Y "
            "(ano de plantio) preservado como alternativa."
        ),
        "cultures": sorted({row["cultura"] for row in output}),
        "safras": sorted({row["safra"] for row in output}),
    }
    path = _write_json(payload, os.path.join(MANIFEST_DIR, "zarc_pam_relation.json"))
    return {
        "ok": True,
        "report": path,
        "csv": payload["csv"],
        "rows": len(output),
    }


# ------------------------------------------------- série municipal mensal


def cmd_municipal_series(args: argparse.Namespace) -> dict[str, Any]:
    """Série municipal mensal de NDVI sobre a área agrícola (retomável)."""
    import numpy as np
    from pystac_client import Client

    from historical import landuse as lu
    from historical import municipal as muni
    from historical import municipal_series as mser
    from historical import radiometry as radio
    from s2_poc import config, network

    network.configure_tls()
    client = Client.open(config.STAC_URL)

    monthly_csv = os.path.join(PROCESSED_DIR, "sentinel2_historical_monthly.csv")
    observed = [
        row
        for row in mser.series_mod.read_monthly_csv(monthly_csv)
        if row.get("status") == "observed"
    ]
    if args.months:
        wanted = {str(m).zfill(2) for m in args.months}
        observed = [r for r in observed if str(r["month"])[5:7] in wanted]
    if args.max_months:
        observed = observed[: args.max_months]

    grid = muni.municipality_grid()
    blocks = muni.grid_blocks(grid, n_blocks=args.blocks)
    out_csv = os.path.join(PROCESSED_DIR, "municipal_ndvi_monthly.csv")
    done = mser.load_completed(out_csv)
    rows: list[dict[str, Any]] = []
    if os.path.exists(out_csv):
        import csv as _csv

        with open(out_csv, newline="", encoding="utf-8-sig") as handle:
            rows = list(_csv.DictReader(handle))

    from agri.geometry_compat import municipality_geometry

    municipality_cells = muni.municipality_mask(grid, municipality_geometry())
    variant_masks: dict[tuple[int, int], dict[str, np.ndarray]] = {}
    for block in blocks:
        bbox = lu.block_bounds_wgs84(grid, block)
        payload20 = lu.read_worldcover_block(2020, bbox)
        payload21 = lu.read_worldcover_block(2021, bbox)
        subgrid = lu.block_subgrid(grid, block)
        # máscaras reamostradas para a grade de 20 m do bloco (mesmo método
        # validado na AOI: centro da célula -> pixel WorldCover)
        crop20 = lu.cropland_grid_mask(payload20["data"], payload20["meta"], subgrid)
        crop21 = lu.cropland_grid_mask(payload21["data"], payload21["meta"], subgrid)
        variant_masks[(block["row_off"], block["col_off"])] = mser.mask_variants(
            crop20, crop21
        )

    for entry in observed:
        month = str(entry["month"])
        date = str(entry.get("datetime") or "")[:10]
        if not date:
            continue
        if all((month, variant) in done for variant in mser.MASK_VARIANTS):
            continue
        item_xg = mser.find_tile_item(client, "sentinel-2-c1-l2a", date, mser.TILE_XG)
        if item_xg is None:
            item_xg = mser.find_tile_item(client, "sentinel-2-l2a", date, mser.TILE_XG)
        item_xf = mser.find_tile_item(client, "sentinel-2-c1-l2a", date, mser.TILE_XF)
        if item_xf is None:
            item_xf = mser.find_tile_item(client, "sentinel-2-l2a", date, mser.TILE_XF)
        if item_xg is None:
            print(f"[municipal] {month}: item do tile 21LXG nao encontrado")
            continue
        collection = (
            "sentinel-2-c1-l2a"
            if "_T21LXG_" in str(item_xg.id)
            else "sentinel-2-l2a"
        )
        profile = radio.item_radiometry(item_xg, collection)
        result = mser.process_month(
            grid,
            blocks,
            item_xg,
            item_xf,
            profile,
            variant_masks,
            municipality_cells,
        )
        for variant, stats in result["variants"].items():
            if (month, variant) in done:
                continue
            rows.append(
                {
                    "month": month,
                    "year": month[:4],
                    "item_id": str(item_xg.id),
                    "catalog": entry.get("catalog"),
                    "baseline": entry.get("baseline"),
                    "radiometry_profile": profile["profile"],
                    "tiles_used": ";".join(result["tiles_used"]),
                    "mask_variant": variant,
                    "mask_year": (
                        "2020+2021" if variant in ("stable", "broad") else variant[-4:]
                    ),
                    "agricultural_pixels": stats["count"],
                    "valid_pixels": stats["count"],
                    "valid_fraction": 1.0 if stats["count"] else None,
                    "ndvi_mean": stats["mean"],
                    "ndvi_median": stats["quantiles"].get("p50"),
                    "ndvi_std": stats["std"],
                    "ndvi_p05": stats["quantiles"].get("p05"),
                    "ndvi_p95": stats["quantiles"].get("p95"),
                    "obstruction_fraction": stats.get("obstruction_fraction"),
                    "scenes": 1,
                    "blocks": len(blocks),
                    "source_manifest": "municipal_ndvi_series.json",
                }
            )
            done.add((month, variant))
        mser.write_rows(rows, out_csv)
        print(
            f"[municipal] {month} ({item_xg.id}) processado; "
            f"{len(rows)} linhas acumuladas"
        )

    manifest = {
        "generated_at": _now(),
        "municipality": MUNICIPALITY,
        "grid": {
            "crs": muni.MUNICIPAL_CRS,
            "res": grid["res"],
            "width": grid["width"],
            "height": grid["height"],
        },
        "blocks": len(blocks),
        "mask_variants": list(mser.MASK_VARIANTS),
        "mask_source": "ESA WorldCover 10 m — classe 40 (Cropland), 2020 e 2021",
        "months_processed": sorted({r["month"] for r in rows}),
        "rows": len(rows),
        "csv": os.path.relpath(out_csv, HERE).replace("\\", "/"),
        "tile_rule": (
            "Mosaico first_valid_wins (D44): 21LXG tem prioridade; 21LXF e lido "
            "apenas nos blocos abaixo de -12,657 graus."
        ),
        "limitations": [
            "Mascara agricola existe apenas para 2020 e 2021 (WorldCover): "
            "aplicada retroativamente aos demais anos (proxy, nao informacao "
            "historica).",
            "Cobertura por tile varia; blocos fora do footprint ficam sem dado.",
        ],
    }
    path = _write_json(
        manifest, os.path.join(MANIFEST_DIR, "municipal_ndvi_series.json")
    )
    return {
        "ok": True,
        "report": path,
        "csv": manifest["csv"],
        "months_processed": len(manifest["months_processed"]),
        "rows": len(rows),
    }


# ------------------------------------------------------- pareamento (V2.5)


def cmd_pair(args: argparse.Namespace) -> dict[str, Any]:
    """Constrói o dataset pareado espacial × agronômico."""
    from agri import pairing, season

    zarc_rows = pairing.read_csv(
        os.path.join(PROCESSED_DIR, "zarc_planting_windows.csv")
    )
    municipal_rows = pairing.read_csv(
        os.path.join(PROCESSED_DIR, "municipal_ndvi_monthly.csv")
    )
    aoi_rows = pairing.read_csv(
        os.path.join(PROCESSED_DIR, "sentinel2_historical_monthly.csv")
    )
    pam_rows = pairing.read_csv(
        os.path.join(PROCESSED_DIR, "productivity_observations.csv")
    )

    dataset = pairing.build_paired_dataset(
        zarc_rows, municipal_rows, aoi_rows, pam_rows, min_months=args.min_months
    )
    out_csv = os.path.join(
        PROCESSED_DIR, "municipal_seasonal_productivity_dataset.csv"
    )
    pairing.write_csv(dataset, out_csv)

    usable = [row for row in dataset if row.get("status") == "paired_usable"]
    by_crop: dict[str, int] = {}
    for row in usable:
        key = f"{row['crop']}|{row['mask_variant']}"
        by_crop[key] = by_crop.get(key, 0) + 1

    manifest = {
        "generated_at": _now(),
        "rows": len(dataset),
        "paired_usable": len(usable),
        "usable_by_crop_and_mask": by_crop,
        "csv": os.path.relpath(out_csv, HERE).replace("\\", "/"),
        "primary_protocol": {
            "mask_variant": "stable",
            "risk_level": season.PRIMARY_RISK,
            "risk_justification": season.PRIMARY_RISK_JUSTIFICATION,
            "window_rule": (
                "janela modal entre as combinações oficiais de solo/ciclo da "
                "safra (as demais ficam como sensibilidade)"
            ),
            "note": (
                "Fixado antes da análise de correlação; não é o subconjunto de "
                "maior correlação."
            ),
        },
        "semantics": {
            "milho": (
                "A PAM publica o rendimento total do milho do ano (1ª + 2ª "
                "safras); as janelas de safra são cenários, não observações "
                "independentes."
            ),
            "mask": (
                "Máscara WorldCover (2020/2021) aplicada retroativamente aos "
                "anos anteriores — proxy espacial, não informação histórica."
            ),
        },
        "sources": {
            "zarc": "data/processed/zarc_planting_windows.csv",
            "municipal_ndvi": "data/processed/municipal_ndvi_monthly.csv",
            "aoi_ndvi": "data/processed/sentinel2_historical_monthly.csv",
            "pam": "data/processed/productivity_observations.csv",
        },
    }
    path = _write_json(
        manifest, os.path.join(MANIFEST_DIR, "seasonal_pairing_manifest.json")
    )
    return {
        "ok": True,
        "manifest": path,
        "csv": manifest["csv"],
        "rows": len(dataset),
        "paired_usable": len(usable),
        "usable_by_crop_and_mask": by_crop,
    }


def cmd_reeval(args: argparse.Namespace) -> dict[str, Any]:
    """Reavalia as associações com a base ampliada (mesmos métodos da V2.3)."""
    import csv as _csv

    from historical import reeval

    dataset_csv = os.path.join(
        PROCESSED_DIR, "municipal_seasonal_productivity_dataset.csv"
    )
    if not os.path.exists(dataset_csv):
        return {"ok": False, "error": f"dataset pareado ausente: {dataset_csv}"}
    with open(dataset_csv, newline="", encoding="utf-8-sig") as handle:
        dataset = list(_csv.DictReader(handle))

    groups = reeval.group_pairs(dataset)
    results: dict[str, Any] = {}
    p_values: dict[str, float] = {}
    for (crop, variant), pairs in sorted(groups.items()):
        key = f"{crop}|{variant}"
        for field, label in (
            ("ndvi_municipal_mean", "ndvi_municipal"),
            ("ndvi_aoi_mean", "ndvi_aoi"),
        ):
            analysis = reeval.analyze_pairs(
                pairs, field, permutations=args.permutations
            )
            analysis["walk_forward"] = reeval.walk_forward(
                pairs, field, min_train=args.min_train
            )
            results[f"{key}|{label}"] = analysis
            if analysis.get("permutation_p") is not None:
                p_values[f"{key}|{label}"] = analysis["permutation_p"]

    corrected = reeval.holm_correction(p_values)
    for key, value in corrected.items():
        if key in results:
            results[key]["holm_p"] = value

    # comparação com a V2.3 (mesmos pares, indicador da AOI)
    v23 = None
    v23_path = os.path.join(MANIFEST_DIR, "exploratory_study.json")
    if os.path.exists(v23_path):
        with open(v23_path, encoding="utf-8") as handle:
            v23 = json.load(handle).get("statistics", {})

    manifest = {
        "generated_at": _now(),
        "results": results,
        "primary_analysis": "soja|stable|ndvi_municipal",
        "protocol": {
            "primary_mask": "stable",
            "primary_indicator": "ndvi_municipal_mean",
            "sensitivity": "máscaras (wc2020/wc2021/broad) e indicador da AOI",
            "permutations": args.permutations,
            "min_train": args.min_train,
            "multiple_comparisons": "correção de Holm aplicada à família de testes",
        },
        "v23_reference": v23,
        "note": (
            "Mesmos métodos da V2.3 (Pearson, Spearman, permutação com semente "
            "fixa, detrendizado, walk-forward com os mesmos baselines)."
        ),
    }
    path = _write_json(manifest, os.path.join(MANIFEST_DIR, "reevaluation.json"))
    summary_csv = os.path.join(MANIFEST_DIR, "reevaluation_summary.csv")
    with open(summary_csv, "w", newline="", encoding="utf-8-sig") as handle:
        writer = _csv.DictWriter(
            handle,
            fieldnames=[
                "key", "n", "pearson_r", "spearman_rho", "permutation_p",
                "holm_p", "ci95_low", "ci95_high", "r_detrended",
                "wf_mae_ols_ndvi", "wf_mae_media", "wf_mae_ultimo",
                "wf_mae_tendencia", "ndvi_beats_baselines",
            ],
        )
        writer.writeheader()
        for key, analysis in results.items():
            wf = analysis.get("walk_forward", {})
            models = wf.get("models", {}) if isinstance(wf, dict) else {}
            ci = analysis.get("bootstrap_ci95") or [None, None]
            writer.writerow(
                {
                    "key": key,
                    "n": analysis.get("n"),
                    "pearson_r": analysis.get("pearson_r"),
                    "spearman_rho": analysis.get("spearman_rho"),
                    "permutation_p": analysis.get("permutation_p"),
                    "holm_p": analysis.get("holm_p"),
                    "ci95_low": ci[0],
                    "ci95_high": ci[1],
                    "r_detrended": analysis.get("pearson_r_detrended"),
                    "wf_mae_ols_ndvi": models.get("ols_com_ndvi", {}).get("mae_kg_ha"),
                    "wf_mae_media": models.get("media_historica", {}).get("mae_kg_ha"),
                    "wf_mae_ultimo": models.get("ultimo_valor", {}).get("mae_kg_ha"),
                    "wf_mae_tendencia": models.get("tendencia", {}).get("mae_kg_ha"),
                    "ndvi_beats_baselines": wf.get("ndvi_beats_baselines"),
                }
            )
    return {
        "ok": True,
        "report": path,
        "summary_csv": os.path.relpath(summary_csv, HERE).replace("\\", "/"),
        "results": {
            key: {
                "n": analysis.get("n"),
                "pearson_r": analysis.get("pearson_r"),
                "permutation_p": analysis.get("permutation_p"),
                "holm_p": analysis.get("holm_p"),
                "ndvi_beats_baselines": analysis.get("walk_forward", {}).get(
                    "ndvi_beats_baselines"
                ),
            }
            for key, analysis in results.items()
        },
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

    p_re = sub.add_parser("relation", help="correspondência safra ZARC × ano PAM")
    p_re.set_defaults(func=cmd_relation)

    p_pr = sub.add_parser("pair", help="dataset pareado espacial × agronômico")
    p_pr.add_argument("--min-months", type=int, default=2)
    p_pr.set_defaults(func=cmd_pair)

    p_rv = sub.add_parser("reeval", help="reavaliação estatística da base ampliada")
    p_rv.add_argument("--permutations", type=int, default=5000)
    p_rv.add_argument("--min-train", type=int, default=5)
    p_rv.set_defaults(func=cmd_reeval)

    p_ms = sub.add_parser(
        "municipal-series", help="série municipal mensal (retomável, 4 máscaras)"
    )
    p_ms.add_argument("--blocks", type=int, default=16)
    p_ms.add_argument("--months", nargs="+", default=None, help="meses (MM) a processar")
    p_ms.add_argument("--max-months", type=int, default=0)
    p_ms.set_defaults(func=cmd_municipal_series)

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
