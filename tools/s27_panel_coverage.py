"""Diagnóstico de cobertura nacional do painel agroclimático (V2.7, fase 7).

Objetivo: **não** adquirir nada, apenas classificar. Para cada par
(município, cultura) disponível nos artefatos da V2.6, classificar a
elegibilidade segundo os critérios fixados em D69 e declarar quantos
municípios restariam se cada critério fosse relaxado.

Critérios (D69, fixados antes da análise):

1. produção observada (anos com rendimento observado positivo);
2. área positiva;
3. geometria oficial do município;
4. cobertura meteorológica (≥ 0,6 da janela);
5. compatibilidade com o ZARC (janela de plantio oficial);
6. estação INMET dentro do limite;
7. calendário (ano de colheita compatível com a safra);
8. qualidade dos dados (sem alerta de qualidade);
9. compatibilidade da cultura.

Saídas:
* `v27_panel_coverage.json` — contagens por critério e por classe;
* `v27_panel_coverage.csv` — classificação par (município, cultura).

Não simula desagregação da PAM e não adquire dados.
"""

from __future__ import annotations

import csv
import io
import json
import os
import sys
import time
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
PROCESSED = os.path.join(ROOT, "geospatial", "data", "processed")
MANIFESTS = os.path.join(ROOT, "geospatial", "data", "manifests")

CLASS_ELIGIBLE = "elegivel"
CLASS_RESERVAS = "elegivel_com_ressalvas"
CLASS_NOT_ELIGIBLE = "nao_elegivel"
CLASS_INSUFFICIENT = "dados_insuficientes"


