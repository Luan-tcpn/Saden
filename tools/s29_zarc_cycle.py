"""V2.9 â€” dicionÃ¡rio oficial do ZARC e teste formal de interaÃ§Ã£o por ciclo (D94).

A V2.8 manteve os cÃ³digos ``Cod_Ciclo`` sem rÃ³tulo porque o dicionÃ¡rio de
dados nÃ£o estava nos artefatos. Ele foi localizado na fonte oficial (MAPA,
Portal de Dados Abertos) e os cÃ³digos estÃ£o registrados abaixo, com a
citaÃ§Ã£o. **Grupo de ciclo nÃ£o Ã© cultivar** e nÃ£o Ã© traduzido para
"precoce/mÃ©dio/tardio": o dicionÃ¡rio diz apenas "Grupo I..VI".

O teste formal responde Ã  pergunta da V2.8 de outra maneira: em vez de
comparar dois coeficientes estimados separadamente (e olhar os t), estima-se
um modelo **com interaÃ§Ã£o** entre a variÃ¡vel climÃ¡tica e o grupo de ciclo,
com efeitos fixos de municÃ­pio e ano e erro agrupado por bloco. O
coeficiente da interaÃ§Ã£o Ã©, diretamente, a diferenÃ§a de inclinaÃ§Ã£o entre os
grupos, com o seu prÃ³prio erro-padrÃ£o.

Uso:
    python tools/s29_zarc_cycle.py
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "geospatial"))

import run_robustness as rr  # noqa: E402
from agroclimate import cycle  # noqa: E402

MANIFESTS = os.path.join(ROOT, "geospatial", "data", "manifests")
OUT_DICT = os.path.join(MANIFESTS, "v29_zarc_dictionary.json")
OUT_INTERACTION = os.path.join(MANIFESTS, "v29_cycle_interaction.json")

COD_CICLO = cycle.COD_CICLO
COD_SOLO = cycle.COD_SOLO
SOURCE = cycle.SOURCE

VARIABLES = ("deficiency_total_mm", "temp_media_c", "precip_acumulada_mm")
MIN_ROWS = 250


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def attach_cycle(rows):
    raw = rr.load_panel()
    index = {}
    for row in raw:
        if str(row.get("status")) != "paired_usable":
            continue
        if str(row.get("climate_source")) != "NASA-POWER":
            continue
        year = row.get("harvest_year") or row.get("pam_reference_year")
        if year in (None, ""):
            continue
        key = (
            str(row.get("ibge_code")),
            str(row.get("crop")),
            str(int(float(year))),
        )
        index.setdefault(
            key,
            {
                "zarc_cycle": str(row.get("zarc_cycle") or ""),
                "zarc_soil": str(row.get("zarc_soil") or ""),
            },
        )
    out = []
    for row in rows:
        key = (str(row["ibge_code"]), str(row["crop"]), str(int(row["year"])))
        merged = dict(row)
        merged.update(index.get(key, {"zarc_cycle": "", "zarc_soil": ""}))
        out.append(merged)
    return out




def main() -> int:
    rows = attach_cycle(rr.prepare(rr.load_panel()))
    by_crop = defaultdict(list)
    for row in rows:
        by_crop[row["crop"]].append(row)

    dictionary = {
        "generated_at": _now(),
        "title": "DicionÃ¡rio de Dados - TÃ¡bua de Risco (ZARC)",
        "institution": "MinistÃ©rio da Agricultura e PecuÃ¡ria (MAPA) â€” CGRA/DEGER/SPA",
        "dataset": "Zoneamento AgrÃ­cola de Risco ClimÃ¡tico (Zarc) â€” TÃ¡bua de Risco",
        "source_page": cycle.SOURCE["url"],
        "document_url": cycle.SOURCE["url"],
        "document_version": cycle.SOURCE["document"],
        "accessed_at": cycle.SOURCE["accessed_at"],
        "license": "Creative Commons Attribution (CC-BY)",
        "cod_ciclo": COD_CICLO,
        "cod_solo": COD_SOLO,
        "note": (
            "Cod_Ciclo identifica GRUPO de ciclo, nao cultivar: o dicionario "
            "lista Grupo I..VI, Perene e Semiperene. Nao ha rotulo "
            "'precoce/medio/tardio' no documento; a traducao para duracao "
            "relativa nao e feita aqui."
        ),
    }
    os.makedirs(MANIFESTS, exist_ok=True)
    with open(OUT_DICT, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(dictionary, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    payload = {
        "generated_at": _now(),
        "method": (
            "Teste formal de interacao: y_w = b1*x_w + b2*(x*I_grupo)_w, com "
            "transformacao within por municipio e ano e erro agrupado por "
            "bloco (CR1). b2 Ã© a diferenca de inclinacao entre grupos; "
            "p-valor com t de G-1 graus de liberdade."
        ),
        "cod_ciclo": COD_CICLO,
        "crops": {},
    }
    for crop in ("soja", "milho", "milho_2"):
        subset = by_crop.get(crop, [])
        if not subset:
            continue
        counts = Counter(str(r.get("zarc_cycle")) for r in subset)
        top = [name for name, _ in counts.most_common() if counts[name] >= MIN_ROWS]
        entry = {
            "class_counts": dict(counts.most_common()),
            "class_labels": {
                name: COD_CICLO.get(name, "nao documentado")
                for name in counts
            },
            "soil_counts": dict(Counter(str(r.get("zarc_soil")) for r in subset).most_common()),
            "tests": {},
        }
        if len(top) >= 2:
            class_a, class_b = top[0], top[1]
            entry["comparison"] = {
                "reference": class_a,
                "reference_label": COD_CICLO.get(class_a),
                "contrast": class_b,
                "contrast_label": COD_CICLO.get(class_b),
            }
            for variable in VARIABLES:
                entry["tests"][variable] = cycle.interaction_test(
                    subset, variable, class_a, class_b
                )
        else:
            entry["comparison"] = {
                "status": "insufficient_classes",
                "note": "menos de duas classes com >= 250 linhas",
            }
        payload["crops"][crop] = entry
        print(f"## {crop}: classes {dict(counts.most_common())}")
        for variable, result in entry["tests"].items():
            if result.get("status") != "ok":
                print(f"   {variable}: {result.get('status')}")
                continue
            diff = result["slope_difference"]
            print(
                f"   {variable}: inclinacao ref={result['slope_reference']['coefficient']:+.4f}"
                f" | diferenca={diff['coefficient']:+.4f}"
                f" (t={diff['t_statistic']:+.2f}, p={diff['p_value']:.4f})"
                f" n={result['n']} blocos={result['n_clusters']}"
            )

    with open(OUT_INTERACTION, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
        handle.write("\n")
    print(f"manifestos: {OUT_DICT} | {OUT_INTERACTION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
