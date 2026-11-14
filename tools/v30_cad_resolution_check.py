"""V3.0 — validação 90 m vs 450 m e BBOX vs polígono (D96).

A aquisição usa ``scaleFactor=0.2`` (~460 m) por eficiência. Este script mede o
que se perde nessa troca, comparando, **na mesma área e com a mesma máscara**:

* a estatística municipal a 90 m (``scaleFactor=1``);
* a estatística municipal a ~450 m (``scaleFactor=0.2``);
* e, para a janela de 450 m, a diferença entre agregação por **polígono** e por
  **bbox** (a aproximação usada na V2.9).

A comparação é feita numa janela de ±0,35° em torno do centroide, interseção
com o polígono municipal: área idêntica nas duas resoluções, e o custo de
transferência fica limitado. O resultado é sobre **variabilidade local**, não
sobre o município inteiro — está declarado no manifesto.

Uso:
    python tools/v30_cad_resolution_check.py
"""

from __future__ import annotations

import csv
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "geospatial"))

from agroclimate import soil  # noqa: E402

BASE = "https://geoinfo.dados.embrapa.br/geoserver/ows"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SADEN-V3.0"}
TIMEOUT = 300
PROCESSED = os.path.join(ROOT, "geospatial", "data", "processed")
MANIFESTS = os.path.join(ROOT, "geospatial", "data", "manifests")
OUT = os.path.join(MANIFESTS, "v30_cad_resolution_check.json")
HALF_DEG = 0.35
PER_STATE = 3


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def fetch(coverage_id, lat0, lat1, lon0, lon1, scale):
    url = (
        f"{BASE}?service=WCS&version=2.0.1&request=GetCoverage"
        f"&coverageId={coverage_id}&format=image/tiff"
        f"&subset=Lat({lat0:.6f},{lat1:.6f})&subset=Long({lon0:.6f},{lon1:.6f})"
        f"&scaleFactor={scale}"
    )
    for attempt in range(2):
        try:
            request = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(
                request, timeout=TIMEOUT, context=_context()
            ) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504):
                time.sleep(4 * (attempt + 1))
                continue
            return None
        except Exception:  # noqa: BLE001
            time.sleep(2)
    return None


def read_layer(data: bytes):
    from rasterio.io import MemoryFile

    with MemoryFile(data) as memfile:
        with memfile.open() as dataset:
            array = dataset.read(1).astype("float32")
            nodata = dataset.nodata
            transform = dataset.transform
    if nodata is not None:
        array[array == nodata] = np.nan
    array[array <= 0] = np.nan
    return array, transform


def polygon_capacity(layers, transform, geometry):
    """CAD 0-100 por pixel dentro do polígono, e a mesma área em bbox."""
    from rasterio.features import geometry_mask

    selected = soil.layers_up_to_depth(100.0)
    keys = [layer["key"] for layer in selected]
    stack = np.stack([layers[key] for key in keys])
    capacity = soil.pixel_capacity_mm(stack, selected)
    inside = geometry_mask(
        [geometry],
        out_shape=capacity.shape,
        transform=transform,
        invert=True,
        all_touched=True,
    )
    polygon_values = capacity[inside]
    polygon_values = polygon_values[np.isfinite(polygon_values)]
    bbox_values = capacity[np.isfinite(capacity)]
    return polygon_values, bbox_values, float(inside.mean())


def summarize(values: np.ndarray) -> dict[str, Any]:
    if values.size == 0:
        return {"status": "sem_dado", "n": 0}
    return {
        "status": "ok",
        "n": int(values.size),
        "mean": float(values.mean()),
        "median": float(np.median(values)),
        "sd": float(values.std(ddof=1)) if values.size > 1 else 0.0,
        "p10": float(np.quantile(values, 0.10)),
        "p90": float(np.quantile(values, 0.90)),
        "cv": float(values.std() / values.mean()) if values.mean() else None,
    }


