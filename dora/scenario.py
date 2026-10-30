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
MONTHS_ES = ["may", "jun", "jul", "ago", "sep", "oct", "nov", "dic", "ene", "feb", "mar", "abr"]

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
        "basis_file": Path(__file__).parent / "data" / "basis_mato_grosso.json",
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


def load_storage_data(reg: str) -> dict:
    """Load and return the JSON storage options dict for a given region (SPEC-20)."""
    norm_reg = normalize_region(reg)
    st_file = Path(__file__).parent / "data" / f"storage_{norm_reg}.json"
    if st_file.is_file():
        return json.loads(st_file.read_text(encoding="utf-8"))
    return {}


def load_sowing_data(reg: str) -> list[dict]:
    """Load and return the JSON sowing windows list for a given region (SPEC-25)."""
    norm_reg = normalize_region(reg)
    sw_file = Path(__file__).parent / "data" / f"sowing_{norm_reg}.json"
    if sw_file.is_file():
        try:
            return json.loads(sw_file.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def load_climate_yields_data(reg: str) -> dict:
    """Load and return the JSON climate yields scenarios dict for a given region (SPEC-25)."""
    norm_reg = normalize_region(reg)
    cy_file = Path(__file__).parent / "data" / f"climate_yields_{norm_reg}.json"
    if cy_file.is_file():
        try:
            return json.loads(cy_file.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _interpolate_monthly(monthly: dict[str, float], season_start: str, p: int) -> float | None:
    """Linearly interpolate a {'YYYY-MM': value} dict across fortnights, flat at the ends."""
    if not monthly:
        return None
    sorted_months = sorted(monthly.keys())
    if not sorted_months:
        return None
    sy, sm = int(season_start[:4]), int(season_start[5:7])
    points = []
    for m_str in sorted_months:
        y, m = int(m_str[:4]), int(m_str[5:7])
        offset = (y - sy) * 12 + (m - sm)
        points.append((2 * offset, float(monthly[m_str])))
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



def fortnight_name(p: int, lang: str = "en") -> str:
    clean_lang = str(lang).lower().strip() if lang else "en"
    if clean_lang == "es":
        month = MONTHS_ES[(p // 2) % 12]
        part = "1ª" if p % 2 == 0 else "2ª"
        suffix = " (año 2)" if p >= 24 else ""
        return f"{part} quincena de {month}{suffix}"
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


def load_routes_data(region: str) -> dict:
    """Load route definitions from dora/data/routes_<region>.json."""
    reg = normalize_region(region)
    path = Path(__file__).parent / "data" / f"routes_{reg}.json"
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


SEA_MODES = ("port", "ocean")   # legs after the port; the rest (truck, rail, barge) are inland


def route_legs_cost(route: dict, p: int, season_start: str = "2026-05", modes: tuple[str, ...] | None = None) -> float:
    """Total cost of the legs of route in fortnight p (USD/t), accounting for seasonality.

    With `modes`, only legs of those modes are counted."""
    cal_m = fortnight_month(season_start, p)
    m_int = int(cal_m.split("-")[1])
    month_names_en = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
    month_names_es = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
    m_en = month_names_en[m_int - 1]
    m_es = month_names_es[m_int - 1]

    tot = 0.0
    for leg in route.get("legs", []):
        if modes is not None and leg.get("mode", "truck") not in modes:
            continue
        base_cost = float(leg.get("usd_t", 0.0))
        by_m = leg.get("usd_t_by_month", {})
        if by_m:
            if cal_m in by_m:
                tot += float(by_m[cal_m])
            elif m_en in by_m:
                tot += float(by_m[m_en])
            elif m_es in by_m:
                tot += float(by_m[m_es])
            elif str(m_int) in by_m:
                tot += float(by_m[str(m_int)])
            else:
                tot += base_cost
        else:
            tot += base_cost
    return tot



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
    basis_usd_t: dict[str, float | dict[str, float]] = field(default_factory=dict)  # crop -> USD/t or {"YYYY-MM": USD/t}
    basis_by_month: dict[str, dict[str, float]] = field(default_factory=dict)       # regional monthly basis (SPEC-20)
    basis_metadata: dict = field(default_factory=dict)                              # source/as_of/placeholder of regional basis
    _auto_basis: dict[str, float] = field(default_factory=dict, repr=False)         # auto-loaded flat basis marker
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
    routes: list[dict] = field(default_factory=list)                          # freight routes to buyer (SPEC-14)
    destination_price_usd_t: dict[str, float] = field(default_factory=dict)   # CFR destination landed price quote (USD/t)
    final_debt_allowed: bool = False                                          # after damage: debt may stay open at the end (SPEC-18)
    payment_options: list[dict] = field(default_factory=list)                 # supplier terms the engine may choose (SPEC-19)
    storage_options: list[dict] = field(default_factory=list)                 # ways to store grain (SPEC-20)
    sowing_windows: dict | list | None = None                                 # sowing windows overrides per crop (SPEC-25)
    sowing_capacity_ha_per_fortnight: float | None = None                     # machinery planter capacity limit per fortnight (SPEC-25)
    harvest_capacity_ha_per_fortnight: float | None = None                    # machinery combine capacity limit per fortnight (SPEC-25)
    climate_scenarios: list[dict] = field(default_factory=list)               # climate scenarios for stochastic engine (SPEC-25)
    double_crop_slack_ha: dict[str, float] | float | None = None              # RHS offset for after constraint perturbation test (SPEC-25 amendment)
    carryover: dict | None = None                                             # carryover stock past season end (SPEC-26)

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

        # Where the reference price is quoted (SPEC-17). "port": the farmer pays freight to it, and the
        # source's marketing cost already includes that freight, so it is taken out of marketing and
        # carried by the route instead. "local_elevator": the basis already discounts the trip onward.
        self.price_point = raw_data.get("price_point", "port")
        self.freight_in_marketing_usd_t = float(raw_data.get("freight_in_marketing_usd_t", 0.0))
        self.freight_in_marketing_source = raw_data.get("freight_in_marketing_source", "")

        # Rent is paid only through the rent_in variable (SPEC-17). A rented farm with no rent given
        # takes the region's verified rent, else the source's (the highest across crops: a full year).
        if self.rented_land and self.regional_rent_usd_ha <= 0:
            land = load_land_data(self.region)
            if land.get("regional_rent_usd_ha") and not land.get("placeholder", False):
                self.regional_rent_usd_ha = float(land["regional_rent_usd_ha"])
            elif any("rent" in d for d in self.data.values()):
                self.regional_rent_usd_ha = max(float(d.get("rent", 0.0)) for d in self.data.values())
            elif land.get("regional_rent_usd_ha"):
                self.regional_rent_usd_ha = float(land["regional_rent_usd_ha"])

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

        is_cbot_source = bool(
            self.price_curve_source and Path(self.price_curve_source).stem.startswith("cbot_")
        )
        if is_cbot_source and not self.basis_usd_t and not self.basis_by_month:
            basis_path = reg_info.get("basis_file")
            if basis_path and basis_path.is_file():
                basis_data = json.loads(basis_path.read_text(encoding="utf-8"))
                self.basis_usd_t = dict(basis_data.get("basis", {}))
                self._auto_basis = dict(self.basis_usd_t)
                self.basis_by_month = dict(basis_data.get("basis_by_month", {}))
                self.basis_metadata = {
                    "source": basis_data.get("source", ""),
                    "as_of": basis_data.get("as_of", ""),
                    "placeholder": basis_data.get("placeholder", False),
                }

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

        if not self.routes:
            # The farmer's freight if given; else, for a port price, the freight inside the source's
            # marketing cost, now shown as its own leg.
            if self.freight_usd_t > 0:
                default_freight, freight_source = float(self.freight_usd_t), "farmer"
            elif self.price_point == "port":
                default_freight, freight_source = self.freight_in_marketing_usd_t, self.freight_in_marketing_source
            else:
                default_freight, freight_source = 0.0, "included in the local basis"
            to = REGIONS.get(self.region, {}).get("port", "terminal") if self.price_point == "port" else "local elevator"
            self.routes = [
                {
                    "id": "default",
                    "name": f"Direct freight ({default_freight:.1f} USD/t)",
                    "capacity_t": None,
                    "legs": [
                        {
                            "mode": "truck",
                            "from": "farm",
                            "to": to,
                            "usd_t": default_freight,
                            "source": freight_source,
                        }
                    ],
                }
            ]


    # ------------------------------------------------------------------
    def curve_price(self, c: str, p: int) -> float | None:
        curve = self.price_curve.get(c)
        if not curve:
            return None
        return _interpolate_monthly(curve, self.season_start, p)

    def basis_at(self, c: str, p: int) -> float:
        """Basis (USD/t) for crop c in fortnight p: scalar, monthly dict, or regional basis_by_month."""
        if c in self.basis_usd_t:
            val = self.basis_usd_t[c]
            if isinstance(val, dict):
                interp = _interpolate_monthly(val, self.season_start, p)
                return 0.0 if interp is None else interp
            if c in self.basis_by_month and self.basis_by_month[c] and self._auto_basis.get(c) == val:
                interp = _interpolate_monthly(self.basis_by_month[c], self.season_start, p)
                return float(val) if interp is None else interp
            return float(val)
        if c in self.basis_by_month and self.basis_by_month[c]:
            interp = _interpolate_monthly(self.basis_by_month[c], self.season_start, p)
            return 0.0 if interp is None else interp
        return 0.0

    def price(self, c: str) -> float:
        harvest_p = self.calendar[c]["harvest"] if hasattr(self, "calendar") and c in self.calendar else CALENDAR[c]["harvest"]
        cp = self.curve_price(c, harvest_p)
        if cp is not None:
            return cp + self.basis_at(c, harvest_p)
        return self.prices.get(c, self.data[c]["price"])

    def crop_yield(self, c: str) -> float:
        return self.yields.get(c, self.data[c]["yield"])

    def route_cost(self, r: dict, p: int) -> float:
        """Total cost of all legs for route r in fortnight p (USD/t)."""
        return route_legs_cost(r, p, self.season_start)

    def destination_price(self, c: str, p: int, r: dict | None = None) -> float:
        """Destination landed price (e.g. CFR China or port price + ocean/port legs)."""
        if self.destination_price_usd_t and c in self.destination_price_usd_t:
            return float(self.destination_price_usd_t[c])

        cp = self.curve_price(c, p)
        if cp is not None:
            gross_p = cp + self.basis_at(c, p)
        else:
            harvest_p = self.calendar[c]["harvest"] if hasattr(self, "calendar") and c in self.calendar else CALENDAR[c]["harvest"]
            months = (p - harvest_p) / 2
            gross_p = self.price(c) * (1 + self.monthly_price_rise) ** months

        ref_r = self.routes[0] if (hasattr(self, "routes") and self.routes) else r
        if ref_r is not None and "legs" in ref_r:
            ocean_port = sum(float(leg.get("usd_t", 0.0)) for leg in ref_r.get("legs", []) if leg.get("mode") in SEA_MODES)
            # A local price already discounts the inland trip of the reference route: add it back so
            # that route nets the local price and other routes differ by their own freight.
            inland_ref = self.inland_cost(ref_r, p) if self.price_point != "port" else 0.0
            return gross_p + inland_ref + ocean_port
        return gross_p

    def inland_cost(self, r: dict, p: int) -> float:
        """Cost of the inland legs (truck, rail, barge) of route r in fortnight p (USD/t)."""
        modes = tuple({leg.get("mode", "truck") for leg in r.get("legs", [])} - set(SEA_MODES))
        return route_legs_cost(r, p, self.season_start, modes=modes)

    def marketing_per_t(self, c: str) -> float:
        """Marketing and harvest costs per tonne, without the freight the route already carries."""
        marketing = self.data[c]["marketing_harvest"] / self.data[c]["yield"]
        if self.price_point == "port":
            marketing -= self.freight_in_marketing_usd_t
        return marketing

    def farm_gate_price(self, c: str, p: int, r: dict) -> float:
        """Farm-gate price = destination price - Σ legs - sales taxes."""
        dest_p = self.destination_price(c, p, r)
        tot_legs = self.route_cost(r, p)
        cp = self.curve_price(c, p)
        if cp is not None:
            gross_p = cp + self.basis_at(c, p)
        else:
            harvest_p = self.calendar[c]["harvest"] if hasattr(self, "calendar") and c in self.calendar else CALENDAR[c]["harvest"]
            months = (p - harvest_p) / 2
            gross_p = self.price(c) * (1 + self.monthly_price_rise) ** months
        gross_receipts_tax = self.gross_receipts_rate * gross_p
        transaction_tax = self.transaction_tax_rate * gross_p
        return dest_p - tot_legs - gross_receipts_tax - transaction_tax

    def farm_gate_decomposition(self, c: str, p: int | None = None, r: dict | None = None) -> dict:
        """Farm-gate price decomposition: destination price - legs - taxes = farm-gate price."""
        if p is None:
            p = self.calendar[c]["harvest"] if hasattr(self, "calendar") and c in self.calendar else CALENDAR[c]["harvest"]
        if r is None:
            r = self.routes[0] if (hasattr(self, "routes") and self.routes) else {}

        dest_p = self.destination_price(c, p, r)
        legs_detail = []
        for leg in r.get("legs", []):
            cost = float(leg.get("usd_t", 0.0))
            if "usd_t_by_month" in leg and p is not None:
                cal_m = fortnight_month(self.season_start, p)
                m_int = int(cal_m.split("-")[1])
                month_names_en = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
                month_names_es = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
                m_en = month_names_en[m_int - 1]
                m_es = month_names_es[m_int - 1]
                by_m = leg["usd_t_by_month"]
                if cal_m in by_m:
                    cost = float(by_m[cal_m])
                elif m_en in by_m:
                    cost = float(by_m[m_en])
                elif m_es in by_m:
                    cost = float(by_m[m_es])
                elif str(m_int) in by_m:
                    cost = float(by_m[str(m_int)])
            legs_detail.append({
                "mode": leg.get("mode", "truck"),
                "from": leg.get("from", ""),
                "to": leg.get("to", ""),
                "usd_t": round(cost, 2),
            })
        tot_legs = sum(l["usd_t"] for l in legs_detail)

        cp = self.curve_price(c, p)
        if cp is not None:
            gross_p = cp + self.basis_at(c, p)
        else:
            harvest_p = self.calendar[c]["harvest"] if hasattr(self, "calendar") and c in self.calendar else CALENDAR[c]["harvest"]
            months = (p - harvest_p) / 2
            gross_p = self.price(c) * (1 + self.monthly_price_rise) ** months

        gross_receipts_tax = round(self.gross_receipts_rate * gross_p, 2)
        transaction_tax = round(self.transaction_tax_rate * gross_p, 2)
        total_taxes = round(gross_receipts_tax + transaction_tax, 2)
        farm_gate_p = round(dest_p - tot_legs - total_taxes, 2)
        marketing = round(self.marketing_per_t(c), 2)
        net_p = round(farm_gate_p - marketing, 2)

        return {
            "crop": c,
            "route_id": r.get("id"),
            "route_name": r.get("name"),
            "price_point": self.price_point,
            "destination_price_usd_t": round(dest_p, 2),
            "legs": legs_detail,
            "total_legs_usd_t": round(tot_legs, 2),
            "inland_freight_usd_t": round(self.inland_cost(r, p), 2),
            "taxes_usd_t": total_taxes,
            "gross_receipts_tax_usd_t": gross_receipts_tax,
            "transaction_tax_usd_t": transaction_tax,
            "farm_gate_price_usd_t": farm_gate_p,
            "marketing_usd_t": marketing,
            "freight_taken_out_of_marketing_usd_t": round(self.freight_in_marketing_usd_t, 2) if self.price_point == "port" else 0.0,
            "net_price_usd_t": net_p,
        }

    def net_price_route(self, c: str, p: int, r: dict) -> float:
        """USD/t the farmer receives selling in fortnight p via route r, after freight, taxes and marketing."""
        return self.farm_gate_price(c, p, r) - self.marketing_per_t(c)

    def net_price(self, c: str, p: int) -> float:
        """USD/t the farmer receives when selling in fortnight p by the first route (the default one if none given)."""
        return self.net_price_route(c, p, self.routes[0])


    def _cost(self, c: str, item: str) -> float:
        overrides = self.costs_override.get(c, {}) if self.costs_override else {}
        return overrides.get(item, self.data[c][item])

    def _calendar(self, c: str) -> dict:
        return self.calendar[c] if hasattr(self, "calendar") and c in self.calendar else CALENDAR[c]

    def resolved_sowing_windows(self) -> dict[str, list[dict]]:
        """Resolve active sowing windows per crop (SPEC-25).
        
        Returns {crop: [window_dict, ...]}. If sowing_windows was not specified, returns
        a single default window per crop corresponding to the region's standard calendar,
        guaranteeing exact numerical equivalence with main.
        """
        reg_sowing = load_sowing_data(self.region)
        reg_by_crop: dict[str, list[dict]] = {}
        for item in reg_sowing:
            if isinstance(item, dict) and "crop" in item:
                reg_by_crop[item["crop"]] = list(item.get("windows", []))

        user_spec = self.sowing_windows
        user_by_crop: dict[str, list[Any]] = {}
        if isinstance(user_spec, list):
            for item in user_spec:
                if isinstance(item, dict) and "crop" in item:
                    user_by_crop[item["crop"]] = list(item.get("windows", []))
        elif isinstance(user_spec, dict):
            user_by_crop = dict(user_spec)

        out: dict[str, list[dict]] = {}
        for c in self.crops:
            cal = self._calendar(c)
            std_yield = self.crop_yield(c)
            default_win = {
                "id": "default",
                "name": f"{c} default",
                "sowing": int(cal["sowing"]),
                "harvest": int(cal["harvest"]),
                "fertilizer": {int(p): float(s) for p, s in cal.get("fertilizer", {}).items()},
                "crop_protection": {int(p): float(s) for p, s in cal.get("crop_protection", {}).items()},
                "yield_factor": 1.0,
                "yield_t_ha": float(std_yield),
                "source": "calendar default",
                "placeholder": False,
            }

            if not user_by_crop or c not in user_by_crop or not user_by_crop[c]:
                out[c] = [default_win]
                continue

            crop_windows: list[dict] = []
            reg_windows = {w["id"]: w for w in reg_by_crop.get(c, []) if isinstance(w, dict) and "id" in w}

            for uw in user_by_crop[c]:
                if isinstance(uw, str):
                    uw_dict = {"id": uw}
                elif isinstance(uw, dict):
                    uw_dict = dict(uw)
                else:
                    continue

                wid = str(uw_dict.get("id", "default"))
                base_w = reg_windows.get(wid, default_win)
                merged = dict(base_w)
                merged.update(uw_dict)
                merged["id"] = wid

                merged["sowing"] = int(merged.get("sowing", cal["sowing"]))
                merged["harvest"] = int(merged.get("harvest", cal["harvest"]))
                if merged.get("after"):
                    merged["after"] = str(merged["after"])

                fert = merged.get("fertilizer")
                if isinstance(fert, dict):
                    merged["fertilizer"] = {int(k): float(v) for k, v in fert.items()}
                else:
                    merged["fertilizer"] = {int(k): float(v) for k, v in cal.get("fertilizer", {}).items()}

                cp = merged.get("crop_protection")
                if isinstance(cp, dict):
                    merged["crop_protection"] = {int(k): float(v) for k, v in cp.items()}
                else:
                    merged["crop_protection"] = {int(k): float(v) for k, v in cal.get("crop_protection", {}).items()}

                if "yield_t_ha" in merged and merged["yield_t_ha"] is not None:
                    merged["yield_t_ha"] = float(merged["yield_t_ha"])
                    if "placeholder" not in uw_dict:
                        merged["placeholder"] = False
                elif merged.get("yield_factor") is not None:
                    yf = float(merged["yield_factor"])
                    merged["yield_t_ha"] = std_yield * yf
                else:
                    merged["yield_t_ha"] = std_yield

                crop_windows.append(merged)

            out[c] = crop_windows if crop_windows else [default_win]

        return out

    def fixed_payments_per_ha_window(self, c: str, w: dict) -> dict[int, float]:
        """USD per hectare paid on fixed dates for window w: field operations at sowing, overhead spread until harvest."""
        cal = self._calendar(c)
        sowing = int(w.get("sowing", cal["sowing"]))
        harvest = int(w.get("harvest", cal["harvest"]))
        payments: dict[int, float] = {sowing: self._cost(c, "field_operations")}
        overhead = self._cost(c, "overhead_rented" if self.rented_land else "overhead_owned")
        season = range(0, harvest + 1)
        for p in season:
            payments[p] = payments.get(p, 0.0) + overhead / len(season)
        tx = 1 + self.transaction_tax_rate if self.transaction_tax_rate > 0 else 1.0
        return {p: v * tx for p, v in payments.items()}

    def input_payments_per_ha_window(self, c: str, w: dict, delay: int, surcharge: float, installments: int = 1,
                                     every: int = 2) -> dict[int, float]:
        """USD per hectare paid for seed, fertilizer and crop protection under one supplier term for window w."""
        cal = self._calendar(c)
        sowing = int(w.get("sowing", cal["sowing"]))
        purchases = [(sowing, self._cost(c, "seed"))]
        fert = w.get("fertilizer") if w.get("fertilizer") is not None else cal.get("fertilizer", {})
        cp = w.get("crop_protection") if w.get("crop_protection") is not None else cal.get("crop_protection", {})
        for p_str, share in fert.items():
            purchases.append((int(p_str), self._cost(c, "fertilizer") * float(share)))
        for p_str, share in cp.items():
            purchases.append((int(p_str), self._cost(c, "crop_protection") * float(share)))
        tx = 1 + self.transaction_tax_rate if self.transaction_tax_rate > 0 else 1.0
        payments: dict[int, float] = {}
        for p0, amount in purchases:
            part = amount * (1 + surcharge) * tx / installments
            for k in range(installments):
                p = min(p0 + delay + k * every, FORTNIGHTS - 1)
                payments[p] = payments.get(p, 0.0) + part
        return payments

    def fixed_payments_per_ha(self, c: str) -> dict[int, float]:
        cal = self._calendar(c)
        return self.fixed_payments_per_ha_window(c, cal)

    def input_payments_per_ha(self, c: str, delay: int, surcharge: float, installments: int = 1,
                              every: int = 2) -> dict[int, float]:
        cal = self._calendar(c)
        return self.input_payments_per_ha_window(c, cal, delay, surcharge, installments, every)

    def payment_terms(self) -> list[dict]:
        """The supplier terms available: the base term (the farmer's, or cash) and the payment options."""
        base_delay = self.input_payment_delay_fortnights
        terms = [{"id": "base", "delay_fortnights": base_delay,
                  "surcharge": self.input_delay_surcharge if base_delay else 0.0,
                  "installments": 1, "every_fortnights": 2}]
        for o in self.payment_options:
            terms.append({"id": str(o["id"]), "delay_fortnights": int(o.get("delay_fortnights", 0)),
                          "surcharge": float(o.get("surcharge", 0.0)), "installments": int(o.get("installments", 1)),
                          "every_fortnights": int(o.get("every_fortnights", 2))})
        return terms

    def storage_options_with_origins(self) -> list[dict]:
        """Resolve storage options, filling omitted fields from regional data and tracking origins."""
        if not self.storage_options:
            return [{
                "id": "own_silo",
                "kind": "own_silo",
                "capacity_t": float(self.storage_capacity_t) if self.storage_capacity_t is not None else None,
                "fill_cost_usd_t": 0.0,
                "monthly_cost_usd_t": float(self.storage_cost_usd_t_month),
                "shrink_at_entry": 0.0,
                "shrink_monthly": 0.0,
                "max_months": None,
                "placeholder": False,
                "origins": {
                    "capacity_t": "model assumption",
                    "fill_cost_usd_t": "model assumption",
                    "monthly_cost_usd_t": "model assumption",
                    "shrink_at_entry": "model assumption",
                    "shrink_monthly": "model assumption",
                    "max_months": "model assumption",
                },
            }]
        reg_storage = load_storage_data(self.region)
        reg_opts = reg_storage.get("options", {})
        resolved = []
        for opt in self.storage_options:
            kind = str(opt.get("kind") or opt.get("id") or "own_silo")
            opt_id = str(opt.get("id") or kind)
            reg_opt = reg_opts.get(kind, {})
            reg_source = reg_opt.get("source") or reg_storage.get("source") or "regional default"
            reg_as_of = reg_opt.get("as_of") or reg_storage.get("as_of") or ""
            reg_placeholder = bool(reg_opt.get("placeholder", reg_storage.get("placeholder", False)))
            reg_origin = f"{reg_source}, as of {reg_as_of}" if reg_as_of else reg_source
            if reg_placeholder:
                reg_origin += ", placeholder"

            origins = {}
            used_placeholder = False
            if "capacity_t" in opt:
                cap = None if opt["capacity_t"] is None else float(opt["capacity_t"])
                origins["capacity_t"] = "farmer"
            elif reg_opt.get("capacity_t") is not None:
                cap = float(reg_opt["capacity_t"])
                origins["capacity_t"] = reg_origin
                used_placeholder = used_placeholder or reg_placeholder
            elif kind == "own_silo":
                cap = float(self.storage_capacity_t) if self.storage_capacity_t is not None else None
                origins["capacity_t"] = "model assumption"
            else:
                cap = None
                origins["capacity_t"] = reg_origin if reg_opt else "model assumption"

            vals = {}
            for fld, fallback in (
                ("fill_cost_usd_t", 0.0),
                ("monthly_cost_usd_t", 0.0),
                ("shrink_at_entry", 0.0),
                ("shrink_monthly", 0.0),
            ):
                if fld in opt:
                    vals[fld] = float(opt[fld])
                    origins[fld] = "farmer"
                elif fld in reg_opt and reg_opt[fld] is not None:
                    vals[fld] = float(reg_opt[fld])
                    origins[fld] = reg_origin
                    used_placeholder = used_placeholder or reg_placeholder
                else:
                    vals[fld] = fallback
                    origins[fld] = "model assumption"

            if "max_months" in opt:
                max_m = None if opt["max_months"] is None else float(opt["max_months"])
                origins["max_months"] = "farmer"
            elif "max_months" in reg_opt:
                max_m = None if reg_opt["max_months"] is None else float(reg_opt["max_months"])
                origins["max_months"] = reg_origin
                used_placeholder = used_placeholder or reg_placeholder
            else:
                max_m = None
                origins["max_months"] = "model assumption"

            resolved.append({
                "id": opt_id,
                "kind": kind,
                "capacity_t": cap,
                "fill_cost_usd_t": vals["fill_cost_usd_t"],
                "monthly_cost_usd_t": vals["monthly_cost_usd_t"],
                "shrink_at_entry": vals["shrink_at_entry"],
                "shrink_monthly": vals["shrink_monthly"],
                "max_months": max_m,
                "placeholder": used_placeholder,
                "origins": origins,
            })
        return resolved

    def effective_storage_options(self) -> list[dict]:
        """Storage options active in the LP: legacy single own_silo when storage_options is empty."""
        return [
            {k: v for k, v in opt.items() if k not in ("placeholder", "origins")}
            for opt in self.storage_options_with_origins()
        ]

    def payments_per_ha(self, c: str) -> dict[int, float]:
        """USD per hectare paid in each fortnight under the base term (marketing excluded)."""
        base = self.payment_terms()[0]
        payments = dict(self.fixed_payments_per_ha(c))
        for p, v in self.input_payments_per_ha(c, base["delay_fortnights"], base["surcharge"]).items():
            payments[p] = payments.get(p, 0.0) + v
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


    def carryover_k(self, sell_month: str) -> int:
        """Number of months k between the season end (fortnight T-1) and sell_month."""
        end_ym = fortnight_month(self.season_start, FORTNIGHTS - 1)
        ey, em = int(end_ym[:4]), int(end_ym[5:7])
        sy, sm = int(sell_month[:4]), int(sell_month[5:7])
        k = (sy - ey) * 12 + (sm - em)
        if k <= 0:
            raise ScenarioError(
                f"carryover sell_month '{sell_month}' must be after season end '{end_ym}'."
            )
        return k

    def carryover_quote(self, c: str, sell_month: str) -> tuple[float | None, str | None]:
        """(quote_usd_t, source) for crop c in sell_month, without extrapolating curves or monthly_price_rise."""
        if self.carryover and isinstance(self.carryover, dict):
            p_map = self.carryover.get("price_usd_t", {})
            if isinstance(p_map, dict) and c in p_map and p_map[c] is not None:
                src = self.carryover.get("price_source") or "farmer quote"
                return float(p_map[c]), str(src)
        if self.price_curve and c in self.price_curve and isinstance(self.price_curve[c], dict):
            if sell_month in self.price_curve[c]:
                cp = float(self.price_curve[c][sell_month])
                src = self.price_curve_source or self.price_curve_metadata.get("source") or "price_curve"
                return cp, str(src)
        return None, None

    def net_price_quote(self, c: str, p: int, gross_p: float, r: dict | None = None) -> float:
        """Net farm-gate price (USD/t) for a given gross price quote at fortnight p via route r."""
        if r is None:
            r = self.routes[0] if (hasattr(self, "routes") and self.routes) else {}
        ref_r = self.routes[0] if (hasattr(self, "routes") and self.routes) else r
        if self.destination_price_usd_t and c in self.destination_price_usd_t:
            dest_p = float(self.destination_price_usd_t[c])
        elif ref_r and "legs" in ref_r:
            ocean_port = sum(float(leg.get("usd_t", 0.0)) for leg in ref_r.get("legs", []) if leg.get("mode") in SEA_MODES)
            inland_ref = self.inland_cost(ref_r, p) if self.price_point != "port" else 0.0
            dest_p = gross_p + inland_ref + ocean_port
        else:
            dest_p = gross_p
        tot_legs = self.route_cost(r, p)
        gross_receipts_tax = self.gross_receipts_rate * gross_p
        transaction_tax = self.transaction_tax_rate * gross_p
        farm_gate = dest_p - tot_legs - gross_receipts_tax - transaction_tax
        return farm_gate - self.marketing_per_t(c)

    def carryover_value(self, c: str, option_id: str) -> float | None:
        """Terminal value V_{c,m} (USD at end of season per tonne at end of July) for crop c in storage option m.
        
        Returns None if carryover is inactive, crop c has no quote, or storage life is exceeded.
        """
        if not self.carryover or not isinstance(self.carryover, dict):
            return None
        sell_month = self.carryover.get("sell_month")
        if not sell_month:
            return None
        k = self.carryover_k(sell_month)
        quote, source = self.carryover_quote(c, sell_month)
        if quote is None:
            return None

        storage_opts = self.effective_storage_options()
        opt = next((o for o in storage_opts if o["id"] == option_id), None)
        if not opt:
            return None

        max_m = opt.get("max_months")
        win_map = self.resolved_sowing_windows() if hasattr(self, "resolved_sowing_windows") else {}
        if c in win_map and win_map[c]:
            h = min(int(w["harvest"]) for w in win_map[c])
        else:
            cal = self.calendar if hasattr(self, "calendar") else CALENDAR
            h = cal[c]["harvest"]
        held_at_end = (FORTNIGHTS - 1 - h) / 2.0
        if max_m is not None and held_at_end + k > float(max_m) + 1e-9:
            return None

        p_sell = (FORTNIGHTS - 1) + 2 * k
        if self.price_curve and c in self.price_curve and sell_month in self.price_curve[c] and (
            not self.carryover.get("price_usd_t") or c not in self.carryover.get("price_usd_t", {})
        ):
            gross_p = quote + self.basis_at(c, p_sell)
        else:
            gross_p = quote

        first_route = self.routes[0] if (hasattr(self, "routes") and self.routes) else {}
        pi_next = self.net_price_quote(c, p_sell, gross_p, first_route)

        shrink_m = float(opt.get("shrink_monthly", 0.0))
        monthly_m = float(opt.get("monthly_cost_usd_t", 0.0))
        ri = fortnightly_rate(self.deposit_rate_annual)
        disc_f = 1.0 / (1.0 + ri)
        R = (1.0 - shrink_m) ** 0.5

        term1 = pi_next * (R ** (2 * k)) * (disc_f ** (2 * k))
        term2 = sum((monthly_m / 2.0) * (R ** q) * (disc_f ** q) for q in range(1, 2 * k + 1))
        return term1 - term2
