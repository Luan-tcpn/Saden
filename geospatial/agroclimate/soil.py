"""Capacidade de água disponível do solo (CAD) — módulo de conversão (V2.7).

Fonte dos dados: Embrapa Solos / GeoInfo — *Mapas de água disponível do solo
do Brasil* (Vasques, G.M., Dart, R.O., Cintra, L.C. & Baca, J.F.M., 2021.
Soil Available Water Maps for Brazil at 0-5, 5-15, 15-30, 30-60, 60-100 and
100-200 cm Depth Intervals with 90 m Spatial Resolution. Version 2021.
Embrapa Solos, Rio de Janeiro). Licença CC BY-NC 3.0 BR.

Unidade declarada das camadas: **mm/cm** — milímetros de água disponível
por centímetro de profundidade de solo. Consequentemente, a capacidade de
água disponível do perfil (em **mm** de água) é a **integração** do valor
multiplicada pela espessura de cada camada:

    CAD(mm) = Σ_camadas  AW(mm/cm) · espessura(cm)

Este módulo implementa essa conversão de forma explícita e testável. Ele
**não** infere propriedades de solo que não estejam nas camadas: onde não
há dado válido, a ausência é preservada (o valor é ``None``), nunca
substituída por um cenário.

Cenários históricos da V2.6 (``35``, ``50`` e ``70`` mm) são mantidos como
**comparação**, não como substituto do dado geoespacial.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

# Intervalos de profundidade publicados (cm) e suas camadas no GeoInfo.
AW_LAYERS: tuple[dict[str, Any], ...] = (
    {"key": "aw_0_5", "coverage_id": "geonode__aw_0_5_def", "top_cm": 5, "bottom_cm": 0},
    {"key": "aw_5_15", "coverage_id": "geonode__aw_5_15_def", "top_cm": 15, "bottom_cm": 5},
    {"key": "aw_15_30", "coverage_id": "geonode__aw_15_30_def", "top_cm": 30, "bottom_cm": 15},
    {"key": "aw_30_60", "coverage_id": "geonode__aw_30_60_def", "top_cm": 60, "bottom_cm": 30},
    {"key": "aw_60_100", "coverage_id": "geonode__aw_60_100_def", "top_cm": 100, "bottom_cm": 60},
    {"key": "aw_100_200", "coverage_id": "geonode__aw_100_200_def", "top_cm": 200, "bottom_cm": 100},
)

# Valores nodata declarados pelo serviço (GeoServer) e valores inválidos.
NODATA_SENTINELS: tuple[float, ...] = (-9999.0, -3.4028235e38)

# Cenários de CAD usados na V2.6 (balanço hídrico) — mantidos para
# comparação; não substituem o dado geoespacial.
V26_SCENARIO_CAPACITIES_MM: tuple[float, ...] = (35.0, 50.0, 70.0)

AW_SOURCE = (
    "Vasques, G.M., Dart, R.O., Cintra, L.C., Baca, J.F.M. (2021). Soil "
    "Available Water Maps for Brazil at 0-5, 5-15, 15-30, 30-60, 60-100 and "
    "100-200 cm Depth Intervals with 90 m Spatial Resolution. Version 2021. "
    "Embrapa Solos, Rio de Janeiro, Brazil."
)
AW_LICENSE = "CC BY-NC 3.0 BR (uso não-comercial)"
AW_UNIT = "mm/cm"


def layer_thickness_cm(layer: Mapping[str, Any]) -> float:
    """Espessura da camada em cm."""
    return float(layer["top_cm"]) - float(layer["bottom_cm"])


def clean_value(value: Any) -> float | None:
    """Normaliza um valor bruto da camada; ``None`` quando ausente/inválido."""
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:  # NaN
        return None
    for sentinel in NODATA_SENTINELS:
        if abs(number - sentinel) < 1e-6:
            return None
    if number <= 0.0:
        return None
    return number


def profile_capacity_mm(
    values_mm_per_cm: Mapping[str, float | None],
    layers: Sequence[Mapping[str, Any]] = AW_LAYERS,
) -> dict[str, Any]:
    """Integra a água disponível do perfil (mm) sobre um conjunto de camadas.

    ``values_mm_per_cm`` mapeia a chave da camada (``"aw_0_5"`` ...) para o
    valor mediano amostrado (mm/cm) ou ``None`` (sem dado válido).

    Devolve, além do total, o detalhe por camada e a fração de cobertura
    do perfil — de modo que a ausência de dado fique explícita.
    """
    detail: list[dict[str, Any]] = []
    total = 0.0
    covered = 0.0
    thickness_total = 0.0
    for layer in layers:
        key = str(layer["key"])
        thickness = layer_thickness_cm(layer)
        thickness_total += thickness
        raw = values_mm_per_cm.get(key)
        value = clean_value(raw)
        if value is None:
            detail.append(
                {
                    "key": key,
                    "top_cm": layer["top_cm"],
                    "bottom_cm": layer["bottom_cm"],
                    "thickness_cm": thickness,
                    "aw_mm_per_cm": None,
                    "contribution_mm": None,
                    "status": "sem_dado",
                }
            )
            continue
        contribution = value * thickness
        total += contribution
        covered += thickness
        detail.append(
            {
                "key": key,
                "top_cm": layer["top_cm"],
                "bottom_cm": layer["bottom_cm"],
                "thickness_cm": thickness,
                "aw_mm_per_cm": value,
                "contribution_mm": contribution,
                "status": "ok",
            }
        )
    complete = thickness_total > 0 and abs(covered - thickness_total) < 1e-9
    return {
        "capacity_mm": total if complete else None,
        "capacity_partial_mm": total,
        "coverage_fraction": (covered / thickness_total) if thickness_total else 0.0,
        "profile_complete": complete,
        "layers": detail,
        "unit_source": AW_UNIT,
        "source": AW_SOURCE,
    }


def profile_capacity_to_depth_mm(
    values_mm_per_cm: Mapping[str, float | None],
    depth_cm: float,
    layers: Sequence[Mapping[str, Any]] = AW_LAYERS,
) -> dict[str, Any]:
    """CAD integrada até uma profundidade máxima (mm).

    A integração usa apenas as camadas **totalmente** contidas no perfil
    pedido: camadas parcialmente atravessadas pela profundidade são
    **excluídas** (e reportadas), para não inventar uma fração de camada.
    """
    selected = [
        layer for layer in layers if float(layer["bottom_cm"]) >= 0 and float(layer["top_cm"]) <= depth_cm
    ]
    excluded = [
        layer["key"] for layer in layers if layer not in selected
    ]
    result = profile_capacity_mm(values_mm_per_cm, selected)
    result["depth_cm"] = depth_cm
    result["excluded_layers"] = excluded
    return result


def layers_up_to_depth(
    depth_cm: float,
    layers: Sequence[Mapping[str, Any]] = AW_LAYERS,
) -> list[Mapping[str, Any]]:
    """Camadas **totalmente** contidas num perfil de ``depth_cm``.

    Uma camada só entra se a sua base estiver dentro do perfil; camadas
    atravessadas pela profundidade ficam de fora, porque fatiar uma camada
    exigiria inventar uma proporção que o dado publicado não suporta.
    """
    return [
        layer
        for layer in layers
        if float(layer["bottom_cm"]) >= 0 and float(layer["top_cm"]) <= depth_cm
    ]


def pixel_capacity_mm(
    stack: "Any",
    layers: Sequence[Mapping[str, Any]],
) -> "Any":
    """CAD por pixel (mm) para as camadas informadas.

    ``stack`` tem forma ``(n_camadas, linhas, colunas)``, na mesma ordem de
    ``layers``. Devolve a integração ``Σ AW(mm/cm) · espessura(cm)`` por
    pixel, com ``NaN`` onde **qualquer** camada do perfil for inválida — a
    ausência não é preenchida.

    A função existe para que a seleção de camadas por profundidade fique num
    só lugar: usar todas as camadas disponíveis para qualquer profundidade
    transforma a CAD de 0–100 cm na de 0–200 cm.
    """
    import numpy as np

    if len(layers) == 0:
        raise ValueError("nenhuma camada para integrar")
    thickness = np.array(
        [layer_thickness_cm(layer) for layer in layers], dtype="float64"
    ).reshape(-1, 1, 1)
    values = np.asarray(stack, dtype="float64")
    if values.shape[0] != thickness.shape[0]:
        raise ValueError(
            f"stack com {values.shape[0]} camadas e {thickness.shape[0]} espessuras"
        )
    capacity = np.nansum(values * thickness, axis=0)
    capacity[np.isnan(values).any(axis=0)] = np.nan
    return capacity


def compare_with_scenarios(
    capacity_mm: float | None,
    scenarios: Sequence[float] = V26_SCENARIO_CAPACITIES_MM,
) -> dict[str, Any]:
    """Compara uma CAD observada com os cenários da V2.6.

    Não classifica risco hídrico: apenas quantifica a razão entre o valor
    observado e cada cenário, e o cenário mais próximo.
    """
    if capacity_mm is None:
        return {
            "capacity_mm": None,
            "status": "sem_dado",
            "ratios": None,
            "closest_scenario_mm": None,
        }
    ratios = {str(int(s)): capacity_mm / s for s in scenarios if s}
    closest = min(scenarios, key=lambda s: abs(capacity_mm - s)) if scenarios else None
    return {
        "capacity_mm": capacity_mm,
        "status": "ok",
        "ratios": ratios,
        "closest_scenario_mm": closest,
        "exceeds_all_scenarios": bool(
            scenarios and capacity_mm > max(scenarios)
        ),
    }
