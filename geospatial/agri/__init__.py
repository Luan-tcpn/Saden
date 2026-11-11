"""SADEN V2.2 — Base observada de produtividade agrícola.

Módulo isolado (não é importado pelo backend Node.js da V1). Elequire e
normaliza dados oficiais de produção agrícola (IBGE/SIDRA e CONAB), verifica
sua qualidade e avalia a compatibilidade com os indicadores Sentinel-2
produzidos na V2.1.

Nada aqui modifica o produto, o modelo Ridge ou a interface.
"""

__all__ = [
    "config",
    "sidra",
    "conab",
    "crosswalk",
    "normalize",
    "validate",
    "compat",
]
