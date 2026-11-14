"""Gera o registro de auditoria (markdown) a partir do manifesto da V3.3.

Evita transcrição manual: a tabela do registro é exatamente a do manifesto.

Uso: python tools/v33_write_audit_register.py
"""

from __future__ import annotations

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
MANIFESTS = os.path.join(ROOT, "geospatial", "data", "manifests")
OUT = os.path.join(ROOT, "docs", "execution", "v3.3", "INFERENCE_AUDIT_REGISTER.md")

FAMILIES = (
    ("F1_v27", "V2.7 — efeitos fixos por variável meteorológica", "v27_robust_inference.json"),
    ("F2_v30", "V3.0 — déficit sob cinco definições", "v30_association_cad.json"),
)


def _fmt(value, digits=4):
    if value is None:
        return "—"
    if isinstance(value, float):
        if value != 0 and abs(value) < 1e-3:
            return f"{value:.2e}"
        return f"{value:.{digits}f}"
    return str(value)


def main() -> int:
    payload = json.load(open(os.path.join(MANIFESTS, "v33_inference_audit.json"), encoding="utf-8"))
    lines: list[str] = []
    lines.append("# V3.3 — REGISTRO DE AUDITORIA DE INFERÊNCIA")
    lines.append("")
    lines.append(
        "Gerado por `tools/v33_write_audit_register.py` a partir de "
        "`geospatial/data/manifests/v33_inference_audit.json`. "
        "Não editar à mão: os números vêm do manifesto."
    )
    lines.append("")
    lines.append("## Cenários")
    lines.append("")
    for key, value in payload["scenarios"].items():
        lines.append(f"* **{key}** — {value}")
    lines.append("")
    lines.append("## Resumo por família")
    lines.append("")
    lines.append("| família | hipóteses | reprodução (dif. máx.) | histórico | auditado (UF×ano + município) |")
    lines.append("|---|---:|---|---|---|")
    for family, label, _source in FAMILIES:
        entry = payload["families"][family]
        historical = entry.get("historical", {})
        audited = entry.get("audited", {})
        hist_text = (
            f"{historical.get('n_significant_raw', '—')} brutos / "
            f"{historical.get('n_significant_holm', '—')} Holm"
            if "n_significant_raw" in historical
            else f"{historical.get('n_significant_holm', '—')} Holm de {historical.get('n_tests', '—')}"
        )
        lines.append(
            "| %s (%s) | %d | %s | %s | %d brutos / %d Holm |"
            % (
                family,
                label,
                entry["hypotheses"],
                _fmt(entry.get("reproduction_max_abs_diff"), 6),
                hist_text,
                audited.get("n_significant_raw_two_way", 0),
                audited.get("n_significant_holm_two_way", 0),
            )
        )
    f3 = payload["families"]["F3_v29_interaction"]
    lines.append(
        "| F3_v29_interaction (V2.9 — interação por grupo de ciclo) | %d | %s | 2 brutos / 1 Holm | %d brutos / %d Holm |"
        % (
            f3["hypotheses"],
            _fmt(f3.get("reproduction_max_abs_diff"), 6),
            f3["audited"]["n_significant_raw_two_way"],
            f3["audited"]["n_significant_holm_two_way"],
        )
    )
    lines.append("")

    for family, label, source in FAMILIES:
        entry = payload["families"][family]
        lines.append(f"## {label}")
        lines.append("")
        lines.append(f"Fonte histórica: `{source}`. Reprodução do coeficiente: diferença máxima "
                     f"{_fmt(entry.get('reproduction_max_abs_diff'), 8)} em {entry.get('reproduction_n')} hipóteses.")
        lines.append("")
        lines.append(
            "| cultura | variável | coef. | SE bloco | SE UF | SE UF×ano | SE duplo | p bloco | p duplo | Holm bloco | Holm duplo | classificação |"
        )
        lines.append("|---|---|---:|---:|---:|---:|---:|---|---|---|---|---|")
        for key in sorted(entry["results"]):
            row = entry["results"][key]
            if row.get("status") != "ok":
                continue
            crop, variable = key.split("|")
            schemes = row["schemes"]
            lines.append(
                "| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | **%s** |"
                % (
                    crop,
                    variable,
                    _fmt(row["coefficient"], 3),
                    _fmt(schemes["bloco_espacial_250km"]["std_error"], 3),
                    _fmt(schemes["uf"]["std_error"], 3),
                    _fmt(schemes["uf_ano"]["std_error"], 3),
                    _fmt(schemes["two_way"]["std_error"], 3),
                    _fmt(schemes["bloco_espacial_250km"]["p_value"]),
                    _fmt(schemes["two_way"]["p_value"]),
                    _fmt(row.get("p_holm_block")),
                    _fmt(row.get("p_holm_two_way")),
                    row.get("classification"),
                )
            )
        lines.append("")

    lines.append("## V2.9 — interações por grupo de ciclo")
    lines.append("")
    lines.append("| cultura | variável | diferença de inclinação | SE bloco | SE duplo | p bloco | p duplo | p histórico |")
    lines.append("|---|---|---:|---:|---:|---|---|---|")
    for key in sorted(f3["results"]):
        row = f3["results"][key]
        if row.get("status") != "ok":
            continue
        crop, variable = key.split("|")
        lines.append(
            "| %s | %s | %s | %s | %s | %s | %s | %s |"
            % (
                crop,
                variable,
                _fmt(row["slope_difference"], 3),
                _fmt(row.get("se_bloco_espacial_250km"), 3),
                _fmt(row.get("se_two_way"), 3),
                _fmt(row.get("p_bloco_espacial_250km")),
                _fmt(row.get("p_two_way")),
                _fmt(row.get("historical_p_value")),
            )
        )
    lines.append("")
    lines.append("## Classificações usadas")
    lines.append("")
    lines.append("| rótulo | significado |")
    lines.append("|---|---|")
    lines.append("| `mantida` | significativa bruta **e** após Holm com agrupamento duplo |")
    lines.append("| `mantida_apenas_bruta` | significativa bruta sob duplo, mas não após Holm |")
    lines.append("| `enfraquecida` | significativa por bloco; p duplo entre 0,05 e 0,10 |")
    lines.append("| `nao_sustentada` | significativa por bloco; p duplo ≥ 0,10 |")
    lines.append("| `reforcada` | não significativa por bloco; significativa após Holm sob duplo |")
    lines.append("| `sem_evidencia_em_nenhum` | não significativa em nenhum esquema |")
    lines.append("| `nao_auditavel` | dados insuficientes para reestimar |")
    lines.append("")
    lines.append("## Limitações do registro")
    lines.append("")
    lines.append("* A auditoria isola o **agrupamento**; modelo, amostra e variável são os históricos.")
    lines.append("* Para F1 e F3 as variáveis são as da janela **histórica** (`_legacy`), porque eram")
    lines.append("  as usadas nas versões originais. Corrigir a janela é outro cenário (C3), tratado")
    lines.append("  em V3.1/V3.3 e não aqui.")
    lines.append("* A família de multiplicidade é a **original** de cada versão (21, 15 e 9), sem")
    lines.append("  rearranjo retrospectivo.")
    lines.append("* `p` do duplo usa CR1 com `t(G−1)`, `G = min(clusters UF×ano, municípios)`; com 31–48")
    lines.append("  clusters UF×ano a aproximação é razoável, mas não exata.")
    with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")
    print(f"escrito: {OUT} ({len(lines)} linhas)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
