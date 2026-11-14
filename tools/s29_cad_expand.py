"""V2.9 — expansão da cobertura de CAD (Embrapa Solos / GeoInfo) (D93).

A V2.8 mediu a CAD em 10 municípios (5 deles no painel) usando janelas de
0,2° na resolução nativa de 90 m. Expandir assim custaria dezenas de GB.

Este script usa a **extensão de escala do WCS 2.0.1** para obter a mesma
camada em resolução reduzida: ``scaleFactor=0.2`` (≈450 m) reduz o volume em
~60× (medido: 4,195 MB → 0,066 MB por janela de 0,5°). Com isso a cobertura
do painel inteiro fica na ordem de centenas de MB, e não dezenas de GB.

O que é calculado por município (bbox oficial do painel):

* por camada: mediana, p10, p90, fração válida;
* por **pixel**: CAD integrada (Σ AW × espessura) — só onde todas as camadas
  são válidas — e então p10/p50/p90 dessa distribuição;
* CAD do perfil em 0–60, 0–100 e 0–200 cm.

A agregação é por **bbox**, não pelo polígono municipal: inclui área vizinha
em municípios de forma irregular. Isso é declarado como limitação; a mediana
é robusta a uma minoria de pixels vizinhos, mas não a todos.

Uso:
    python tools/s29_cad_expand.py --pilot 24
    python tools/s29_cad_expand.py --full          # retomável
    python tools/s29_cad_expand.py --full --scale 0.1
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import ssl
import statistics
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "geospatial"))

from agroclimate import soil  # noqa: E402

BASE = "https://geoinfo.dados.embrapa.br/geoserver/ows"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SADEN-V2.9"}
TIMEOUT = 120
RETRIES = 2
PROCESSED = os.path.join(ROOT, "geospatial", "data", "processed")
MANIFESTS = os.path.join(ROOT, "geospatial", "data", "manifests")
OUT_JSON = os.path.join(MANIFESTS, "v29_cad_expansion.json")

LAYERS = tuple((layer["key"], layer["coverage_id"]) for layer in soil.AW_LAYERS)
DEPTHS_CM = (60.0, 100.0, 200.0)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def fetch(coverage_id: str, lat0: float, lat1: float, lon0: float, lon1: float, scale: float):
    url = (
        f"{BASE}?service=WCS&version=2.0.1&request=GetCoverage"
        f"&coverageId={coverage_id}&format=image/tiff"
        f"&subset=Lat({lat0:.6f},{lat1:.6f})&subset=Long({lon0:.6f},{lon1:.6f})"
        f"&scaleFactor={scale}"
    )
    last = ""
    for attempt in range(RETRIES + 1):
        try:
            request = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(request, timeout=TIMEOUT, context=_context()) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            last = f"HTTP {exc.code}"
            if exc.code == 429:
                time.sleep(5 * (attempt + 1))
                continue
            return None
        except Exception as exc:  # noqa: BLE001
            last = f"{type(exc).__name__}: {exc}"
            time.sleep(2 * (attempt + 1))
    return {"error": last}


def read_array(data: bytes) -> np.ndarray | None:
    import rasterio
    from rasterio.io import MemoryFile

    with MemoryFile(data) as memfile:
        with memfile.open() as dataset:
            array = dataset.read(1).astype("float64")
            nodata = dataset.nodata
    if nodata is not None:
        array[array == nodata] = np.nan
    array[array <= 0] = np.nan
    return array


def summarize(values: np.ndarray) -> dict[str, Any]:
    valid = values[np.isfinite(values)]
    if valid.size == 0:
        return {"valid_fraction": 0.0, "n_valid": 0}
    return {
        "valid_fraction": float(valid.size / values.size),
        "n_valid": int(valid.size),
        "median": float(np.median(valid)),
        "p10": float(np.quantile(valid, 0.10)),
        "p90": float(np.quantile(valid, 0.90)),
        "mean": float(valid.mean()),
    }


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_municipalities() -> list[dict[str, Any]]:
    path = os.path.join(PROCESSED, "panel_municipalities.csv")
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def panel_codes() -> set[str]:
    path = os.path.join(PROCESSED, "agroclimatic_productivity_panel.csv")
    codes: set[str] = set()
    with open(path, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            if str(row.get("status")) == "paired_usable" and str(
                row.get("climate_source")
            ) == "NASA-POWER":
                codes.add(str(row.get("ibge_code")))
    return codes


def select_pilot(municipalities: list[dict[str, Any]], n: int) -> list[dict[str, Any]]:
    """Piloto estratificado por UF: municípios do painel, ordenados por área."""
    codes = panel_codes()
    usable = [
        m
        for m in municipalities
        if str(m.get("ibge_code")) in codes
        and _to_float(m.get("bbox_min_lat")) is not None
        and _to_float(m.get("area_km2")) is not None
    ]
    by_state: dict[str, list[dict[str, Any]]] = {}
    for record in usable:
        by_state.setdefault(str(record.get("state")), []).append(record)
    states = sorted(by_state)
    per_state = max(1, n // max(len(states), 1))
    chosen: list[dict[str, Any]] = []
    for state in states:
        rows = sorted(by_state[state], key=lambda r: -(_to_float(r.get("area_km2")) or 0.0))
        # pega municípios ao longo da distribuição de área (grande, médio, pequeno)
        if not rows:
            continue
        picks = [rows[0], rows[len(rows) // 2], rows[-1]][:per_state]
        chosen.extend(picks)
    return chosen[:n]


def run(municipalities: list[dict[str, Any]], scale: float, delay: float, out: dict) -> None:
    done = {str(r["ibge_code"]) for r in out.get("municipalities", [])}
    consecutive_failures = 0
    for index, record in enumerate(municipalities, start=1):
        code = str(record["ibge_code"])
        if code in done:
            continue
        lat0 = _to_float(record.get("bbox_min_lat"))
        lat1 = _to_float(record.get("bbox_max_lat"))
        lon0 = _to_float(record.get("bbox_min_lon"))
        lon1 = _to_float(record.get("bbox_max_lon"))
        if None in (lat0, lat1, lon0, lon1):
            continue
        arrays: dict[str, np.ndarray] = {}
        failed: list[str] = []
        for key, coverage_id in LAYERS:
            data = fetch(coverage_id, lat0, lat1, lon0, lon1, scale)
            if data is None or isinstance(data, dict):
                failed.append(key)
                continue
            try:
                array = read_array(data)
            except Exception:  # noqa: BLE001
                failed.append(key)
                continue
            if array is None:
                failed.append(key)
                continue
            arrays[key] = array
            time.sleep(delay)
        entry: dict[str, Any] = {
            "ibge_code": code,
            "municipality": record.get("municipality"),
            "state": record.get("state"),
            "bbox": [lon0, lat0, lon1, lat1],
            "scale_factor": scale,
            "layers": {key: summarize(values) for key, values in arrays.items()},
            "failed_layers": failed,
        }
        # integrações por profundidade a partir das medianas por camada
        medians = {
            key: (entry["layers"][key].get("median") if key in entry["layers"] else None)
            for key, _ in LAYERS
        }
        for depth in DEPTHS_CM:
            result = soil.profile_capacity_to_depth_mm(medians, depth)
            entry[f"cad_0_{int(depth)}_cm_mm"] = result["capacity_mm"]
        # distribuição **por pixel** da CAD, usando só as camadas do perfil
        for depth in DEPTHS_CM:
            selected = [
                layer for layer in soil.AW_LAYERS if float(layer["top_cm"]) <= depth
            ]
            keys = [layer["key"] for layer in selected]
            if not all(k in arrays for k in keys):
                continue
            shapes = {arrays[k].shape for k in keys}
            if len(shapes) != 1:
                entry[f"cad_0_{int(depth)}_pixels"] = {"status": "grid_mismatch"}
                continue
            thickness = np.array(
                [soil.layer_thickness_cm(layer) for layer in selected], dtype="float64"
            ).reshape(-1, 1, 1)
            stack = np.stack([arrays[k] for k in keys])
            cad_pixel = np.nansum(stack * thickness, axis=0)
            cad_pixel[np.isnan(stack).any(axis=0)] = np.nan
            valid = cad_pixel[np.isfinite(cad_pixel)]
            if valid.size == 0:
                entry[f"cad_0_{int(depth)}_pixels"] = {"status": "no_valid_pixels"}
                continue
            entry[f"cad_0_{int(depth)}_pixels"] = {
                "median": float(np.median(valid)),
                "p10": float(np.quantile(valid, 0.10)),
                "p90": float(np.quantile(valid, 0.90)),
                "n_valid_pixels": int(valid.size),
                "valid_fraction": float(valid.size / cad_pixel.size),
            }
        out["municipalities"].append(entry)
        if failed:
            consecutive_failures += 1
        else:
            consecutive_failures = 0
        out["updated_at"] = _now()
        out["n_done"] = len(out["municipalities"])
        os.makedirs(MANIFESTS, exist_ok=True)
        with open(OUT_JSON, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(out, handle, ensure_ascii=False, indent=2, default=str)
            handle.write("\n")
        if index % 25 == 0:
            print(f"  {index}/{len(municipalities)} municípios", flush=True)
        if consecutive_failures >= 10:
            print("  [parada] 10 falhas consecutivas — serviço indisponível", flush=True)
            out["stopped_reason"] = "consecutive_failures"
            break


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", type=int, default=0)
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--scale", type=float, default=0.2)
    parser.add_argument("--delay", type=float, default=0.05)
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    municipalities = load_municipalities()
    if args.pilot:
        selected = select_pilot(municipalities, args.pilot)
        mode = f"pilot_{args.pilot}"
    elif args.full:
        codes = panel_codes()
        selected = [
            m
            for m in municipalities
            if str(m.get("ibge_code")) in codes
            and _to_float(m.get("bbox_min_lat")) is not None
        ]
        mode = "full_panel"
    else:
        parser.error("use --pilot N ou --full")
        return 2

    if args.reset and os.path.exists(OUT_JSON):
        os.remove(OUT_JSON)
    out: dict[str, Any] = {
        "generated_at": _now(),
        "mode": mode,
        "scale_factor": args.scale,
        "source": soil.AW_SOURCE,
        "license": soil.AW_LICENSE,
        "unit": soil.AW_UNIT,
        "note": (
            "Agregacao por bbox do municipio (nao pelo poligono): inclui area "
            "vizinha em municipios irregulares. Medianas e quantis sao "
            "robustos a uma minoria de pixels vizinhos, nao a todos."
        ),
        "municipalities": [],
    }
    if os.path.exists(OUT_JSON) and not args.reset:
        try:
            out = json.load(open(OUT_JSON, encoding="utf-8"))
        except json.JSONDecodeError:
            pass
        out["mode"] = mode
        out["scale_factor"] = args.scale
    print(f"modo {mode}: {len(selected)} municípios, scaleFactor={args.scale}", flush=True)
    run(selected, args.scale, args.delay, out)
    out["generated_at"] = out.get("generated_at") or _now()
    out["n_target"] = len(selected)
    with open(OUT_JSON, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(out, handle, ensure_ascii=False, indent=2, default=str)
        handle.write("\n")
    with_values = [
        r for r in out["municipalities"] if r.get("cad_0_100_pixels")
    ]
    if with_values:
        medians = [r["cad_0_100_pixels"]["median"] for r in with_values]
        print(
            f"concluído: {len(out['municipalities'])} municípios; "
            f"CAD 0-100 (mediana por município) min={min(medians):.1f} "
            f"mediana={statistics.median(medians):.1f} max={max(medians):.1f} mm"
        )
    print(f"manifesto: {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
