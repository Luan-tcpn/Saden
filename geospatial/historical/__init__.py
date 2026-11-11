"""SADEN V2.3 — série histórica Sentinel-2 e diagnóstico radiométrico.

Módulo **isolado**: não altera o pipeline da V2.1 (`s2_poc`), que permanece
intacto (Perfil A/B, máscara SCL, mosaico, série 2023–2025 e manifests).
"""

__all__ = ["radiometry", "series", "landuse", "study"]
