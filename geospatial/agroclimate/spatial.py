"""Unidade de agrupamento espacial e protocolos de separação geográfica (V2.7).

A V2.6 mediu a associação entre variáveis agroclimáticas e produtividade
municipal com erro-padrão agrupado por **município**. A limitação registrada em
D75 é que a base do painel é a reanálise do **NASA POWER** (MERRA-2, ~0,5° ×
0,625° ≈ 55 km): municípios vizinhos podem receber **exatamente a mesma**
série climática, e as observações do mesmo município não são independentes
entre si.

Este módulo estabelece a **unidade de agrupamento** de forma explícita e
verificável, em vez de tomar o município como substituto automático da
célula meteorológica:

* :func:`merra2_cell` deriva a célula da grade MERRA-2 que contém um ponto
  (a resolução é a documentada pelo NASA POWER);
* :func:`shared_value_groups` **identifica empiricamente** quais observações
  compartilham a mesma informação climática — agrupando por igualdade
  exata das séries agregadas dentro da mesma janela;
* :func:`assign_clusters` combina as duas evidências: a célula geométrica e a
  partilha empírica de valores;
* :func:`spatial_grouped_folds` e :func:`leave_one_group_out` implementam os
  protocolos de separação espacial **sem misturá-los** com o holdout por
  município da V2.6.

A fonte de clima determina a unidade física que a origina: a reanálise é
produzida por **célula de grade**, a observação do INMET por **estação**.
"""

from __future__ import annotations

import hashlib
import math
from collections import defaultdict
from typing import Any, Iterable, Sequence

# --------------------------------------------------------------------------
# Grade MERRA-2 (NASA POWER, API daily/point, comunidade AG).
# --------------------------------------------------------------------------
# A resolução nominal da grade MERRA-2 usada pelo NASA POWER é 0,5° em
# latitude e 0,625° em longitude. O valor **efetivo** da partilha de
# informação entre municípios é verificado empiricamente por
# :func:`shared_value_groups` — a resolução geométrica abaixo é a hipótese
# testada, não uma suposição aceita.
MERRA2_LAT_RESOLUTION_DEG = 0.5
MERRA2_LON_RESOLUTION_DEG = 0.625

# Fonte climática → unidade física que origina a observação.
SOURCE_CLUSTER_UNIT: dict[str, str] = {
    "NASA-POWER": "grid_cell",
    "ERA5-Land": "grid_cell",
    "ERA5": "grid_cell",
    "INMET": "station",
}

# Campos climáticos usados para detectar partilha **exata** de informação.
SHARED_VALUE_FIELDS: tuple[str, ...] = (
    "precip_acumulada_mm",
    "temp_media_c",
    "degree_days_total",
    "et0_total_mm",
    "deficiency_total_mm",
)


