"""Aquisição e leitura das planilhas oficiais da CONAB (Boletim de Safras).

O que foi verificado em 2026-11-11 (documentado no relatório da V2.2):

* ``https://www.gov.br/conab/pt-br/.../boletim-da-safra-de-graos`` publica
  planilhas ``.xlsx`` (granéis) e ``.xls`` (café) por **levantamento**;
* a granularidade dessas planilhas é **estadual (UF)** e nacional — não há
  dado municipal nesses arquivos;
* as variáveis são área (mil ha), produtividade (kg/ha) e produção (mil t),
  comparando a safra corrente com a anterior;
* os valores são **estimativas de levantamento** (provisórias e revisadas),
  não observações de campo;
* ``dados.gov.br`` responde 401 (exige autenticação) e ``sigs.conab.gov.br`` /
  ``api.conab.gov.br`` não resolvem DNS neste ambiente — o único acesso
  automatizável é o portal de boletins.
"""

from __future__ import annotations

import gzip
import io
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from . import config

USER_AGENT = "Mozilla/5.0 (compatible; SADEN-V2.2 academic research)"


class ConabError(RuntimeError):
    """Falha ao obter dados da CONAB."""


def _fetch(url: str, timeout: int = 120) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        raise ConabError(f"HTTP {exc.code} em {url}") from exc
    except Exception as exc:  # noqa: BLE001
        raise ConabError(f"falha de rede em {url}: {type(exc).__name__}") from exc
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return raw


def list_spreadsheets(index_url: str) -> list[dict[str, str]]:
    """Lista as planilhas publicadas na página índice de um boletim."""
    from urllib.parse import urljoin

    text = _fetch(index_url).decode("utf-8", "replace")
    links = re.findall(r'href="([^"]+)"', text)
    files = []
    for link in links:
        if not re.search(r"\.(xlsx?|csv)(\?|$)", link, re.I):
            continue
        url = urljoin(index_url, link)
        name = url.rsplit("/", 1)[-1]
        levantamento = ""
        match = re.search(r"(\d+[oº])-levantamento-safra-(\d{4})-(\d{2})", url, re.I)
        if match:
            levantamento = f"{match.group(1)}-levantamento-safra-{match.group(2)}/{match.group(3)}"
        reference = ""
        ref = re.search(r"-(\d{4})\.(xlsx?|csv)$", name, re.I)
        if ref:
            reference = ref.group(1)
        files.append(
            {
                "name": name,
                "url": url,
                "levantamento": levantamento,
                "reference_year": reference,
            }
        )
    return files


def download(url: str, destination: str) -> dict[str, Any]:
    """Baixa uma planilha e grava o arquivo bruto com checksum."""
    raw = _fetch(url)
    os.makedirs(os.path.dirname(os.path.abspath(destination)), exist_ok=True)
    with open(destination, "wb") as handle:
        handle.write(raw)
    import hashlib

    digest = hashlib.sha256(raw).hexdigest()
    return {
        "url": url,
        "path": destination,
        "bytes": len(raw),
        "sha256": digest,
        "acquired_at": datetime.now(timezone.utc).isoformat(),
    }


def _cell(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, float):
        return value
    return value


def _to_number(value: Any) -> float | None:
    value = _cell(value)
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace("%", "").strip()
    if text in {"", "-", "--", "..", "..."}:
        return None
    try:
        return float(text.replace(".", "").replace(",", ".")) if text.count(",") == 1 and "." in text else float(text)
    except ValueError:
        return None


def _read_sheet_rows(path: str, sheet: str) -> list[list[Any]]:
    """Lê as linhas de uma planilha (xlsx com openpyxl, xls com xlrd)."""
    if path.lower().endswith(".xlsx"):
        import openpyxl

        workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
        try:
            if sheet not in workbook.sheetnames:
                return []
            return [list(row) for row in workbook[sheet].iter_rows(values_only=True)]
        finally:
            workbook.close()
    import xlrd

    book = xlrd.open_workbook(path)
    try:
        if sheet not in book.sheet_names():
            return []
        worksheet = book.sheet_by_name(sheet)
        return [worksheet.row_values(i) for i in range(worksheet.nrows)]
    finally:
        book.release_resources()


def sheet_names(path: str) -> list[str]:
    if path.lower().endswith(".xlsx"):
        import openpyxl

        workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
        try:
            return list(workbook.sheetnames)
        finally:
            workbook.close()
    import xlrd

    book = xlrd.open_workbook(path)
    try:
        return list(book.sheet_names())
    finally:
        book.release_resources()


def _detect_safras(header_rows: list[list[Any]]) -> list[str]:
    """Encontra as safras declaradas no cabeçalho (ex.: 'Safra 24/25')."""
    safras: list[str] = []
    for row in header_rows[:6]:
        for value in row:
            text = str(_cell(value) or "")
            match = re.search(r"Safra\s*(\d{2}/\d{2})", text, re.I)
            if match and match.group(1) not in safras:
                safras.append(match.group(1))
    return safras


HEADER_ROW_MARKERS = ("ÁREA", "AREA")
SKIP_LABELS = ("SUBTOTAL", "MATO GROSSO", "BRASIL", "TOTAL GERAL")


def _is_header_row(row: list[Any]) -> bool:
    cells = [_cell(value) for value in row[:3]]
    if not cells or cells[1] is None:
        return False
    return any(marker in str(cells[1]).upper() for marker in HEADER_ROW_MARKERS)


