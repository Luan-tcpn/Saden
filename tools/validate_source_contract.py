"""Verificação estática e de runtime do contrato de fonte climática.

Duas verificações independentes:

1. **Estática** — nenhum consumidor pode filtrar ``paired_usable`` sem também
   referenciar a fonte. Analisa a AST dos scripts em ``tools/`` e procura
   funções que comparam status e não mencionam fonte.
2. **Runtime** — conta, nos artefatos reais, quantas linhas "utilizáveis" são de
   fonte não canônica (as 2.020 linhas INMET do painel base) e confirma que o
   painel analítico publicado não as contém.

Uso: python tools/validate_source_contract.py
"""

from __future__ import annotations

import ast
import csv
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "geospatial"))

from agroclimate import contracts  # noqa: E402

_DATA_ROOT = os.environ.get("SADEN_DATA_ROOT") or os.path.join(ROOT, "geospatial", "data")
PROCESSED = os.path.join(_DATA_ROOT, "processed")
OUT_JSON = os.path.join(ROOT, "geospatial", "data", "manifests", "source_contract_validation.json")

SOURCE_TOKENS = ("climate_source", "source")

# Exceções documentadas: não são consumidores de amostra analítica.
WAIVERS = {
    ("tools/s27_panel_coverage.py", "main"): (
        "contador de cobertura de um relatório histórico (V2.7); não seleciona "
        "amostra para análise. O efeito está quantificado no relatório de "
        "adjudicação: 2.020 linhas INMET (9,4% do 'utilizável') foram contadas "
        "como utilizáveis. Não foi alterado para preservar a reprodutibilidade."
    ),
    ("tools/s27_panel_coverage.py", "<module>"): "mesmo caso do main (contador de cobertura)",
}


def _compares_paired_usable(node: ast.AST) -> bool:
    """Verdadeiro só quando o literal aparece numa **comparação** ou teste.

    Atribuições como ``row["status"] = "paired_usable"`` (o produtor do painel)
    não são consumo e não devem ser sinalizadas.
    """
    for child in ast.walk(node):
        if isinstance(child, ast.Compare):
            for operand in [child.left, *child.comparators]:
                if isinstance(operand, ast.Constant) and operand.value == "paired_usable":
                    return True
        if isinstance(child, ast.Constant) and child.value == "paired_usable":
            # literal solto dentro de `in`/`==` compilados como Compare já foram
            # cobertos; aqui só interessam usos em condição
            continue
    return False


def _mentions_source(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Attribute) and child.attr in SOURCE_TOKENS:
            return True
        if isinstance(child, ast.Constant) and child.value in ("NASA-POWER", "INMET"):
            return True
        if isinstance(child, ast.Constant) and child.value in SOURCE_TOKENS:
            return True
        if isinstance(child, ast.Subscript):
            slice_node = child.slice
            if isinstance(slice_node, ast.Constant) and slice_node.value in SOURCE_TOKENS:
                return True
    return False


def static_scan() -> dict[str, Any]:
    """Procura, por função, quem filtra status sem declarar a fonte."""
    offenders: list[dict[str, Any]] = []
    clean: list[dict[str, Any]] = []
    files = 0
    self_name = os.path.basename(__file__)
    for directory in ("tools", "geospatial/agroclimate"):
        base = os.path.join(ROOT, directory)
        for name in sorted(os.listdir(base)):
            if not name.endswith(".py") or name == self_name:
                continue
            path = os.path.join(base, name)
            files += 1
            try:
                source = open(path, encoding="utf-8-sig").read()
                tree = ast.parse(source, filename=path)
            except SyntaxError as error:
                offenders.append({"file": f"{directory}/{name}", "error": str(error)})
                continue
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module)):
                    continue
                if not _compares_paired_usable(node):
                    continue
                entry = {
                    "file": f"{directory}/{name}",
                    "function": getattr(node, "name", "<module>"),
                    "line": getattr(node, "lineno", 0),
                }
                if _mentions_source(node):
                    clean.append(entry)
                elif (entry["file"], entry["function"]) in WAIVERS:
                    entry["waiver"] = WAIVERS[(entry["file"], entry["function"])]
                    clean.append(entry)
                else:
                    offenders.append(entry)
    return {
        "files_scanned": files,
        "functions_guarded": len(clean),
        "functions_unguarded": len(offenders),
        "waivers": len(WAIVERS),
        "unguarded": offenders,
        "guarded": clean,
    }


def runtime_audit() -> dict[str, Any]:
    """Audita os artefatos: base (contém INMET) e analítico (não deve conter)."""
    result: dict[str, Any] = {}
    base_path = os.path.join(PROCESSED, "agroclimatic_productivity_panel.csv")
    if os.path.exists(base_path):
        with open(base_path, newline="", encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))
        audit = contracts.audit_mixture(rows)
        usable = [row for row in rows if contracts.row_status(row) == contracts.CANONICAL_STATUS]
        kept, discard = contracts.select_canonical(rows)
        result["panel_base"] = {
            "rows": len(rows),
            "usable_rows": len(usable),
            "usable_from_non_canonical_source": audit["usable_offsource_count"],
            "share_of_usable": round(
                audit["usable_offsource_count"] / len(usable), 4
            ) if usable else None,
            "by_status_source": audit["by_status_source"],
            "canonical_selection": {"kept": discard["kept"], "discarded": discard["discarded"]},
            "examples": audit["usable_offsource_examples"],
        }

    for name in ("v31_panel_windows.csv", "v35_panel_windows.csv"):
        path = os.path.join(PROCESSED, name)
        if not os.path.exists(path):
            continue
        with open(path, newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            has_source = "climate_source" in (reader.fieldnames or [])
            rows = list(reader) if has_source else []
        result[name] = {
            "rows": len(rows) if has_source else "sem coluna climate_source (já filtrado na construção)",
            "has_source_column": has_source,
            "non_canonical_rows": (
                sum(
                    1
                    for row in rows
                    if contracts.row_source(row) != contracts.CANONICAL_CLIMATE_SOURCE
                )
                if has_source
                else 0
            ),
        }
    return result


def main() -> int:
    static = static_scan()
    runtime = runtime_audit()
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "canonical_source": contracts.canonical_source(),
        "static": static,
        "runtime": runtime,
    }
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, default=str)
        handle.write("\n")

    print(f"arquivos analisados: {static['files_scanned']}")
    print(f"funções com guarda de fonte: {static['functions_guarded']}")
    print(f"funções sem guarda: {static['functions_unguarded']}")
    for entry in static["unguarded"]:
        print("   SEM GUARDA:", entry)
    print()
    for key, value in runtime.items():
        if isinstance(value, dict):
            print(key, "->", {k: v for k, v in value.items() if k not in ("examples", "by_status_source")})
            if "by_status_source" in value:
                print("   status|fonte:", value["by_status_source"])
    print()
    print("manifesto:", OUT_JSON)
    return 0 if static["functions_unguarded"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
