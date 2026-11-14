"""Metadados completos das camadas de água disponível (AW) da Embrapa Solos.

Extrai do ``DescribeCoverage`` do WCS GeoInfo:
* título oficial (``gml:name``), com unidade, profundidade e resolução;
* extensão e sistema de referência;
* URL do registro de metadados (ISO 19115) — de onde vêm licença,
  resumo e data de publicação;
* implementação de serviço (formato de saída, compressão, tile).

Nenhumacoverage de dados é transferida: apenas metadados.
"""

from __future__ import annotations

import json
import os
import re
import ssl
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
OUT = os.path.join(ROOT, "geospatial", "data", "manifests", "v27_cad_layer_metadata.json")
BASE = "https://geoinfo.dados.embrapa.br/geoserver/ows"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SADEN-V2.7"}
NS = {
    "wcs": "http://www.opengis.net/wcs/2.0",
    "ows": "http://www.opengis.net/ows/2.0",
    "gml": "http://www.opengis.net/gml/3.2",
    "gmlcov": "http://www.opengis.net/gmlcov/1.0",
    "xlink": "http://www.w3.org/1999/xlink",
    "swe": "http://www.opengis.net/swe/2.0",
    "wcsgs": "http://www.geoserver.org/wcsgs/2.0",
}
AW_LAYERS = [
    "geonode__aw_0_5_def",
    "geonode__aw_5_15_def",
    "geonode__aw_15_30_def",
    "geonode__aw_30_60_def",
    "geonode__aw_60_100_def",
    "geonode__aw_100_200_def",
]


def context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def fetch(url: str, tries: int = 3) -> bytes:
    last = ""
    for attempt in range(tries):
        try:
            request = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(request, timeout=90, context=context()) as r:
                return r.read()
        except Exception as exc:
            last = f"{type(exc).__name__}: {exc}"
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(last)


def text_of(node, path: str) -> str | None:
    found = node.find(path, NS)
    if found is None or found.text is None:
        return None
    return found.text.strip()


def main() -> int:
    report: dict = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "base_url": BASE,
        "layers": {},
    }
    for name in AW_LAYERS:
        url = (
            f"{BASE}?service=WCS&request=DescribeCoverage&version=2.0.1"
            f"&coverageId={name}"
        )
        body = fetch(url)
        root = ET.fromstring(body)
        desc = root.find("wcs:CoverageDescription", NS)
        if desc is None:
            report["layers"][name] = {"status": "sem_descricao"}
            continue
        envelope = desc.find(".//gml:Envelope", NS)
        axis_labels = []
        limits = []
        if envelope is not None:
            for axis in envelope.findall(".//gml:AxisLabel", NS):
                axis_labels.append((axis.text or "").strip())
            for lower in envelope.findall(".//gml:lowerBound", NS):
                limits.append((lower.text or "").strip())
            for upper in envelope.findall(".//gml:upperBound", NS):
                limits.append((upper.text or "").strip())
        crs = None
        crs_node = desc.find(".//gml:Envelope/gml:Envelope", NS)
        srs = desc.find(".//gml:boundedBy//gml:Envelope", NS)
        for node in desc.iter():
            if node.tag.endswith("}Envelope"):
                crs = node.attrib.get("srsName")
                break
        fields = []
        for field in desc.findall(".//gmlcov:Field", NS):
            fields.append(
                {
                    "name": field.attrib.get("gml:id"),
                    "definition": text_of(field, "gmlcov:Definition"),
                    "uom": text_of(field, "gmlcov:uom"),
                    "quantity_type": text_of(field, "swe:Quantity/ swe:uom")
                    or text_of(field, "swe:Quantity/swe:uom"),
                }
            )
        service_params = {}
        for sp in desc.findall(".//wcs:ServiceParameters/*", NS):
            service_params[sp.tag.split("}")[-1]] = (sp.text or "").strip()
        metadata_url = None
        for node in desc.findall(".//ows:MetadataURL", NS):
            metadata_url = node.attrib.get(
                "{http://www.w3.org/1999/xlink}href"
            )
            break
        service_metadata_url = None
        for node in desc.findall(".//wcs:ServiceMetadataURL", NS):
            service_metadata_url = node.attrib.get(
                "{http://www.w3.org/1999/xlink}href"
            )
            break
        report["layers"][name] = {
            "title": text_of(desc, "gml:name"),
            "abstract": text_of(desc, "gml:abstract"),
            "description": text_of(desc, "gml:description"),
            "crs": crs,
            "axis_labels": axis_labels,
            "axis_limits": limits,
            "fields": fields,
            "service_parameters": service_params,
            "metadata_url": metadata_url,
            "service_metadata_url": service_metadata_url,
        }
        time.sleep(0.4)

    # Registro de metadados (ISO 19115) da primeira camada: licença e data
    first = report["layers"].get(AW_LAYERS[0], {})
    meta_url = first.get("metadata_url")
    if meta_url:
        try:
            body = fetch(meta_url)
            text = body.decode("utf-8", "replace")
            report["metadata_record"] = {
                "url": meta_url,
                "bytes": len(body),
                "license_hits": sorted(
                    set(
                        re.findall(
                            r"https?://[^\"'<>\s]*(?:licen[çc]e|licenca|copyright|cc-by|creativ[^\"'<>\s]*)"
                            r"[^\"'<>\s]*",
                            text,
                            flags=re.IGNORECASE,
                        )
                    )
                )[:20],
                "license_context": re.findall(
                    r"[^<>]{0,160}(?:licen[çc]e|CC[- ]?BY|Creative Commons)[^<>]{0,160}",
                    text,
                    flags=re.IGNORECASE,
                )[:12],
                "title_hits": re.findall(
                    r"<gmd:title[^>]*>\s*<gco:CharacterString>([^<]{5,300})",
                    text,
                )[:5],
                "abstract_hits": re.findall(
                    r"<gmd:abstract[^>]*>\s*<gco:CharacterString>([^<]{20,2000})",
                    text,
                )[:3],
                "dates": re.findall(
                    r"<gmd:date[^>]*>\s*<gco:DateTime>([^<]+)", text
                )[:6],
            }
        except Exception as exc:
            report["metadata_record"] = {"url": meta_url, "error": str(exc)}

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    for name, info in report["layers"].items():
        print(f"--- {name}")
        print("   titulo :", info.get("title"))
        print("   crs    :", info.get("crs"))
        print("   campos :", json.dumps(info.get("fields"), ensure_ascii=False)[:400])
        print("   metadad:", info.get("metadata_url"))
    if "metadata_record" in report:
        rec = report["metadata_record"]
        print()
        print("licencas:", rec.get("license_hits"))
        print("datas:", rec.get("dates"))
        print("titulo:", rec.get("title_hits"))
    print(f"manifesto: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
