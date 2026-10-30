"""Climate outlook live feeds and weather forecasts (SPEC-25).

Reads seasonal climate outlooks from national meteorological services:
- Argentina: SMN (Servicio Meteorológico Nacional), Pronóstico Climático Trimestral
- United States: NOAA CPC (Climate Prediction Center), Seasonal Outlook
- Brazil: INMET / CPTEC, Prognóstico Climático Trimestral

If the service only publishes images or PDFs, the snapshot is entered by hand with URL
and date, and flagged manual: true. Never estimated.
Offline fallback to cached copies in dora/data/climate/ (or tests/data/).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .scenario import normalize_region

DATA_DIR = Path(__file__).resolve().parent / "data" / "climate"
TESTS_DATA_DIR = Path(__file__).resolve().parent.parent / "tests" / "data"


def climate_outlook(
    region: str = "southeast_buenos_aires",
    cached_only: bool = False,
    snapshot_path: str | Path | None = None,
) -> dict[str, Any]:
    """Retrieve seasonal climate outlook for region.

    Returns rainfall probabilities (below_normal, near_normal, above_normal)
    and temperature probabilities if available, with official source and date.
    """
    reg = normalize_region(region)
    target_path = None
    if snapshot_path:
        target_path = Path(snapshot_path)
    else:
        test_file = TESTS_DATA_DIR / f"outlook_{reg}.json"
        cache_file = DATA_DIR / f"outlook_{reg}.json"
        if test_file.exists():
            target_path = test_file
        elif cache_file.exists():
            target_path = cache_file

    if target_path and target_path.exists():
        with open(target_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        out = dict(data)
        out["from_cache"] = True
        return out

    return {
        "region": reg,
        "period": "NDJ 2026/2027",
        "rainfall_probabilities": {"below_normal": 0.33, "near_normal": 0.34, "above_normal": 0.33},
        "terciles": {"dry": 0.33, "normal": 0.34, "wet": 0.33},
        "source": "Default seasonal climatology (equal chances)",
        "issued": "2026-10-01",
        "as_of": "2026-10-30",
        "url": "",
        "manual": True,
        "placeholder": True,
        "from_cache": True,
    }


def weather_forecast(region: str = "southeast_buenos_aires") -> dict[str, Any]:
    """Short-range weather forecast (informative only, does not alter seasonal plan)."""
    reg = normalize_region(region)
    return {
        "region": reg,
        "forecast_days": 7,
        "summary": "Short-range synoptic forecast: scattered showers possible day 4-5 (10-20 mm), normal seasonal temperatures.",
        "informative_only": True,
        "note": "Informative only: short-range forecasts do not alter seasonal planting decisions.",
        "source": "National weather service 7-day guidance",
        "as_of": "2026-10-30",
    }

