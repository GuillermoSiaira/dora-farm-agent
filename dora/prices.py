"""Price curves from futures markets and spot exchanges."""
from __future__ import annotations

import json
import re
from pathlib import Path

CURVES_DIR = Path(__file__).parent / "data" / "price_curves"

BUSHELS_PER_TONNE = {"corn": 39.368, "soybean": 36.744, "wheat": 36.744}
_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def cents_per_bushel_to_usd_per_tonne(crop: str, cents: float) -> float:
    if crop not in BUSHELS_PER_TONNE:
        raise ValueError(f"Unknown crop '{crop}'. Available: {sorted(BUSHELS_PER_TONNE)}")
    return (cents / 100.0) * BUSHELS_PER_TONNE[crop]


def available_curves() -> list[str]:
    """Snapshot names in dora/data/price_curves/."""
    if not CURVES_DIR.is_dir():
        return []
    return sorted(p.stem for p in CURVES_DIR.glob("*.json"))


def load_curve(path: str | Path) -> dict:
    """Read a snapshot file and return the normalized curve in USD/t."""
    p = Path(path)
    if not p.is_file():
        candidates = [
            CURVES_DIR / p.name,
            CURVES_DIR / f"{p.name}.json",
        ]
        for c in candidates:
            if c.is_file():
                p = c
                break
        else:
            avail = available_curves()
            raise FileNotFoundError(f"Snapshot '{path}' not found. Available: {', '.join(avail)}")

    data = json.loads(p.read_text(encoding="utf-8"))
    unit = data.get("unit", "").lower()
    raw_curve = data.get("curve", {})

    converted_curve: dict[str, dict[str, float]] = {}
    for crop, months in raw_curve.items():
        converted_curve[crop] = {}
        for month, price in months.items():
            if not isinstance(month, str) or not _MONTH_RE.match(month):
                raise ValueError(f"Month '{month}' is not in 'YYYY-MM' format in {p.name}")
            if isinstance(price, bool) or not isinstance(price, (int, float)) or price <= 0:
                raise ValueError(f"Price for '{crop}' in '{month}' must be > 0, got {price} in {p.name}")

            if unit == "cents/bu":
                converted_price = cents_per_bushel_to_usd_per_tonne(crop, float(price))
            elif unit in ("usd/t", "usd/tonne"):
                converted_price = float(price)
            else:
                raise ValueError(f"Unknown unit '{data.get('unit')}' in {p.name}")
            converted_curve[crop][month] = converted_price

    res = {
        "curve": converted_curve,
        "source": data.get("source", ""),
        "as_of": data.get("as_of", ""),
    }
    if "placeholder" in data:
        res["placeholder"] = bool(data["placeholder"])
    return res
