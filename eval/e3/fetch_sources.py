"""Fetches source pages and files for real prices and saves evidence to eval/e3/sources/."""
from __future__ import annotations

import json
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SOURCES_DIR = ROOT / "eval" / "e3" / "sources"
SOURCES_DIR.mkdir(parents=True, exist_ok=True)

# Sources list: (id, url, is_local_file)
SOURCES_TO_FETCH = [
    {
        "id": "bcra_fx_20261102",
        "url": "https://api.bcra.gob.ar/estadisticas/v4.0/Monetarias/5",
        "ext": "json",
    },
    {
        "id": "cs_urea_granel",
        "url": "https://www.camposimple.com.ar/default/urea-granel-1-tn.html",
        "ext": "html",
    },
    {
        "id": "cs_map_granel",
        "url": "https://www.camposimple.com.ar/default/map-granel-4.html",
        "ext": "html",
    },
    {
        "id": "cs_dap_granel",
        "url": "https://www.camposimple.com.ar/default/dap-1-tn-granel-logistica.html",
        "ext": "html",
    },
    {
        "id": "cs_soja_semilla",
        "url": "https://www.camposimple.com.ar/default/dm-46e21-40-kgs-10.html",
        "ext": "html",
    },
    {
        "id": "cs_glifosato",
        "url": "https://www.camposimple.com.ar/default/la-tijereta-platinum-ii-glifosato-54-20-lts-1.html",
        "ext": "html",
    },
    {
        "id": "cs_atrazina",
        "url": "https://www.camposimple.com.ar/default/atrazina-atrazina-90-15-kgs-1.html",
        "ext": "html",
    },
    {
        "id": "cs_dual_gold",
        "url": "https://www.camposimple.com.ar/default/dual-gold-s-metolacloro-96-5-lts-2.html",
        "ext": "html",
    },
    {
        "id": "cs_trigo_semilla",
        "url": "https://www.camposimple.com.ar/default/dm-catalpa-trigo-bolsas-40-kg-3.html",
        "ext": "html",
    },
    {
        "id": "ia_isu_corn_fertilizer",
        "url": "dora/data/iowa_2026.json",
        "is_local": True,
        "ext": "json",
    },
    {
        "id": "ia_isu_corn_seed",
        "url": "dora/data/iowa_2026.json",
        "is_local": True,
        "ext": "json",
    },
    {
        "id": "ia_isu_soybean_herbicide",
        "url": "dora/data/iowa_2026.json",
        "is_local": True,
        "ext": "json",
    },
]


def fetch_all() -> list[dict]:
    index = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    for item in SOURCES_TO_FETCH:
        sid = item["id"]
        url = item["url"]
        ext = item["ext"]
        out_path = SOURCES_DIR / f"{sid}.{ext}"

        if item.get("is_local"):
            local_src = ROOT / url
            content = local_src.read_text(encoding="utf-8")
            out_path.write_text(content, encoding="utf-8")
            record = {
                "id": sid,
                "url": f"file://{url}",
                "final_url": f"file://{url}",
                "status": 200,
                "fetched_at": datetime.now().isoformat(timespec="seconds"),
                "saved_file": str(out_path.relative_to(ROOT)).replace("\\", "/"),
                "content_length": len(content),
            }
            index.append(record)
            print(f"[{sid}] local: {url} -> {out_path.name} ({len(content)} bytes)")
            continue

        print(f"[{sid}] fetching {url}...", flush=True)
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            status = resp.status
            final_url = resp.geturl()
            raw_bytes = resp.read()
            out_path.write_bytes(raw_bytes)
            record = {
                "id": sid,
                "url": url,
                "final_url": final_url,
                "status": status,
                "fetched_at": datetime.now().isoformat(timespec="seconds"),
                "saved_file": str(out_path.relative_to(ROOT)).replace("\\", "/"),
                "content_length": len(raw_bytes),
            }
            index.append(record)
            print(f"[{sid}] 200 OK -> {out_path.name} ({len(raw_bytes)} bytes)")

    index_path = SOURCES_DIR / "index.json"
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved index with {len(index)} records to {index_path}")
    return index


if __name__ == "__main__":
    fetch_all()

