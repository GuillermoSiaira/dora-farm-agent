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
DATA_NUCLEO = Path(__file__).parent / "data" / "magyp_nucleo_2026-06.json"
DATA_IOWA = Path(__file__).parent / "data" / "iowa_2026.json"
DATA_MATO_GROSSO = Path(__file__).parent / "data" / "mato_grosso_2026.json"
DATA = DATA_SE_BA
FORTNIGHTS = 30
MONTHS = ["May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr"]

REGIONS = {
    "southeast_buenos_aires": {
        "name": "Southeast Buenos Aires (Balcarce)",
        "port": "Quequén",
        "distance_km": 120,
        "default_freight_usd_t": 18.0,
        "freight_source": "CATAC reference freight table for ~120 km to Quequén",
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
        "coords": (-58.25, -37.85),
        "country": "argentina",
    },
    "pampas_core": {
        "name": "Pampas Core (Pergamino)",
        "port": "Up-River Rosario",
        "distance_km": 110,
        "default_freight_usd_t": 16.5,
        "freight_source": "CATAC reference freight table for ~110 km to Rosario Up-River",
        "data_file": DATA_NUCLEO,
        "calendar": {
            "wheat":     {"sowing": 3,  "harvest": 15, "fertilizer": {3: 0.5, 8: 0.5},   "crop_protection": {10: 1.0}},
            "corn":      {"sowing": 10, "harvest": 21, "fertilizer": {10: 0.5, 13: 0.5}, "crop_protection": {11: 1.0}},
            "soybean":   {"sowing": 12, "harvest": 22, "fertilizer": {12: 1.0},          "crop_protection": {15: 1.0}},
            "sunflower": {"sowing": 10, "harvest": 19, "fertilizer": {10: 1.0},          "crop_protection": {12: 1.0}},
        },
        "season_start": "2026-05",
        "crops": ("wheat", "corn", "soybean", "sunflower"),
        "basis_file": Path(__file__).parent / "data" / "basis_argentina.json",
        "coords": (-60.57, -33.89),
        "country": "argentina",
    },
    "iowa": {
        "name": "Iowa (central)",
        "port": "Mississippi River terminals",
        "distance_km": 180,
        "default_freight_usd_t": 12.0,
        "freight_source": "USDA AMS Grain Transportation Report, truck rates ~180 km",
        "data_file": DATA_IOWA,
        "calendar": {
            "corn":      {"sowing": 1, "harvest": 13, "fertilizer": {1: 0.5, 3: 0.5}, "crop_protection": {3: 1.0}},
            "soybean":   {"sowing": 2, "harvest": 12, "fertilizer": {2: 1.0},          "crop_protection": {4: 1.0}},
        },
        "season_start": "2026-04",
        "crops": ("corn", "soybean"),
        "basis_file": Path(__file__).parent / "data" / "basis_iowa.json",
        "coords": (-93.6, 42.0),
        "country": "united_states",
    },
    "mato_grosso": {
        "name": "Mato Grosso (Sorriso)",
        "port": "Santos / Paranaguá",
        "distance_km": 1400,
        "default_freight_usd_t": 75.0,
        "freight_source": "ESALQ-LOG freight indicators for ~1,400 km Sorriso to Santos",
        "data_file": DATA_MATO_GROSSO,
        "calendar": {
            "soybean":   {"sowing": 11, "harvest": 19, "fertilizer": {11: 1.0}, "crop_protection": {13: 1.0}},
            "corn":      {"sowing": 19, "harvest": 27, "fertilizer": {19: 1.0}, "crop_protection": {21: 1.0}},
        },
        "season_start": "2026-05",
        "crops": ("corn", "soybean"),
        "basis_file": Path(__file__).parent / "data" / "basis_iowa.json",
        "coords": (-55.71, -12.54),
        "placeholder": True,
        "country": "brazil",
    },
}

CALENDAR = REGIONS["southeast_buenos_aires"]["calendar"]


def normalize_region(r: str | None) -> str:
    if not r:
        return "southeast_buenos_aires"
    clean = r.strip().lower().replace(" ", "_").replace("-", "_")
    if clean in ("southeast_buenos_aires", "argentina", "buenos_aires", "balcarce"):
        return "southeast_buenos_aires"
    if clean in ("pampas_core", "zona_nucleo", "nucleo", "pergamino"):
        return "pampas_core"
    if clean == "iowa":
        return "iowa"
    if clean in ("mato_grosso", "sorriso", "brazil", "brasil"):
        return "mato_grosso"
    return clean


def load_region_data(reg: str) -> dict:
    """Load and return the JSON data dict for a given region."""
    norm_reg = normalize_region(reg)
    if norm_reg not in REGIONS:
        norm_reg = "southeast_buenos_aires"
    data_file = REGIONS[norm_reg]["data_file"]
    return json.loads(data_file.read_text(encoding="utf-8"))


