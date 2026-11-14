"""V3.2 — diagnósticos de identificabilidade e testes de inclinação por UF.

Fase 3 (identificabilidade) e Fase 7 (inferência) do roadmap da V3.2.

Família confirmatória, fixada no pré-registro: **6 testes globais**
(3 culturas × 2 variáveis primárias: precipitação acumulada corrigida e
temperatura média corrigida), corrigidos por Holm. Os contrastes por UF são
secundários e descritivos. As variáveis adicionais (graus-dia, calor extremo,
déficit com CAD) são exploratórias, com FDR.

Uso: python tools/v32_slope_tests.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "geospatial"))
sys.path.insert(0, HERE)

from agroclimate import heterogeneity, robust  # noqa: E402

import v31_models as base  # noqa: E402  (mesmos loaders da V3.1, sem duplicar)

MANIFESTS = os.path.join(ROOT, "geospatial", "data", "manifests")
OUT_JSON = os.path.join(MANIFESTS, "v32_slope_tests.json")
OUT_DIAG = os.path.join(MANIFESTS, "v32_coverage_diagnostics.json")

CROPS = ("soja", "milho", "milho_2")
PRIMARY = ("precip_corrected", "temp_corrected")
EXPLORATORY = ("degree_days_corrected", "heat_corrected", "deficit_cad100")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bh_adjust(p_values: dict[str, float]) -> dict[str, float]:
    """Benjamini-Hochberg (FDR) — usado só na família exploratória."""
    items = sorted(p_values.items(), key=lambda kv: kv[1])
    total = len(items)
    adjusted: dict[str, float] = {}
    running = 1.0
    for rank in range(total, 0, -1):
        key, value = items[rank - 1]
        running = min(running, value * total / rank)
        adjusted[key] = min(running, 1.0)
    return adjusted


def main() -> int:
    started = time.time()
    rows_by_crop = base.load_rows()
    rows_by_crop.pop("__dropped__", None)

    payload: dict[str, Any] = {
        "generated_at": _now(),
        "preregistration": "docs/V3_2_PREREGISTRATION.md",
        "design": {
            "estimator": "within dois fatores (município e ano) + interações UF x clima",
            "inference": "CR1 agrupado por bloco espacial; F(q, G-1) no teste global",
            "reference_state": "primeira UF em ordem alfabética (o teste global não depende dela)",
            "family_confirmatory": "3 culturas x 2 variáveis primárias = 6 testes globais, Holm",
            "family_secondary": "contrastes UF x variável por cultura, Holm dentro da cultura",
            "family_exploratory": "3 variáveis adicionais x 3 culturas, Benjamini-Hochberg",
            "variables_primary": list(PRIMARY),
            "variables_exploratory": list(EXPLORATORY),
        },
        "crops": {},
    }

    diagnostics: dict[str, Any] = {"generated_at": _now(), "crops": {}}
    for crop in CROPS:
        rows = rows_by_crop.get(crop, [])
        print(f"=== {crop}: {len(rows)} linhas ===", flush=True)
        diagnostics["crops"][crop] = heterogeneity.coverage_diagnostics(
            rows, PRIMARY + EXPLORATORY
        )
        entry: dict[str, Any] = {"n_rows": len(rows), "tests": {}, "single_variable": {}, "exploratory": {}}
        # especificação primária: as DUAS variáveis juntas (a da V3.1). Testar
        # cada variável sozinha deixaria a outra no erro e, como as anomalias
        # de precipitação e temperatura são correlacionadas (≈ −0,6 a −0,7
        # within), o coeficiente de uma capturaria o efeito da outra.
        joint = heterogeneity.slope_heterogeneity(rows, PRIMARY)
        entry["joint"] = joint
        # sensibilidade ao esquema de agrupamento (bloco espacial, como V2.7-V3.1)
        entry["joint_block_clustering"] = heterogeneity.slope_heterogeneity(
            rows, PRIMARY, cluster="block"
        )
        for variable in PRIMARY:
            entry["tests"][variable] = joint.get("global_tests", {}).get(variable, {})
            test = entry["tests"][variable]
            block_test = (
                entry["joint_block_clustering"]
                .get("global_tests", {})
                .get(variable, {})
            )
            if joint.get("status") == "ok":
                print(
                    "  joint %-16s F(%s,%s)=%.2f p=%.4f | bloco: F=%.2f p=%.4f | ref %s slope=%+.4f"
                    % (
                        variable,
                        test.get("df1"),
                        test.get("df2"),
                        test.get("statistic") or float("nan"),
                        test.get("p_value") if test.get("p_value") is not None else float("nan"),
                        block_test.get("statistic") or float("nan"),
                        block_test.get("p_value") if block_test.get("p_value") is not None else float("nan"),
                        joint["reference_state"],
                        joint["common_slopes"][variable],
                    ),
                    flush=True,
                )
            else:
                print(f"  joint {variable:<16} {joint.get('status')}", flush=True)
        for variable in PRIMARY:
            single = heterogeneity.slope_heterogeneity(rows, (variable,))
            entry["single_variable"][variable] = single
            test = single.get("global_tests", {}).get(variable, {})
            if single.get("status") == "ok":
                print(
                    "  sep   %-16s F(%s,%s)=%.2f p=%.4f (sensibilidade)"
                    % (
                        variable,
                        test.get("df1"),
                        test.get("df2"),
                        test.get("statistic") or float("nan"),
                        test.get("p_value") if test.get("p_value") is not None else float("nan"),
                    ),
                    flush=True,
                )
        for variable in EXPLORATORY:
            entry["exploratory"][variable] = heterogeneity.slope_heterogeneity(
                rows, (variable,)
            )
        payload["crops"][crop] = entry

    # --- Holm na família confirmatória (6 testes globais) -------------------
    confirmatory: dict[str, float] = {}
    for crop, entry in payload["crops"].items():
        for variable in PRIMARY:
            test = entry["tests"].get(variable, {})
            if test.get("p_value") is not None:
                confirmatory[f"{crop}|{variable}"] = float(test["p_value"])
    holm = robust.holm_adjust(confirmatory) if confirmatory else {}
    payload["confirmatory_family"] = {
        "size": len(confirmatory),
        "raw": confirmatory,
        "holm": holm,
        "rejected_holm_0.05": sorted(
            key for key, value in holm.items() if value is not None and value < 0.05
        ),
    }

    # --- BH na família exploratória ----------------------------------------
    exploratory_p: dict[str, float] = {}
    for crop, entry in payload["crops"].items():
        for variable, result in entry["exploratory"].items():
            test = result.get("global_tests", {}).get(variable, {})
            if test.get("p_value") is not None:
                exploratory_p[f"{crop}|{variable}"] = float(test["p_value"])
    payload["exploratory_family"] = {
        "size": len(exploratory_p),
        "raw": exploratory_p,
        "bh": _bh_adjust(exploratory_p) if exploratory_p else {},
    }

    payload["elapsed_s"] = round(time.time() - started, 1)
    os.makedirs(MANIFESTS, exist_ok=True)
    for path, data in ((OUT_JSON, payload), (OUT_DIAG, diagnostics)):
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2, default=str)
            handle.write("\n")

    print("\n=== família confirmatória (Holm) ===")
    for key in sorted(confirmatory):
        print(
            "  %-28s p=%.5f  holm=%.5f %s"
            % (
                key,
                confirmatory[key],
                holm[key],
                "REJEITA H0" if holm[key] < 0.05 else "n.s.",
            )
        )
    print(f"\nmanifestos: {OUT_JSON}\n            {OUT_DIAG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
