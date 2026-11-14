"""Pipeline canônico do painel agroclimático.

Este é o **único ponto de entrada oficial** para reconstruir as variáveis de
janela e os descritores hídricos do painel. Ele não reimplementa cálculo: chama
as funções já validadas (`v31_rebuild_panel._aggregate` para a janela corrigida
e `v33_water_variables._descriptors` para o estresse), com configuração
declarativa em `config/panel_v35.json`.

Os scripts históricos continuam existindo e **não** foram convertidos em
wrappers: eles são a única forma de reproduzir os artefatos publicados das
versões anteriores. Ver `tools/legacy/README.md` e `docs/PIPELINE.md`.

Estágios
--------
``validate``  confere configuração, arquivos e cadastro municipal;
``build``     reconstrói janela + água para os municípios pedidos;
``verify``    compara a saída com o painel de referência V3.5;
``all``       validate → build → verify.

Escopo parcial
--------------
``--codes A,B,C`` ou ``--limit N`` restringem os municípios. É o modo usado no
teste de clone limpo; o caminho de código é exatamente o mesmo do build completo.

Uso:
    python tools/pipeline/build_panel.py --stage validate
    python tools/pipeline/build_panel.py --stage build --limit 12
    python tools/pipeline/build_panel.py --stage verify
    python tools/pipeline/build_panel.py --stage all
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable, Sequence

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "geospatial"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from agroclimate import corrections  # noqa: E402
from agroclimate import cycle  # noqa: E402
from agroclimate import evapotranspiration as et_module  # noqa: E402
from agroclimate import thermal  # noqa: E402
from agroclimate import water_balance as wb_module  # noqa: E402

import v31_rebuild_panel as rb  # noqa: E402
import v33_water_variables as wv  # noqa: E402

CONFIG_PATH = os.path.join(ROOT, "config", "panel_v35.json")
BUILD_VERSION = "consolidated-2026-11-14"
DEFAULT_PREFIX = "panel_canonical_v2"
OUT_JSON = os.path.join(ROOT, "geospatial", "data", "manifests", "panel_canonical_build_v2.json")


def output_paths(prefix: str = DEFAULT_PREFIX) -> tuple[str, str]:
    """Saídas versionadas por prefixo — permite build em blocos, sem sobrescrita."""
    base = os.path.join(ROOT, "geospatial", "data", "processed")
    return (
        os.path.join(base, f"{prefix}_windows.csv"),
        os.path.join(base, f"{prefix}_water.csv"),
    )


OUT_PANEL, OUT_WATER = output_paths()

PROFILE_BY_CROP = {"soja": "soja_gilmore", "milho": "milho_embrapa", "milho_2": "milho_embrapa"}
CAD_LABELS = {"cad_0_60": 60, "cad_0_100": 100, "cad_0_200": 200}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_config(path: str = CONFIG_PATH) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        config = json.load(handle)
    config["_path"] = path
    return config


def _abs(relative: str) -> str:
    """Resolve um caminho da configuração.

    ``SADEN_DATA_ROOT`` permite que um clone limpo leia os dados derivados de um
    arquivo externo (eles não cabem no bundle). Só afeta caminhos sob
    ``geospatial/data``; o resto continua relativo ao repositório.
    """
    path = relative.replace("/", os.sep)
    if os.path.isabs(path):
        return path
    data_root = os.environ.get("SADEN_DATA_ROOT")
    prefix = os.path.join("geospatial", "data", "")
    if data_root and path.startswith(prefix):
        return os.path.join(data_root, path[len(prefix):])
    return os.path.join(ROOT, path)


def _num(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _sha(path: str) -> str | None:
    if not os.path.exists(path):
        return None
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


# --------------------------------------------------------------------- validate


def validate(config: dict[str, Any]) -> dict[str, Any]:
    """Confere config, arquivos de entrada e cadastro municipal."""
    inputs = config["inputs"]
    report: dict[str, Any] = {"ok": True, "files": {}, "problems": []}

    for key in ("municipalities", "panel_base_legacy", "panel_base_sp"):
        path = _abs(inputs[key])
        exists = os.path.exists(path)
        report["files"][key] = {
            "path": inputs[key],
            "exists": exists,
            "bytes": os.path.getsize(path) if exists else None,
            "sha256": _sha(path) if exists else None,
        }
        if not exists:
            report["problems"].append(f"entrada ausente: {key}")

    climate_status = []
    for relative in inputs["climate_files"]:
        path = _abs(relative)
        exists = os.path.exists(path)
        climate_status.append(
            {
                "path": relative,
                "exists": exists,
                "bytes": os.path.getsize(path) if exists else None,
                "sha256": _sha(path) if exists else None,
            }
        )
        if not exists:
            report["problems"].append(f"clima ausente: {relative}")
    report["climate_files"] = climate_status

    cad_status = []
    for relative in inputs["cad"]:
        path = _abs(relative)
        exists = os.path.exists(path)
        entry: dict[str, Any] = {"path": relative, "exists": exists}
        if exists:
            payload = json.load(open(path, encoding="utf-8"))
            entry["municipalities"] = len(payload.get("municipalities", {}))
            entry["sha256"] = _sha(path)
        else:
            report["problems"].append(f"CAD ausente: {relative}")
        cad_status.append(entry)
    report["cad_files"] = cad_status

    # cadastro municipal: unicidade, UF coerente e unidades não municipais
    registry_path = _abs(inputs["municipalities"])
    excluded: list[dict[str, str]] = []
    codes: set[str] = set()
    duplicates: list[str] = []
    bad_uf = 0
    states = set(config["states"])
    if os.path.exists(registry_path):
        with open(registry_path, newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                code = str(row.get("ibge_code") or "")
                state = str(row.get("state") or "")
                if state not in states:
                    continue
                name = str(row.get("municipality") or "")
                if any(pattern in name for pattern in config["rules"]["exclude_municipality_name_patterns"]):
                    excluded.append({"ibge_code": code, "municipality": name, "state": state})
                    continue
                if code in codes:
                    duplicates.append(code)
                codes.add(code)
                if int(code) % 10000 == 1 or int(code) % 10000 == 2:
                    if int(code) % 10000 <= 2 and code[2:] in ("00001", "00002"):
                        bad_uf += 1
    report["registry"] = {
        "municipalities_in_scope": len(codes),
        "duplicates": sorted(set(duplicates)),
        "excluded_non_municipal": excluded,
        "n_excluded": len(excluded),
        "suspicious_codes": bad_uf,
    }
    if duplicates:
        report["problems"].append(f"códigos duplicados no cadastro: {sorted(set(duplicates))[:5]}")
    report["ok"] = not report["problems"]
    return report


# ------------------------------------------------------------------------ build


def load_registry(config: dict[str, Any]) -> dict[str, dict[str, str]]:
    states = set(config["states"])
    patterns = config["rules"]["exclude_municipality_name_patterns"]
    out: dict[str, dict[str, str]] = {}
    with open(_abs(config["inputs"]["municipalities"]), newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            state = str(row.get("state") or "")
            if state not in states:
                continue
            name = str(row.get("municipality") or "")
            if any(pattern in name for pattern in patterns):
                continue
            out[str(row["ibge_code"])] = {
                "state": state,
                "municipality": name,
                "centroid_lat": row.get("centroid_lat"),
                "centroid_lon": row.get("centroid_lon"),
            }
    return out


def load_cad(config: dict[str, Any]) -> dict[str, dict[str, float | None]]:
    merged: dict[str, dict[str, float | None]] = {}
    for relative in config["inputs"]["cad"]:
        path = _abs(relative)
        if not os.path.exists(path):
            continue
        payload = json.load(open(path, encoding="utf-8"))
        for code, entry in payload.get("municipalities", {}).items():
            merged[code] = {name: entry.get(f"{name}_mm") for name in CAD_LABELS}
    return merged


def load_panel_rows(config: dict[str, Any], codes: set[str]) -> list[dict[str, Any]]:
    """Linhas analíticas elegíveis dos painéis base (legado + SP)."""
    rules = config["rules"]
    crops = set(config["crops"])
    rows: list[dict[str, Any]] = []
    for key in ("panel_base_legacy", "panel_base_sp"):
        path = _abs(config["inputs"][key])
        if not os.path.exists(path):
            continue
        with open(path, newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                code = str(row.get("ibge_code") or "")
                if code not in codes:
                    continue
                if str(row.get("status")) != rules["require_status"]:
                    continue
                if str(row.get("climate_source")) != rules["require_climate_source"]:
                    continue
                crop = str(row.get("crop"))
                if crop not in crops:
                    continue
                months = [m for m in str(row.get("zarc_window_months") or "").split(";") if m]
                if not months:
                    continue
                rows.append(
                    {
                        "ibge_code": code,
                        "crop": crop,
                        "safra": str(row.get("safra")),
                        "months": months,
                        "state": row.get("state"),
                        "zarc_cycle": str(row.get("zarc_cycle") or ""),
                        "harvest_year": row.get("harvest_year"),
                        "yield_kg_ha": _num(row.get("yield_kg_ha")),
                    }
                )
    return rows


def load_climate(config: dict[str, Any], codes: Sequence[str]):
    """Carrega os arquivos de clima declarados, restringindo aos códigos pedidos.

    O filtro de fonte é explícito, não posicional: ``climate_daily.csv`` contém
    NASA-POWER e INMET sob a mesma chave (município, dia), com valores
    diferentes. Depender da ordem do arquivo escolheria a fonte por acidente.
    Só a fonte declarada em ``rules.require_climate_source`` entra; o descarte é
    contado e devolvido no manifesto.
    """
    index = {code: position for position, code in enumerate(codes)}
    required_source = config["rules"]["require_climate_source"]
    dates: list[str] = []
    day_index: dict[str, int] = {}
    capacity = 4000
    fields = rb.FIELDS
    matrices = {
        field: np.full((len(codes), capacity), np.nan, dtype="float32") for field in fields
    }
    seen: set[tuple[str, str]] = set()
    conflicting = 0
    discarded_other_source: Counter = Counter()
    for relative in config["inputs"]["climate_files"]:
        path = _abs(relative)
        if not os.path.exists(path):
            continue
        with open(path, newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                code = str(row.get("ibge_code") or "")
                if code not in index:
                    continue
                source = str(row.get("source") or "")
                if source != required_source:
                    discarded_other_source[source] += 1
                    continue
                day = str(row.get("date"))
                stamp = (code, day)
                if stamp in seen:
                    conflicting += 1
                    continue
                seen.add(stamp)
                slot = day_index.get(day)
                if slot is None:
                    slot = len(dates)
                    if slot >= capacity:
                        capacity *= 2
                        for field in fields:
                            padded = np.full((len(codes), capacity), np.nan, dtype="float32")
                            padded[:, :slot] = matrices[field][:, :slot]
                            matrices[field] = padded
                    day_index[day] = slot
                    dates.append(day)
                position = index[code]
                for field in fields:
                    value = _num(row.get(field))
                    if value is not None:
                        matrices[field][position, slot] = value
    n_days = len(dates)
    for field in fields:
        matrices[field] = matrices[field][:, :n_days]
    return matrices, dates, {
        "duplicate_code_day_rows": conflicting,
        "n_days": n_days,
        "required_source": required_source,
        "discarded_other_source_rows": dict(discarded_other_source),
    }


def build(
    config: dict[str, Any],
    codes: Iterable[str] | None = None,
    force: bool = False,
    out_prefix: str = DEFAULT_PREFIX,
    states: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Reconstrói janela corrigida e descritores hídricos."""
    started = time.time()
    registry = load_registry(config)
    selected = set(codes) if codes else set(registry)
    if states:
        wanted = {str(item).upper() for item in states}
        selected = {code for code in selected if registry.get(code, {}).get("state") in wanted}
    selected &= set(registry)
    out_panel, out_water = output_paths(out_prefix)
    cad = load_cad(config)
    rows = load_panel_rows(config, selected)
    ordered_codes = sorted({row["ibge_code"] for row in rows})
    matrices, dates, climate_info = load_climate(config, ordered_codes)
    position_of = {code: index for index, code in enumerate(ordered_codes)}
    rules = config["rules"]

    window_rows: list[dict[str, Any]] = []
    water_rows: list[dict[str, Any]] = []
    skipped = {"sem_centroide": 0, "janela_curta": 0}

    by_code: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_code[row["ibge_code"]].append(row)

    for position, code in enumerate(ordered_codes):
        if len(ordered_codes) > 200 and position % 100 == 0:
            print(
                f"  [{position}/{len(ordered_codes)}] {len(window_rows)} linhas "
                f"({time.time() - started:.0f}s)",
                flush=True,
            )
        meta = registry[code]
        latitude = _num(meta.get("centroid_lat"))
        if latitude is None:
            skipped["sem_centroide"] += len(by_code[code])
            continue
        position = position_of[code]
        day_arrays = {field: matrices[field][position] for field in rb.FIELDS}
        for row in by_code[code]:
            profile = thermal.PROFILES.get(PROFILE_BY_CROP.get(row["crop"], ""))
            start_c, end_c = cycle.window_bounds(row["months"], corrected=True)
            days = [i for i, day in enumerate(dates) if start_c <= day <= end_c]
            if len(days) < rules["min_window_days"]:
                skipped["janela_curta"] += 1
                continue
            records = rb._window_records(dates, day_arrays, None, days, latitude)
            record: dict[str, Any] = {
                "ibge_code": code,
                "crop": row["crop"],
                "safra": row["safra"],
                "state": meta["state"],
                "zarc_cycle": row["zarc_cycle"],
                "harvest_year": row["harvest_year"],
                "yield_kg_ha": row["yield_kg_ha"],
                "months": ";".join(row["months"]),
                "n_months_listed": len(row["months"]),
                "n_window_days": len(days),
                "window_start": start_c,
                "window_end": end_c,
            }
            aggregate = rb._aggregate(
                records, profile, latitude, cad_mm=rules["coverage_reference_cad_mm"],
                with_balance=True,
            )
            # física corrigida (D128-D130): ET0 com C1+C2 e balanço com C3.
            # Substitui apenas as variáveis afetadas; o resto da agregação de
            # janela permanece idêntico ao histórico.
            corrected_series = corrections.daily_et0_series(records, float(latitude))
            corrected_monthly = wb_module.daily_to_monthly(corrected_series)
            corrected_balance = corrections.sequential_water_balance(
                corrected_monthly, cad_mm=float(rules["coverage_reference_cad_mm"])
            )
            valid_monthly = [row for row in corrected_balance if row.get("status") == "ok"]
            aggregate["et0_total_mm"] = sum(row["et0_mm"] for row in corrected_monthly)
            aggregate["etp_total_mm"] = aggregate["et0_total_mm"]
            aggregate["deficiency_total_mm"] = sum(row["def_mm"] for row in valid_monthly)
            aggregate["excess_total_mm"] = sum(row["exc_mm"] for row in valid_monthly)
            aggregate["etr_total_mm"] = sum(row["etr_mm"] for row in valid_monthly)
            for key, value in aggregate.items():
                record[f"{key}_corrected"] = value
            record["physics_version"] = corrections.CORRECTION_ID
            for name, depth in CAD_LABELS.items():
                capacity = cad.get(code, {}).get(name)
                if not capacity:
                    continue
                scenario = rb._aggregate(
                    records, profile, latitude, cad_mm=float(capacity), with_balance=True
                )
                scenario_balance = corrections.sequential_water_balance(
                    corrected_monthly, cad_mm=float(capacity)
                )
                scenario_valid = [row for row in scenario_balance if row.get("status") == "ok"]
                scenario["deficiency_total_mm"] = sum(row["def_mm"] for row in scenario_valid)
                scenario["excess_total_mm"] = sum(row["exc_mm"] for row in scenario_valid)
                record[f"deficiency_{name}"] = scenario.get("deficiency_total_mm")
                record[f"excess_{name}"] = scenario.get("excess_total_mm")
                record[f"cad_{name}_mm"] = float(capacity)
            window_rows.append(record)

            series = corrected_series
            precip = {r["date"]: r["precip_mm"] for r in records}
            for item in series:
                item["precip_mm"] = precip.get(str(item.get("date")))
            monthly = wb_module.daily_to_monthly(series)
            for label, depth in wv.CAD_LABELS.items():
                if depth is None:
                    capacity = rules["coverage_reference_cad_mm"]
                else:
                    capacity = cad.get(code, {}).get(label)
                    if not capacity:
                        continue
                balance = corrections.sequential_water_balance(monthly, cad_mm=float(capacity))
                descriptor = wv._descriptors(balance, float(capacity))
                water = {
                    "ibge_code": code,
                    "crop": row["crop"],
                    "safra": row["safra"],
                    "state": meta["state"],
                    "harvest_year": row["harvest_year"],
                    "yield_kg_ha": row["yield_kg_ha"],
                    "scenario": label,
                }
                water.update(descriptor)
                water_rows.append(water)

    _write(window_rows, out_panel, force=force)
    _write(water_rows, out_water, force=force)
    summary = {
        "build_version": BUILD_VERSION,
        "physics_version": corrections.CORRECTION_ID,
        "config": os.path.basename(config["_path"]),
        "config_version": config["version"],
        "municipalities_requested": len(selected),
        "municipalities_in_output": len({row["ibge_code"] for row in window_rows}),
        "window_rows": len(window_rows),
        "water_rows": len(water_rows),
        "skipped": skipped,
        "climate": climate_info,
        "outputs": {
            "panel": os.path.relpath(out_panel, ROOT).replace("\\", "/"),
            "panel_sha256": _sha(out_panel),
            "water": os.path.relpath(out_water, ROOT).replace("\\", "/"),
            "water_sha256": _sha(out_water),
        },
        "elapsed_s": round(time.time() - started, 1),
    }
    return summary