def _detect_periods(rows: list[list[Any]], index: int) -> tuple[list[str], str]:
    """Lê os rótulos de período da linha seguinte ao cabeçalho.

    Devolve ``([período_a, período_b], tipo)`` onde tipo é ``"safra"``
    (ex.: ``24/25``) ou ``"ano_civil"`` (ex.: ``2025``, bloco "culturas de
    inverno").
    """
    for offset in (1, 2):
        if index + offset >= len(rows):
            break
        candidate = rows[index + offset]
        values = [_cell(value) for value in candidate[:3]]
        if not values or values[1] is None or values[2] is None:
            continue
        first, second = str(values[1]).strip(), str(values[2]).strip()
        if re.match(r"^Safra\s*\d{2}/\d{2}$", first, re.I) and re.match(
            r"^Safra\s*\d{2}/\d{2}$", second, re.I
        ):
            return [
                re.search(r"(\d{2}/\d{2})", first, re.I).group(1),
                re.search(r"(\d{2}/\d{2})", second, re.I).group(1),
            ], "safra"
        if re.match(r"^(19|20)\d{2}$", first) and re.match(r"^(19|20)\d{2}$", second):
            return [first, second], "ano_civil"
    return [], ""


_PARENT_TOTAL = re.compile(r"^(?P<label>.+?)\s+TOTAL$", re.I)
_PARENT_SAFRA = re.compile(r"^(?P<label>.+?)\s+(?P<safra>\d\s*[ªºa]\s*SAFRA)$", re.I)


def _scope_and_full_label(
    label: str, group_parent: str | None
) -> tuple[str, str, str | None]:
    """Devolve ``(escopo, rótulo_completo, novo_grupo_pai)``.

    Na planilha, linhas como "Cores"/"Preto"/"Caupi" são **tipos** do produto
    pai declarado imediatamente antes ("FEIJÃO 1ª SAFRA"). Linhas em caixa
    alta ("SOJA", "ARROZ") são produtos novos e não herdam o rótulo anterior.
    """
    text = label.strip()
    total = _PARENT_TOTAL.match(text)
    if total:
        return "total", text, group_parent
    safra = _PARENT_SAFRA.match(text)
    if safra:
        return "grupo_safra", text, text
    is_child_style = text != text.upper() and not re.search(r"\d", text)
    if group_parent and is_child_style:
        return "componente", f"{group_parent} - {text}", group_parent
    return "produto", text, None


def parse_state_sheet(path: str, sheet: str = "MT") -> list[dict[str, Any]]:
    """Extrai registros de uma aba por UF (produto × período).

    A aba tem **dois blocos**: o bloco principal (comparação de safras) e o
    bloco "CULTURAS DE INVERNO" (comparação de anos civis). Os rótulos
    "Cores"/"Preto"/"Caupi" são componentes do produto pai ("FEIJÃO 1ª
    SAFRA") e por isso são prefixados com o pai.
    """
    rows = _read_sheet_rows(path, sheet)
    if not rows:
        return []

    records: list[dict[str, Any]] = []
    periods: list[str] = []
    period_kind = ""
    group_parent: str | None = None

    for index, row in enumerate(rows):
        label = _cell(row[0] if row else None)
        if label is None:
            continue
        text = str(label).strip()
        if _is_header_row(row):
            periods, period_kind = _detect_periods(rows, index)
            group_parent = None
            continue
        if not periods or len(periods) < 2:
            continue
        upper = text.upper()
        if upper.startswith(("LEGENDA", "FONTE", "NOTA")) or upper in SKIP_LABELS:
            continue
        if upper.startswith("CULTURAS DE INVERNO"):
            continue

        values = list(row) + [None] * (10 - len(row))
        area_a, area_b = _to_number(values[1]), _to_number(values[2])
        prod_a, prod_b = _to_number(values[4]), _to_number(values[5])
        quant_a, quant_b = _to_number(values[7]), _to_number(values[8])
        if area_a is None and area_b is None and prod_a is None and quant_a is None:
            continue

        scope, full_label, new_group = _scope_and_full_label(text, group_parent)
        if new_group:
            group_parent = new_group
        elif scope == "produto":
            group_parent = None

        for period_label, area, produtividade, quantidade in (
            (periods[0], area_a, prod_a, quant_a),
            (periods[1], area_b, prod_b, quant_b),
        ):
            if area is None and quantidade is None:
                continue
            records.append(
                {
                    "uf": sheet,
                    "product_original": full_label,
                    "product_scope": scope,
                    "period_kind": period_kind,
                    "period_label": period_label,
                    "area_mil_ha": area,
                    "produtividade_kg_ha": produtividade,
                    "producao_mil_t": quantidade,
                }
            )
    return records


def parse_coffee_sheet(path: str) -> list[dict[str, Any]]:
    """Extrai registros do boletim de café (formato ``.xls`` legado)."""
    names = sheet_names(path)
    for sheet in names:
        rows = _read_sheet_rows(path, sheet)
        if not rows:
            continue
        text = " ".join(
            str(_cell(value) or "") for row in rows[:12] for value in row[:8]
        ).upper()
        if "PRODUTIVIDADE" in text and ("ÁREA" in text or "AREA" in text):
            return parse_state_sheet(path, sheet)
    return []