def load_land_data(reg: str) -> dict:
    """Load and return the JSON land dict for a given region."""
    norm_reg = normalize_region(reg)
    land_file = Path(__file__).parent / "data" / f"land_{norm_reg}.json"
    if land_file.is_file():
        return json.loads(land_file.read_text(encoding="utf-8"))
    return {}


def load_taxes_data(country_or_region: str) -> dict:
    """Load and return the JSON taxes dict for a given country or region."""
    norm = normalize_region(country_or_region)
    if norm in REGIONS:
        country = REGIONS[norm].get("country", "argentina")
    else:
        country = country_or_region.lower().strip().replace(" ", "_")
        if country in ("argentina", "ar"):
            country = "argentina"
        elif country in ("united_states", "us", "usa", "eeuu", "iowa"):
            country = "united_states"
        elif country in ("brazil", "brasil", "br", "mato_grosso"):
            country = "brazil"
        else:
            country = "argentina"

    tax_file = Path(__file__).parent / "data" / f"taxes_{country}.json"
    if tax_file.is_file():
        return json.loads(tax_file.read_text(encoding="utf-8"))
    return {}


def load_livestock_data(reg: str) -> dict:
    """Load and return the JSON livestock dict for a given region."""
    norm_reg = normalize_region(reg)
    ls_file = Path(__file__).parent / "data" / f"livestock_{norm_reg}.json"
    if ls_file.is_file():
        return json.loads(ls_file.read_text(encoding="utf-8"))
    return {}



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
    freight_usd_t: float = 0.0                                               # cost of trucking 1 t to selling point / port
    costs_override: dict[str, dict[str, float]] = field(default_factory=dict) # crop -> {item: USD/ha}
    owned_ha: float | None = None                                            # owned land (ha); defaults to area_ha
    max_rent_in_ha: float = 0.0                                               # land that can be rented in (ha)
    allow_rent_out: bool = True                                              # owned land can be rented out at regional rent
    max_buy_ha: float = 0.0                                                  # land that can be bought (ha)
    land_price_usd_ha: float = 0.0                                           # regional market price (USD/ha)
    land_appreciation_annual: float = 0.0                                    # annual land appreciation (e.g. 0.02 = 2%)
    land_tax_usd_ha_year: float = 0.0                                        # property tax (USD/ha/year)
    regional_rent_usd_ha: float = 0.0                                        # regional cash rent (USD/ha)
    gross_receipts_rate: float = 0.0                                         # gross receipts tax on sales (e.g. 0.01 = 1%)
    transaction_tax_rate: float = 0.0                                        # tax per cash movement, sales and payments (Argentina: 0.006)
    income_tax_rate: float = 0.0                                             # flat income tax on profit at end (e.g. 0.35 = 35%)
    export_fx_regime: str = "official"                                       # export exchange-rate regime ("official", etc.)
    livestock: list[str] = field(default_factory=list)                       # livestock activities allowed
    livestock_only_ha: float = 0.0                                           # cattle-only land / lowlands (ha)
    herd_end_value: float | None = None                                      # end-of-season herd valuation (USD/ha)
    max_livestock_share: float | None = None                                 # max share of shared land for livestock
    livestock_data: dict = field(default_factory=dict)                       # loaded livestock activity parameters

    # Land fields are resolved on read, never written back, so dataclasses.replace(sc, area_ha=...) stays exact.
    @property
    def owned(self) -> float:
        """Owned hectares: owned_ha if given, else area_ha (0 when the land is rented)."""
        if self.owned_ha is not None:
            return self.owned_ha
        return 0.0 if self.rented_land else self.area_ha

    @property
    def rent_in_cap(self) -> float:
        """Hectares that can be rented in: max_rent_in_ha, or all of area_ha when the land is rented."""
        if self.max_rent_in_ha > 0 or self.owned_ha is not None or not self.rented_land:
            return self.max_rent_in_ha
        return self.area_ha

    def __post_init__(self):
        self.region = normalize_region(self.region)
        if self.region not in REGIONS:
            raise ScenarioError(f"Unknown region '{self.region}'. Supported: {', '.join(REGIONS)}")

        reg_info = REGIONS[self.region]
        self.calendar = reg_info["calendar"]

        if self.region in ("iowa", "mato_grosso"):
            if self.crops == ("wheat", "corn", "soybean", "sunflower"):
                self.crops = reg_info["crops"]
            if self.season_start == "2026-05" and "season_start" in reg_info:
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

        if self.livestock_only_ha < 0:
            raise ScenarioError("livestock_only_ha must be non-negative.")
        if self.max_livestock_share is not None and not (0 <= self.max_livestock_share <= 1):
            raise ScenarioError("max_livestock_share must be between 0 and 1.")

        if self.livestock:
            raw_ls = load_livestock_data(self.region)
            if not raw_ls or "activities" not in raw_ls:
                raise ScenarioError(f"Livestock activities are not supported for region '{self.region}'.")
            avail = raw_ls["activities"]
            unknown_ls = set(self.livestock) - set(avail)
            if unknown_ls:
                raise ScenarioError(f"Unknown livestock activities: {sorted(unknown_ls)}. Available: {sorted(avail)}")
            self.livestock_data = {a: avail[a] for a in self.livestock}
        elif self.livestock_only_ha > 0:
            raw_ls = load_livestock_data(self.region)
            if raw_ls and "activities" in raw_ls:
                self.livestock_data = raw_ls["activities"]

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
        """USD/t the farmer receives when selling in fortnight p, after marketing costs, freight, and sales taxes."""
        marketing_per_t = self.data[c]["marketing_harvest"] / self.data[c]["yield"]
        cp = self.curve_price(c, p)
        if cp is not None:
            gross_p = cp + self.basis_usd_t.get(c, 0.0)
        else:
            harvest_p = self.calendar[c]["harvest"] if hasattr(self, "calendar") and c in self.calendar else CALENDAR[c]["harvest"]
            months = (p - harvest_p) / 2
            gross_p = self.price(c) * (1 + self.monthly_price_rise) ** months

        gross_receipts_tax = self.gross_receipts_rate * gross_p
        transaction_tax = self.transaction_tax_rate * gross_p

        return gross_p - self.freight_usd_t - marketing_per_t - gross_receipts_tax - transaction_tax

    def payments_per_ha(self, c: str) -> dict[int, float]:
        """USD per hectare paid in each fortnight (marketing excluded)."""
        d = self.data[c]
        cal = self.calendar[c] if hasattr(self, "calendar") and c in self.calendar else CALENDAR[c]
        payments: dict[int, float] = {}

        def add(p: int, amount: float):
            payments[p] = payments.get(p, 0.0) + amount

        crop_overrides = self.costs_override.get(c, {}) if hasattr(self, "costs_override") and self.costs_override else {}

        def get_cost(item: str) -> float:
            return crop_overrides.get(item, d[item])

        delay = self.input_payment_delay_fortnights
        surcharge = 1 + self.input_delay_surcharge if delay else 1.0
        add(cal["sowing"], get_cost("field_operations"))
        add(min(cal["sowing"] + delay, FORTNIGHTS - 1), get_cost("seed") * surcharge)
        for item in ("fertilizer", "crop_protection"):
            for p, share in cal[item].items():
                add(min(p + delay, FORTNIGHTS - 1), get_cost(item) * share * surcharge)
        if self.rented_land:
            add(0, d["rent"])                    # rent is paid upfront
            overhead = get_cost("overhead_rented")
        else:
            overhead = get_cost("overhead_owned")
        season = range(0, cal["harvest"] + 1)
        for p in season:
            add(p, overhead / len(season))

        if self.transaction_tax_rate > 0:
            for p in payments:
                payments[p] *= (1 + self.transaction_tax_rate)

        return payments

    def livestock_payments_per_ha(self, a: str) -> dict[int, float]:
        """USD per hectare paid in each fortnight for livestock activity a."""
        act = self.livestock_data.get(a, {})
        raw_payments = act.get("payments", {})
        tx = (1 + self.transaction_tax_rate) if self.transaction_tax_rate > 0 else 1.0
        return {int(p): float(amt) * tx for p, amt in raw_payments.items()}

    def livestock_net_income(self, a: str) -> tuple[int, float]:
        """(sale_fortnight, net_income_usd_ha) for livestock activity a after sales taxes."""
        act = self.livestock_data.get(a, {})
        sale_p = int(act.get("sale_fortnight", 22))
        gross_inc = float(act.get("income_usd_ha", 0.0))
        tx_tax = self.transaction_tax_rate * gross_inc if self.transaction_tax_rate > 0 else 0.0
        gr_tax = self.gross_receipts_rate * gross_inc if self.gross_receipts_rate > 0 else 0.0
        net_inc = gross_inc - tx_tax - gr_tax
        return sale_p, net_inc

    def livestock_herd_purchase_price(self, a: str) -> float:
        """Purchase price per ha at fortnight 0 for herd purchase activities."""
        act = self.livestock_data.get(a, {})
        return float(act.get("herd_purchase_price_usd_ha", 0.0))

    def livestock_herd_end_value(self, a: str) -> float:
        """End of season valuation per ha for herd purchase activities."""
        if a == "cow_calf_herd_purchase":
            if self.herd_end_value is not None:
                return float(self.herd_end_value)
            act = self.livestock_data.get(a, {})
            return float(act.get("default_herd_end_value", 500.0))
        return 0.0

