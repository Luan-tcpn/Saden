#!/usr/bin/env python
"""CLI da prova de conceito Sentinel-2 (SADEN V2.1).

Exemplos (a partir da raiz do repositório):

    geospatial\\.venv\\Scripts\\python.exe geospatial\\run_poc.py --check-only
    geospatial\\.venv\\Scripts\\python.exe geospatial\\run_poc.py

Os rasters grandes vão para `geospatial/artifacts/` (ignorado pelo Git); apenas
prévias PNG pequenas ficam versionadas em `geospatial/previews/`.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from s2_poc import config  # noqa: E402
from s2_poc import pipeline  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(
        description="SADEN V2.1 — PoC Sentinel-2 L2A (NDVI/EVI/NDMI)"
    )
    parser.add_argument("--check-only", action="store_true", help="apenas descoberta STAC/AOI, sem baixar raster")
    parser.add_argument("--start", default=config.DEFAULT_START, help="data inicial YYYY-MM-DD")
    parser.add_argument("--end", default=config.DEFAULT_END, help="data final YYYY-MM-DD")
    parser.add_argument("--max-cloud", type=float, default=config.DEFAULT_MAX_CLOUD, help="nuvem máxima (%%)")
    parser.add_argument("--max-scenes", type=int, default=config.DEFAULT_MAX_SCENES, help="máximo de cenas (1 por mês)")
    parser.add_argument("--artifacts", default=os.path.join(here, "artifacts"), help="diretório de rasters/metadados (ignorado no Git)")
    parser.add_argument("--previews", default=os.path.join(here, "previews"), help="diretório de prévias PNG")
    parser.add_argument("--no-preview", action="store_true", help="não gerar PNG")
    args = parser.parse_args(argv)

    try:
        summary = pipeline.run(
            artifacts_dir=args.artifacts,
            previews_dir=None if args.no_preview else args.previews,
            start=args.start,
            end=args.end,
            max_cloud=args.max_cloud,
            max_scenes=args.max_scenes,
            write_preview=not args.no_preview,
            check_only=args.check_only,
        )
    except Exception as exc:  # noqa: BLE001 - CLI deve falhar com mensagem clara
        print(json.dumps({"ok": False, "error": type(exc).__name__, "message": str(exc)}, ensure_ascii=False))
        return 1

    concise = {
        "ok": True,
        "mode": summary["mode"],
        "catalog": summary["catalog"]["url"],
        "collection": summary["catalog"]["collection"],
        "aoi_bbox": summary["aoi"]["bbox"],
        "aoi_note": summary["aoi"]["note"],
        "search": summary["search"],
        "selected_items": summary["items"],
        "scenes": [
            {
                "item_id": s["item_id"],
                "datetime": str(s["datetime"])[:10],
                "cloud_cover": round(float(s["cloud_cover"]), 4) if s["cloud_cover"] is not None else None,
                "kept_fraction": round(s["mask_summary"]["kept_fraction"], 4),
                "stats": {
                    name: {
                        "valid_fraction": round(v["valid_fraction"], 4),
                        "min": round(v["min"], 4) if v["min"] is not None else None,
                        "max": round(v["max"], 4) if v["max"] is not None else None,
                        "mean": round(v["mean"], 4) if v["mean"] is not None else None,
                    }
                    for name, v in s["stats"].items()
                },
                "files": {k: v["path"] for k, v in s["files"].items()},
                "preview": s["preview"],
            }
            for s in summary["scenes"]
        ],
        "artifacts": summary["artifacts"],
        "warnings": summary["warnings"],
        "versions": summary["versions"],
    }
    print(json.dumps(concise, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
