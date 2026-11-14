"""V3.4 — mapeamento municipal das macrorregiões sojícolas (MAPA/ZARC).

Fonte: **Instrução Normativa SPA/MAPA nº 1, de 9 de novembro de 2021**, anexo
atualizado pelas Portarias nº 387/2023 e nº 281/2025, que estabelece as
macrorregiões sojícolas e as regiões edafoclimáticas para indicação de
cultivares de soja no ZARC.

Formato usado: a **planilha oficial** publicada pelo MAPA na mesma página de
normativos do ZARC ("Planilha dos municípios e suas respectivas regiões
edafoclimáticas"), que é a versão legível por máquina do mesmo anexo. O PDF da
IN foi consultado e confere com a planilha; a planilha evita erro de
transcrição. O arquivo é baixado do sítio oficial, guardado fora do Git (não é
redistribuído) e identificado por SHA-256.

Limitação registrada: a finalidade original do normativo é **indicação de
cultivares de soja**. Ele é usado aqui como classificação **agroclimática
municipal do território**, não como recomendação de cultivar, e a extensão ao
milho é aproximação declarada no protocolo da V3.4.

Uso: python tools/v34_region_mapping.py
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
import tempfile
import time
import unicodedata
import urllib.request
from datetime import datetime, timezone
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
DATA = os.path.join(ROOT, "geospatial", "data")
EXTERNAL = os.path.join(DATA, "external")
MANIFESTS = os.path.join(DATA, "manifests")
PROCESSED = os.path.join(DATA, "processed")

XLSX_URL = (
    "https://www.gov.br/agricultura/pt-br/assuntos/riscos-seguro/"
    "programa-nacional-de-zoneamento-agricola-de-risco-climatico/"
    "MacrorregioSojicolasAtualizado_2025.xlsx"
)
PDF_URL = (
    "https://www.gov.br/agricultura/pt-br/assuntos/riscos-seguro/"
    "programa-nacional-de-zoneamento-agricola-de-risco-climatico/"
    "INSTRUONORMATIVAN1DE9DENOVEMBRODE2021MACRORREGIOSOJCOLASATUALIZADO2025.pdf"
)
XLSX = os.path.join(EXTERNAL, "MacrorregioSojicolasAtualizado_2025.xlsx")
OUT_LONG = os.path.join(MANIFESTS, "v34_region_mapping_long.csv")
OUT_JSON = os.path.join(MANIFESTS, "v34_region_mapping.json")
OUT_PANEL = os.path.join(PROCESSED, "municipality_region_mapping.csv")

PANEL_STATES = ("PR", "RS", "MS", "MT", "GO", "BA")


def strip_accents(text: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch)
    )


def normalize(text: str) -> str:
    """Forma canônica: sem acento, sem caixa, só letras."""
    return re.sub(r"[^a-z]", "", strip_accents(str(text)).lower())


def download() -> None:
    os.makedirs(EXTERNAL, exist_ok=True)
    if os.path.exists(XLSX) and os.path.getsize(XLSX) > 50_000:
        print(f"planilha em cache: {os.path.getsize(XLSX)} bytes")
        return
    print("baixando a planilha oficial do MAPA...", flush=True)
    request = urllib.request.Request(
        XLSX_URL,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            "Referer": (
                "https://www.gov.br/agricultura/pt-br/assuntos/riscos-seguro/"
                "programa-nacional-de-zoneamento-agricola-de-risco-climatico/"
                "normativos-do-zarc"
            ),
        },
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        payload = response.read()
    with open(XLSX, "wb") as handle:
        handle.write(payload)
    print(f"baixado: {len(payload)} bytes")


def read_rows() -> list[dict[str, Any]]:
    import openpyxl

    workbook = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    sheet = workbook[workbook.sheetnames[0]]
    rows: list[dict[str, Any]] = []
    header_seen = False
    for values in sheet.iter_rows(values_only=True):
        if not header_seen:
            if values and str(values[0]).strip().lower().startswith("macrorregi"):
                header_seen = True
            continue
        macro, edafo, uf, municipality = values[0], values[1], values[2], values[3]
        if uf is None or municipality is None:
            continue
        try:
            macro_int = int(macro)
        except (TypeError, ValueError):
            continue
        rows.append(
            {
                "macroregion": str(macro_int),
                "edapho_region": str(int(edafo)) if edafo is not None else "",
                "uf": str(uf).strip().upper(),
                "municipality_raw": str(municipality).strip(),
                "municipality_key": normalize(municipality),
            }
        )
    workbook.close()
    return rows


def join_panel(rows: list[dict[str, Any]]) -> dict[str, Any]:
    lookup = {(row["uf"], row["municipality_key"]): row for row in rows}
    panel_path = os.path.join(PROCESSED, "panel_municipalities.csv")
    joined: list[dict[str, Any]] = []
    unmatched: list[dict[str, str]] = []
    with open(panel_path, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            uf = str(row.get("state") or "").upper()
            if uf not in PANEL_STATES:
                continue
            key = normalize(row.get("municipality") or "")
            found = lookup.get((uf, key))
            if found is None:
                unmatched.append({"uf": uf, "municipality": str(row.get("municipality"))})
                continue
            joined.append(
                {
                    "ibge_code": str(row["ibge_code"]),
                    "municipality": row.get("municipality"),
                    "uf": uf,
                    "edapho_region": found["edapho_region"],
                    "macroregion": found["macroregion"],
                }
            )
    return {"joined": joined, "unmatched": unmatched}


def main() -> int:
    started = time.time()
    download()
    digest = hashlib.sha256(open(XLSX, "rb").read()).hexdigest()
    rows = read_rows()
    print(f"linhas na planilha: {len(rows)}", flush=True)

    panel_rows = [row for row in rows if row["uf"] in PANEL_STATES]
    by_state: dict[str, int] = {}
    by_macro: dict[str, int] = {}
    by_pair: dict[str, int] = {}
    for row in panel_rows:
        by_state[row["uf"]] = by_state.get(row["uf"], 0) + 1
        by_macro[row["macroregion"]] = by_macro.get(row["macroregion"], 0) + 1
        pair = f"{row['uf']}|MRS{row['macroregion']}"
        by_pair[pair] = by_pair.get(pair, 0) + 1
    print("por UF:", dict(sorted(by_state.items())))
    print("por macrorregião:", dict(sorted(by_macro.items())))
    print("UF × macrorregião:")
    for key in sorted(by_pair):
        print(f"   {key:<10} {by_pair[key]}")

    duplicates = [
        key for key in {k for k in {(r['uf'], r['municipality_key']) for r in panel_rows}}
        if sum(1 for r in panel_rows if (r['uf'], r['municipality_key']) == key) > 1
    ]

    os.makedirs(MANIFESTS, exist_ok=True)
    with open(OUT_LONG, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["uf", "municipality_raw", "municipality_key", "edapho_region", "macroregion"],
        )
        writer.writeheader()
        writer.writerows(panel_rows)

    joined = join_panel(panel_rows)
    with open(OUT_PANEL, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["ibge_code", "municipality", "uf", "edapho_region", "macroregion"],
        )
        writer.writeheader()
        writer.writerows(joined["joined"])

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "normative": "Instrução Normativa SPA/MAPA nº 1, de 9 de novembro de 2021",
            "annex_updates": [
                "Portaria SPA/MAPA nº 387, de 16 de outubro de 2023",
                "Portaria SPA/MAPA nº 281, de 28 de maio de 2025",
            ],
            "institution": "Ministério da Agricultura e Pecuária (MAPA) — Secretaria de Política Agrícola",
            "published_spreadsheet": "Planilha dos municípios e suas respectivas regiões edafoclimáticas",
            "url_xlsx": XLSX_URL,
            "url_pdf": PDF_URL,
            "url_landing": (
                "https://www.gov.br/agricultura/pt-br/assuntos/riscos-seguro/"
                "programa-nacional-de-zoneamento-agricola-de-risco-climatico/normativos-do-zarc"
            ),
            "accessed_at": datetime.now(timezone.utc).date().isoformat(),
            "xlsx_sha256": digest,
            "xlsx_bytes": os.path.getsize(XLSX),
            "purpose_original": "indicação de cultivares de soja no ZARC",
        },
        "coverage": {
            "rows_total": len(rows),
            "rows_panel_states": len(panel_rows),
            "by_state": dict(sorted(by_state.items())),
            "by_macroregion": dict(sorted(by_macro.items())),
            "by_state_macroregion": dict(sorted(by_pair.items())),
            "duplicate_state_municipality": len(duplicates),
        },
        "join": {
            "panel_municipalities": len(joined["joined"]) + len(joined["unmatched"]),
            "matched": len(joined["joined"]),
            "unmatched": len(joined["unmatched"]),
            "unmatched_examples": joined["unmatched"][:20],
        },
        "limitations": [
            "finalidade original é indicação de cultivares de SOJA; extensão ao milho é aproximação declarada",
            "macrorregião sojícola não é bioma: MRS 4 inclui MT (Cerrado e transição amazônica), GO e oeste da BA",
            "MRS 2 é uma faixa de transição (norte do PR e centro-sul do MS) e não é classificada como Sul nem como Cerrado",
            "a planilha só lista municípios com indicação de soja; ausência não é erro de parse",
        ],
        "elapsed_s": round(time.time() - started, 1),
    }
    with open(OUT_JSON, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
        handle.write("\n")
    print(json.dumps(payload["join"], ensure_ascii=False, indent=2))
    print(f"mapeamento: {OUT_PANEL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
