"""Configuração de TLS para GDAL/rasterio no Windows.

Problema real observado em 2026-11-11: o GDAL usa schannel e recusa o caminho do
CA bundle quando ele contém caracteres não-ASCII (o repositório está em
"Área de Trabalho"). A solução é copiar o `cacert.pem` do certifi para um
caminho ASCII e apontar CURL_CA_BUNDLE/GDAL_HTTP_CAINFO para ele ANTES de abrir
qualquer COG remoto. Isso mantém a verificação TLS ligada.
"""

from __future__ import annotations

import os
import shutil
import tempfile

import certifi


def configure_tls(ca_path: str | None = None) -> str:
    """Copia o CA bundle para um caminho ASCII e exporta as variáveis.

    Retorna o caminho usado. Deve ser chamado antes de `rasterio.open(url)`.
    """
    if ca_path is None:
        ca_path = os.path.join(tempfile.gettempdir(), "saden-cacert.pem")
    ca_path = os.path.abspath(ca_path)
    if not ca_path.isascii():
        raise ValueError(f"caminho de CA precisa ser ASCII: {ca_path!r}")
    source = certifi.where()
    if not (os.path.exists(ca_path) and os.path.getsize(ca_path) == os.path.getsize(source)):
        os.makedirs(os.path.dirname(ca_path), exist_ok=True)
        shutil.copyfile(source, ca_path)
    for name in ("CURL_CA_BUNDLE", "GDAL_HTTP_CAINFO", "SSL_CERT_FILE"):
        os.environ[name] = ca_path
    return ca_path
