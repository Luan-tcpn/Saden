"""Comparação dos perfis de máscara SCL (Checkpoint B).

Nenhum perfil é exposto ao usuário final: são parâmetros internos de
processamento/diagnóstico. O perfil ``A_historical`` reproduz exatamente a
máscara da PoC; ``B_restrictive`` exclui também as classes 2 (dark area) e 6
(água). A classe 2 é comumente usada pelo classificador para sombra escura,
terreno escuro e água turva; a classe 6 é água. Manter ou remover essas classes
muda o alvo estatístico e precisa ser decidido por evidência (cobertura,
semântica e estabilidade), não por conveniência.
"""

from __future__ import annotations

from typing import Any, Iterable

import numpy as np

from . import config


def profile_classes(profile: str = "A_historical") -> tuple[int, ...]:
    """Classes excluídas pelo perfil (ordem determinística)."""
    try:
        return tuple(sorted(set(config.SCL_PROFILES[profile])))
    except KeyError as exc:  # pragma: no cover - validação de entrada
        raise ValueError(
            f"perfil SCL desconhecido: {profile!r}; "
            f"disponíveis: {sorted(config.SCL_PROFILES)}"
        ) from exc


def keep_mask(scl: np.ndarray, profile: str = "A_historical") -> np.ndarray:
    """``True`` onde a classe SCL é aproveitável segundo o perfil.

    Valores fora de 0..11 não são encontrados no produto oficial; por padrão
    permanecem válidos para preservar exatamente o comportamento histórico.
    Use :func:`unknown_mask` para auditar esses casos.
    """
    arr = np.asarray(scl)
    keep = np.ones(arr.shape, dtype=bool)
    for cls in profile_classes(profile):
        keep &= arr != cls
    return keep


def unknown_mask(scl: np.ndarray) -> np.ndarray:
    """``True`` onde o código não é uma classe SCL oficial (0..11)."""
    arr = np.asarray(scl)
    return (arr < 0) | (arr > 11)


def class_counts(scl: np.ndarray, valid_mask: np.ndarray | None = None) -> dict[str, Any]:
    """Contagem/percentual de cada classe SCL e de códigos desconhecidos."""
    arr = np.asarray(scl)
    selected = np.ones(arr.shape, dtype=bool) if valid_mask is None else np.asarray(valid_mask, dtype=bool)
    if selected.shape != arr.shape:
        raise ValueError(f"máscara {selected.shape} difere do SCL {arr.shape}")
    values = arr[selected].astype("int64")
    total = int(values.size)
    counts: list[dict[str, Any]] = []
    for code in sorted(config.SCL_CLASSES):
        n = int(np.count_nonzero(values == code))
        counts.append(
            {
                "class": code,
                "name": config.SCL_CLASSES[code],
                "pixels": n,
                "fraction": (n / total) if total else 0.0,
                "kept_by_A": code not in profile_classes("A_historical"),
                "kept_by_B": code not in profile_classes("B_restrictive"),
            }
        )
    unknown = int(np.count_nonzero(unknown_mask(values)))
    return {
        "total_pixels": total,
        "classes": counts,
        "unknown_pixels": unknown,
        "unknown_fraction": (unknown / total) if total else 0.0,
    }


def compare_profiles(
    scl: np.ndarray,
    profiles: Iterable[str] = ("A_historical", "B_restrictive"),
) -> dict[str, Any]:
    """Compara perfis: cobertura válida e pixels que mudam de estado."""
    profiles = list(profiles)
    masks = {name: keep_mask(scl, name) for name in profiles}
    total = int(np.asarray(scl).size)
    per_profile = []
    for name in profiles:
        keep = masks[name]
        kept = int(np.count_nonzero(keep))
        per_profile.append(
            {
                "profile": name,
                "excluded_classes": list(profile_classes(name)),
                "total_pixels": total,
                "valid_pixels": kept,
                "invalid_pixels": total - kept,
                "valid_fraction": (kept / total) if total else 0.0,
            }
        )

    transitions: dict[str, Any] = {}
    if len(profiles) >= 2:
        first, second = masks[profiles[0]], masks[profiles[1]]
        transitions = {
            "pair": [profiles[0], profiles[1]],
            "both_valid": int(np.count_nonzero(first & second)),
            "first_valid_second_invalid": int(np.count_nonzero(first & ~second)),
            "first_invalid_second_valid": int(np.count_nonzero(~first & second)),
            "both_invalid": int(np.count_nonzero(~first & ~second)),
            "changed_pixels": int(np.count_nonzero(first != second)),
        }
        transitions["changed_fraction"] = (
            transitions["changed_pixels"] / total if total else 0.0
        )

    return {"profiles": per_profile, "transitions": transitions}


def masked_index(indices: np.ndarray, keep: np.ndarray) -> np.ndarray:
    """Aplica máscara explícita a um índice, devolvendo float32 com NaN."""
    arr = np.asarray(indices, dtype="float64")
    if arr.shape != np.asarray(keep).shape:
        raise ValueError(f"índice {arr.shape} difere da máscara {np.asarray(keep).shape}")
    return np.where(keep, arr, np.nan).astype("float32")


def class_index_stats(
    scl: np.ndarray,
    indices: dict[str, np.ndarray],
    min_pixels: int = 1,
) -> dict[str, Any]:
    """Estatísticas de cada índice **dentro de cada classe SCL**.

    Permite separar água, sombra, vegetação e solo sem tratá-los como uma
    média única. Classes com menos de ``min_pixels`` são omitidas.
    """
    from .indices import array_stats

    arr = np.asarray(scl)
    out: dict[str, Any] = {}
    for name, values in indices.items():
        values = np.asarray(values)
        if values.shape != arr.shape:
            raise ValueError(f"{name}: shape {values.shape} difere do SCL {arr.shape}")
        per_class = []
        for code in sorted(config.SCL_CLASSES):
            subset = np.where(arr == code, values, np.nan)
            stats = array_stats(subset)
            if stats["valid_pixels"] >= min_pixels:
                per_class.append(
                    {
                        "class": code,
                        "name": config.SCL_CLASSES[code],
                        "pixels": int(np.count_nonzero(arr == code)),
                        **stats,
                    }
                )
        out[name] = per_class
    return out