def select(municipalities, codes, cad_done):
    usable = [
        m
        for m in municipalities
        if str(m.get("ibge_code")) in codes
        and str(m.get("ibge_code")) in cad_done
        and m.get("centroid_lat") not in (None, "")
        and m.get("area_km2") not in (None, "")
    ]
    by_state: dict[str, list[dict]] = defaultdict(list)
    for record in usable:
        by_state[str(record["state"])].append(record)
    chosen = []
    for state in sorted(by_state):
        rows = sorted(by_state[state], key=lambda r: float(r["area_km2"]))
        count = min(PER_STATE, len(rows))
        if count == 0:
            continue
        if count == 1:
            picks = [rows[len(rows) // 2]]
        else:
            step = (len(rows) - 1) / (count - 1)
            picks = [rows[int(round(i * step))] for i in range(count)]
        chosen.extend(picks)
    return chosen


def main() -> int:
    import json as _json

    from shapely.geometry import shape

    cad = _json.load(open(os.path.join(MANIFESTS, "v30_cad_polygon.json"), encoding="utf-8"))
    cad_done = set(cad["municipalities"])
    municipalities = list(
        csv.DictReader(
            open(
                os.path.join(PROCESSED, "panel_municipalities.csv"),
                newline="",
                encoding="utf-8-sig",
            )
        )
    )
    geometries = {}
    with open(os.path.join(PROCESSED, "panel_municipalities.geojson"), encoding="utf-8") as handle:
        collection = _json.load(handle)
    for feature in collection["features"]:
        geometries[str(feature["properties"].get("ibge_code"))] = shape(feature["geometry"])

    chosen = select(municipalities, cad_done, cad_done)
    print(f"municípios selecionados: {len(chosen)}", flush=True)
    layers = tuple((layer["key"], layer["coverage_id"]) for layer in soil.AW_LAYERS)
    rows = []
    for record in chosen:
        code = str(record["ibge_code"])
        lat = float(record["centroid_lat"])
        lon = float(record["centroid_lon"])
        lat0, lat1 = lat - HALF_DEG, lat + HALF_DEG
        lon0, lon1 = lon - HALF_DEG, lon + HALF_DEG
        stats: dict[str, dict[str, Any]] = {}
        failed = []
        for scale, label in ((1.0, "90m"), (0.2, "450m")):
            arrays = {}
            transform = None
            for key, coverage_id in layers:
                data = fetch(coverage_id, lat0, lat1, lon0, lon1, scale)
                if data is None:
                    failed.append(f"{label}:{key}")
                    continue
                try:
                    array, layer_transform = read_layer(data)
                except Exception:  # noqa: BLE001
                    failed.append(f"{label}:{key}")
                    continue
                if transform is None:
                    transform = layer_transform
                arrays[key] = array
            if transform is None or len(arrays) != len(layers):
                continue
            polygon_values, bbox_values, inside_share = polygon_capacity(
                arrays, transform, geometries[code]
            )
            stats[label] = {
                "polygon": summarize(polygon_values),
                "bbox": summarize(bbox_values),
                "polygon_share_of_window": inside_share,
            }
        if "90m" not in stats or "450m" not in stats:
            print(f"  {code} {record['municipality']}: falha ({failed})", flush=True)
            continue
        rows.append(
            {
                "ibge_code": code,
                "municipality": record["municipality"],
                "state": record["state"],
                "area_km2": float(record["area_km2"]),
                "stats": stats,
            }
        )
        p90 = stats["90m"]["polygon"]
        p450 = stats["450m"]["polygon"]
        print(
            f"  {record['state']} {record['municipality'][:22]:<22} "
            f"mediana 90m={p90['median']:.1f} 450m={p450['median']:.1f} "
            f"(dif {p450['median']-p90['median']:+.1f}) | sd 90m={p90['sd']:.1f} 450m={p450['sd']:.1f}",
            flush=True,
        )

    def _pair(a: str, b: str, field: str):
        values = [
            (r["stats"][a]["polygon"][field], r["stats"][b]["polygon"][field])
            for r in rows
            if r["stats"][a]["polygon"].get("status") == "ok"
            and r["stats"][b]["polygon"].get("status") == "ok"
        ]
        if not values:
            return None
        first = np.array([v[0] for v in values])
        second = np.array([v[1] for v in values])
        return {
            "n": len(values),
            "median_90m": float(np.median(first)),
            "median_450m": float(np.median(second)),
            "mean_diff_450m_minus_90m": float(np.mean(second - first)),
            "median_abs_diff": float(np.median(np.abs(second - first))),
            "correlation": float(np.corrcoef(first, second)[0, 1]) if len(values) > 2 else None,
        }

    bbox_vs_polygon = [
        (r["stats"]["450m"]["bbox"]["median"], r["stats"]["450m"]["polygon"]["median"])
        for r in rows
        if r["stats"]["450m"]["bbox"].get("status") == "ok"
        and r["stats"]["450m"]["polygon"].get("status") == "ok"
    ]
    bbox_summary = None
    if bbox_vs_polygon:
        bbox = np.array([v[0] for v in bbox_vs_polygon])
        poly = np.array([v[1] for v in bbox_vs_polygon])
        bbox_summary = {
            "n": len(bbox_vs_polygon),
            "mean_bbox": float(bbox.mean()),
            "mean_polygon": float(poly.mean()),
            "mean_diff_bbox_minus_polygon": float(np.mean(bbox - poly)),
            "median_abs_diff": float(np.median(np.abs(bbox - poly))),
            "max_abs_diff": float(np.max(np.abs(bbox - poly))),
            "correlation": float(np.corrcoef(bbox, poly)[0, 1]) if len(bbox) > 2 else None,
        }
    payload = {
        "generated_at": _now(),
        "window_deg": HALF_DEG,
        "note": (
            "Comparação feita numa janela de +/-0,35 grau em torno do centroide, "
            "restrita ao poligono municipal: mede variabilidade LOCAL, nao o "
            "municipio inteiro."
        ),
        "n_municipalities": len(rows),
        "median_90m_vs_450m": _pair("90m", "450m", "median"),
        "sd_90m_vs_450m": _pair("90m", "450m", "sd"),
        "p10_90m_vs_450m": _pair("90m", "450m", "p10"),
        "p90_90m_vs_450m": _pair("90m", "450m", "p90"),
        "bbox_vs_polygon_450m": bbox_summary,
        "municipalities": rows,
    }
    with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
        handle.write("\n")
    print(_json.dumps({k: v for k, v in payload.items() if k != "municipalities"},
                      ensure_ascii=False, indent=2))
    print(f"manifesto: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
