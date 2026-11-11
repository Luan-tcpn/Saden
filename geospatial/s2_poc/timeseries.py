"""Série temporal exploratória 2023–2025 (Checkpoint E).

Regras metodológicas aplicadas:

* a unidade é o **mês de aquisição**; cada linha preserva o item STAC, a
  data/hora real, o baseline e a máscara aplicada;
* a seleção de cena considera a **fração obstruída sobre a AOI** (classes SCL
  de nuvem/sombra/saturado/nodata), não apenas ``eo:cloud_cover`` do tile;
* meses sem observação utilizável são marcados ``no_usable_observation`` com o
  motivo — **nunca** são preenchidos, interpolados ou repetidos;
* a grade, a máscara e a conversão radiométrica são as mesmas de todos os
  meses (20 m, ``EPSG:32721``, Perfil A), o que torna a série comparável.
"""

from __future__ import annotations

import csv
import os
from datetime import datetime, timezone
from typing import Any, Iterable, Sequence

import numpy as np

from . import config

SERIES_CSV_COLUMNS = [
    "month",
    "status",
    "reason",
    "item_id",
    "datetime",
    "tile",
    "baseline",
    "cloud_cover_tile_pct",
    "obstruction_fraction_aoi",
    "scl_profile",
    "index",
    "total_pixels",
    "valid_pixels",
    "valid_fraction",
    "area_km2_valid",
    "min",
    "max",
    "mean",
    "median",
    "std",
    "p05",
    "p25",
    "p75",
    "p95",
    "out_of_range_pixels",
    "degenerate_pixels",
    "scene_count",
]

STATUS_OBSERVED = "observed"
STATUS_MISSING = "no_usable_observation"

# Motivos possíveis para um mês sem observação.
REASON_NO_SCENE = "no_covering_scene_in_catalog"
REASON_ALL_CLOUDY = "all_candidates_exceed_max_obstruction"
REASON_UNSUPPORTED = "no_supported_baseline"


def _parse_month_start(value: str) -> datetime:
    """Aceita ``YYYY-MM`` ou ``YYYY-MM-DD``."""
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError(f"data de início inválida: {value!r}")


def month_range(start: str, end: str) -> list[str]:
    """Lista de meses ``YYYY-MM`` entre ``start`` e ``end`` (inclusive)."""
    begin = _parse_month_start(start)
    finish = _parse_month_start(end)
    if finish < begin:
        raise ValueError(f"intervalo inválido: {start} … {end}")
    months: list[str] = []
    year, month = begin.year, begin.month
    while (year, month) <= (finish.year, finish.month):
        months.append(f"{year:04d}-{month:02d}")
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return months


def obstruction_fraction(
    scl: np.ndarray,
    obstruction_classes: Iterable[int] = config.SCL_OBSTRUCTION_CLASSES,
) -> dict[str, Any]:
    """Fração de pixels obstruídos (nuvem/sombra/saturado/nodata) sobre a AOI.

    É esta métrica — e não o ``eo:cloud_cover`` do tile inteiro — que decide a
    qualidade da cena sobre a área de interesse.
    """
    arr = np.asarray(scl)
    total = int(arr.size)
    classes = tuple(sorted(set(int(c) for c in obstruction_classes)))
    obstructed = np.isin(arr, classes)
    count = int(np.count_nonzero(obstructed))
    return {
        "total_pixels": total,
        "obstructed_pixels": count,
        "obstruction_fraction": (count / total) if total else 0.0,
        "obstruction_classes": list(classes),
        "coverage_fraction": 1.0 - ((count / total) if total else 0.0),
    }


def choose_best_candidate(
    candidates: Sequence[dict[str, Any]],
) -> tuple[dict[str, Any] | None, str]:
    """Escolhe a melhor candidata do mês de forma determinística.

    Cada candidata traz ``obstruction_fraction`` (sobre a AOI) e
    ``cloud_cover`` (do tile). Critério: menor obstrução; empate → menor
    nuvem do tile; empate → menor ``item_id``.
    """
    if not candidates:
        return None, REASON_NO_SCENE
    ranked = sorted(
        candidates,
        key=lambda c: (
            float(c.get("obstruction_fraction", 1.0)),
            float(c.get("cloud_cover") or 999.0),
            str(c.get("item_id", "")),
        ),
    )
    return ranked[0], "selected"