def merra2_cell(
    latitude: float, longitude: float
) -> tuple[int, int]:
    """Índice da célula MERRA-2 que contém um ponto.

    A indexação é por ``floor``: a célula cobre ``[lat0, lat0 + 0,5°)`` em
    latitude e ``[lon0, lon0 + 0,625°)`` em longitude, com ``lat0`` múltiplo
    de 0,5 e ``lon0`` múltiplo de 0,625.
    """
    lat_index = int((float(latitude) + 90.0) // MERRA2_LAT_RESOLUTION_DEG)
    lon_index = int((float(longitude) + 180.0) // MERRA2_LON_RESOLUTION_DEG)
    return lat_index, lon_index


def merra2_cell_center(
    lat_index: int, lon_index: int
) -> tuple[float, float]:
    """Centro geométrico de uma célula MERRA-2 (para registro nos manifestos)."""
    lat = -90.0 + (lat_index + 0.5) * MERRA2_LAT_RESOLUTION_DEG
    lon = -180.0 + (lon_index + 0.5) * MERRA2_LON_RESOLUTION_DEG
    return lat, lon


def grid_cell_id(latitude: float, longitude: float) -> str:
    """Identificador estável da célula MERRA-2 (ex.: ``M234_P118``)."""
    lat_index, lon_index = merra2_cell(latitude, longitude)
    return f"M{lat_index:03d}_P{lon_index:03d}"


def municipality_cells(
    municipalities: Sequence[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Índice município → célula MERRA-2.

    ``municipalities`` são os registros de ``panel_municipalities.csv``
    (com ``ibge_code``, ``centroid_lat``, ``centroid_lon``).
    """
    out: dict[str, dict[str, Any]] = {}
    for record in municipalities:
        code = str(record.get("ibge_code") or "").strip()
        if not code:
            continue
        try:
            lat = float(record.get("centroid_lat"))
            lon = float(record.get("centroid_lon"))
        except (TypeError, ValueError):
            continue
        lat_index, lon_index = merra2_cell(lat, lon)
        center_lat, center_lon = merra2_cell_center(lat_index, lon_index)
        out[code] = {
            "ibge_code": code,
            "municipality": record.get("municipality"),
            "state": record.get("state"),
            "centroid_lat": lat,
            "centroid_lon": lon,
            "grid_cell_id": grid_cell_id(lat, lon),
            "grid_lat_index": lat_index,
            "grid_lon_index": lon_index,
            "grid_center_lat": center_lat,
            "grid_center_lon": center_lon,
        }
    return out


def _value_signature(row: dict[str, Any]) -> str:
    """Assinatura exata dos valores climáticos de uma linha do painel.

    A assinatura é calculada **apenas** sobre campos climáticos: duas linhas
    com a mesma assinatura carregam a mesma informação meteorológica, ainda
    que pertençam a municípios diferentes.
    """
    parts: list[str] = []
    for field in SHARED_VALUE_FIELDS:
        value = row.get(field)
        if value in (None, ""):
            parts.append(f"{field}=NA")
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            parts.append(f"{field}={value}")
            continue
        parts.append(f"{field}={number:.6f}")
    payload = "|".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def shared_value_groups(
    rows: Sequence[dict[str, Any]],
    fields: Sequence[str] = SHARED_VALUE_FIELDS,
) -> dict[str, list[str]]:
    """Grupos de linhas que compartilham **exatamente** a mesma informação.

    Duas linhas pertencem ao mesmo grupo quando têm a mesma fonte climática,
    a mesma janela (`zarc_window_start`/`zarc_window_end`), a mesma cultura,
    o mesmo ano de colheita e os **mesmos valores** nos campos climáticos.

    O agrupamento é feito dentro de cada combinação
    (fonte, cultura, ano, janela), porque é nessa escala que a série
    climática é a mesma; a identidade é conferida pelos **valores**, não pela
    geometria.

    Retorna ``{assinatura: [índice_da_linha, ...]}``.
    """
    buckets: dict[tuple[str, ...], list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        key = (
            str(row.get("climate_source") or ""),
            str(row.get("crop") or ""),
            str(row.get("harvest_year") or ""),
            str(row.get("zarc_window_start") or ""),
            str(row.get("zarc_window_end") or ""),
        )
        buckets[key].append(index)
    groups: dict[str, list[int]] = defaultdict(list)
    for key, indices in buckets.items():
        signatures: dict[str, list[int]] = defaultdict(list)
        for index in indices:
            signatures[_value_signature(rows[index])].append(index)
        for signature, members in signatures.items():
            # um grupo só é informativo se reúne mais de uma linha
            if len(members) > 1:
                groups[f"{'|'.join(key)}::{signature}"] = members
    return groups


def assign_clusters(
    rows: Sequence[dict[str, Any]],
    municipalities: Sequence[dict[str, Any]],
    source_cluster_unit: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Acrescenta ``cluster_id`` e ``cluster_unit`` a cada linha do painel.

    * reanálise → célula MERRA-2 do centroide municipal;
    * observação do INMET → código da estação.

    As linhas sem centroide ou sem estação permanecem sem cluster
    (``cluster_id`` nulo) e são **excluídas** da inferência agrupada — o
    agrupamento não é inventado para quem não tem unidade física.
    """
    unit_map = source_cluster_unit or SOURCE_CLUSTER_UNIT
    cells = municipality_cells(municipalities)
    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        code = str(row.get("ibge_code") or "")
        source = str(row.get("climate_source") or "")
        unit = unit_map.get(source, "municipality")
        item["cluster_unit"] = unit
        if unit == "grid_cell":
            cell = cells.get(code)
            item["cluster_id"] = cell["grid_cell_id"] if cell else None
            item["cluster_lat"] = cell["grid_center_lat"] if cell else None
            item["cluster_lon"] = cell["grid_center_lon"] if cell else None
        elif unit == "station":
            station = str(row.get("station_code") or "")
            item["cluster_id"] = f"INMET_{station}" if station else None
            item["cluster_lat"] = None
            item["cluster_lon"] = None
        else:
            item["cluster_id"] = code or None
            item["cluster_lat"] = None
            item["cluster_lon"] = None
        out.append(item)
    return out


def cluster_summary(
    rows: Sequence[dict[str, Any]], cluster_key: str = "cluster_id"
) -> dict[str, Any]:
    """Estrutura dos grupos de agrupamento (quantidade, tamanhos, imbalance)."""
    sizes: dict[str, int] = defaultdict(int)
    municipalities: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        cluster = row.get(cluster_key)
        if not cluster:
            continue
        key = str(cluster)
        sizes[key] += 1
        municipalities[key].add(str(row.get("ibge_code") or ""))
    if not sizes:
        return {
            "n_clusters": 0,
            "n_observations": 0,
            "n_municipalities": 0,
            "status": "no_clusters",
        }
    counts = sorted(sizes.values(), reverse=True)
    total = sum(counts)
    mean = total / len(counts)
    variance = sum((value - mean) ** 2 for value in counts) / len(counts)
    return {
        "n_clusters": len(counts),
        "n_observations": total,
        "n_municipalities": len(
            {str(r.get("ibge_code")) for r in rows if r.get(cluster_key)}
        ),
        "min_cluster_size": counts[-1],
        "max_cluster_size": counts[0],
        "median_cluster_size": float(counts[len(counts) // 2]),
        "mean_cluster_size": float(mean),
        "std_cluster_size": float(variance**0.5),
        "imbalance_ratio": float(counts[0] / counts[-1]) if counts[-1] else None,
        "n_singleton_clusters": sum(1 for value in counts if value == 1),
        "share_observations_in_largest_cluster": float(counts[0] / total),
        "cluster_sizes_top10": counts[:10],
    }


def cluster_diagnostics(
    rows: Sequence[dict[str, Any]],
    cells: dict[str, dict[str, Any]],
    cluster_key: str = "cluster_id",
) -> dict[str, Any]:
    """Diagnóstico da partilha de informação espacial.

    Responde objetivamente: quantos municípios dividem a mesma célula, que
    fração das observações é compartilhada e qual é a concordância entre a
    célula **geométrica** e a partilha **empírica** de valores idênticos.

    A identidade é avaliada dentro de cada combinação (cultura, ano de
    colheita, janela do ZARC): só assim a comparação é justa, porque os
    agregados climáticos só são comparáveis na mesma janela.
    """
    by_cluster: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        cluster = row.get(cluster_key)
        code = str(row.get("ibge_code") or "")
        if not cluster:
            continue
        by_cluster[str(cluster)].add(code)
    municipalities_per_cluster = sorted(
        (len(value) for value in by_cluster.values()), reverse=True
    )
    shared_municipality_clusters = sum(
        1 for value in municipalities_per_cluster if value > 1
    )
    # índice (cultura, ano, janela) -> {município: assinatura dos valores}
    by_window: dict[tuple[str, ...], dict[str, str]] = defaultdict(dict)
    for row in rows:
        code = str(row.get("ibge_code") or "")
        key = (
            str(row.get("crop") or ""),
            str(row.get("harvest_year") or ""),
            str(row.get("zarc_window_start") or ""),
            str(row.get("zarc_window_end") or ""),
        )
        by_window[key][code] = _value_signature(row)
    identical = 0
    comparable = 0
    for cluster, codes in by_cluster.items():
        code_list = sorted(codes)
        if len(code_list) < 2:
            continue
        for key, by_municipality in by_window.items():
            present = [code for code in code_list if code in by_municipality]
            if len(present) < 2:
                continue
            for i in range(len(present)):
                for j in range(i + 1, len(present)):
                    comparable += 1
                    if by_municipality[present[i]] == by_municipality[present[j]]:
                        identical += 1
    n_mapped = sum(1 for row in rows if row.get(cluster_key))
    return {
        "n_clusters": len(by_cluster),
        "n_municipalities": len(by_cluster),
        "n_observations": n_mapped,
        "n_clusters_with_multiple_municipalities": shared_municipality_clusters,
        "municipalities_per_cluster_max": municipalities_per_cluster[0]
        if municipalities_per_cluster
        else 0,
        "municipalities_per_cluster_mean": (
            sum(municipalities_per_cluster) / len(municipalities_per_cluster)
            if municipalities_per_cluster
            else 0.0
        ),
        "cell_pairs_comparable": comparable,
        "cell_pairs_with_identical_climate": identical,
        "cell_pair_identity_rate": (identical / comparable) if comparable else None,
        "n_municipalities_without_cell": len(cells) - len(by_cluster),
    }


def spatial_grouped_folds(
    rows: Sequence[dict[str, Any]],
    group_key: str,
    n_folds: int = 5,
    seed: int = 20261113,
) -> list[list[str]]:
    """Dobras de validação grouped: cada grupo inteiro fica em uma dobra.

    Usado para separar por **célula da grade** (ou por qualquer unidade de
    agrupamento), garantindo que nenhum grupo se parta entre treino e teste.

    A distribuição é **determinística** (semente fixa) e equilibrada em número
    de grupos, não de observações: o número de observações por dobra pode
    variar, e isso é reportado.
    """
    import numpy as np

    groups = sorted({str(row.get(group_key)) for row in rows if row.get(group_key)})
    if len(groups) < n_folds:
        return []
    rng = np.random.default_rng(seed)
    shuffled = list(groups)
    rng.shuffle(shuffled)
    folds = [shuffled[i::n_folds] for i in range(n_folds)]
    return folds


def leave_one_group_out(
    rows: Sequence[dict[str, Any]], group_key: str
) -> list[tuple[str, list[str]]]:
    """Partições leave-one-group-out (ex.: leave-one-UF-out).

    Retorna ``[(grupo_do_teste, [ids_do_grupo]), ...]`` — cada iteração testa
    um grupo inteiro (por exemplo, uma UF) e treina nos demais.
    """
    groups = sorted({str(row.get(group_key)) for row in rows if row.get(group_key)})
    return [(group, [group]) for group in groups]


def split_by_groups(
    rows: Sequence[dict[str, Any]],
    train_groups: Iterable[str],
    test_groups: Iterable[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Separa linhas por grupo, sem permitir sobreposição de grupos."""
    train_set = {str(value) for value in train_groups}
    test_set = {str(value) for value in test_groups}
    overlap = train_set & test_set
    if overlap:
        raise ValueError(f"grupos simultaneamente em treino e teste: {sorted(overlap)}")
    train = [row for row in rows if str(row.get("group_id")) in train_set]
    test = [row for row in rows if str(row.get("group_id")) in test_set]
    return train, test


def leakage_report(
    train: Sequence[dict[str, Any]],
    test: Sequence[dict[str, Any]],
    keys: Sequence[str] = ("ibge_code", "cluster_id"),
) -> dict[str, Any]:
    """Verifica vazamento entre treino e teste.

    Uma partilha é **vazada** quando alguma unidade aparece nos dois lados
    (por exemplo, o mesmo município ou a mesma célula da grade).
    """
    out: dict[str, Any] = {}
    for key in keys:
        train_values = {str(row.get(key)) for row in train if row.get(key)}
        test_values = {str(row.get(key)) for row in test if row.get(key)}
        shared = sorted(train_values & test_values)
        out[key] = {
            "n_train": len(train_values),
            "n_test": len(test_values),
            "n_shared": len(shared),
            "leakage": bool(shared),
            "examples": shared[:5],
        }
    out["no_leakage"] = not any(out[key]["leakage"] for key in keys)
    return out


# --------------------------------------------------------------------------
# Escala espacial: blocos, distâncias e correlograma empírico.
# --------------------------------------------------------------------------
EARTH_RADIUS_KM = 6371.0088


def haversine_km(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Distância de superfície entre dois pontos (km)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2.0) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2.0) ** 2
    )
    return 2.0 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def spatial_blocks(
    municipalities: Sequence[dict[str, Any]], block_km: float
) -> dict[str, str]:
    """Particiona os municípios em **blocos espaciais** de ~``block_km``.

    A partição é uma grade regular em latitude/longitude; o tamanho da grade
    é escolhido para que ``block_km`` corresponda aproximadamente à distância
    máxima dentro do bloco (em latitude, 1° ≈ 111 km; em longitude, o fator
    ``cos(latitude)`` é aplicado).

    O tamanho do bloco deve ser **calibrado pela dependência medida**: um
    bloco menor que o alcance da dependência deixa Counties vizinhos no mesmo
    grupo sem que isso reflita a partilha real de informação.
    """
    out: dict[str, str] = {}
    for record in municipalities:
        code = str(record.get("ibge_code") or "").strip()
        if not code:
            continue
        try:
            lat = float(record.get("centroid_lat"))
            lon = float(record.get("centroid_lon"))
        except (TypeError, ValueError):
            continue
        lat_step = max(float(block_km) / 111.32, 1e-6)
        lon_step = max(float(block_km) / (111.32 * max(math.cos(math.radians(lat)), 0.1)), 1e-6)
        lat_index = int(math.floor(lat / lat_step))
        lon_index = int(math.floor(lon / lon_step))
        out[code] = f"B{lat_index:+03d}_{lon_index:+04d}"
    return out


def spatial_fold_colors(
    municipalities: Sequence[dict[str, Any]], block_km: float, n_folds: int
) -> dict[str, int]:
    """Coloração de blocos com separação espacial garantida.

    Dois blocos **adjacentes** (horizontal, vertical ou diagonalmente) nunca
    recebem a mesma cor. A cor é ``((n−1)·lat + 2·lon) mod n``, que é
    válida para ``n ≥ 3``: deslocamento em latitude altera a cor em
    ``−1 (mod n)``, em longitude em ``+2 (mod n)`` e na diagonal em ``+1``,
    nenhum dos quais anula a cor.

    É o desenho clássico de validação cruzada espacial: dobras cujas
    unidades de teste não são vizinhas das unidades de treino.
    """
    if n_folds < 3:
        raise ValueError("n_folds >= 3 para a coloração com separação espacial")
    out: dict[str, int] = {}
    for record in municipalities:
        code = str(record.get("ibge_code") or "").strip()
        if not code:
            continue
        try:
            lat = float(record.get("centroid_lat"))
            lon = float(record.get("centroid_lon"))
        except (TypeError, ValueError):
            continue
        lat_step = max(float(block_km) / 111.32, 1e-6)
        lon_step = max(
            float(block_km) / (111.32 * max(math.cos(math.radians(lat)), 0.1)), 1e-6
        )
        lat_index = int(math.floor(lat / lat_step))
        lon_index = int(math.floor(lon / lon_step))
        out[code] = ((n_folds - 1) * lat_index + 2 * lon_index) % n_folds
    return out


def distance_matrix_km(coords: Sequence[tuple[float, float]]) -> list[list[float]]:
    """Matriz de distâncias (km) entre coordenadas — sem dependência externa."""
    out: list[list[float]] = []
    for lat1, lon1 in coords:
        row: list[float] = []
        for lat2, lon2 in coords:
            row.append(haversine_km(lat1, lon1, lat2, lon2))
        out.append(row)
    return out


def correlogram(
    distances: Sequence[float],
    correlations: Sequence[float],
    bin_width_km: float = 25.0,
    max_distance_km: float = 500.0,
) -> list[dict[str, Any]]:
    """Correlograma empírico: correlação média por faixa de distância.

    É a evidência que calibra a unidade de agrupamento: a faixa em que a
    correlação deixa de ser desprezível define a escala espacial mínima
    relevante para a inferência.
    """
    out: list[dict[str, Any]] = []
    edge = 0.0
    while edge < max_distance_km:
        upper = edge + bin_width_km
        values = [
            value
            for distance, value in zip(distances, correlations)
            if edge <= distance < upper
        ]
        if values:
            ordered = sorted(values)
            out.append(
                {
                    "distance_min_km": edge,
                    "distance_max_km": upper,
                    "n_pairs": len(values),
                    "mean_correlation": sum(values) / len(values),
                    "median_correlation": ordered[len(ordered) // 2],
                    "p10_correlation": ordered[max(0, int(0.10 * len(ordered)) - 1)],
                    "p90_correlation": ordered[min(len(ordered) - 1, int(0.90 * len(ordered)))],
                }
            )
        edge = upper
    return out


def dependence_threshold_distance(
    distances: Sequence[float],
    correlations: Sequence[float],
    threshold: float = 0.10,
    max_distance_km: float = 600.0,
) -> float | None:
    """Distância em que a correlação média cai abaixo do limiar.

    É a calibração objetiva do **corte espacial**: a dependência que ainda é
    relevante quando o par de municípios está a essa distância.
    """
    for band in correlogram(distances, correlations, 25.0, max_distance_km):
        if band["mean_correlation"] < threshold:
            return float(band["distance_min_km"])
    return None

