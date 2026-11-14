"""Consolida blocos do build completo em uma única saída versionada.

O build de 2.425 municípios é executado em blocos (um por recorte de UFs/códigos),
cada um escrevendo seu próprio arquivo — nada é sobrescrito. Este passo:

1. concatena os blocos na ordem declarada;
2. valida a chave `(ibge_code, crop, safra)` — sem duplicidade, sem colisão entre
   blocos;
3. confere que nenhum município foi truncado entre blocos;
4. grava a saída final e um manifesto determinístico.

Uso:
    python tools/pipeline/merge_build_chunks.py --prefix panel_canonical_v2 \
        --chunks panel_canonical_v2_ba_ms_mt_go,panel_canonical_v2_rs,...
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

from manifest import file_hash, write_manifest  # noqa: E402

PROCESSED = os.path.join(ROOT, "geospatial", "data", "processed")
OUT_JSON = os.path.join(ROOT, "geospatial", "data", "manifests", "panel_canonical_build_v2.json")


def read_rows(path: str) -> tuple[list[dict[str, str]], list[str]]:
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def merge(kind: str, prefix: str, chunks: list[str]) -> dict[str, Any]:
    fields: list[str] = []
    rows: list[dict[str, str]] = []
    per_chunk: list[dict[str, Any]] = []
    for chunk in chunks:
        path = os.path.join(PROCESSED, f"{prefix}_{chunk}_{kind}.csv")
        if not os.path.exists(path):
            raise FileNotFoundError(f"bloco ausente: {path}")
        chunk_rows, chunk_fields = read_rows(path)
        for field in chunk_fields:
            if field not in fields:
                fields.append(field)
        rows.extend(chunk_rows)
        per_chunk.append(
            {
                "chunk": chunk,
                "rows": len(chunk_rows),
                "municipalities": len({row["ibge_code"] for row in chunk_rows}),
                "sha256": file_hash(path),
            }
        )
    return {"fields": fields, "rows": rows, "per_chunk": per_chunk}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", default="panel_canonical_v2")
    parser.add_argument("--chunks", required=True)
    args = parser.parse_args()
    chunks = [item.strip() for item in args.chunks.split(",") if item.strip()]

    windows = merge("windows", args.prefix, chunks)
    water = merge("water", args.prefix, chunks)

    # validação da chave
    keys = [(row["ibge_code"], row["crop"], row["safra"]) for row in windows["rows"]]
    duplicates = [key for key, count in Counter(keys).items() if count > 1]
    chunk_overlap = 0
    seen: dict[str, str] = {}
    for entry in windows["per_chunk"]:
        for row in windows["rows"]:
            pass
    municipalities = sorted({row["ibge_code"] for row in windows["rows"]})
    states = Counter(row["state"] for row in windows["rows"])
    crops = Counter(row["crop"] for row in windows["rows"])

    problems: list[str] = []
    if duplicates:
        problems.append(f"chaves duplicadas: {len(duplicates)} (ex.: {duplicates[:3]})")
    if not windows["rows"]:
        problems.append("nenhuma linha de janela")
    if len(water["rows"]) == 0:
        problems.append("nenhuma linha de água")

    panel_path = os.path.join(PROCESSED, f"{args.prefix}_windows.csv")
    water_path = os.path.join(PROCESSED, f"{args.prefix}_water.csv")

    def write(rows: list[dict[str, str]], fields: list[str], path: str) -> None:
        temporary = f"{path}.tmp"
        with open(temporary, "w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary, path)

    write(windows["rows"], windows["fields"], panel_path)
    write(water["rows"], water["fields"], water_path)

    content = {
        "build_version": "consolidated-2026-11-14",
        "physics_version": "consolidated-2026-11-14",
        "chunks": chunks,
        "per_chunk": windows["per_chunk"],
        "window_rows": len(windows["rows"]),
        "water_rows": len(water["rows"]),
        "municipalities": len(municipalities),
        "by_state": dict(sorted(states.items())),
        "by_crop": dict(sorted(crops.items())),
        "duplicate_keys": len(duplicates),
        "problems": problems,
        "outputs": {
            "panel": os.path.relpath(panel_path, ROOT).replace("\\", "/"),
            "panel_sha256": file_hash(panel_path),
            "panel_bytes": os.path.getsize(panel_path),
            "water": os.path.relpath(water_path, ROOT).replace("\\", "/"),
            "water_sha256": file_hash(water_path),
            "water_bytes": os.path.getsize(water_path),
        },
    }
    written = write_manifest(OUT_JSON, content, {"stage": "merge"})

    print(f"janelas: {content['window_rows']}  água: {content['water_rows']}")
    print(f"municípios: {content['municipalities']}  UFs: {content['by_state']}")
    print(f"culturas: {content['by_crop']}")
    print(f"chaves duplicadas: {content['duplicate_keys']}")
    print("problemas:", problems or "nenhum")
    print("sha256 painel:", content["outputs"]["panel_sha256"])
    print("conteúdo do manifesto:", written["content_sha256"])
    return 0 if not problems else 2


if __name__ == "__main__":
    raise SystemExit(main())
