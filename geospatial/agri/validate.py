"""Verificações de qualidade da base observada de produtividade.

As verificações **sinalizam**; não eliminam registros silenciosamente. Cada
achado guarda o motivo, a severidade e a referência da linha normalizada.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Sequence

SEVERITY_INFO = "info"
SEVERITY_WARNING = "warning"
SEVERITY_ERROR = "error"

CHECKS = [
    "duplicidade",
    "codigo_municipal_invalido",
    "ano_ausente",
    "valor_nulo",
    "unidade_inconsistente",
    "area_zero_com_producao",
    "produtividade_negativa",
    "rendimento_divergente",
    "safra_vs_ano_civil",
    "classificacao_sem_correspondencia",
    "codigo_municipio_desconhecido",
    "revisao_entre_boletins",
    "dupla_contagem_agregado_componente",
]


def _key(record: dict[str, Any]) -> tuple:
    return (
        record.get("institution"),
        record.get("dataset_id"),
        str(record.get("geography_code")),
        str(record.get("crop_code") or record.get("crop_name_original")),
        str(record.get("reference_year") or record.get("safra")),
        record.get("variable_normalized"),
    )


def check_duplicates(records: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter(_key(record) for record in records)
    findings = []
    for key, count in counts.items():
        if count > 1:
            findings.append(
                {
                    "check": "duplicidade",
                    "severity": SEVERITY_WARNING,
                    "key": list(key),
                    "message": f"{count} registros idênticos para a mesma chave",
                }
            )
    return findings


def check_geography(records: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    findings = []
    known = {"5107925"}
    uf_codes = {
        "11", "12", "13", "14", "15", "16", "17", "21", "22", "23", "24", "25",
        "26", "27", "28", "29", "31", "32", "33", "35", "41", "42", "43", "50",
        "51", "52", "53", "54",
    }
    for record in records:
        code = str(record.get("geography_code") or "")
        kind = record.get("geography_type")
        if kind == "municipio" and code not in known:
            findings.append(
                {
                    "check": "codigo_municipal_invalido",
                    "severity": SEVERITY_ERROR,
                    "key": list(_key(record)),
                    "message": f"código municipal fora do escopo: {code}",
                }
            )
        if kind == "uf" and code not in uf_codes:
            findings.append(
                {
                    "check": "codigo_municipio_desconhecido",
                    "severity": SEVERITY_WARNING,
                    "key": list(_key(record)),
                    "message": f"código de UF inesperado: {code}",
                }
            )
    return findings


def check_missing_values(records: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    findings = []
    for record in records:
        if record.get("value_normalized") is None:
            findings.append(
                {
                    "check": "valor_nulo",
                    "severity": SEVERITY_INFO,
                    "key": list(_key(record)),
                    "message": (
                        f"valor ausente (status={record.get('observation_status')}): "
                        f"{record.get('crop_name_original')} / "
                        f"{record.get('variable_normalized')}"
                    ),
                }
            )
        if record.get("reference_year") in (None, "") and not record.get("safra"):
            findings.append(
                {
                    "check": "ano_ausente",
                    "severity": SEVERITY_ERROR,
                    "key": list(_key(record)),
                    "message": "registro sem ano de referência e sem safra",
                }
            )
    return findings


def check_units(records: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    expected = {
        "area_plantada_ha": "ha",
        "area_colhida_ha": "ha",
        "quantidade_produzida_t": "t",
        "rendimento_medio_kg_ha": "kg/ha",
    }
    findings = []
    for record in records:
        variable = record.get("variable_normalized")
        unit = record.get("unit_normalized")
        if variable in expected and unit != expected[variable]:
            findings.append(
                {
                    "check": "unidade_inconsistente",
                    "severity": SEVERITY_ERROR,
                    "key": list(_key(record)),
                    "message": f"unidade '{unit}' inesperada para {variable}",
                }
            )
    return findings


def check_plausibility(records: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    findings = []
    for record in records:
        value = record.get("value_normalized")
        variable = record.get("variable_normalized")
        if value is None:
            continue
        if variable in {"area_plantada_ha", "area_colhida_ha"} and value < 0:
            findings.append(
                {
                    "check": "produtividade_negativa",
                    "severity": SEVERITY_ERROR,
                    "key": list(_key(record)),
                    "message": f"área negativa: {value}",
                }
            )
        if variable == "quantidade_produzida_t" and value < 0:
            findings.append(
                {
                    "check": "produtividade_negativa",
                    "severity": SEVERITY_ERROR,
                    "key": list(_key(record)),
                    "message": f"quantidade negativa: {value}",
                }
            )
    return findings


def check_area_production_consistency(records: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detecta área zero com produção positiva (inconsistência lógica)."""
    by_group: dict[tuple, dict[str, Any]] = {}
    for record in records:
        if record.get("institution") != "IBGE":
            continue
        key = (
            str(record.get("geography_code")),
            str(record.get("crop_code")),
            str(record.get("reference_year")),
        )
        by_group.setdefault(key, {})[record.get("variable_normalized")] = record

    findings = []
    for key, group in by_group.items():
        area = group.get("area_colhida_ha") or group.get("area_plantada_ha")
        quantity = group.get("quantidade_produzida_t")
        if not area or not quantity:
            continue
        area_value = area.get("value_normalized")
        quantity_value = quantity.get("value_normalized")
        if area_value == 0 and quantity_value and quantity_value > 0:
            findings.append(
                {
                    "check": "area_zero_com_producao",
                    "severity": SEVERITY_ERROR,
                    "key": list(key),
                    "message": (
                        f"área colhida = 0 com quantidade produzida = {quantity_value} t"
                    ),
                }
            )
    return findings


