"""Manifestos determinísticos: conteúdo canônico separado de metadados de execução.

Problema resolvido (D131): os manifestos anteriores embutiam ``generated_at`` no
mesmo arquivo, então o SHA-256 mudava a cada execução e não servia como
verificação de integridade — apenas como proveniência.

Aqui o conteúdo é serializado de forma canônica e hasheado; a data, a duração e o
ambiente vão para um arquivo irmão ``*.run.json``, que pode variar livremente.

Canonicalização aplicada:

* chaves ordenadas em todo objeto;
* números em formato estável (inteiros como inteiros, floats com ``repr`` curto);
* listas preservadas na ordem (a ordem de listas é semântica, não acidental);
* ``None`` explícito, sem campos omitidos;
* UTF-8 sem BOM, ``\\n`` como terminador de linha;
* caminhos normalizados para separador ``/`` e relativos ao repositório.

Uso:
    from manifest import write_manifest
    write_manifest(path, content, run_metadata)
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from typing import Any

VOLATILE_KEYS = {
    "generated_at",
    "elapsed_s",
    "started_at",
    "finished_at",
    "duration_s",
    "host",
    "pid",
    "python",
    "platform",
    "cwd",
    "executed_at",
}


def _normalise(value: Any, key: str | None = None) -> Any:
    """Normaliza para serialização estável; remove campos voláteis."""
    if key in VOLATILE_KEYS:
        return "__volatile__"
    if isinstance(value, dict):
        return {str(k): _normalise(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalise(item) for item in value]
    if isinstance(value, float):
        if value != value:  # NaN
            return "NaN"
        if value in (float("inf"), float("-inf")):
            return "Infinity" if value > 0 else "-Infinity"
        # formato estável e curto; evita diferenças de plataforma no repr
        return float(f"{value:.12g}")
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    return str(value)


def canonical_json(content: dict[str, Any]) -> str:
    """Serialização canônica do conteúdo, sem metadados voláteis."""
    normalised = _normalise(content)
    return json.dumps(
        normalised,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def content_hash(content: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(content).encode("utf-8")).hexdigest()


def file_hash(path: str) -> str | None:
    if not os.path.exists(path):
        return None
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_manifest(
    path: str,
    content: dict[str, Any],
    run_metadata: dict[str, Any] | None = None,
    started: float | None = None,
) -> dict[str, Any]:
    """Escreve ``path`` (conteúdo canônico) e ``path.run.json`` (execução)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = dict(content)
    digest = content_hash(payload)
    payload["content_sha256"] = digest

    text = json.dumps(
        _normalise(payload),
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
        allow_nan=False,
    ) + "\n"
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)

    metadata = dict(run_metadata or {})
    metadata.setdefault("generated_at", datetime.now(timezone.utc).isoformat())
    if started is not None:
        metadata.setdefault("elapsed_s", round(time.time() - started, 1))
    metadata.setdefault("host", platform.node())
    metadata.setdefault("platform", platform.platform())
    metadata.setdefault("python", sys.version.split()[0])
    metadata.setdefault("content_sha256", digest)
    metadata.setdefault("manifest_path", os.path.basename(path))
    run_path = f"{path}.run.json"
    with open(run_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(metadata, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    return {"content_sha256": digest, "manifest": path, "run_metadata": run_path}
