"""Sondagem do WCS da Embrapa Solos (GeoInfo) — água disponível do solo.

Fonte: https://geoinfo.dados.embrapa.br/geoserver/ows (WCS 2.0.1)

Este script é **evidência** da fase de investigação da CAD (V2.7). Ele:
1. consulta ``GetCapabilities`` e grava a resposta bruta;
2. extrai os identificadores de cobertura e as URLs de metadados;
3. consulta ``DescribeCoverage`` das camadas de água disponível
   (``aw_*``) para confirmar **unidade**, **profundidade**, **resolução**,
   **sistema de referência** e **licença**;
4. registra tudo em ``geospatial/data/manifests/v27_cad_wcs_probe.json``.

Nenhuma requisiçãomassive é feita: apenas metadados.

Uso:
    python tools/s27_wcs_probe.py
"""

from __future__ import annotations

import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
OUT = os.path.join(ROOT, "geospatial", "data", "manifests", "v27_cad_wcs_probe.json")
BASE = "https://geoinfo.dados.embrapa.br/geoserver/ows"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SADEN-V2.7"}
TIMEOUT = 90
RETRIES = 2


def context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def fetch(url: str, tries: int = RETRIES + 1) -> tuple[int, bytes, str]:
    last = ""
    for attempt in range(tries):
        try:
            request = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(
                request, timeout=TIMEOUT, context=context()
            ) as response:
                return response.status, response.read(), ""
        except urllib.error.HTTPError as exc:  # erro do servidor, com corpo
            body = exc.read() if hasattr(exc, "read") else b""
            last = f"HTTP {exc.code}"
            if exc.code in (429, 503):
                delay = int(exc.headers.get("Retry-After", 5)) if exc.headers else 5
                time.sleep(min(delay, 30))
                continue
            return exc.code, body, last
        except Exception as exc:  # DNS / TLS / timeout
            last = f"{type(exc).__name__}: {exc}"
            time.sleep(2 * (attempt + 1))
    return 0, b"", last


def main() -> int:
    report: dict = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "base_url": BASE,
        "attempts": [],
    }

    status, body, err = fetch(
        f"{BASE}?service=WCS&request=GetCapabilities&version=2.0.1"
    )
    text = body.decode("utf-8", "replace")
    raw_path = os.path.join(
        ROOT, "geospatial", "data", "processed", "embrapa_solos_wcs_capabilities.xml"
    )
    os.makedirs(os.path.dirname(raw_path), exist_ok=True)
    with open(raw_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    report["capabilities_raw"] = os.path.relpath(raw_path, ROOT)
    report["attempts"].append(
        {
            "url": "GetCapabilities",
            "status": status,
            "bytes": len(body),
            "error": err,
            "head": text[:1200],
        }
    )

    coverage_ids = sorted(
        set(re.findall(r"<wcs:CoverageId>([^<]+)</wcs:CoverageId>", text))
    )
    if not coverage_ids:
        coverage_ids = sorted(set(re.findall(r"<CoverageId>([^<]+)</CoverageId>", text)))
    report["n_coverage_ids"] = len(coverage_ids)
    report["coverage_ids"] = coverage_ids

    # Metadados por camada (formato ISO 19115)
    metadata_urls = sorted(
        set(re.findall(r"<wcs:MetadataURL[^>]*>([^<]+)</wcs:MetadataURL>", text))
    )
    if not metadata_urls:
        metadata_urls = sorted(set(re.findall(r"<MetadataURL[^>]*>([^<]+)</MetadataURL>", text)))
    report["metadata_urls"] = metadata_urls[:80]

    # Descrição das camadas de água disponível
    described: dict[str, dict] = {}
    for name in coverage_ids:
        if "_aw_" not in name.lower():
            continue
        status_d, body_d, err_d = fetch(
            f"{BASE}?service=WCS&request=DescribeCoverage&version=2.0.1"
            f"&coverageId={name}"
        )
        cov = body_d.decode("utf-8", "replace")
        units = re.findall(r"<wcs:UnitSymbol>([^<]+)</wcs:UnitSymbol>", cov)
        fields = re.findall(r"<wcs:fieldName>([^<]+)</wcs:fieldName>", cov)
        envelopes = re.findall(r"<(?:wcs:)?[Ee]nvelope[^>]*>([^<]+)</", cov)
        crs = re.findall(r"<(?:wcs:)?(?:supportedCrs|requestResponseCRSs)[^>]*>([^<]+)<", cov)
        tile = re.findall(r"<(?:wcs:)?(?:high|low)[XY]>([^<]+)</", cov)
        described[name] = {
            "status": status_d,
            "error": err_d,
            "bytes": len(body_d),
            "unit_symbols": units,
            "field_names": fields,
            "axis_envelopes": envelopes,
            "crs": crs[:6],
            "axis_limits": tile[:12],
            "head": cov[:900],
        }
        time.sleep(0.3)
    report["descriptions"] = described

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    print(f"status GetCapabilities: {status} | bytes: {len(body)} | erro: {err}")
    print(f"coverageIds: {len(coverage_ids)}")
    for name in coverage_ids[:60]:
        print("  -", name)
    print(f"camadas 'aw' descritas: {len(described)}")
    for name, info in described.items():
        print(f"  {name}: status={info['status']} unidades={info['unit_symbols']} "
              f"campos={info['field_names']}")
    print(f"manifesto: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
