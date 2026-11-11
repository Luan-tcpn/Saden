"""Auditoria radiométrica de produtos Sentinel-2 L2A.

Fatos verificados em 2026-11-11 contra o catálogo Earth Search e os COGs reais:

* Os assets expõem ``raster:bands[0].scale = 0.0001`` e
  ``offset = -0.1`` (Processing Baseline >= 04.00).
* ``rasterio.read()`` devolve o DN uint16 **bruto**; ``ds.scales``/``ds.offsets``
  são apenas metadados e **não** são aplicados automaticamente. Converter uma
  única vez com ``DN * scale + offset`` é, portanto, correto.
* Baselines observados na janela 2023–2025: 05.09, 05.10, 05.11. Baseline
  anterior a 04.00 não tem offset e **não** é suportada sem tratamento
  específico — nesse caso o processamento deve ser bloqueado.
"""

from __future__ import annotations

from typing import Any

MIN_SUPPORTED_BASELINE = 4.0

# Faixa de DN esperada em L2A (BOA_QUANTIFICATION_VALUE = 10000).
L2A_DN_MAX = 10000


class UnsupportedProductError(RuntimeError):
    """Produto cujo baseline/escala não pode ser convertido com segurança."""


def parse_baseline(value: Any) -> float | None:
    """Converte '05.11' (string) em 5.11; devolve None se ausente/inválido."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def asset_radiometry(asset: Any) -> dict[str, Any]:
    """Lê scale/offset/nodata/dtype/resolução do metadado STAC do asset."""
    bands = asset.extra_fields.get("raster:bands") or []
    band = bands[0] if bands else {}
    return {
        "scale": band.get("scale"),
        "offset": band.get("offset"),
        "nodata": band.get("nodata"),
        "data_type": band.get("data_type"),
        "spatial_resolution": band.get("spatial_resolution"),
    }


def item_baseline(item: Any) -> float | None:
    return parse_baseline(item.properties.get("s2:processing_baseline"))


def assert_supported_item(item: Any, band_names: tuple[str, ...]) -> dict[str, Any]:
    """Valida baseline e coerência radiométrica entre as bandas contínuas.

    Levanta :class:`UnsupportedProductError` se o produto não puder ser
    convertido com segurança (baseline ausente/< 4.0, escala/offset ausentes
    ou diferentes entre bandas, dtype inesperado).
    """
    baseline = item_baseline(item)
    if baseline is None:
        raise UnsupportedProductError(
            f"{item.id}: s2:processing_baseline ausente — conversão não verificável"
        )
    if baseline < MIN_SUPPORTED_BASELINE:
        raise UnsupportedProductError(
            f"{item.id}: baseline {baseline} < {MIN_SUPPORTED_BASELINE} "
            "(sem BOA_ADD_OFFSET); asset bloqueado"
        )

    per_band: dict[str, dict[str, Any]] = {}
    for name in band_names:
        asset_name = {
            "blue": "blue", "red": "red", "nir": "nir", "swir": "swir16"
        }.get(name, name)
        asset = item.assets.get(asset_name)
        if asset is None:
            raise UnsupportedProductError(f"{item.id}: asset ausente {asset_name!r}")
        meta = asset_radiometry(asset)
        if meta["scale"] is None or meta["offset"] is None:
            raise UnsupportedProductError(
                f"{item.id}/{asset_name}: scale ou offset ausente no metadado"
            )
        if meta["data_type"] not in ("uint16", "uint8"):
            raise UnsupportedProductError(
                f"{item.id}/{asset_name}: dtype inesperado {meta['data_type']!r}"
            )
        per_band[name] = meta

    reference = per_band[band_names[0]]
    for name, meta in per_band.items():
        if (meta["scale"], meta["offset"], meta["nodata"]) != (
            reference["scale"], reference["offset"], reference["nodata"]
        ):
            raise UnsupportedProductError(
                f"{item.id}: radiometria inconsistente entre bandas "
                f"({name}={meta} vs {band_names[0]}={reference})"
            )

    return {
        "item_id": item.id,
        "baseline": baseline,
        "baseline_raw": item.properties.get("s2:processing_baseline"),
        "scale": reference["scale"],
        "offset": reference["offset"],
        "nodata": reference["nodata"],
        "bands": per_band,
        "conversion": "DN * scale + offset (DN nodata -> NaN antes da escala)",
        "baseline_supported": True,
    }


def file_radiometry(ds: Any) -> dict[str, Any]:
    """Metadados radiométricos lidos do COG aberto (não aplica escala)."""
    return {
        "dtype": ds.dtypes[0] if ds.dtypes else None,
        "scales": tuple(ds.scales),
        "offsets": tuple(ds.offsets),
        "nodata": ds.nodata,
        "crs": str(ds.crs),
        "res": tuple(ds.res),
        "transform": tuple(ds.transform)[:6],
        "width": ds.width,
        "height": ds.height,
    }


def check_file_matches_asset(file_meta: dict[str, Any], asset_meta: dict[str, Any]) -> dict[str, Any]:
    """Confere se o COG declara a mesma escala/offset do metadado STAC.

    Não aplica escala: apenas garante que a conversão manual corresponde ao que
    o arquivo declara (evita dupla aplicação ou conversão inventada).
    """
    scale_file = file_meta["scales"][0] if file_meta["scales"] else None
    offset_file = file_meta["offsets"][0] if file_meta["offsets"] else None
    matches = (
        scale_file == asset_meta.get("scale") and offset_file == asset_meta.get("offset")
    )
    return {
        "file_scale": scale_file,
        "file_offset": offset_file,
        "asset_scale": asset_meta.get("scale"),
        "asset_offset": asset_meta.get("offset"),
        "matches": bool(matches),
        "read_returns_raw_dn": True,
    }
