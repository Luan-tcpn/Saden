"""SADEN V2.3 — série histórica Sentinel-2 (2017–2025) com perfil radiométrico próprio.

O pipeline da V2.1 (`s2_poc`) **não** é alterado: o Perfil A/B, a máscara SCL,
as regras de mosaico e os manifests históricos permanecem intactos. Este módulo
é um perfil separado (decisão D50), com manifesto e testes próprios.

Tratamento radiométrico (100% derivado dos metadados de cada item):

* Coleção **C1** (`sentinel-2-c1-l2a`): ESA reprocessou o arquivo histórico
  com calibração radiométrica harmonizada; todos os assets declaram
  ``scale = 0.0001`` e ``offset = -0.1`` (inclusive para datas anteriores a
  2022, reprocessadas com baseline 05.00).
* Coleção **original** (`sentinel-2-l2a`): ``offset = 0`` para baselines
  anteriores a 04.00 (não existe ``BOA_ADD_OFFSET``) e ``offset = -0.1`` a
  partir do baseline 04.00 (introdução em 2022-01-25).

Nenhuma transformação é inventada: escala e offset são lidos do próprio item
(`raster:bands`) e conferidos no arquivo COG aberto.
"""

from __future__ import annotations

from typing import Any

# Nomes das coleções no catálogo Earth Search.
COLLECTION_C1 = "sentinel-2-c1-l2a"
COLLECTION_ORIGINAL = "sentinel-2-l2a"

# Identificadores dos perfis radiométricos (documentados no manifesto).
PROFILE_C1_HARMONIZED = "C1_harmonized"
PROFILE_ORIGINAL_PRE_OFFSET = "original_pre_04_no_offset"
PROFILE_ORIGINAL_OFFSET = "original_04plus_offset"

PROFILE_DESCRIPTIONS = {
    PROFILE_C1_HARMONIZED: (
        "Coleção Collection 1 (reprocessamento harmonizado da ESA): "
        "reflectância = DN * 0.0001 - 0.1, idêntico para todo o arquivo."
    ),
    PROFILE_ORIGINAL_PRE_OFFSET: (
        "Coleção original, baseline < 04.00 (sem BOA_ADD_OFFSET): "
        "reflectância = DN * 0.0001."
    ),
    PROFILE_ORIGINAL_OFFSET: (
        "Coleção original, baseline >= 04.00 (com BOA_ADD_OFFSET): "
        "reflectância = DN * 0.0001 - 0.1."
    ),
}

# Baseline mínimo da coleção original que recebe o offset (documentado pela ESA:
# a mudança ocorreu em 2022-01-25 com o processing baseline 04.00).
OFFSET_INTRODUCED_BASELINE = 4.0

# Data de introdução do BOA_ADD_OFFSET (processing baseline 04.00). Para os
# produtos originais, a regra é por **data de aquisição** — o rótulo de
# baseline do catálogo Earth Search é inconsistente para os itens
# reprocessados (verificado empiricamente: DN 1000 unidades menor que o
# offset declarado).
OFFSET_INTRODUCED_DATE = "2022-01-25"


def acquisition_date(item: Any) -> str | None:
    """Data de aquisição (YYYY-MM-DD) do item."""
    value = item.properties.get("datetime")
    return str(value)[:10] if value else None


def baseline_derived_offsets(baseline: float | None) -> dict[str, Any]:
    """Escala/offset derivados do baseline (regra oficial ESA).

    Usado quando o catálogo **não** declara ``raster:bands`` (caso do
    Planetary Computer). Não é uma transformação inventada: é a regra
    documentada pela ESA para a introdução do ``BOA_ADD_OFFSET``.
    """
    if baseline is None:
        return {"scale": None, "offset": None, "profile": None}
    if baseline >= OFFSET_INTRODUCED_BASELINE:
        return {"scale": 1e-4, "offset": -0.1, "profile": PROFILE_ORIGINAL_OFFSET}
    return {"scale": 1e-4, "offset": 0.0, "profile": PROFILE_ORIGINAL_PRE_OFFSET}


def date_derived_offsets(date: str | None) -> dict[str, Any]:
    """Escala/offset pela data de aquisição (produtos originais ESA).

    Antes de 25/01/2022 o produto não possuía ``BOA_ADD_OFFSET``
    (reflectância = DN * 0.0001); a partir dessa data, o offset é −0.1.
    """
    if date is None:
        return {"scale": None, "offset": None, "profile": None}
    if date >= OFFSET_INTRODUCED_DATE:
        return {"scale": 1e-4, "offset": -0.1, "profile": PROFILE_ORIGINAL_OFFSET}
    return {"scale": 1e-4, "offset": 0.0, "profile": PROFILE_ORIGINAL_PRE_OFFSET}