def check_yield_consistency(
    records: Sequence[dict[str, Any]],
    tolerance: float = 0.05,
) -> list[dict[str, Any]]:
    """Compara o rendimento publicado com o calculado (quantidade/área).

    A tolerância é de 5% (arredondamento e pequenas divergências de
    fechamento da PAM).
    """
    from .normalize import computed_yield_t_ha, published_yield_kg_ha_to_t_ha

    by_group: dict[tuple, dict[str, Any]] = {}
    for record in records:
        if record.get("institution") != "IBGE":
            continue
        key = (
            str(record.get("geography_code")),
            str(record.get("crop_code")),
            str(record.get("reference_year")),
        )
        by_group.setdefault(key, {})[record.get("variable_normalized")] = record

    findings = []
    for key, group in by_group.items():
        published = group.get("rendimento_medio_kg_ha")
        quantity = group.get("quantidade_produzida_t")
        area = group.get("area_colhida_ha") or group.get("area_plantada_ha")
        if not (published and quantity and area):
            continue
        published_t_ha = published_yield_kg_ha_to_t_ha(published.get("value_normalized"))
        computed = computed_yield_t_ha(
            quantity.get("value_normalized"), area.get("value_normalized")
        )
        if published_t_ha is None or computed is None or published_t_ha <= 0:
            continue
        relative = abs(computed - published_t_ha) / published_t_ha
        if relative > tolerance:
            findings.append(
                {
                    "check": "rendimento_divergente",
                    "severity": SEVERITY_WARNING,
                    "key": list(key),
                    "message": (
                        f"rendimento publicado {published_t_ha * 1000:.1f} kg/ha vs "
                        f"calculado {computed * 1000:.1f} kg/ha "
                        f"({relative * 100:.2f}% de diferença)"
                    ),
                    "relative_difference": relative,
                }
            )
    return findings