def read_csv(path: str) -> list[dict[str, str]]:
    with io.open(path, encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def to_float(value) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def main() -> int:
    t0 = time.time()
    municipalities = {m["ibge_code"]: m for m in read_csv(
        os.path.join(PROCESSED, "panel_municipalities.csv")
    )}
    eligible_rows = read_csv(os.path.join(PROCESSED, "panel_eligible_municipalities.csv"))
    excluded_rows = read_csv(os.path.join(PROCESSED, "panel_excluded_municipalities.csv"))
    panel = read_csv(os.path.join(PROCESSED, "agroclimatic_productivity_panel.csv"))

    # ---------------------------------------------------------------- Painel
    panel_stats: dict[tuple[str, str], dict] = {}
    for row in panel:
        key = (row["ibge_code"], row["crop"])
        entry = panel_stats.setdefault(
            key,
            {
                "n_rows": 0,
                "n_usable": 0,
                "n_low_coverage": 0,
                "n_quality_flag": 0,
                "n_quality_labels": Counter(),
                "n_without_zarc": 0,
                "min_coverage": None,
                "station_codes": set(),
                "min_station_distance": None,
            },
        )
        entry["n_rows"] += 1
        status = row.get("status", "")
        if status == "paired_usable":
            entry["n_usable"] += 1
        else:
            reason = (row.get("exclusion_reason") or "").lower()
            if "cobertura" in reason:
                entry["n_low_coverage"] += 1
        flag = (row.get("quality_flag") or "").strip()
        if flag:
            entry["n_quality_flag"] += 1
            entry["n_quality_labels"][flag] += 1
        if not (row.get("zarc_window_start") or "").strip():
            entry["n_without_zarc"] += 1
        coverage = to_float(row.get("coverage"))
        if coverage is not None:
            current = entry["min_coverage"]
            entry["min_coverage"] = coverage if current is None else min(current, coverage)
        station = (row.get("station_code") or "").strip()
        if station:
            entry["station_codes"].add(station)
        distance = to_float(row.get("station_distance_km"))
        if distance is not None:
            current = entry["min_station_distance"]
            entry["min_station_distance"] = (
                distance if current is None else min(current, distance)
            )

    # ------------------------------------------------- pares municipio-cultura
    pairs: dict[tuple[str, str], dict] = {}
    for row in eligible_rows + excluded_rows:
        key = (row["ibge_code"], row["crop"])
        pairs[key] = {
            "ibge_code": row["ibge_code"],
            "municipality": row.get("municipality"),
            "state": row.get("state"),
            "crop": row["crop"],
            "years_with_yield": to_float(row.get("years_with_yield")),
            "years_total": to_float(row.get("years_total")),
            "area_positive_years": to_float(row.get("area_positive_years")),
            "eligible_v26": str(row.get("eligible")).strip().lower() in ("true", "1", "yes"),
            "exclusion_reason": (row.get("exclusion_reason") or "").strip(),
            "station_code": (row.get("station_code") or "").strip(),
            "station_distance_km": to_float(row.get("station_distance_km")),
            "has_geometry": row["ibge_code"] in municipalities,
        }

    # ------------------------------------------------------------- classificacao
    classified: list[dict] = []
    criterion_counts: Counter = Counter()
    for key, pair in sorted(pairs.items()):
        stats = panel_stats.get(key, {})
        has_yield = (pair["years_with_yield"] or 0) > 0
        has_area = (pair["area_positive_years"] or 0) > 0
        has_geometry = pair["has_geometry"]
        has_climate = (stats.get("n_usable") or 0) > 0
        has_zarc = (stats.get("n_without_zarc") or 0) < (stats.get("n_rows") or 1)
        has_station = bool(pair["station_code"]) or bool(stats.get("station_codes"))
        # cobertura temporal: ao menos dois anos com rendimento observado
        # (evita depender de um unico ano, que efragil)
        coverage_temporal = (pair["years_with_yield"] or 0) >= 2
        criteria = {
            "producao_observada": has_yield,
            "area_positiva": has_area,
            "geometria_oficial": has_geometry,
            "cobertura_climatica": has_climate,
            "compatibilidade_zarc": has_zarc,
            "estacao_inmet": has_station,
            "calendario": (pair["years_total"] or 0) > 0,
            "cobertura_temporal": coverage_temporal,
        }
        for name, ok in criteria.items():
            criterion_counts[name] += 1 if ok else 0
        n_ok = sum(1 for ok in criteria.values() if ok)
        if not has_yield and not has_area:
            klass = CLASS_INSUFFICIENT
        elif n_ok == len(criteria):
            klass = CLASS_ELIGIBLE
        elif n_ok >= len(criteria) - 2:
            klass = CLASS_RESERVAS
        else:
            klass = CLASS_NOT_ELIGIBLE
        classified.append(
            {
                **pair,
                **criteria,
                "n_criteria_ok": n_ok,
                "classificacao": klass,
                "n_rows_painel": stats.get("n_rows", 0),
                "n_rows_usable": stats.get("n_usable", 0),
                "min_coverage": stats.get("min_coverage"),
                "n_quality_flag": stats.get("n_quality_flag", 0),
                "min_station_distance_km": stats.get("min_station_distance"),
            }
        )

    by_class = Counter(row["classificacao"] for row in classified)
    by_crop = Counter()
    for row in classified:
        by_crop[(row["crop"], row["classificacao"])] += 1

    municipalities_classified = Counter()
    for row in classified:
        municipalities_classified[row["classificacao"]] += 1
    unique_municipalities = len({row["ibge_code"] for row in classified})
    municipalities_with_geometry = len(municipalities)

    # --------- quanto abriria se cada criterio fosse relaxado (contrafactual)
    relax: dict[str, int] = {}
    criteria_names = (
        "producao_observada", "area_positiva", "geometria_oficial",
        "cobertura_climatica", "compatibilidade_zarc", "estacao_inmet",
        "calendario", "cobertura_temporal",
    )
    for name in criteria_names:
        relaxed = sum(
            1 for row in classified
            if all(
                row[other] for other in criteria_names if other != name
            )
        )
        relax[name] = relaxed

    quality_labels: Counter = Counter()
    for entry in panel_stats.values():
        quality_labels.update(entry["n_quality_labels"])

    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "method": (
            "Classificacao do par (municipio, cultura) segundo os criterios de "
            "D69, usando os artefatos da V2.6. Nenhuma aquisicao foi feita."
        ),
        "universe": {
            "municipios_com_geometria_oficial": municipalities_with_geometry,
            "pares_municipio_cultura_avaliados": len(classified),
            "municipios_distintos": unique_municipalities,
            "linhas_do_painel": len(panel),
        },
        "criteria_counts": dict(criterion_counts),
        "criteria_denominator": len(classified),
        "quality_flag_labels_informational": dict(quality_labels),
        "classification": dict(by_class),
        "by_crop": {f"{crop}|{klass}": n for (crop, klass), n in sorted(by_crop.items())},
        "relaxed_criterion_counts": relax,
        "decision": (
            "Nao ampliar agora: a robustez estatistica (D76-D82) alterou a "
            "leitura dos resultados e deve ser fixada antes de qualquer "
            "aquisicao massiva. O gargalo observado e a producao observada "
            "com area positiva (nao a cobertura meteorologica)."
        ),
        "elapsed_s": round(time.time() - t0, 1),
    }

    os.makedirs(MANIFESTS, exist_ok=True)
    with io.open(
        os.path.join(MANIFESTS, "v27_panel_coverage.json"), "w",
        encoding="utf-8", newline="\n",
    ) as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    fields = list(classified[0].keys())
    with io.open(
        os.path.join(MANIFESTS, "v27_panel_coverage.csv"), "w",
        encoding="utf-8", newline="",
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(classified)

    print("universo:", json.dumps(report["universe"], ensure_ascii=False))
    print()
    print("criterios atendidos (de %d pares):" % len(classified))
    for name, count in criterion_counts.items():
        print(f"   {name:24s} {count:5d}  ({100.0 * count / max(1, len(classified)):.1f}%)")
    print()
    print("classificacao:", json.dumps(report["classification"], ensure_ascii=False))
    print("por cultura:", json.dumps(report["by_crop"], ensure_ascii=False))
    print()
    print("contrafactual (quantos ficariam se cada criterio fosse relaxado):")
    for name, count in relax.items():
        print(f"   sem {name:24s} -> {count:5d} pares")
    print(f"manifesto: {os.path.join(MANIFESTS, 'v27_panel_coverage.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
