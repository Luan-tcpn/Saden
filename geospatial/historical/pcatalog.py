"""Acesso ao catálogo Sentinel-2 do Planetary Computer (Microsoft).

Por que: o catálogo Earth Search (C1) tem lacunas reais de ingestão (2017 com
uma data, 2022 com cinco datas), enquanto o PC mantém a cobertura completa
2017–2025 dos produtos ESA. Os assets do PC são COGs no Azure Blob e exigem
token SAS público (sem conta, sem custo), obtido por
``https://planetarycomputer.microsoft.com/api/sas/v1/sign``.

Os itens do PC **não** trazem ``raster:bands`` (metadados de escala/offset
ausentes): a conversão radiométrica é derivada do ``processing baseline``,
conforme a regra oficial da ESA (offset −0,1 apenas a partir do baseline 04.00).
Essa regra é validada empiricamente contra a coleção C1 (harmonizada) no
experimento radiométrico.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

PC_STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
PC_SAS = "https://planetarycomputer.microsoft.com/api/sas/v1/sign"
COLLECTION = "sentinel-2-l2a"

USER_AGENT = "SADEN-V2.3/0.1 (investigacao academica)"

# nomes de assets por coleção
BAND_NAMES = {
    "red": "B04",
    "nir": "B08",
    "scl": "SCL",
}


def open_catalog():
    from pystac_client import Client

    return Client.open(PC_STAC)


_SIGN_CACHE: dict[str, str] = {}


def sign_href(href: str, timeout: int = 60, retries: int = 5) -> str:
    """Devolve a URL assinada (SAS público) de um asset do PC.

    O endpoint de assinatura limita a taxa (HTTP 429); por isso há cache em
    memória e repetição com espera progressiva.
    """
    if href in _SIGN_CACHE:
        return _SIGN_CACHE[href]
    query = urllib.parse.urlencode({"href": href})
    last_error: Exception | None = None
    for attempt in range(retries):
        request = urllib.request.Request(
            f"{PC_SAS}?{query}", headers={"User-Agent": USER_AGENT}
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            signed = payload.get("href") or href
            _SIGN_CACHE[href] = signed
            return signed
        except urllib.error.HTTPError as exc:  # pragma: no cover - falha real
            last_error = exc
            if exc.code not in (429, 500, 502, 503):
                break
            time.sleep(2.0 * (attempt + 1))
        except Exception as exc:  # pragma: no cover
            last_error = exc
            time.sleep(2.0 * (attempt + 1))
    raise RuntimeError(
        f"falha ao assinar asset do PC: {last_error}"
    )


def asset_href(item: Any, role: str, sign: bool = True) -> str:
    """URL do asset correspondente a 'red'/'nir'/'scl' (com assinatura se PC)."""
    name = BAND_NAMES[role]
    asset = item.assets.get(name)
    if asset is None:
        raise KeyError(f"{item.id}: asset {name} ausente")
    href = asset.href
    if sign and href.startswith("https://sentinel2l2a"):
        href = sign_href(href)
    return href


def covers(item: Any, bbox: list[float], tol: float = 1e-6) -> bool:
    """Verifica se o item cobre a bbox da AOI (footprint do catálogo)."""
    box = item.bbox
    if not box:
        return False
    return (
        box[0] <= bbox[0] + tol
        and box[1] <= bbox[1] + tol
        and box[2] >= bbox[2] - tol
        and box[3] >= bbox[3] - tol
    )


def tile_code(item: Any) -> str | None:
    """Código MGRS do item (o PC usa 'MGRS-21LXG')."""
    code = item.properties.get("grid:code")
    if code:
        return str(code)
    identifier = str(item.id)
    if "_T21LXG" in identifier:
        return "MGRS-21LXG"
    if "_T21LXF" in identifier:
        return "MGRS-21LXF"
    return None