def _write(rows: list[dict[str, Any]], path: str, force: bool = False) -> None:
    """Escrita atômica, com proteção contra sobrescrita por padrão.

    O episódio de V3.5 (aquisição CAD sobrescrevendo `v30_cad_polygon.json`)
    mostrou que sobrescrita silenciosa de artefato é o risco mais caro deste
    repositório. Um arquivo existente só é substituído com ``--force``.
    """
    if os.path.exists(path) and not force:
        raise FileExistsError(
            f"saída já existe: {path}. Use --force para substituir "
            f"(ou escolha outro diretório de saída)."
        )
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = f"{path}.tmp"
    with open(temporary, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


# ----------------------------------------------------------------------- verify

COMPARED_COLUMNS = (
    "precip_acumulada_mm_corrected",
    "temp_media_c_corrected",
    "degree_days_total_corrected",
    "extreme_heat_days_corrected",
    "et0_total_mm_corrected",
    "deficiency_total_mm_corrected",
    "excess_total_mm_corrected",
    "deficiency_cad_0_60",
    "deficiency_cad_0_100",
    "deficiency_cad_0_200",
)


def verify(config: dict[str, Any]) -> dict[str, Any]:
    """Compara a construção canônica com o painel de referência V3.5."""
    reference_path = _abs(config["reference_outputs"]["panel_windows"])
    if not os.path.exists(reference_path):
        return {"status": "reference_missing", "path": reference_path}
    if not os.path.exists(OUT_PANEL):
        return {"status": "output_missing", "path": OUT_PANEL}

    reference: dict[tuple[str, str, str], dict[str, str]] = {}
    with open(reference_path, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            reference[(str(row["ibge_code"]), str(row["crop"]), str(row["safra"]))] = row
    built: dict[tuple[str, str, str], dict[str, str]] = {}
    with open(OUT_PANEL, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            built[(str(row["ibge_code"]), str(row["crop"]), str(row["safra"]))] = row

    shared = sorted(set(built) & set(reference))
    comparisons: dict[str, Any] = {}
    worst = 0.0
    for column in COMPARED_COLUMNS:
        diffs: list[float] = []
        for key in shared:
            left = _num(built[key].get(column))
            right = _num(reference[key].get(column))
            if left is None or right is None:
                continue
            diffs.append(abs(left - right))
        if diffs:
            array = np.asarray(diffs)
            comparisons[column] = {
                "n": int(array.size),
                "max_abs_diff": float(array.max()),
                "n_exact": int((array < 1e-9).sum()),
            }
            worst = max(worst, float(array.max()))
    return {
        "status": "ok",
        "rows_built": len(built),
        "rows_reference": len(reference),
        "rows_shared": len(shared),
        "only_built": len(set(built) - set(reference)),
        "only_reference": len(set(reference) - set(built)),
        "max_abs_difference": worst,
        "tolerance": 1e-6,
        "within_tolerance": worst <= 1e-6,
        "by_column": comparisons,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", default="all", choices=("validate", "build", "verify", "all"))
    parser.add_argument("--config", default=CONFIG_PATH)
    parser.add_argument("--codes", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--out-manifest", default=OUT_JSON)
    parser.add_argument("--force", action="store_true", help="permite substituir saídas existentes")
    parser.add_argument("--out-prefix", default=DEFAULT_PREFIX, help="prefixo das saídas (build em blocos)")
    parser.add_argument("--states", default="", help="lista de UFs separada por vírgula")
    args = parser.parse_args()

    started = time.time()
    config = load_config(args.config)
    result: dict[str, Any] = {"stage": args.stage, "build_version": BUILD_VERSION}

    if args.stage in ("validate", "all"):
        result["validate"] = validate(config)
        print(json.dumps(result["validate"]["registry"], ensure_ascii=False, indent=2))
        if result["validate"]["problems"]:
            print("problemas:", result["validate"]["problems"])

    if args.stage in ("build", "all"):
        codes: list[str] | None = None
        if args.codes:
            codes = [c.strip() for c in args.codes.split(",") if c.strip()]
        elif args.limit:
            registry = load_registry(config)
            codes = sorted(registry)[: args.limit]
        result["build"] = build(
            config,
            codes,
            force=args.force,
            out_prefix=args.out_prefix,
            states=[s.strip() for s in args.states.split(",") if s.strip()] or None,
        )
        print(json.dumps(result["build"], ensure_ascii=False, indent=2)[:1600])

    if args.stage in ("verify", "all"):
        result["verify"] = verify(config)
        print(json.dumps(result["verify"], ensure_ascii=False, indent=2)[:1600])

    if args.stage in ("build", "all", "verify"):
        from manifest import write_manifest

        written = write_manifest(args.out_manifest, result, {"stage": args.stage}, started=started)
        print("manifesto:", written["manifest"], "conteúdo:", written["content_sha256"][:16])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
