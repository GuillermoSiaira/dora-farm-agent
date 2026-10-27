"""A crop season, fortnight by fortnight.

The season starts in early May (fortnight 0) and lasts 30 fortnights (until July
of the next year), so the summer crops have time to be stored and sold.

Costs, yields and prices come from MAGyP's margins report (see
data/magyp_southeast_2026-06.json). The payment and harvest calendar is a
reasonable assumption for Southeast Buenos Aires and can be changed per scenario.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

DATA_SE_BA = Path(__file__).parent / "data" / "magyp_southeast_2026-06.json"
DATA_IOWA = Path(__file__).parent / "data" / "iowa_2026.json"
DATA = DATA_SE_BA
FORTNIGHTS = 30
MONTHS = ["May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr"]

REGIONS = {
    "southeast_buenos_aires": {
        "name": "Southeast Buenos Aires",
        "data_file": DATA_SE_BA,
        "calendar": {
            "wheat":     {"sowing": 3,  "harvest": 15, "fertilizer": {3: 0.5, 8: 0.5},   "crop_protection": {10: 1.0}},
            "corn":      {"sowing": 11, "harvest": 22, "fertilizer": {11: 0.5, 14: 0.5}, "crop_protection": {12: 1.0}},
            "soybean":   {"sowing": 13, "harvest": 23, "fertilizer": {13: 1.0},          "crop_protection": {16: 1.0}},
            "sunflower": {"sowing": 11, "harvest": 19, "fertilizer": {11: 1.0},          "crop_protection": {13: 1.0}},
        },
        "season_start": "2026-05",
        "crops": ("wheat", "corn", "soybean", "sunflower"),
        "basis_file": Path(__file__).parent / "data" / "basis_argentina.json",
    },
    "iowa": {
        "name": "Iowa",
        "data_file": DATA_IOWA,
        "calendar": {
            "corn":      {"sowing": 1, "harvest": 13, "fertilizer": {1: 0.5, 3: 0.5}, "crop_protection": {3: 1.0}},
            "soybean":   {"sowing": 2, "harvest": 12, "fertilizer": {2: 1.0},          "crop_protection": {4: 1.0}},
        },
        "season_start": "2026-04",
        "crops": ("corn", "soybean"),
        "basis_file": Path(__file__).parent / "data" / "basis_iowa.json",
    },
}

CALENDAR = REGIONS["southeast_buenos_aires"]["calendar"]


def normalize_region(r: str | None) -> str:
    if not r:
        return "southeast_buenos_aires"
    clean = r.strip().lower().replace(" ", "_").replace("-", "_")
    if clean in ("southeast_buenos_aires", "argentina", "buenos_aires"):
        return "southeast_buenos_aires"
    if clean == "iowa":
        return "iowa"
    return clean


def fortnight_name(p: int) -> str:
    name = f"{'early' if p % 2 == 0 else 'late'} {MONTHS[(p // 2) % 12]}"
    return name + (" (year 2)" if p >= 24 else "")


def fortnight_month(season_start: str, p: int) -> str:
    """The calendar month ('YYYY-MM') of fortnight p."""
    year = int(season_start[:4])
    month = int(season_start[5:7])
    total_months = (month - 1) + (p // 2)
    y = year + total_months // 12
    m = (total_months % 12) + 1
    return f"{y:04d}-{m:02d}"


class ScenarioError(ValueError):
    pass


def fortnightly_rate(annual: float) -> float:
    return (1 + annual) ** (1 / 24) - 1


@dataclass
class Scenario:
    area_ha: float = 500.0
    crops: tuple[str, ...] = ("wheat", "corn", "soybean", "sunflower")
    max_crop_share: float = 0.5                  # rotation: no crop on more than half the land
    rented_land: bool = False                    # with June-2026 margins, no crop pays the rent
    own_capital_usd: float = 50_000.0
    credit_line_usd: float = 100_000.0
    credit_rate_annual: float = 0.10             # dollar loan
    deposit_rate_annual: float = 0.04            # what idle cash earns
    input_payment_delay_fortnights: int = 0      # the supplier collects inputs k fortnights later
    input_delay_surcharge: float = 0.0           # surcharge for that delay (0.03 = 3%)
    storage_capacity_t: float = 1_000.0
    storage_cost_usd_t_month: float = 2.0
    monthly_price_rise: float = 0.008            # price rises after harvest (assumption)
    prices: dict[str, float] = field(default_factory=dict)   # USD/t at harvest; MAGyP's if missing
    yields: dict[str, float] = field(default_factory=dict)   # t/ha; MAGyP's if missing
    season_start: str = "2026-05"
    price_curve: dict[str, dict[str, float]] = field(default_factory=dict)   # crop -> {"YYYY-MM": USD/t}
    basis_usd_t: dict[str, float] = field(default_factory=dict)              # crop -> USD/t
    price_curve_source: str | None = None
    price_curve_metadata: dict = field(default_factory=dict)
    constraints: list[dict] = field(default_factory=list)                    # farmer constraints
    region: str = "southeast_buenos_aires"

    def __post_init__(self):
        self.region = normalize_region(self.region)
        if self.region not in REGIONS:
            raise ScenarioError(f"Unknown region '{self.region}'. Supported: {', '.join(REGIONS)}")

        reg_info = REGIONS[self.region]
        self.calendar = reg_info["calendar"]

        if self.region == "iowa":
            if self.crops == ("wheat", "corn", "soybean", "sunflower"):
                self.crops = reg_info["crops"]
            if self.season_start == "2026-05":
                self.season_start = reg_info["season_start"]

        data_file = reg_info["data_file"]
        raw_data = json.loads(data_file.read_text(encoding="utf-8"))
        crops_data = raw_data["crops"]
        unknown = set(self.crops) - set(crops_data)
        if unknown:
            raise ValueError(f"No data for crops: {sorted(unknown)}. Available: {sorted(crops_data)}")
        self.data = {c: crops_data[c] for c in self.crops}

        if self.price_curve_source and not self.price_curve:
            if self.price_curve_source in ("cbot_latest", "argentina_latest"):
                try:
                    from .feeds import refresh
                    refresh()
                except Exception:
                    pass
            from .prices import load_curve
            snap = load_curve(self.price_curve_source)
            self.price_curve = snap["curve"]
            self.price_curve_metadata = {
                "source": snap["source"],
                "as_of": snap["as_of"],
                "placeholder": snap.get("placeholder", False),
            }

        if self.price_curve_source == "cbot_latest" and not self.basis_usd_t:
            basis_path = reg_info.get("basis_file")
            if basis_path and basis_path.is_file():
                basis_data = json.loads(basis_path.read_text(encoding="utf-8"))
                self.basis_usd_t = basis_data.get("basis", {})

    # ------------------------------------------------------------------
    def curve_price(self, c: str, p: int) -> float | None:
        curve = self.price_curve.get(c)
        if not curve:
            return None
        sorted_months = sorted(curve.keys())
        if not sorted_months:
            return None
        sy, sm = int(self.season_start[:4]), int(self.season_start[5:7])
        points = []
        for m_str in sorted_months:
            y, m = int(m_str[:4]), int(m_str[5:7])
            offset = (y - sy) * 12 + (m - sm)
            first_p = 2 * offset
            points.append((first_p, float(curve[m_str])))

        if p <= points[0][0]:
            return points[0][1]
        if p >= points[-1][0]:
            return points[-1][1]

        for i in range(len(points) - 1):
            p0, v0 = points[i]
            p1, v1 = points[i + 1]
            if p0 <= p <= p1:
                if p1 == p0:
                    return v0
                return v0 + (p - p0) / (p1 - p0) * (v1 - v0)
        return points[-1][1]

    def price(self, c: str) -> float:
        harvest_p = self.calendar[c]["harvest"] if hasattr(self, "calendar") and c in self.calendar else CALENDAR[c]["harvest"]
        cp = self.curve_price(c, harvest_p)
        if cp is not None:
            return cp + self.basis_usd_t.get(c, 0.0)
        return self.prices.get(c, self.data[c]["price"])

    def crop_yield(self, c: str) -> float:
        return self.yields.get(c, self.data[c]["yield"])

    def net_price(self, c: str, p: int) -> float:
        """USD/t the farmer receives when selling in fortnight p, after marketing costs."""
        marketing_per_t = self.data[c]["marketing_harvest"] / self.data[c]["yield"]
        cp = self.curve_price(c, p)
        if cp is not None:
            return cp + self.basis_usd_t.get(c, 0.0) - marketing_per_t
        harvest_p = self.calendar[c]["harvest"] if hasattr(self, "calendar") and c in self.calendar else CALENDAR[c]["harvest"]
        months = (p - harvest_p) / 2
        return self.price(c) * (1 + self.monthly_price_rise) ** months - marketing_per_t

    def payments_per_ha(self, c: str) -> dict[int, float]:
        """USD per hectare paid in each fortnight (marketing excluded)."""
        d = self.data[c]
        cal = self.calendar[c] if hasattr(self, "calendar") and c in self.calendar else CALENDAR[c]
        payments: dict[int, float] = {}

        def add(p: int, amount: float):
            payments[p] = payments.get(p, 0.0) + amount

        delay = self.input_payment_delay_fortnights
        surcharge = 1 + self.input_delay_surcharge if delay else 1.0
        add(cal["sowing"], d["field_operations"])
        add(min(cal["sowing"] + delay, FORTNIGHTS - 1), d["seed"] * surcharge)
        for item in ("fertilizer", "crop_protection"):
            for p, share in cal[item].items():
                add(min(p + delay, FORTNIGHTS - 1), d[item] * share * surcharge)
        if self.rented_land:
            add(0, d["rent"])                    # rent is paid upfront
            overhead = d["overhead_rented"]
        else:
            overhead = d["overhead_owned"]
        season = range(0, cal["harvest"] + 1)
        for p in season:
            add(p, overhead / len(season))
        return payments
