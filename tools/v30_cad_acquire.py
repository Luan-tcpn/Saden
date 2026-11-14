"""V3.0 — aquisição da CAD com estatística por **polígono municipal** (D96).

A V2.9 agregava por *bbox* do município, o que inclui área vizinha em
municípios de forma irregular. Aqui a aquisição muda de unidade:

* **uma requisição por UF e por camada** (6 UFs × 6 camadas = 36 janelas), em
  vez de 6 por município (≈7.800). Medido: MS 16,8 MB em 2,4 s, MT 37,8 MB em
  4,0 s, PR 8,4 MB em 1,2 s;
* cada município é mascarado pelo **seu polígono oficial** (IBGE), e a
  estatística é calculada só sobre pixels dentro do limite;
* a CAD é integrada **por pixel** em 0–60, 0–100 e 0–200 cm, e as estatísticas
  (mediana, quantis, desvio, fração válida) são da distribuição municipal —
  não de uma média de médias.

Retomada: o manifesto é gravado após cada UF; UFs concluídas são puladas.

Uso:
    python tools/v30_cad_acquire.py
    python tools/v30_cad_acquire.py --states MT,MS --reset
"""

from __future__ import annotations

import argparse
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
RETRIES = 2
PROCESSED = os.path.join(ROOT, "geospatial", "data", "processed")
MANIFESTS = os.path.join(ROOT, "geospatial", "data", "manifests")
OUT = os.path.join(MANIFESTS, "v30_cad_polygon.json")
OUT_CSV = os.path.join(MANIFESTS, "v30_cad_polygon.csv")

LAYERS = tuple((layer["key"], layer["coverage_id"]) for layer in soil.AW_LAYERS)
DEPTHS_CM = (60.0, 100.0, 200.0)
SCALE = 0.2


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def fetch(coverage_id: str, lat0: float, lat1: float, lon0: float, lon1: float):
    """Baixa uma camada para uma janela; devolve (bytes, segundos)."""
    url = (
        f"{BASE}?service=WCS&version=2.0.1&request=GetCoverage"
        f"&coverageId={coverage_id}&format=image/tiff"
        f"&subset=Lat({lat0:.6f},{lat1:.6f})&subset=Long({lon0:.6f},{lon1:.6f})"
        f"&scaleFactor={SCALE}"
    )
    last = ""
    for attempt in range(RETRIES + 1):
        started = time.time()
        try:
            request = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(
                request, timeout=TIMEOUT, context=_context()
            ) as response:
                return response.read(), time.time() - started
        except urllib.error.HTTPError as exc:
            last = f"HTTP {exc.code}"
            if exc.code in (429, 500, 502, 503, 504):
                time.sleep(5 * (attempt + 1))
                continue
            return None, 0.0
        except Exception as exc:  # noqa: BLE001
            last = f"{type(exc).__name__}"
            time.sleep(2 * (attempt + 1))
    print(f"    [falha] {coverage_id}: {last}", flush=True)
    return None, 0.0


def read_raster(data: bytes):
    """Lê o GeoTIFF em memória e devolve (array float32 com NaN, transform)."""
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


