"""V2.8 — estratificação por classe de ciclo do ZARC (D89).

O painel carrega ``zarc_cycle``, a **classe de ciclo** publicada pelo ZARC,
por município e safra. Isso não é cultivar: é a classe de duração de ciclo
usada na portaria. A V2.7 construiu a janela fenológica como um cenário
térmico único e registrou, como pendência, investigar a informação de ciclo.

Este script responde a duas perguntas verificáveis:

1. As classes de ciclo implicam **janelas de plantio de durações
   diferentes**? (contagem de meses da janela ZARC por classe)
2. A associação agroclimática **se mantém dentro de cada classe**? É o teste
   de estabilidade da associação à estratificação por ciclo — não uma
   comparação de cultivares.

Onde uma classe concentra a quase totalidade das linhas, a estratificação é
declarada **não conclusiva por falta de dados**, em vez de estimada com
poder desprezível.

Uso:
    python tools/s28_cycle_stratification.py
"""

from __future__ import annotations

import csv
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "geospatial"))

import run_robustness as rr  # noqa: E402
from agroclimate import spatial_inference  # noqa: E402

MANIFESTS = os.path.join(ROOT, "geospatial", "data", "manifests")
OUT = os.path.join(MANIFESTS, "v28_cycle_stratification.json")

CROPS = ("soja", "milho", "milho_2")
VARIABLES = ("deficiency_total_mm", "temp_media_c", "precip_acumulada_mm", "et0_total_mm")
MIN_ROWS_PER_CLASS = 300


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _window_length(months: str) -> int | None:
    if not months:
        return None
    parts = [m for m in str(months).split(";") if m.strip()]
    return len(parts) if parts else None


def attach_cycle(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Reanexa ``zarc_cycle`` e a janela ZARC às linhas analíticas.

    ``analysis.prepare_rows`` usa uma lista fechada de campos e não carrega a
    classe de ciclo. A junção é feita por ``(ibge_code, crop, ano de
    colheita)`` sobre o painel bruto — a mesma chave que define a observação.
    """
    raw = rr.load_panel()
    index: dict[tuple[str, str, str], dict[str, str]] = {}
    duplicates = 0
    for row in raw:
        if str(row.get("status")) != "paired_usable":
            continue
        if str(row.get("climate_source")) != "NASA-POWER":
            continue
        year = row.get("harvest_year") or row.get("pam_reference_year")
        if year in (None, ""):
            continue
        key = (str(row.get("ibge_code")), str(row.get("crop")), str(int(float(year))))
        if key in index:
            duplicates += 1
            continue
        index[key] = {
            "zarc_cycle": str(row.get("zarc_cycle") or ""),
            "zarc_soil": str(row.get("zarc_soil") or ""),
            "zarc_window_months": str(row.get("zarc_window_months") or ""),
        }
    enriched = []
    missing = 0
    for row in rows:
        key = (str(row["ibge_code"]), str(row["crop"]), str(int(row["year"])))
        extra = index.get(key)
        merged = dict(row)
        if extra is None:
            missing += 1
            merged.update({"zarc_cycle": "", "zarc_soil": "", "zarc_window_months": ""})
        else:
            merged.update(extra)
        enriched.append(merged)
    return enriched, {
        "raw_rows_indexed": len(index),
        "duplicate_keys": duplicates,
        "unmatched_rows": missing,
    }


def _estimate(rows, variables, block_key="spatial_block"):
    """Coeficiente within com EP agrupado por bloco espacial."""
    out: dict[str, Any] = {}
    for variable in variables:
        prepared = spatial_inference.within_data(rows, variable)
        if prepared.get("status") != "ok":
            out[variable] = {"status": prepared.get("status")}
            continue
        groups = [str(g) for g in prepared["municipalities"]]
        # `within_data` devolve as linhas efetivamente usadas: a ordem de
        # agrupamento é construída delas, não da lista original
        block_groups = [str(r.get(block_key) or "") for r in prepared["rows"]]
        scheme = {"municipio": groups, "bloco_espacial": block_groups}
        result = spatial_inference.clustered_within_inference(
            prepared, scheme, correction="CR1"
        )
        scheme_out = result.get("schemes", {})
        out[variable] = {
            "status": result.get("status"),
            "coefficient": result.get("coefficient"),
            "n": result.get("n"),
            "municipality": scheme_out.get("municipio", {}),
            "spatial_block": scheme_out.get("bloco_espacial", {}),
        }
    return out


def main() -> int:
    rows = rr.prepare(rr.load_panel())
    rows, join_report = attach_cycle(rows)
    by_crop: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_crop[str(row["crop"])].append(row)

    payload: dict[str, Any] = {
        "generated_at": _now(),
        "note": (
            "zarc_cycle e a classe de ciclo publicada no ZARC, nao a cultivar. "
            "Estratificar por classe testa estabilidade da associacao; nao "
            "identifica material genetico."
        ),
        "join": join_report,
        "min_rows_per_class": MIN_ROWS_PER_CLASS,
        "crops": {},
    }
    for crop in CROPS:
        subset = by_crop.get(crop, [])
        if not subset:
            continue
        classes = Counter(str(r.get("zarc_cycle")) for r in subset)
        window_by_class: dict[str, Counter] = defaultdict(Counter)
        for row in subset:
            length = _window_length(row.get("zarc_window_months"))
            if length is not None:
                window_by_class[str(row.get("zarc_cycle"))][length] += 1
        crop_out: dict[str, Any] = {
            "n_rows": len(subset),
            "classes": dict(classes.most_common()),
            "class_share": {
                name: count / len(subset) for name, count in classes.most_common()
            },
            "window_length_by_class": {
                name: dict(counter.most_common()) for name, counter in window_by_class.items()
            },
            "pooled": _estimate(subset, VARIABLES),
            "by_class": {},
        }
        for name, count in classes.most_common():
            if count < MIN_ROWS_PER_CLASS:
                crop_out["by_class"][name] = {
                    "status": "insufficient_rows",
                    "n_rows": count,
                }
                continue
            class_rows = [r for r in subset if str(r.get("zarc_cycle")) == name]
            crop_out["by_class"][name] = {
                "status": "ok",
                "n_rows": len(class_rows),
                "estimate": _estimate(class_rows, VARIABLES),
            }
        payload["crops"][crop] = crop_out

    os.makedirs(MANIFESTS, exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
        handle.write("\n")

    for crop, entry in payload["crops"].items():
        print(f"{crop}: classes {entry['classes']}")
        for name, block in entry["by_class"].items():
            if block.get("status") != "ok":
                print(f"  cycle {name}: {block['status']} (n={block['n_rows']})")
                continue
            pieces = []
            for variable in ("deficiency_total_mm", "temp_media_c"):
                estimate = block["estimate"].get(variable, {})
                scheme = estimate.get("spatial_block", {})
                if scheme.get("status") == "ok":
                    pieces.append(
                        f"{variable}={estimate['coefficient']:+.4f}"
                        f" (t={scheme['t_statistic']:+.2f})"
                    )
            print(f"  cycle {name}: n={block['n_rows']} " + " | ".join(pieces))
    print(f"manifesto: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