def check_classification(records: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    findings = []
    for record in records:
        if record.get("match_class") in (None, "none"):
            findings.append(
                {
                    "check": "classificacao_sem_correspondencia",
                    "severity": SEVERITY_INFO,
                    "key": list(_key(record)),
                    "message": (
                        "produto sem vínculo declarado com as commodities do SADEN: "
                        f"{record.get('crop_name_original')}"
                    ),
                }
            )
    return findings


def check_safra_vs_year(records: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sinaliza o desalinhamento entre ano civil (IBGE) e safra (CONAB)."""
    findings = []
    for record in records:
        if record.get("institution") != "CONAB":
            continue
        safra = str(record.get("safra") or "")
        if "/" not in safra:
            continue
        start = int(safra.split("/")[0])
        end = int(safra.split("/")[1])
        findings.append(
            {
                "check": "safra_vs_ano_civil",
                "severity": SEVERITY_INFO,
                "key": list(_key(record)),
                "message": (
                    f"safra {safra} cobre os anos civis {2000 + start} e "
                    f"{2000 + end}: não equivale a um único ano civil"
                ),
            }
        )
    return findings


def check_revisions_between_bulletins(
    records: Sequence[dict[str, Any]],
    tolerance: float = 1e-9,
) -> list[dict[str, Any]]:
    """Detecta a mesma safra/valor reestimada em boletins diferentes.

    A CONAB revisa estimativas a cada levantamento; a mesma safra aparece com
    valores diferentes em arquivos distintos. Isso **não** é duplicata: são
    vintages diferentes e precisam ser identificados.
    """
    groups: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if record.get("institution") != "CONAB":
            continue
        key = (
            str(record.get("geography_code")),
            str(record.get("crop_name_original")),
            str(record.get("safra")),
            str(record.get("variable_normalized")),
        )
        groups[key].append(record)

    findings = []
    for key, group in groups.items():
        datasets = {str(r.get("dataset_id")) for r in group}
        values = sorted(
            {
                float(r["value_normalized"])
                for r in group
                if r.get("value_normalized") is not None
                and str(r.get("value_normalized")).strip() != ""
            }
        )
        if len(datasets) > 1 and len(values) > 1:
            findings.append(
                {
                    "check": "revisao_entre_boletins",
                    "severity": SEVERITY_WARNING,
                    "key": list(key),
                    "message": (
                        f"mesma safra reestimada em {len(datasets)} boletins com "
                        f"valores distintos: {sorted(values)}"
                    ),
                }
            )
    return findings


def check_aggregate_double_counting(records: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sinaliza quando total e componentes do mesmo produto coexistem."""
    component_scopes = {"componente_safra", "grupo_safra", "componente"}
    groups: dict[tuple, set[str]] = defaultdict(set)
    for record in records:
        scope = record.get("crop_scope")
        if scope in (None, "", "produto"):
            continue
        key = (
            str(record.get("institution")),
            str(record.get("geography_code")),
            str(record.get("crop_name_normalized")),
            str(record.get("reference_year") or record.get("safra")),
        )
        groups[key].add(str(scope))
    findings = []
    for key, scopes in groups.items():
        if "total" in scopes and scopes & component_scopes:
            findings.append(
                {
                    "check": "dupla_contagem_agregado_componente",
                    "severity": SEVERITY_WARNING,
                    "key": list(key),
                    "message": (
                        "registros 'Total' e componentes ('1ª/2ª Safra', tipos) do "
                        "mesmo produto coexistem: somar ambos duplica a produção"
                    ),
                }
            )
    return findings


def run_all(records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Executa todas as verificações e devolve achados + resumo."""
    findings: list[dict[str, Any]] = []
    findings += check_duplicates(records)
    findings += check_geography(records)
    findings += check_missing_values(records)
    findings += check_units(records)
    findings += check_plausibility(records)
    findings += check_area_production_consistency(records)
    findings += check_yield_consistency(records)
    findings += check_classification(records)
    findings += check_safra_vs_year(records)
    findings += check_revisions_between_bulletins(records)
    findings += check_aggregate_double_counting(records)

    by_check = Counter(finding["check"] for finding in findings)
    by_severity = Counter(finding["severity"] for finding in findings)
    return {
        "records_checked": len(records),
        "findings": findings,
        "counts_by_check": dict(by_check),
        "counts_by_severity": dict(by_severity),
        "checks_executed": CHECKS,
        "policy": (
            "Nenhum registro foi removido: os achados apenas sinalizam. "
            "Registros sinalizados permanecem rastreáveis na base."
        ),
    }