def missing_month_record(month: str, reason: str, candidates: int = 0) -> dict[str, Any]:
    """Registro explícito de mês sem observação (sem valores inventados)."""
    return {
        "month": month,
        "status": STATUS_MISSING,
        "reason": reason,
        "candidate_scenes": candidates,
        "item_id": None,
        "datetime": None,
        "indices": {},
    }


def observed_month_record(
    month: str,
    item_id: str,
    datetime_iso: str,
    tile: str | None,
    baseline: float | None,
    cloud_cover: float | None,
    obstruction: float,
    profile: str,
    indices: dict[str, Any],
    scene_count: int = 1,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "month": month,
        "status": STATUS_OBSERVED,
        "reason": None,
        "candidate_scenes": scene_count,
        "item_id": item_id,
        "datetime": datetime_iso,
        "tile": tile,
        "baseline": baseline,
        "cloud_cover": cloud_cover,
        "obstruction_fraction": obstruction,
        "scl_profile": profile,
        "indices": indices,
        "scene_count": scene_count,
        "extra": extra or {},
    }


def series_rows(
    records: Sequence[dict[str, Any]],
    area_per_pixel_km2: float = 0.0004,
) -> list[dict[str, Any]]:
    """Achata os registros mensais em linhas CSV (uma por mês × índice)."""
    rows: list[dict[str, Any]] = []
    for record in records:
        month = record["month"]
        if record["status"] != STATUS_OBSERVED:
            row = {col: None for col in SERIES_CSV_COLUMNS}
            row.update(
                {
                    "month": month,
                    "status": record["status"],
                    "reason": record.get("reason"),
                    "scene_count": 0,
                    "total_pixels": None,
                }
            )
            rows.append(row)
            continue
        for name, stats in record["indices"].items():
            row = {col: None for col in SERIES_CSV_COLUMNS}
            row.update(
                {
                    "month": month,
                    "status": record["status"],
                    "reason": record.get("reason"),
                    "item_id": record.get("item_id"),
                    "datetime": record.get("datetime"),
                    "tile": record.get("tile"),
                    "baseline": record.get("baseline"),
                    "cloud_cover_tile_pct": record.get("cloud_cover"),
                    "obstruction_fraction_aoi": record.get("obstruction_fraction"),
                    "scl_profile": record.get("scl_profile"),
                    "index": name,
                    "total_pixels": stats.get("total_pixels"),
                    "valid_pixels": stats.get("valid_pixels"),
                    "valid_fraction": stats.get("valid_fraction"),
                    "area_km2_valid": (
                        stats.get("valid_pixels") * area_per_pixel_km2
                        if stats.get("valid_pixels") is not None
                        else None
                    ),
                    "min": stats.get("min"),
                    "max": stats.get("max"),
                    "mean": stats.get("mean"),
                    "median": stats.get("median"),
                    "std": stats.get("std"),
                    "p05": stats.get("p05"),
                    "p25": stats.get("p25"),
                    "p75": stats.get("p75"),
                    "p95": stats.get("p95"),
                    "out_of_range_pixels": stats.get("out_of_range_pixels"),
                    "degenerate_pixels": stats.get("degenerate_pixels"),
                    "scene_count": record.get("scene_count", 1),
                }
            )
            rows.append(row)
    return rows


def write_series_csv(rows: Sequence[dict[str, Any]], path: str) -> str:
    """Grava a série mensal em CSV (UTF-8 BOM, abre no Excel)."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=SERIES_CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in SERIES_CSV_COLUMNS})
    return path


def series_summary(records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Resumo auditável da série: cobertura mensal e lacunas."""
    observed = [r for r in records if r["status"] == STATUS_OBSERVED]
    missing = [r for r in records if r["status"] != STATUS_OBSERVED]
    reasons: dict[str, list[str]] = {}
    for record in missing:
        reasons.setdefault(str(record.get("reason")), []).append(record["month"])
    return {
        "months_total": len(records),
        "months_observed": len(observed),
        "months_missing": len(missing),
        "missing_months": [r["month"] for r in missing],
        "missing_reasons": {k: sorted(v) for k, v in reasons.items()},
        "observed_items": [
            {"month": r["month"], "item_id": r.get("item_id"), "datetime": r.get("datetime")}
            for r in observed
        ],
        "baselines": sorted({r.get("baseline") for r in observed if r.get("baseline") is not None}),
        "note": (
            "Meses ausentes não foram preenchidos, interpolados ou repetidos; "
            "as lacunas são reais do catálogo/qualidade."
        ),
    }


def run_utc() -> str:
    return datetime.now(timezone.utc).isoformat()
