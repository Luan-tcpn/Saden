"""Amostra geográfica controlada da CAD (Embrapa Solos / GeoInfo).

Para um conjunto **controlado** de municípios do painel da V2.7, baixa
uma janela pequena de cada uma das 6 camadas de água disponível do solo
(Vasques et al., 2021; CC BY-NC 3.0 BR), calcula o valor mediano por
camada (mm/cm), integra a **capacidade de água disponível do perfil** (mm)
e compara com os cenários de 35/50/70 mm da V2.6.

Características:
* apenas janelas pequenas (padrão 0,2°) — volume controlado;
* até 2 tentativas adicionais em erro transitório, com espera crescente;
* ausência de dado é preservada (``None``), nunca preenchida;
* resultado gravado em ``v27_cad_sample.json`` e ``v27_cad_sample.csv``.

Uso:
    python tools/s27_cad_sample.py --sample 12
    python tools/s27_cad_sample.py --sample 12 --window-deg 0.2
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "geospatial"))

from agroclimate import soil  # noqa: E402

BASE = "https://geoinfo.dados.embrapa.br/geoserver/ows"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SADEN-V2.7"}
TIMEOUT = 180
RETRIES = 2
MANIFESTS = os.path.join(ROOT, "geospatial", "data", "manifests")
PROCESSED = os.path.join(ROOT, "geospatial", "data", "processed")


def context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def fetch_coverage(coverage_id: str, lat0: float, lat1: float, lon0: float, lon1: float):
    """Baixa a cobertura (GeoTIFF) de uma janela. Retorna bytes ou ``None``."""
    url = (
        f"{BASE}?service=WCS&version=2.0.1&request=GetCoverage"
        f"&coverageId={coverage_id}&format=image/tiff"
        f"&subset=Lat({lat0:.6f},{lat1:.6f})&subset=Long({lon0:.6f},{lon1:.6f})"
    )
    last = ""
    for attempt in range(RETRIES + 1):
        try:
            request = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(
                request, timeout=TIMEOUT, context=context()
            ) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            last = f"HTTP {exc.code}"
            if exc.code == 429:
                delay = 5 * (attempt + 1)
                time.sleep(delay)
                continue
            return None
        except Exception as exc:
            last = f"{type(exc).__name__}: {exc}"
            time.sleep(2 * (attempt + 1))
    print(f"    [aviso] falha em {coverage_id}: {last}")
    return None


def read_window(data: bytes):
    """Estatísticas de uma janela GeoTIFF em memória."""
    import rasterio
    from rasterio.io import MemoryFile

    with MemoryFile(data) as memfile:
        with memfile.open() as src:
            array = src.read(1, masked=True)
            nodata = src.nodata
            values = np.asarray(array.compressed(), dtype="float64")
            valid = int(array.count())
            total = int(array.size)
            if values.size == 0:
                return {
                    "median": None,
                    "mean": None,
                    "min": None,
                    "max": None,
                    "valid_pixels": valid,
                    "total_pixels": total,
                    "valid_fraction": 0.0,
                    "nodata": nodata,
                    "crs": str(src.crs),
                    "resolution_deg": list(src.res),
                }
            return {
                "median": float(np.median(values)),
                "mean": float(np.mean(values)),
                "min": float(np.min(values)),
                "max": float(np.max(values)),
                "valid_pixels": valid,
                "total_pixels": total,
                "valid_fraction": valid / total if total else 0.0,
                "nodata": nodata,
                "crs": str(src.crs),
                "resolution_deg": list(src.res),
            }


def select_sample(municipalities: list[dict], n: int) -> list[dict]:
    """Amostra espacialmente estratificada (grade lat/lon)."""
    grid: dict[tuple[int, int], list[dict]] = {}
    for row in municipalities:
        try:
            lat = float(row["centroid_lat"])
            lon = float(row["centroid_lon"])
        except (TypeError, ValueError):
            continue
        if not (-34.0 <= lat <= 6.0 and -74.0 <= lon <= -34.0):
            continue
        key = (int((lat + 34) // 4), int((lon + 74) // 6))
        grid.setdefault(key, []).append(row)
    keys = sorted(grid)
    chosen: list[dict] = []
    step = max(1, len(keys) // max(1, n))
    for index, key in enumerate(keys):
        if len(chosen) >= n:
            break
        if index % step and len(chosen) < n:
            continue
        candidates = grid[key]
        candidates.sort(key=lambda r: float(r.get("area_km2") or 0))
        chosen.append(candidates[len(candidates) // 2])
    # completa se ainda faltar
    for key in keys:
        if len(chosen) >= n:
            break
        for row in grid[key]:
            if row not in chosen:
                chosen.append(row)
                break
    return chosen[:n]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", type=int, default=12)
    parser.add_argument("--window-deg", type=float, default=0.2)
    args = parser.parse_args()

    t0 = time.time()
    municipalities = []
    path = os.path.join(PROCESSED, "panel_municipalities.csv")
    with io.open(path, encoding="utf-8-sig", newline="") as handle:
        municipalities = list(csv.DictReader(handle))
    selected = select_sample(municipalities, args.sample)
    print(f"amostra: {len(selected)} municípios")

    report: dict = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": soil.AW_SOURCE,
        "license": soil.AW_LICENSE,
        "unit": soil.AW_UNIT,
        "window_deg": args.window_deg,
        "method": (
            "Mediana dos pixels validos de uma janela quadrada centrada no "
            "centroide do municipio, por camada de profundidade; integracao "
            "da CAD em mm (AW mm/cm x espessura da camada em cm)."
        ),
        "scenarios_v26_mm": list(soil.V26_SCENARIO_CAPACITIES_MM),
        "municipalities": [],
    }
    rows: list[dict] = []

    for row in selected:
        lat = float(row["centroid_lat"])
        lon = float(row["centroid_lon"])
        half = args.window_deg / 2.0
        lat0, lat1 = lat - half, lat + half
        lon0, lon1 = lon - half, lon + half
        values: dict[str, float | None] = {}
        stats: dict[str, dict] = {}
        for layer in soil.AW_LAYERS:
            data = fetch_coverage(layer["coverage_id"], lat0, lat1, lon0, lon1)
            if not data:
                values[layer["key"]] = None
                stats[layer["key"]] = {"status": "falha"}
                continue
            info = read_window(data)
            stats[layer["key"]] = info
            values[layer["key"]] = info["median"]
            time.sleep(0.4)
        profile = soil.profile_capacity_mm(values)
        profile_100 = soil.profile_capacity_to_depth_mm(values, 100.0)
        profile_60 = soil.profile_capacity_to_depth_mm(values, 60.0)
        comparison = soil.compare_with_scenarios(profile["capacity_mm"])
        entry = {
            "ibge_code": row["ibge_code"],
            "municipality": row["municipality"],
            "state": row["state"],
            "centroid_lat": lat,
            "centroid_lon": lon,
            "values_mm_per_cm": values,
            "layer_stats": stats,
            "capacity_mm": profile["capacity_mm"],
            "coverage_fraction": profile["coverage_fraction"],
            "profile_complete": profile["profile_complete"],
            "capacity_0_100mm": profile_100["capacity_mm"],
            "capacity_0_60mm": profile_60["capacity_mm"],
            "comparison": comparison,
        }
        report["municipalities"].append(entry)
        print(
            f"  {row['municipality']} ({row['state']}): "
            f"CAD 0-200 = {profile['capacity_mm']} mm | 0-100 = {profile_100['capacity_mm']} "
            f"| cobertura {profile['coverage_fraction']:.2f}",
            flush=True,
        )
        rows.append(
            {
                "ibge_code": row["ibge_code"],
                "municipality": row["municipality"],
                "state": row["state"],
                "lat": lat,
                "lon": lon,
                "cad_0_200_mm": profile["capacity_mm"],
                "cad_0_100_mm": profile_100["capacity_mm"],
                "cad_0_60_mm": profile_60["capacity_mm"],
                "coverage_fraction": profile["coverage_fraction"],
                "ratio_to_50mm": (comparison.get("ratios") or {}).get("50"),
                "closest_scenario_mm": comparison.get("closest_scenario_mm"),
                **{f"aw_{k}": values.get(k) for k in values},
            }
        )

    capacities = [
        e["capacity_0_100mm"] for e in report["municipalities"] if e["capacity_0_100mm"]
    ]
    report["summary"] = {
        "n_municipalities": len(report["municipalities"]),
        "n_with_complete_profile": sum(
            1 for e in report["municipalities"] if e["profile_complete"]
        ),
        "capacity_0_100_mm": {
            "min": min(capacities) if capacities else None,
            "median": float(np.median(capacities)) if capacities else None,
            "max": max(capacities) if capacities else None,
            "mean": float(np.mean(capacities)) if capacities else None,
        },
        "scenario_comparison": {
            "n_above_35mm": sum(1 for c in capacities if c > 35),
            "n_above_50mm": sum(1 for c in capacities if c > 50),
            "n_above_70mm": sum(1 for c in capacities if c > 70),
            "n_total": len(capacities),
        },
    }
    report["elapsed_s"] = round(time.time() - t0, 1)

    os.makedirs(MANIFESTS, exist_ok=True)
    with io.open(
        os.path.join(MANIFESTS, "v27_cad_sample.json"), "w", encoding="utf-8", newline="\n"
    ) as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    if rows:
        with io.open(
            os.path.join(MANIFESTS, "v27_cad_sample.csv"),
            "w",
            encoding="utf-8",
            newline="",
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    print()
    print("resumo:", json.dumps(report["summary"], ensure_ascii=False, indent=1))
    print(f"manifesto: {os.path.join(MANIFESTS, 'v27_cad_sample.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