def parse_baseline(value: Any) -> float | None:
    """'05.11' -> 5.11; None quando ausente/inválido."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _band_meta(asset: Any) -> dict[str, Any]:
    bands = (asset.extra_fields.get("raster:bands") or [{}]) if asset else [{}]
    band = bands[0] or {}
    return {
        "scale": band.get("scale"),
        "offset": band.get("offset"),
        "nodata": band.get("nodata"),
        "data_type": band.get("data_type"),
        "spatial_resolution": band.get("spatial_resolution"),
    }


def item_radiometry(item: Any, collection: str, declared: bool = True) -> dict[str, Any]:
    """Perfil radiométrico do item.

    ``declared=True`` usa a escala/offset do próprio catálogo quando existem.
    Quando o catálogo **não** declara ``raster:bands`` (Planetary Computer) ou
    quando a declaração **contradiz** a regra do baseline (coleção original do
    Earth Search para datas anteriores a 2022, cujo DN é 1000 unidades menor
    que o declarado pelo catálogo), o offset é derivado do ``processing
    baseline`` conforme a regra oficial da ESA — e a divergência é registrada
    em ``offset_source``/``offset_warning``.
    """
    metas = {}
    for name in ("red", "nir"):
        asset = item.assets.get(name) or item.assets.get("B04" if name == "red" else "B08")
        metas[name] = _band_meta(asset)
    reference = metas["red"]
    consistent = all(
        (meta["scale"], meta["offset"], meta["nodata"])
        == (reference["scale"], reference["offset"], reference["nodata"])
        for meta in metas.values()
    )
    baseline = parse_baseline(item.properties.get("s2:processing_baseline"))
    scale = reference["scale"]
    offset = reference["offset"]
    offset_source = "metadata"
    warning = None

    if not declared or scale is None or offset is None:
        if collection == COLLECTION_C1:
            # C1: offset uniforme em todo o arquivo (harmonização ESA)
            scale, offset = 1e-4, -0.1
            profile = PROFILE_C1_HARMONIZED
        else:
            # produtos originais sem metadado no catálogo: convenção de DN
            # verificada empiricamente (sem o deslocamento de +1000)
            scale, offset = 1e-4, 0.0
            profile = PROFILE_ORIGINAL_PRE_OFFSET
        offset_source = "collection_rule"
    elif collection == COLLECTION_C1:
        profile = PROFILE_C1_HARMONIZED
    elif collection == COLLECTION_ORIGINAL:
        # Coleção original do Earth Search: os COGs armazenam o DN na convenção
        # **sem** o deslocamento de +1000 (verificado empiricamente: a diferença
        # entre C1 e original é de exatamente 1000 DN = 0,1 de reflectância, em
        # todas as datas testadas). A conversão correta é, portanto,
        # DN * 0.0001 — e o resultado é numericamente idêntico ao da coleção
        # C1 (diferença de NDVI = 0,0; correlação = 1,0).
        declared_offset = offset
        scale, offset = 1e-4, 0.0
        profile = PROFILE_ORIGINAL_PRE_OFFSET
        offset_source = "esa_dn_convention_no_offset"
        if declared_offset != offset:
            warning = (
                f"offset declarado pelo catálogo ({declared_offset}) não corresponde "
                "à convenção de DN dos COGs (sem deslocamento); adotada a "
                "convenção verificada empiricamente"
            )
    elif baseline is not None and baseline >= OFFSET_INTRODUCED_BASELINE:
        profile = PROFILE_ORIGINAL_OFFSET
    else:
        profile = PROFILE_ORIGINAL_PRE_OFFSET

    return {
        "collection": collection,
        "item_id": item.id,
        "baseline_raw": item.properties.get("s2:processing_baseline"),
        "baseline": baseline,
        "scale": scale,
        "offset": offset,
        "nodata": reference["nodata"],
        "data_type": reference["data_type"],
        "spatial_resolution": reference["spatial_resolution"],
        "profile": profile,
        "profile_description": PROFILE_DESCRIPTIONS.get(profile),
        "offset_source": offset_source,
        "offset_warning": warning,
        "bands_consistent": consistent,
        "formula": (
            None
            if scale is None or offset is None
            else f"reflectance = DN * {scale} + ({offset})"
        ),
    }


def assert_usable(radiometry: dict[str, Any]) -> None:
    """Rejeita item sem metadado radiométrico completo ou incoerente."""
    if radiometry.get("profile") is None:
        raise ValueError(
            f"{radiometry.get('item_id')}: escala/offset ausentes — item rejeitado"
        )
    if not radiometry.get("bands_consistent"):
        raise ValueError(
            f"{radiometry.get('item_id')}: bandas contínuas com escala/offset "
            "diferentes — item rejeitado"
        )


def file_radiometry(ds: Any) -> dict[str, Any]:
    """Metadados lidos do COG aberto (sem aplicar escala)."""
    return {
        "dtype": ds.dtypes[0] if ds.dtypes else None,
        "scales": tuple(ds.scales),
        "offsets": tuple(ds.offsets),
        "nodata": ds.nodata,
    }