def load_panel_municipalities() -> list[dict[str, Any]]:
    path = os.path.join(PROCESSED, "panel_municipalities.csv")
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def load_panel_codes() -> set[str]:
    path = os.path.join(PROCESSED, "agroclimatic_productivity_panel.csv")
    codes: set[str] = set()
    with open(path, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            if str(row.get("status")) == "paired_usable" and str(
                row.get("climate_source")
            ) == "NASA-POWER":
                codes.add(str(row.get("ibge_code")))
    return codes


def load_geometries(codes: set[str]):
    import json as _json

    from shapely.geometry import shape

    path = os.path.join(PROCESSED, "panel_municipalities.geojson")
    with open(path, encoding="utf-8") as handle:
        collection = _json.load(handle)
    out = {}
    for feature in collection["features"]:
        code = str(feature["properties"].get("ibge_code"))
        if code not in codes:
            continue
        out[code] = {
            "geometry": shape(feature["geometry"]),
            "state": feature["properties"].get("state"),
            "municipality": feature["properties"].get("municipality"),
        }
    return out


def _stats(values: np.ndarray) -> dict[str, Any]:
    valid = values[np.isfinite(values)]
    if valid.size == 0:
        return {"status": "sem_dado", "n": 0}
    return {
        "status": "ok",
        "n": int(valid.size),
        "mean": float(valid.mean()),
        "median": float(np.median(valid)),
        "sd": float(valid.std(ddof=1)) if valid.size > 1 else 0.0,
        "p10": float(np.quantile(valid, 0.10)),
        "p25": float(np.quantile(valid, 0.25)),
        "p75": float(np.quantile(valid, 0.75)),
        "p90": float(np.quantile(valid, 0.90)),
        "min": float(valid.min()),
        "max": float(valid.max()),
    }


def municipality_stats(
    layers: dict[str, np.ndarray],
    transform,
    geometry,
    bounds: tuple[float, float, float, float],
) -> dict[str, Any]:
    """Estatística de CAD por profundidade, restrita ao polígono municipal."""
    from rasterio.features import geometry_mask
    from rasterio.windows import Window, from_bounds, transform as window_transform

    lon0, lat0, lon1, lat1 = bounds
    window = from_bounds(lon0, lat0, lon1, lat1, transform).round_offsets().round_lengths()
    height, width = layers[LAYERS[0][0]].shape
    col_off = max(0, int(window.col_off))
    row_off = max(0, int(window.row_off))
    col_end = min(width, int(window.col_off + window.width))
    row_end = min(height, int(window.row_off + window.height))
    if col_end <= col_off or row_end <= row_off:
        return {"status": "fora_da_janela"}
    sub_window = Window(col_off, row_off, col_end - col_off, row_end - row_off)
    sub_transform = window_transform(sub_window, transform)
    shape_ = (row_end - row_off, col_end - col_off)
    inside = geometry_mask(
        [geometry], out_shape=shape_, transform=sub_transform, invert=True, all_touched=True
    )
    if not inside.any():
        return {"status": "poligono_sem_pixel"}
    out: dict[str, Any] = {
        "window_pixels": int(inside.sum()),
        "polygon_bbox_window": [col_off, row_off, col_end, row_end],
    }
    for depth in DEPTHS_CM:
        selected = soil.layers_up_to_depth(depth)
        keys = [layer["key"] for layer in selected]
        if not all(key in layers for key in keys):
            out[f"cad_0_{int(depth)}"] = {"status": "camada_ausente"}
            continue
        stack = np.stack(
            [
                layers[key][row_off:row_end, col_off:col_end]
                for key in keys
            ]
        )
        capacity = soil.pixel_capacity_mm(stack, selected)
        masked = np.where(inside, capacity, np.nan)
        stats = _stats(masked)
        out[f"cad_0_{int(depth)}"] = stats
    return out


def main() -> int:
    global SCALE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--states", default="")
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--scale", type=float, default=SCALE)
    args = parser.parse_args()
    SCALE = args.scale

    codes = load_panel_codes()
    municipalities = {
        str(m["ibge_code"]): m for m in load_panel_municipalities()
    }
    geometries = load_geometries(codes)
    print(f"municípios no painel: {len(codes)}; com geometria: {len(geometries)}", flush=True)

    by_state: dict[str, list[str]] = defaultdict(list)
    for code, record in geometries.items():
        by_state[str(record["state"])].append(code)
    wanted = [s.strip() for s in args.states.split(",") if s.strip()]
    states = sorted(by_state)
    if wanted:
        states = [s for s in states if s in wanted]

    out: dict[str, Any] = {
        "generated_at": _now(),
        "method": (
            "WCS GetCoverage por UF e camada, scaleFactor=0.2 (~460 m), com "
            "mascara do poligono municipal oficial e CAD integrada por pixel "
            "em 0-60/0-100/0-200 cm. Requisicoes: 6 camadas por UF."
        ),
        "source": soil.AW_SOURCE,
        "license": soil.AW_LICENSE,
        "unit": soil.AW_UNIT,
        "scale_factor": SCALE,
        "states_done": [],
        "municipalities": {},
    }
    if os.path.exists(OUT) and not args.reset:
        try:
            out = json.load(open(OUT, encoding="utf-8"))
        except json.JSONDecodeError:
            pass
        out["scale_factor"] = SCALE
    done = set(out.get("states_done", []))

    started = time.time()
    for state in states:
        if state in done:
            print(f"{state}: já concluída", flush=True)
            continue
        members = sorted(by_state[state])
        lats = [
            (
                float(municipalities[c]["bbox_min_lat"]),
                float(municipalities[c]["bbox_max_lat"]),
                float(municipalities[c]["bbox_min_lon"]),
                float(municipalities[c]["bbox_max_lon"]),
            )
            for c in members
            if municipalities.get(c)
        ]
        if not lats:
            continue
        lat0 = min(v[0] for v in lats)
        lat1 = max(v[1] for v in lats)
        lon0 = min(v[2] for v in lats)
        lon1 = max(v[3] for v in lats)
        print(f"{state}: {len(members)} municípios, bbox lat {lat0:.2f}..{lat1:.2f} "
              f"lon {lon0:.2f}..{lon1:.2f}", flush=True)
        arrays: dict[str, np.ndarray] = {}
        transform = None
        failed_layers: list[str] = []
        volume = 0
        for key, coverage_id in LAYERS:
            data, seconds = fetch(coverage_id, lat0, lat1, lon0, lon1)
            if data is None:
                failed_layers.append(key)
                continue
            try:
                array, layer_transform = read_raster(data)
            except Exception:  # noqa: BLE001
                failed_layers.append(key)
                continue
            if transform is None:
                transform = layer_transform
            elif getattr(layer_transform, "c", None) != getattr(transform, "c", None):
                failed_layers.append(key)
                continue
            arrays[key] = array
            volume += len(data)
            print(f"   {key}: {len(data)/1e6:.2f} MB em {seconds:.1f}s", flush=True)
        if failed_layers:
            print(f"   [aviso] camadas com falha: {failed_layers} — UF adiada", flush=True)
            continue
        for code in members:
            record = geometries[code]
            row = municipalities.get(code)
            if row is None:
                continue
            bounds = (
                float(row["bbox_min_lon"]),
                float(row["bbox_min_lat"]),
                float(row["bbox_max_lon"]),
                float(row["bbox_max_lat"]),
            )
            stats = municipality_stats(arrays, transform, record["geometry"], bounds)
            entry = {
                "ibge_code": code,
                "municipality": record["municipality"],
                "state": record["state"],
                "area_km2": float(row.get("area_km2") or 0.0) or None,
                "depth_stats": stats,
            }
            for depth in DEPTHS_CM:
                block = stats.get(f"cad_0_{int(depth)}", {})
                entry[f"cad_0_{int(depth)}_mm"] = block.get("median")
            out["municipalities"][code] = entry
        out["states_done"] = sorted(set(out.get("states_done", [])) | {state})
        out["updated_at"] = _now()
        out["volume_mb"] = round(out.get("volume_mb", 0.0) + volume / 1e6, 1)
        os.makedirs(MANIFESTS, exist_ok=True)
        with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(out, handle, ensure_ascii=False, indent=2, default=str)
            handle.write("\n")
        print(f"   {state} concluída; manifesto com {len(out['municipalities'])} municípios", flush=True)
        del arrays

    out["elapsed_s"] = round(time.time() - started, 1)
    out["n_municipalities"] = len(out["municipalities"])
    out["n_requested"] = len(geometries)
    with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(out, handle, ensure_ascii=False, indent=2, default=str)
        handle.write("\n")
    rows = []
    for code, entry in sorted(out["municipalities"].items()):
        for depth in DEPTHS_CM:
            block = entry["depth_stats"].get(f"cad_0_{int(depth)}", {})
            rows.append(
                {
                    "ibge_code": code,
                    "municipality": entry["municipality"],
                    "state": entry["state"],
                    "depth_cm": int(depth),
                    "cad_median_mm": block.get("median"),
                    "cad_mean_mm": block.get("mean"),
                    "cad_sd_mm": block.get("sd"),
                    "cad_p10_mm": block.get("p10"),
                    "cad_p90_mm": block.get("p90"),
                    "valid_fraction": (
                        block.get("n", 0) / entry["depth_stats"].get("window_pixels", 1)
                        if block.get("status") == "ok"
                        else None
                    ),
                }
            )
    if rows:
        with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
    print(f"concluído: {out['n_municipalities']}/{out['n_requested']} municípios; "
          f"{out['elapsed_s']} s; manifesto: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
