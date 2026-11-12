"""Leitor de ZIP remoto por requisições HTTP *Range*.

Os arquivos históricos anuais do INMET têm ~100 MB cada e contêm o CSV de
todas as estações do ano. Baixar o arquivo inteiro para extrair poucas
estações é desperdício; este módulo expõe um objeto de arquivo com
``read``/``seek``/``tell`` sobre requisições *Range*, o que permite abrir o
ZIP remoto com a biblioteca padrão :mod:`zipfile` e extrair **apenas** os
membros necessários.

Nenhum arquivo bruto é gravado em disco.
"""

from __future__ import annotations

import io
import urllib.request
import zipfile
from typing import Any

DEFAULT_USER_AGENT = "SADEN-V2.6/0.1 (investigacao academica; dados abertos)"
BLOCK = 1 << 20  # 1 MiB por leitura


class RangeHTTPError(RuntimeError):
    """Falha ao ler um intervalo HTTP."""


class HTTPRangeReader(io.RawIOBase):
    """Objeto de arquivo somente-leitura apoiado em ``Range: bytes=``."""

    def __init__(
        self,
        url: str,
        timeout: int = 180,
        user_agent: str = DEFAULT_USER_AGENT,
        block: int = BLOCK,
    ) -> None:
        super().__init__()
        self.url = url
        self.timeout = timeout
        self.user_agent = user_agent
        self.block = block
        self._pos = 0
        self._size: int | None = None
        self._cache: dict[tuple[int, int], bytes] = {}
        self._cache_order: list[tuple[int, int]] = []
        self._cache_max = 24
        self.requests = 0
        self.bytes_read = 0

    # ------------------------------------------------------------ infra
    def _open(self, start: int | None = None, end: int | None = None):
        headers = {"User-Agent": self.user_agent, "Accept": "*/*"}
        if start is not None:
            headers["Range"] = f"bytes={start}-{'' if end is None else end}"
        request = urllib.request.Request(self.url, headers=headers)
        self.requests += 1
        try:
            return urllib.request.urlopen(request, timeout=self.timeout)
        except Exception as exc:  # noqa: BLE001
            raise RangeHTTPError(f"{type(exc).__name__} ao ler {self.url}") from exc

    def _head_size(self) -> int:
        if self._size is not None:
            return self._size
        response = self._open()
        try:
            length = response.headers.get("Content-Length")
            if length is None:
                raise RangeHTTPError("servidor não devolveu Content-Length")
            self._size = int(length)
        finally:
            response.close()
        return self._size

    def _fetch(self, start: int, end: int) -> bytes:
        """Bytes no intervalo [start, end] (inclusive)."""
        key = (start, end)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        size = self._head_size()
        end = min(end, size - 1)
        response = self._open(start, end)
        try:
            data = response.read()
        finally:
            response.close()
        self.bytes_read += len(data)
        self._cache[key] = data
        self._cache_order.append(key)
        while len(self._cache_order) > self._cache_max:
            old = self._cache_order.pop(0)
            self._cache.pop(old, None)
        return data

    # ---------------------------------------------------- interface file
    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def writable(self) -> bool:
        return False

    def tell(self) -> int:
        return self._pos

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        if whence == io.SEEK_SET:
            self._pos = offset
        elif whence == io.SEEK_CUR:
            self._pos += offset
        elif whence == io.SEEK_END:
            self._pos = self._head_size() + offset
        else:
            raise ValueError(f"whence invalido: {whence}")
        return self._pos

    def size(self) -> int:
        return self._head_size()

    def read(self, size: int = -1) -> bytes:
        total = self._head_size()
        if self._pos >= total:
            return b""
        if size is None or size < 0:
            size = total - self._pos
        size = min(size, total - self._pos)
        if size == 0:
            return b""
        out = bytearray()
        start0 = self._pos
        while len(out) < size:
            start = self._pos
            end = min(start + self.block - 1, total - 1)
            chunk = self._fetch(start, end)
            expected = end - start + 1
            if not chunk:
                raise RangeHTTPError(
                    f"resposta vazia no intervalo {start}-{end} de {self.url}"
                )
            if len(chunk) < expected:
                raise RangeHTTPError(
                    f"resposta truncada no intervalo {start}-{end} de {self.url} "
                    f"({len(chunk)} de {expected} bytes)"
                )
            out += chunk
            self._pos = start + len(chunk)
        # o bloco pode ser maior que o pedido: devolve exatamente `size`
        # e reposiciona o cursor no fim do que foi efetivamente devolvido
        result = bytes(out[:size])
        self._pos = start0 + len(result)
        return result

    def readinto(self, buffer: Any) -> int:  # pragma: no cover - interface
        data = self.read(len(buffer))
        buffer[: len(data)] = data
        return len(data)


def zip_members(
    url: str,
    timeout: int = 180,
    user_agent: str = DEFAULT_USER_AGENT,
) -> dict[str, zipfile.ZipInfo]:
    """Índice (nome -> ZipInfo) do ZIP remoto, sem baixar os membros."""
    reader = HTTPRangeReader(url, timeout=timeout, user_agent=user_agent)
    with zipfile.ZipFile(reader) as archive:
        return {info.filename: info for info in archive.infolist()}


def read_member(
    url: str,
    member: str,
    timeout: int = 180,
    user_agent: str = DEFAULT_USER_AGENT,
    reader: HTTPRangeReader | None = None,
) -> bytes:
    """Extrai **um** membro do ZIP remoto (bytes descomprimidos)."""
    owned = reader is None
    handle = reader or HTTPRangeReader(url, timeout=timeout, user_agent=user_agent)
    try:
        with zipfile.ZipFile(handle) as archive:
            with archive.open(member) as member_handle:
                return member_handle.read()
    finally:
        if owned:
            handle.close()
