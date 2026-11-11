#!/usr/bin/env python
"""CLI da V2.2 — base observada de produtividade agrícola (IBGE/SIDRA + CONAB).

A partir da raiz do repositório (Windows):

    geospatial\\.venv\\Scripts\\python.exe geospatial\\run_productivity.py inventory
    geospatial\\.venv\\Scripts\\python.exe geospatial\\run_productivity.py acquire
    geospatial\\.venv\\Scripts\\python.exe geospatial\\run_productivity.py normalize
    geospatial\\.venv\\Scripts\\python.exe geospatial\\run_productivity.py validate
    geospatial\\.venv\\Scripts\\python.exe geospatial\\run_productivity.py compat

Os subcomandos usam **rede** (APIs/arquivos oficiais). A suíte de testes
offline (`geospatial/tests`) é independente.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agri import compat, config, conab, crosswalk, normalize, sidra, validate  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = config.RAW_DIR
PROCESSED_DIR = config.PROCESSED_DIR
MANIFEST_DIR = config.MANIFEST_DIR

PROCESSING_VERSION = "V2.2/0.1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dirs() -> None:
    for path in (RAW_DIR, PROCESSED_DIR, MANIFEST_DIR):
        os.makedirs(path, exist_ok=True)


def _write_json(data: Any, path: str) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, default=str)
    return path


def _git_commit() -> str | None:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=HERE,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return proc.stdout.strip() or None
    except Exception:  # pragma: no cover
        return None


def _versions() -> dict[str, str]:
    versions = {"python": platform.python_version(), "processing": PROCESSING_VERSION}
    for module in ("openpyxl", "xlrd", "pandas"):
        try:
            versions[module] = __import__(module).__version__
        except Exception:  # pragma: no cover
            versions[module] = "not-installed"
    return versions


# ------------------------------------------------------------------ inventory


def cmd_inventory(args: argparse.Namespace) -> dict[str, Any]:
    """Inventário das fontes oficiais (metadados e condições de acesso)."""
    _ensure_dirs()
    inventory: dict[str, Any] = {
        "generated_at": _now(),
        "git_commit": _git_commit(),
        "versions": _versions(),
        "municipality": None,
        "sources": [],
        "saden_commodities": config.SADEN_COMMODITIES,
        "crosswalk": crosswalk.crosswalk_table(),
    }

    # município (fonte oficial)
    municipality = sidra.fetch_municipality_metadata()
    inventory["municipality"] = {
        "requested": config.MUNICIPALITY,
        "official": municipality,
        "confirmed": (
            str(municipality.get("id")) == config.MUNICIPALITY["ibge_code"]
            and municipality.get("nome") == config.MUNICIPALITY["name"]
        ),
    }

    # IBGE: metadados do agregado PAM
    try:
        metadata = sidra.fetch_aggregate_metadata()
        inventory["sources"].append(
            {
                "institution": "IBGE",
                "dataset": config.PAM_RESEARCH,
                "official_id": config.PAM_TABLE,
                "documentation": "https://sidra.ibge.gov.br/tabela/5457",
                "metadata_url": config.IBGE_AGGREGATE_METADATA,
                "access": "API pública, sem chave, sem custo (HTTP GET)",
                "granularity": "municipio (N6) e níveis superiores",
                "periodicity": metadata.get("periodicidade"),
                "variables": metadata.get("variaveis"),
                "classifications": [
                    {"id": c.get("id"), "name": c.get("nome")}
                    for c in metadata.get("classificacoes", [])
                ],
                "license": config.LICENSES["ibge_sidra"],
                "status": "acessivel",
            }
        )
    except Exception as exc:  # noqa: BLE001
        inventory["sources"].append(
            {
                "institution": "IBGE",
                "dataset": config.PAM_RESEARCH,
                "official_id": config.PAM_TABLE,
                "access": "API pública, sem chave",
                "status": "erro",
                "error": f"{type(exc).__name__}: {exc}",
            }
        )

    # CONAB: planilhas oficiais
    conab_entry: dict[str, Any] = {
        "institution": "CONAB",
        "dataset": "Boletim de Safras (grãos) e Boletim da Safra de Café",
        "documentation": config.CONAB_HOME,
        "access": "download HTTP de planilhas oficiais (.xlsx/.xls)",
        "granularity": "uf (estadual) e nacional — sem dado municipal nos arquivos",
        "variables": ["area (mil ha)", "produtividade (kg/ha)", "producao (mil t)"],
        "license": config.LICENSES["conab"],
        "blocked_endpoints": [
            {
                "endpoint": config.CONAB_SIGS_URL,
                "issue": "DNS não resolve neste ambiente (dados por município)",
                "evidence": "socket.gethostbyname -> gaierror",
            },
            {
                "endpoint": "https://dados.gov.br/api/3/action/package_search",
                "issue": "HTTP 401 (exige autenticação) — catálogo CKAN",
                "evidence": "resposta HTTP 401 nas consultas de catálogo",
            },
            {
                "endpoint": config.CONAB_API_URL,
                "issue": "DNS não resolve",
                "evidence": "socket.gethostbyname -> gaierror",
            },
        ],
    }
    try:
        grains = conab.list_spreadsheets(config.CONAB_GRAINS_INDEX)
        conab_entry["spreadsheets_grains"] = grains
        conab_entry["status"] = "acessivel"
    except Exception as exc:  # noqa: BLE001
        conab_entry["spreadsheets_grains"] = []
        conab_entry["status"] = "erro"
        conab_entry["error"] = f"{type(exc).__name__}: {exc}"
    inventory["sources"].append(conab_entry)

    path = _write_json(inventory, os.path.join(MANIFEST_DIR, "source_inventory.json"))
    return {
        "ok": True,
        "manifest": path,
        "municipality_confirmed": inventory["municipality"]["confirmed"],
        "sources": [
            {
                "institution": s["institution"],
                "official_id": s.get("official_id"),
                "granularity": s.get("granularity"),
                "status": s.get("status"),
            }
            for s in inventory["sources"]
        ],
        "crosswalk_rows": len(inventory["crosswalk"]),
    }


# ------------------------------------------------------------------- acquire


def cmd_acquire(args: argparse.Namespace) -> dict[str, Any]:
    """Adquire dados reais: PAM municipal (SIDRA) + planilhas CONAB."""
    _ensure_dirs()
    results: dict[str, Any] = {"generated_at": _now(), "git_commit": _git_commit()}

    # ---------------------------------------------------------------- IBGE
    years = list(range(args.year_start, args.year_end + 1))
    sidra_result = sidra.fetch_pam(years=years)
    raw_path = os.path.join(RAW_DIR, "sidra", f"pam_5457_{config.MUNICIPALITY['ibge_code']}_{args.year_start}-{args.year_end}.json")
    os.makedirs(os.path.dirname(raw_path), exist_ok=True)
    with open(raw_path, "w", encoding="utf-8") as handle:
        json.dump(sidra_result, handle, ensure_ascii=False, indent=2)

    crops = sorted(
        {
            str(r.get("product_name"))
            for r in sidra_result.get("records", [])
            if r.get("product_name")
        }
    )
    variables = sorted(
        {str(r.get("variable_name")) for r in sidra_result.get("records", []) if r.get("variable_name")}
    )
    ibge_manifest = {
        "institution": "IBGE",
        "dataset_name": config.PAM_RESEARCH,
        "official_id": config.PAM_TABLE,
        "documentation": "https://sidra.ibge.gov.br/tabela/5457",
        "api_documentation": "https://apisidra.ibge.gov.br/definicoes",
        "acquisition_method": "GET https://apisidra.ibge.gov.br/values/...",
        "query_parameters": {
            "table": config.PAM_TABLE,
            "level": "n6",
            "locality": config.MUNICIPALITY["ibge_code"],
            "variables": ",".join(sorted(config.PAM_VARIABLES)),
            "periods": f"{args.year_start},{args.year_end}",
            "classification": config.PAM_CLASSIFICATION,
            "categories": "all",
        },
        "query_url": sidra_result.get("url"),
        "acquired_at": sidra_result.get("acquired_at"),
        "covered_period": f"{args.year_start}-{args.year_end}",
        "geographic_coverage": "município 5107925 (Sorriso/MT)",
        "crops_included": crops,
        "variables_included": variables,
        "unit": sorted({str(r.get("unit_name")) for r in sidra_result.get("records", []) if r.get("unit_name")}),
        "license": config.LICENSES["ibge_sidra"],
        "license_status": config.LICENSES["ibge_sidra"]["status"],
        "record_count": len(sidra_result.get("records", [])),
        "files": [
            {
                "path": os.path.relpath(raw_path, HERE).replace("\\", "/"),
                "bytes": os.path.getsize(raw_path),
            }
        ],
        "checksums": {},
        "processing_version": PROCESSING_VERSION,
        "known_limitations": [
            "Granularidade municipal: não descreve a AOI de validação (0,47% do município).",
            "Ano de referência é o ano civil da coleta/ano agrícola reported.",
            "A PAM divulga dados consolidados, com revisões em anos posteriores.",
        ],
    }
    ibge_manifest["files"][0]["sha256"] = _sha256(raw_path)
    ibge_manifest["checksums"] = {
        ibge_manifest["files"][0]["path"]: ibge_manifest["files"][0]["sha256"]
    }
    ibge_manifest_path = _write_json(
        ibge_manifest, os.path.join(MANIFEST_DIR, "manifest_sidra_pam.json")
    )

    # --------------------------------------------------------------- CONAB
    conab_manifest = {
        "institution": "CONAB",
        "dataset_name": "Boletim de Safras (CONAB) — planilhas oficiais",
        "official_id": "boletim-de-safras-graos",
        "documentation": config.CONAB_GRAINS_INDEX,
        "acquisition_method": "download HTTP de planilhas .xlsx publicadas no portal",
        "acquired_at": _now(),
        "geographic_coverage": "UF (estadual) e Brasil",
        "variables_included": ["area_plantada_ha", "rendimento_medio_kg_ha", "quantidade_produzida_t"],
        "license": config.LICENSES["conab"],
        "license_status": config.LICENSES["conab"]["status"],
        "records": [],
        "files": [],
        "checksums": {},
        "processing_version": PROCESSING_VERSION,
        "known_limitations": [
            "Granularidade estadual: não permite atribuição municipal nem por AOI.",
            "Valores são estimativas de levantamento, revisadas a cada boletím.",
            "Safra não equivale a ano civil.",
        ],
        "blocked_endpoints": [
            "sigs.conab.gov.br (dados por município) — DNS não resolve",
            "dados.gov.br/api/3/action — HTTP 401 (autenticação exigida)",
        ],
    }
    conab_files: list[dict[str, Any]] = []
    try:
        spreadsheets = conab.list_spreadsheets(config.CONAB_GRAINS_INDEX)
        conab_manifest["index_listing"] = spreadsheets
        selected = _select_conab_files(spreadsheets, args.conab_safras)
        for entry in selected:
            destination = os.path.join(RAW_DIR, "conab", entry["name"])
            meta = conab.download(entry["url"], destination)
            meta.update(
                {
                    "levantamento": entry.get("levantamento"),
                    "reference_year": entry.get("reference_year"),
                    "path": os.path.relpath(destination, HERE).replace("\\", "/"),
                }
            )
            conab_files.append(meta)
    except Exception as exc:  # noqa: BLE001
        conab_manifest["error"] = f"{type(exc).__name__}: {exc}"
    conab_manifest["files"] = conab_files
    conab_manifest["checksums"] = {f["path"]: f["sha256"] for f in conab_files}
    conab_manifest["file_count"] = len(conab_files)
    conab_manifest_path = _write_json(
        conab_manifest, os.path.join(MANIFEST_DIR, "manifest_conab_safras.json")
    )

    results["ibge"] = {"manifest": ibge_manifest_path, "records": ibge_manifest["record_count"]}
    results["conab"] = {"manifest": conab_manifest_path, "files": len(conab_files)}
    results["raw_dir"] = os.path.relpath(RAW_DIR, HERE).replace("\\", "/")
    return {"ok": True, **results}


def _select_conab_files(
    spreadsheets: list[dict[str, str]], safras: list[str]
) -> list[dict[str, str]]:
    """Seleciona o último levantamento disponível de cada safra pedida."""
    chosen: list[dict[str, str]] = []
    for safra in safras:
        target = safra.replace("-", "/")
        candidates = [
            item
            for item in spreadsheets
            if item.get("levantamento", "").endswith(f"safra-{target}")
        ]
        if not candidates:
            continue

        def ordinal(item: dict[str, str]) -> int:
            prefix = item.get("levantamento", "").split("-")[0]
            digits = "".join(ch for ch in prefix if ch.isdigit())
            return int(digits) if digits else 0

        candidates.sort(key=ordinal)
        chosen.append(candidates[-1])
    return chosen


def _sha256(path: str) -> str:
    import hashlib

    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ----------------------------------------------------------------- normalize


def cmd_normalize(args: argparse.Namespace) -> dict[str, Any]:
    """Normaliza os dados acquired em uma base tabular única."""
    _ensure_dirs()
    records: list[dict[str, Any]] = []

    # IBGE
    sidra_files = sorted(
        os.path.join(RAW_DIR, "sidra", name)
        for name in os.listdir(os.path.join(RAW_DIR, "sidra"))
        if name.endswith(".json")
    ) if os.path.isdir(os.path.join(RAW_DIR, "sidra")) else []
    for path in sidra_files:
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
        records.extend(
            normalize.build_ibge_records(payload, payload.get("url", ""), "sidra_api")
        )

    # CONAB
    conab_files = sorted(
        os.path.join(RAW_DIR, "conab", name)
        for name in os.listdir(os.path.join(RAW_DIR, "conab"))
        if name.lower().endswith((".xlsx", ".xls"))
    ) if os.path.isdir(os.path.join(RAW_DIR, "conab")) else []
    for path in conab_files:
        try:
            parsed = conab.parse_state_sheet(path, "MT")
        except Exception as exc:  # noqa: BLE001
            print(f"[aviso] planilha {os.path.basename(path)} não processada: {exc}")
            continue
        meta = {
            "name": os.path.basename(path),
            "dataset_id": os.path.basename(path),
            "acquired_at": _now(),
            "reference_period": None,
            "revision": os.path.basename(path),
        }
        records.extend(
            normalize.build_conab_records(parsed, meta, "https://www.gov.br/conab")
        )

    csv_path = os.path.join(PROCESSED_DIR, "productivity_observations.csv")
    json_path = os.path.join(PROCESSED_DIR, "productivity_observations.json")
    normalize.write_csv(records, csv_path)
    normalize.write_json(records, json_path)

    summary = {
        "generated_at": _now(),
        "records": len(records),
        "by_institution": {},
        "by_geography_type": {},
        "by_match_class": {},
        "by_nature": {},
        "csv": os.path.relpath(csv_path, HERE).replace("\\", "/"),
        "json": os.path.relpath(json_path, HERE).replace("\\", "/"),
        "sha256_csv": _sha256(csv_path),
    }
    for record in records:
        for field, key in (
            ("institution", "by_institution"),
            ("geography_type", "by_geography_type"),
            ("match_class", "by_match_class"),
            ("nature", "by_nature"),
        ):
            value = str(record.get(field))
            summary[key][value] = summary[key].get(value, 0) + 1
    path = _write_json(summary, os.path.join(MANIFEST_DIR, "normalized_base_summary.json"))
    return {"ok": True, "summary_manifest": path, **summary}


# ------------------------------------------------------------------ validate


def cmd_validate(args: argparse.Namespace) -> dict[str, Any]:
    """Executa as verificações de qualidade sobre a base normalizada."""
    csv_path = os.path.join(PROCESSED_DIR, "productivity_observations.csv")
    if not os.path.exists(csv_path):
        return {"ok": False, "error": f"base normalizada ausente: {csv_path}"}
    records = normalize.read_csv(csv_path)
    for record in records:
        raw_value = record.get("value_normalized")
        if raw_value in (None, ""):
            record["value_normalized"] = None
            continue
        try:
            record["value_normalized"] = float(raw_value)
        except (TypeError, ValueError):
            record["value_normalized"] = None
    report = validate.run_all(records)
    report["generated_at"] = _now()
    report["git_commit"] = _git_commit()
    # O relatório versionado guarda erros e avisos; os achados informativos
    # (4.548 produtos fora do escopo, 946 valores ausentes) ficam no arquivo
    # completo, reproduzível pelo mesmo comando e não versionado.
    relevant = [
        finding
        for finding in report["findings"]
        if finding["severity"] in (validate.SEVERITY_ERROR, validate.SEVERITY_WARNING)
    ]
    full_findings = os.path.join(MANIFEST_DIR, "quality_findings_full.csv")
    _write_findings_csv(report["findings"], full_findings)
    report.pop("findings", None)  # lista completa fica no CSV não versionado
    report["findings_versioned"] = relevant
    report["findings_full_csv"] = os.path.relpath(full_findings, HERE).replace("\\", "/")
    report["findings_policy"] = (
        "O relatório versionado contém os achados de severidade error/warning; "
        "o CSV completo (inclui os informativos) é regenerado pelo mesmo comando."
    )
    path = _write_json(report, os.path.join(MANIFEST_DIR, "quality_report.json"))
    csv_out = os.path.join(MANIFEST_DIR, "quality_findings.csv")
    _write_findings_csv(relevant, csv_out)
    return {
        "ok": True,
        "report": path,
        "findings_csv": os.path.relpath(csv_out, HERE).replace("\\", "/"),
        "records_checked": report["records_checked"],
        "counts_by_severity": report["counts_by_severity"],
        "counts_by_check": report["counts_by_check"],
        "findings_relevant": len(relevant),
    }


def _write_findings_csv(findings: list[dict[str, Any]], path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["check", "severity", "message", "key"], extrasaction="ignore"
        )
        writer.writeheader()
        for finding in findings:
            writer.writerow(
                {
                    "check": finding["check"],
                    "severity": finding["severity"],
                    "message": finding["message"],
                    "key": " | ".join(str(part) for part in finding.get("key", [])),
                }
            )


# -------------------------------------------------------------------- compat


def cmd_compat(args: argparse.Namespace) -> dict[str, Any]:
    """Avalia compatibilidade espacial e temporal com o Sentinel-2."""
    from shapely.geometry import box

    csv_path = os.path.join(PROCESSED_DIR, "productivity_observations.csv")
    records = normalize.read_csv(csv_path) if os.path.exists(csv_path) else []

    # geometria real do município (IBGE) e AOI de validação
    from agri.geometry_compat import municipality_geometry  # noqa: WPS433

    municipality = municipality_geometry()
    aoi_geom = box(*config.VALIDATION_AOI_BBOX)
    spatial = compat.spatial_geometry_report(municipality, aoi_geom)

    ibge_class = compat.classify_spatial("municipio", spatial["aoi_fraction_of_municipality"])
    conab_class = compat.classify_spatial("uf", spatial["aoi_fraction_of_municipality"])

    s2 = compat.s2_yearly_aggregation()
    s2_years = sorted(s2.get("years", {}).keys())
    temporal = compat.temporal_overlap(records, s2_years)

    matrix = []
    for crop in config.SADEN_COMMODITIES:
        for source, granularity, classification in (
            ("IBGE/SIDRA (PAM 5457)", "municipio", ibge_class),
            ("CONAB (Boletim de Safras)", "uf", conab_class),
        ):
            matrix.append(
                {
                    "crop": crop["name"],
                    "crop_key": crop["key"],
                    "source": source,
                    "geographic_unit": granularity,
                    "class_for_aoi": classification["class"],
                    "class_label": compat.CLASS_LABELS[classification["class"]],
                    "justification": classification["justification"],
                    "reference_period_type": (
                        "ano civil" if source.startswith("IBGE") else "safra"
                    ),
                    "overlap_with_s2_2023_2025": (
                        "2023-2025 (ano civil)" if source.startswith("IBGE")
                        else "safras 2023/24, 2024/25, 2025/26 (2 anos civis cada)"
                    ),
                }
            )

    report = {
        "generated_at": _now(),
        "git_commit": _git_commit(),
        "spatial": spatial,
        "spatial_classification": {
            "IBGE/SIDRA (PAM 5457)": ibge_class,
            "CONAB (Boletim de Safras)": conab_class,
        },
        "temporal": temporal,
        "sentinel2_series": s2,
        "s2_calendar_note": compat.tmp_calendar_note(),
        "compatibility_matrix": matrix,
    }
    path = _write_json(report, os.path.join(MANIFEST_DIR, "compatibility_report.json"))

    matrix_csv = os.path.join(MANIFEST_DIR, "compatibility_matrix.csv")
    with open(matrix_csv, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "crop",
                "source",
                "geographic_unit",
                "class_for_aoi",
                "class_label",
                "reference_period_type",
                "overlap_with_s2_2023_2025",
                "justification",
            ],
            extrasaction="ignore",
        )
        writer.writeheader()
        for row in matrix:
            writer.writerow(row)

    # tabela de correspondência cultura × período × fonte × indicador
    table_rows = compat.correspondence_table(records, s2)
    table_csv = os.path.join(MANIFEST_DIR, "correspondence_table.csv")
    if table_rows:
        with open(table_csv, "w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(table_rows[0].keys()))
            writer.writeheader()
            for row in table_rows:
                writer.writerow(row)
    report["correspondence_table_rows"] = len(table_rows)

    return {
        "ok": True,
        "report": path,
        "matrix_csv": os.path.relpath(matrix_csv, HERE).replace("\\", "/"),
        "correspondence_table_csv": os.path.relpath(table_csv, HERE).replace("\\", "/"),
        "correspondence_rows": len(table_rows),
        "spatial": {
            "aoi_fraction_of_municipality": round(
                spatial["aoi_fraction_of_municipality"] * 100, 4
            ),
            "aoi_fully_inside_municipality": spatial["aoi_fully_inside_municipality"],
            "municipality_area_km2": round(spatial["municipality_area_km2"], 2),
        },
        "temporal": {
            "ibge_years_overlapping_s2": temporal["ibge_years_overlapping_s2"],
            "conab_safras_in_overlap": temporal["conab_safras_in_overlap"],
            "s2_years": s2_years,
        },
        "classes": {
            "IBGE/SIDRA": ibge_class["class"],
            "CONAB": conab_class["class"],
        },
    }


# --------------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="SADEN V2.2 — base observada de produtividade agrícola"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_inv = sub.add_parser("inventory", help="inventário de fontes oficiais")
    p_inv.set_defaults(func=cmd_inventory)

    p_acq = sub.add_parser("acquire", help="aquisição real (SIDRA + CONAB)")
    p_acq.add_argument("--year-start", type=int, default=config.PAM_YEAR_START)
    p_acq.add_argument("--year-end", type=int, default=config.PAM_YEAR_END)
    p_acq.add_argument(
        "--conab-safras",
        default="2024-25,2025-26",
        help="safras da CONAB (último levantamento de cada uma)",
    )
    p_acq.set_defaults(func=cmd_acquire)

    p_norm = sub.add_parser("normalize", help="base normalizada (CSV/JSON)")
    p_norm.set_defaults(func=cmd_normalize)

    p_val = sub.add_parser("validate", help="verificações de qualidade")
    p_val.set_defaults(func=cmd_validate)

    p_com = sub.add_parser("compat", help="compatibilidade espacial/temporal")
    p_com.set_defaults(func=cmd_compat)

    args = parser.parse_args(argv)
    safras = [
        s.strip() for s in getattr(args, "conab_safras", "").split(",") if s.strip()
    ]
    if hasattr(args, "conab_safras"):
        args.conab_safras = safras
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
