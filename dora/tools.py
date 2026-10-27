"""Tools the agent calls. JSON in, JSON out.

The language model does not calculate or write equations: it fills in the
parameters of a scenario, which are validated here, and reads the results the
engine returns. Every scenario parameter carries its origin: the farmer said it,
it comes from MAGyP's report, or it is a model assumption.
"""
from __future__ import annotations

import json
import re
from dataclasses import fields

from .engine import optimize
from .geo import field_from_map
from .prices import available_curves, load_curve
from .scenario import (
    CALENDAR, FORTNIGHTS, MONTHS, REGIONS, Scenario, ScenarioError,
    fortnight_name, normalize_region, load_taxes_data, load_land_data,
)

SOURCE_MAGYP = "MAGyP margins report, Jun-2026, Southeast Buenos Aires"
SOURCE_IOWA = "Iowa State University Extension (Ag Decision Maker A1-20)"
FROM_FARMER = "farmer"
ASSUMPTION = "model assumption"

_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

# name -> (type, minimum, maximum, unit, description)
PARAMETERS = {
    "area_ha": (float, 1, 100_000, "ha", "Farmland available"),
    "crops": (list, None, None, "", f"Crops that can be sown, from: {', '.join(CALENDAR)}"),
    "max_crop_share": (float, 0.05, 1, "share", "Rotation cap: maximum share of the land under one crop"),
    "rented_land": (bool, None, None, "", "True if the land is rented (MAGyP's rent is added)"),
    "own_capital_usd": (float, 0, 100_000_000, "USD", "Own capital available at the start of the season (May)"),
    "credit_line_usd": (float, 0, 100_000_000, "USD", "Credit line limit"),
    "credit_rate_annual": (float, 0, 1, "annual share", "Rate of the dollar loan (0.10 = 10%)"),
    "deposit_rate_annual": (float, 0, 1, "annual share", "What idle cash earns (0.04 = 4%)"),
    "input_payment_delay_fortnights": (int, 0, 12, "fortnights", "Payment term from the input supplier (90 days = 6)"),
    "input_delay_surcharge": (float, 0, 0.5, "share", "Supplier surcharge for that term (0.03 = 3%)"),
    "storage_capacity_t": (float, 0, 1_000_000, "t", "Own storage capacity (silo or silo bags)"),
    "storage_cost_usd_t_month": (float, 0, 50, "USD/t/month", "Cost of storing one tonne for a month"),
    "monthly_price_rise": (float, -0.05, 0.05, "share per month", "Monthly price change after harvest"),
    "prices": (dict, 1, 2_000, "USD/t", "Harvest price per crop, if the farmer gives it"),
    "yields": (dict, 0.1, 20, "t/ha", "Yield per crop, if the farmer gives it"),
    "price_curve_source": (str, None, None, "", "Snapshot name with the price curve"),
    "basis_usd_t": (dict, -200, 200, "USD/t", "Basis against the curve per crop (local price = curve + basis)"),
    "constraints": (list, None, None, "", "Farmer constraints on the plan (min_area, max_area, min_share, forward_sale)"),
    "region": (str, None, None, "", "Region for farming/prices ('southeast_buenos_aires', 'pampas_core', 'iowa', 'mato_grosso')"),
    "freight_usd_t": (float, 0.0, 500.0, "USD/t", "Cost of trucking one tonne from farm to port or selling point"),
    "costs_override": (dict, None, None, "USD/ha", "Cost overrides in USD/ha per crop and item, e.g. {'corn': {'fertilizer': 210.0}}"),
    "owned_ha": (float, 0, 100_000, "ha", "Owned farmland"),
    "max_rent_in_ha": (float, 0, 100_000, "ha", "Maximum land that can be rented in"),
    "allow_rent_out": (bool, None, None, "", "True if owned land can be rented out at regional rent"),
    "max_buy_ha": (float, 0, 100_000, "ha", "Maximum land that can be bought"),
    "land_price_usd_ha": (float, 0, 200_000, "USD/ha", "Regional market land price per hectare"),
    "land_appreciation_annual": (float, -0.5, 1.0, "annual share", "Expected annual land appreciation (e.g. 0.02 = 2%)"),
    "land_tax_usd_ha_year": (float, 0, 10_000, "USD/ha/year", "Land property tax per hectare per year"),
    "regional_rent_usd_ha": (float, 0, 50_000, "USD/ha", "Regional cash rental rate per hectare"),
    "gross_receipts_rate": (float, 0, 0.5, "share", "Gross receipts / turnover tax rate on sales"),
    "transaction_tax_rate": (float, 0, 0.2, "share", "Tax on bank transactions / debits and credits"),
    "income_tax_rate": (float, 0, 0.9, "share", "Effective flat income tax rate on season profit"),
    "export_fx_regime": (str, None, None, "", "Effective export exchange rate regime ('official', etc.)"),
    "livestock": (list, None, None, "activities", "List of allowed livestock activities ('cow_calf', 'cow_calf_herd_purchase', 'steer_fattening')"),
    "livestock_only_ha": (float, 0, 100_000, "ha", "Land usable only by livestock (lowlands / bajo)"),
    "herd_end_value": (float, 0, 100_000, "USD/ha", "Valuation of purchased breeding herd at season end"),
    "max_livestock_share": (float, 0, 1.0, "share", "Maximum share of shared arable land allocated to livestock"),
}
_ASSUMPTIONS = {f.name for f in fields(Scenario)} - {
    "prices", "yields", "crops", "area_ha", "price_curve", "basis_usd_t",
    "price_curve_source", "price_curve_metadata", "season_start", "constraints", "region", "freight_usd_t", "costs_override",
    "owned_ha", "max_rent_in_ha", "max_buy_ha", "livestock", "livestock_only_ha", "herd_end_value", "max_livestock_share", "livestock_data",
}


SENSITIVITY_PARAMETERS = ("own_capital_usd", "credit_line_usd", "credit_rate_annual", "input_payment_delay_fortnights",
                          "input_delay_surcharge", "storage_capacity_t", "area_ha", "monthly_price_rise")
MAX_SENSITIVITY_VALUES = 10


def _is_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _validate(params: dict) -> tuple[Scenario, list[str]]:
    if not isinstance(params, dict):
        raise ScenarioError("The scenario must be a JSON object of parameters.")
    errors, clean = [], {}
    for name, value in params.items():
        if name not in PARAMETERS:
            errors.append(f"'{name}' is not a parameter. Valid: {', '.join(PARAMETERS)}.")
            continue
        kind, lo, hi, unit, _ = PARAMETERS[name]
        if kind is bool:
            if isinstance(value, bool):
                clean[name] = value
            else:
                errors.append(f"'{name}' must be true or false.")
        elif kind is list:
            if name == "crops":
                if isinstance(value, list) and value and all(c in CALENDAR for c in value):
                    clean[name] = tuple(dict.fromkeys(value))
                else:
                    errors.append(f"'crops' must be a list with items from: {', '.join(CALENDAR)}.")
            elif name == "constraints":
                if not isinstance(value, list):
                    errors.append("'constraints' must be a list.")
                else:
                    clean_constraints = []
                    for idx, c in enumerate(value):
                        if not isinstance(c, dict):
                            errors.append(f"Constraint {idx} must be an object.")
                            continue
                        ctype = c.get("type")
                        if ctype not in ("min_area", "max_area", "min_share", "forward_sale"):
                            errors.append(f"Constraint {idx} has unknown type '{ctype}'. Valid: min_area, max_area, min_share, forward_sale.")
                            continue
                        crop = c.get("crop")
                        if crop not in CALENDAR:
                            errors.append(f"Constraint {idx} ({ctype}) has unknown crop '{crop}'. Valid: {', '.join(CALENDAR)}.")
                            continue
                        if ctype in ("min_area", "max_area"):
                            ha = c.get("ha")
                            if not _is_number(ha) or ha < 0:
                                errors.append(f"Constraint {idx} ({ctype}) 'ha' must be a non-negative number.")
                        elif ctype == "min_share":
                            share = c.get("share")
                            if not _is_number(share) or not (0 < share <= 1):
                                errors.append(f"Constraint {idx} ({ctype}) 'share' must be between 0 and 1.")
                        elif ctype == "forward_sale":
                            month = c.get("month")
                            if not isinstance(month, str) or not _MONTH_RE.match(month):
                                errors.append(f"Constraint {idx} ({ctype}) 'month' must be in 'YYYY-MM' format.")
                            tonnes = c.get("tonnes")
                            if not _is_number(tonnes) or tonnes < 0:
                                errors.append(f"Constraint {idx} ({ctype}) 'tonnes' must be a non-negative number.")
                            price = c.get("price_usd_t")
                            if not _is_number(price) or price <= 0:
                                errors.append(f"Constraint {idx} ({ctype}) 'price_usd_t' must be > 0.")
                        clean_constraints.append(dict(c))
                    clean[name] = clean_constraints
            elif name == "livestock":
                if isinstance(value, list) and all(isinstance(a, str) for a in value):
                    clean[name] = list(dict.fromkeys(value))
                else:
                    errors.append("'livestock' must be a list of activity names.")
        elif kind is dict:
            if name == "costs_override":
                if not isinstance(value, dict):
                    errors.append("'costs_override' must be an object crop -> item -> USD/ha.")
                    continue
                clean_ov = {}
                for c, items_dict in value.items():
                    if c not in CALENDAR:
                        errors.append(f"'costs_override': '{c}' is not a known crop.")
                        continue
                    if not isinstance(items_dict, dict):
                        errors.append(f"'costs_override.{c}' must be an object item -> USD/ha.")
                        continue
                    clean_items = {}
                    for it, cost_val in items_dict.items():
                        if not _is_number(cost_val) or cost_val < 0:
                            errors.append(f"'costs_override.{c}.{it}' must be a non-negative number.")
                        else:
                            clean_items[it] = float(cost_val)
                    clean_ov[c] = clean_items
                clean[name] = clean_ov
            else:
                if not isinstance(value, dict):
                    errors.append(f"'{name}' must be an object crop -> value in {unit}.")
                    continue
                for c, v in value.items():
                    if c not in CALENDAR:
                        errors.append(f"'{name}': '{c}' is not a known crop.")
                    elif not _is_number(v) or not lo <= v <= hi:
                        errors.append(f"'{name}.{c}' must be between {lo} and {hi} {unit}.")
                clean[name] = {c: float(v) for c, v in value.items() if c in CALENDAR and _is_number(v) and lo <= v <= hi}
        elif kind is str:
            if not isinstance(value, str):
                errors.append(f"'{name}' must be a string.")
            elif name == "price_curve_source":
                if value in ("cbot_latest", "argentina_latest"):
                    try:
                        from .feeds import refresh
                        refresh()
                    except Exception:
                        pass
                avail = available_curves()
                if value not in avail:
                    errors.append(f"Unknown price_curve_source '{value}'. Available: {', '.join(avail)}.")
                else:
                    try:
                        snap = load_curve(value)
                        clean["price_curve"] = snap["curve"]
                        clean["price_curve_source"] = value
                        clean["price_curve_metadata"] = {
                            "source": snap["source"],
                            "as_of": snap["as_of"],
                            "placeholder": snap.get("placeholder", False),
                        }
                    except (ValueError, FileNotFoundError) as e:
                        errors.append(str(e))
            elif name == "region":
                norm_reg = normalize_region(value)
                if norm_reg not in REGIONS:
                    errors.append(f"Unknown region '{value}'. Valid: {', '.join(REGIONS)}.")
                else:
                    clean[name] = norm_reg
            else:
                clean[name] = value
        elif value is None and name in ("herd_end_value", "max_livestock_share", "owned_ha"):
            clean[name] = None
        elif not _is_number(value):
            errors.append(f"'{name}' must be a number in {unit}.")
        elif kind is int and float(value) != int(value):
            errors.append(f"'{name}' must be a whole number of {unit}.")
        elif not lo <= value <= hi:
            errors.append(f"'{name}' = {value} is out of range: between {lo} and {hi} {unit}.")
        else:
            clean[name] = kind(value)
    if clean.get("price_curve_source") == "cbot_latest" and "basis_usd_t" not in clean:
        reg = clean.get("region", "southeast_buenos_aires")
        basis_path = REGIONS[reg].get("basis_file")
        if basis_path and basis_path.is_file():
            basis_data = json.loads(basis_path.read_text(encoding="utf-8"))
            clean["basis_usd_t"] = basis_data.get("basis", {})
    if errors:
        raise ScenarioError(" ".join(errors))
    try:
        return Scenario(**clean), sorted(clean)
    except (ValueError, ScenarioError) as e:
        raise ScenarioError(str(e))


def build_scenario(scenario: dict) -> dict:
    """Validate the scenario and return every parameter with its value, unit and origin."""
    sc, given = _validate(scenario)
    out = {}
    for name, (_, _, _, unit, _) in PARAMETERS.items():
        if name in ("prices", "yields"):
            continue
        value = getattr(sc, name)
        if name == "costs_override":
            origin = "farmer document" if (name in given and value) else "default"
        else:
            origin = FROM_FARMER if name in given else (ASSUMPTION if name in _ASSUMPTIONS else "default")
        if name == "constraints":
            echoed = [{**c, "origin": FROM_FARMER} for c in value]
            out[name] = {"value": echoed, "unit": unit, "origin": origin}
        else:
            out[name] = {"value": list(value) if isinstance(value, tuple) else value, "unit": unit, "origin": origin}
    default_source = SOURCE_IOWA if sc.region == "iowa" else SOURCE_MAGYP
    for c in sc.crops:
        harvest_p = sc.calendar[c]["harvest"] if hasattr(sc, "calendar") and c in sc.calendar else CALENDAR[c]["harvest"]
        has_curve = sc.curve_price(c, harvest_p) is not None
        if has_curve:
            meta = sc.price_curve_metadata
            source = meta.get("source", "curve")
            as_of = meta.get("as_of", "")
            is_placeholder = meta.get("placeholder", False)
            price_origin = f"{source}, as of {as_of}" if as_of else source
            if is_placeholder:
                price_origin += ", placeholder"
            out[f"price_{c}"] = {"value": sc.price(c), "unit": "USD/t at harvest", "origin": price_origin}
            out[f"price_curve_{c}"] = {"value": sc.price_curve[c], "unit": "USD/t", "origin": price_origin}
        else:
            out[f"price_{c}"] = {"value": sc.price(c), "unit": "USD/t at harvest",
                                 "origin": FROM_FARMER if c in sc.prices else default_source}
        out[f"yield_{c}"] = {"value": sc.crop_yield(c), "unit": "t/ha",
                             "origin": FROM_FARMER if c in sc.yields else default_source}
        out[f"harvest_{c}"] = {"value": fortnight_name(harvest_p), "unit": "fortnight",
                               "origin": ASSUMPTION}
    return {"scenario": out}


def _sales_by_month(result) -> dict:
    out = {}
    for c, sales in result.sales.items():
        by_month = {}
        for p, t in sales.items():
            month = MONTHS[(p // 2) % 12] + (" (year 2)" if p >= 24 else "")
            by_month[month] = by_month.get(month, 0) + t
        if by_month:
            out[c] = {m: round(t, 1) for m, t in by_month.items()}
    return out


def evaluate_season(scenario: dict) -> dict:
    """Optimize the season and return the plan and the main results."""
    sc, _ = _validate(scenario)
    r = optimize(sc)
    out = r.summary()
    peak = max(range(FORTNIGHTS), key=lambda p: r.debt[p])
    out.update({
        "sales_t_by_month": _sales_by_month(r),
        "max_credit_fortnight": fortnight_name(peak) if r.debt[peak] > 1e-6 else None,
        "unsown_ha": round(sc.area_ha - sum(r.hectares.values()), 1),
        "cash": [round(float(c)) for c in r.cash],
        "debt": [round(float(d)) for d in r.debt],
        "note": "NPV and shadow prices in USD of today (May), discounted at the deposit rate.",
    })
    meta = sc.price_curve_metadata
    if meta:
        out["price_source"] = f"{meta.get('source', '')}, as of {meta.get('as_of', '')}"
        if meta.get("placeholder"):
            out["warning"] = "Prices come from a placeholder snapshot, not real quotes: say so to the farmer."

    constraint_reports = []
    for c, dual in zip(sc.constraints, r.constraint_duals):
        ctype = c["type"]
        is_binding = abs(dual) > 1e-6
        cost = round(float(dual), 2)
        if ctype in ("min_area", "max_area"):
            unit = "USD/ha"
            if is_binding:
                meaning = (
                    f"meeting this costs {cost} USD of today per hectare; "
                    f"loosening it by one hectare would raise the present value by that amount"
                )
            else:
                meaning = "this constraint is not binding; loosening it does not change the present value"
        elif ctype == "min_share":
            unit = "USD/share point"
            if is_binding:
                meaning = (
                    f"meeting this costs {cost} USD of today per share point; "
                    f"loosening it by one share point would raise the present value by that amount"
                )
            else:
                meaning = "this constraint is not binding; loosening it does not change the present value"
        elif ctype == "forward_sale":
            unit = "USD/t"
            if is_binding:
                if cost > 0:
                    meaning = (
                        f"delivering this costs {cost} USD of today per tonne; "
                        f"delivering one tonne less would raise the present value by that amount"
                    )
                else:
                    meaning = (
                        f"this contract benefits the farm by {-cost} USD of today per tonne "
                        f"compared to market prices"
                    )
            else:
                meaning = "this constraint is not binding; delivering one tonne more or less leaves the present value unchanged"
        else:
            unit = ""
            meaning = ""

        rep = {
            "type": ctype,
            "label": c.get("label"),
            "binding": is_binding,
            "opportunity_cost": cost,
            "unit": unit,
            "meaning": meaning,
        }
        constraint_reports.append(rep)
    out["constraints"] = constraint_reports

    x_val = round(float(r.land_shadow_price), 2)
    y_val = round(float(sc.regional_rent_usd_ha), 2)
    z_val = round(float(sc.land_price_usd_ha * sc.deposit_rate_annual), 2)
    land_comp = f"an extra hectare is worth {x_val} to you; renting one costs {y_val}; the money tied up in one costs {z_val} a year"
    out["land_comparison"] = land_comp
    out["land_tenure"] = {
        "owned_ha": round(sc.owned, 1),
        "rent_in_ha": round(r.rent_in_ha, 1),
        "rent_out_ha": round(r.rent_out_ha, 1),
        "buy_ha": round(r.buy_ha, 1),
        "land_shadow_price_usd_ha": x_val,
        "regional_rent_usd_ha": y_val,
        "land_cost_of_capital_usd_ha": z_val,
        "comparison": land_comp,
        "return_on_capital": round(r.return_on_capital, 4),
        "return_on_capital_and_land": round(r.return_on_capital_and_land, 4),
    }
    if sc.income_tax_rate > 0:
        out["income_tax_note"] = (
            f"Income tax rate {sc.income_tax_rate * 100:.1f}% scales the reported values but does not alter the plan."
        )

    return out


def shadow_prices(scenario: dict) -> dict:
    """What each scarce resource is worth, and fortnight by fortnight when capital is scarce."""
    sc, _ = _validate(scenario)
    r = optimize(sc)
    fortnights = []
    for p in range(FORTNIGHTS - 1):
        row = {
            "fortnight": fortnight_name(p),
            "internal_rate_annual": round(r.internal_rate_annual[p], 4),
            "usd_today_per_dollar": float(r.cash_value[p]),
        }
        if r.credit_shadow_price[p] > 1e-6:
            row["usd_per_extra_dollar_of_credit"] = round(r.credit_shadow_price[p], 4)
        if r.storage_shadow_price[p] > 1e-6:
            row["usd_per_extra_tonne_of_storage"] = round(r.storage_shadow_price[p], 2)
        fortnights.append(row)
    res_dict = {
        "own_capital": {"usd_per_extra_dollar": round(r.capital_shadow_price, 4),
                        "meaning": "what one more dollar of capital is worth beyond depositing it at the market rate"},
        "land": {"usd_per_extra_ha": round(r.land_shadow_price, 2)},
        "storage": {"usd_per_extra_tonne": round(sum(r.storage_shadow_price), 2)},
        "credit_line": {"usd_per_extra_dollar": round(sum(r.credit_shadow_price), 4)},
        "market_rate_annual": sc.deposit_rate_annual,
        "by_fortnight": fortnights,
    }
    if sc.livestock_only_ha > 0 or r.livestock_only_shadow_price > 0:
        res_dict["cattle_only_land"] = {"usd_per_extra_ha": round(r.livestock_only_shadow_price, 2)}
    return res_dict


def sensitivity(scenario: dict, parameter: str, values: list) -> dict:
    """Re-run the season for several values of one parameter."""
    if parameter not in SENSITIVITY_PARAMETERS:
        raise ScenarioError(f"'{parameter}' does not support sensitivity. Options: {', '.join(SENSITIVITY_PARAMETERS)}.")
    if not isinstance(values, list) or not 1 <= len(values) <= MAX_SENSITIVITY_VALUES:
        raise ScenarioError(f"'values' must be a list of 1 to {MAX_SENSITIVITY_VALUES} numbers.")
    _validate(scenario)
    rows = []
    for v in values:
        sc, _ = _validate({**scenario, parameter: v})
        r = optimize(sc)
        rows.append({parameter: v, "npv_usd": round(r.npv, 2),
                     "hectares": {c: round(h, 1) for c, h in r.hectares.items() if h > 1e-6},
                     "max_credit_usd": round(max(r.debt), 2),
                     "capital_shadow_price": round(r.capital_shadow_price, 4)})
    return {"parameter": parameter, "results": rows}


def refresh_prices() -> dict:
    """Refresh the CBOT price curve and local basis/snapshots."""
    from .feeds import refresh
    return refresh()


def record_document(
    kind: str,
    items: list[dict],
    scenario: dict | Scenario | None = None,
) -> dict:
    """Record extracted items from a farmer document and reconcile against regional defaults."""
    from .feeds import BcraFxFeed
    from .scenario import load_region_data

    # Resolve scenario context if provided
    sc_obj = None
    area_ha = None
    region = "southeast_buenos_aires"
    crops = ["wheat", "corn", "soybean", "sunflower"]

    if scenario is not None:
        if isinstance(scenario, Scenario):
            sc_obj = scenario
            area_ha = sc_obj.area_ha
            region = sc_obj.region
            crops = list(sc_obj.crops)
        elif isinstance(scenario, dict):
            area_ha = scenario.get("area_ha")
            region = scenario.get("region", region)
            crops = scenario.get("crops", crops)
            try:
                sc_obj, _ = _validate(scenario)
                area_ha = sc_obj.area_ha
                region = sc_obj.region
                crops = list(sc_obj.crops)
            except Exception:
                pass

    reg_data = load_region_data(region)
    reg_crops = reg_data.get("crops", {})

    missing: list[str] = []
    replaces: list[str] = []
    proposals: list[dict] = []
    processed_items: list[dict] = []
    fx_conversion: dict | None = None

    def _normalize_concept(c_text: str) -> str | None:
        c_lower = c_text.lower().strip()
        if any(w in c_lower for w in ["fertiliz", "urea", "fosfat", "fósfor", "map", "dap"]):
            return "fertilizer"
        if any(w in c_lower for w in ["semill", "seed"]):
            return "seed"
        if any(w in c_lower for w in ["protecc", "protect", "agroquim", "herbicid", "insecticid", "fungicid", "fitosanitar"]):
            return "crop_protection"
        if any(w in c_lower for w in ["labor", "operaci", "operat", "siembr", "pulveriz", "cosech", "field_op"]):
            return "field_operations"
        if any(w in c_lower for w in ["overhead", "estructur"]):
            return "overhead_owned"
        if any(w in c_lower for w in ["rent", "arrend"]):
            return "rent"
        return None

    for it in items:
        concept = str(it.get("concept", "")).strip()
        amount = float(it.get("amount", 0.0))
        currency = str(it.get("currency", "USD")).strip().upper()
        unit = str(it.get("unit", "")).strip().lower()
        date_str = it.get("date")
        crop_raw = it.get("crop")

        # 1. Currency conversion if ARS
        converted_usd = amount
        if currency == "ARS":
            bcra = BcraFxFeed()
            try:
                rate, fx_date = bcra.fetch_rate_and_date(date_str)
            except Exception:
                try:
                    rate = float(bcra.fetch_rate(date_str))
                    fx_date = date_str or "latest"
                except Exception:
                    rate = 1.0
                    fx_date = date_str or "unknown"
            converted_usd = amount / rate
            fx_conversion = {
                "currency": "ARS",
                "rate": rate,
                "date": fx_date,
                "amount_ars": amount,
                "amount_usd": round(converted_usd, 2),
            }

        cost_item = _normalize_concept(concept)

        # 2. Crop resolution
        if crop_raw:
            norm_c = crop_raw.lower().strip()
            crop_name = {
                "trigo": "wheat", "maiz": "corn", "maíz": "corn",
                "soja": "soybean", "girasol": "sunflower"
            }.get(norm_c, norm_c)
        elif len(crops) == 1:
            crop_name = crops[0]
        else:
            crop_name = "wheat"

        # 3. Unit / Hectares resolution
        is_per_ha = any(u in unit for u in ["/ha", "usd/ha", "ars/ha", "per ha", "por ha"])
        item_ha = it.get("area_ha") or it.get("hectares") or area_ha

        if is_per_ha:
            usd_ha = converted_usd
        elif item_ha and float(item_ha) > 0:
            usd_ha = converted_usd / float(item_ha)
        else:
            usd_ha = None
            if "missing: hectares" not in missing:
                missing.append("missing: hectares")

        # 4. Propose replacement & deviation check
        if cost_item and usd_ha is not None:
            default_val = reg_crops.get(crop_name, {}).get(cost_item)
            deviation_flag = False
            dev_pct = 0.0
            if default_val and default_val > 0:
                dev_pct = abs(usd_ha - default_val) / default_val
                if dev_pct > 0.50:
                    deviation_flag = True

            proposal = {
                "crop": crop_name,
                "item": cost_item,
                "concept": concept,
                "proposed_usd_ha": round(usd_ha, 2),
                "default_usd_ha": default_val,
                "deviation_pct": round(dev_pct * 100.0, 1),
                "deviation_flag": deviation_flag,
            }
            if deviation_flag:
                proposal["flag"] = f"Deviation of {dev_pct*100.0:.1f}% from regional default ({default_val} USD/ha)"
            proposals.append(proposal)
            replaces.append(f"{crop_name}.{cost_item} = {round(usd_ha, 2)} USD/ha")

        processed_items.append({
            "concept": concept,
            "cost_item": cost_item,
            "crop": crop_name,
            "amount": amount,
            "currency": currency,
            "amount_usd": round(converted_usd, 2),
            "unit": unit or ("USD/ha" if is_per_ha else "total"),
        })

    # Completeness report
    all_standard_items = ("seed", "fertilizer", "crop_protection", "field_operations", "overhead_owned")
    farmer_coeffs = [f"{p['crop']}.{p['item']}" for p in proposals]
    default_coeffs = [
        f"{c}.{it}"
        for c in crops
        for it in all_standard_items
        if f"{c}.{it}" not in farmer_coeffs
    ]
    completeness = {
        "farmer_coefficients": farmer_coeffs,
        "default_coefficients": default_coeffs,
        "ratio_farmer": round(len(farmer_coeffs) / max(1, len(farmer_coeffs) + len(default_coeffs)), 2),
    }

    res = {
        "kind": kind,
        "items": processed_items,
        "proposals": proposals,
        "missing": missing,
        "replaces": replaces,
        "completeness": completeness,
    }
    if fx_conversion:
        res["fx_conversion"] = fx_conversion
        res["rate"] = fx_conversion["rate"]
        res["date"] = fx_conversion["date"]
        res["bcra_rate"] = fx_conversion["rate"]
        res["bcra_date"] = fx_conversion["date"]

    return res


def tax_wedge(scenario: dict) -> dict:
    """Breakdown of taxes by form, in USD and % of gross revenue, with public sources."""
    sc, _ = _validate(scenario)
    r = optimize(sc)

    total_sales_revenue = 0.0
    crop_tonnes = {}
    for c, sales in r.sales.items():
        crop_tonnes[c] = sum(sales.values())
        for p, t in sales.items():
            cp = sc.curve_price(c, p)
            if cp is not None:
                gross_p = cp + sc.basis_usd_t.get(c, 0.0)
            else:
                harvest_p = sc.calendar[c]["harvest"] if hasattr(sc, "calendar") and c in sc.calendar else CALENDAR[c]["harvest"]
                months = (p - harvest_p) / 2
                gross_p = sc.price(c) * (1 + sc.monthly_price_rise) ** months
            total_sales_revenue += gross_p * t

    tax_data = load_taxes_data(sc.region)
    export_duties_dict = tax_data.get("export_duties", {})
    as_of = tax_data.get("date", "2026-06")

    # Rates: use scenario if set, otherwise country tax defaults
    gross_receipts_rate = sc.gross_receipts_rate if sc.gross_receipts_rate > 0 else tax_data.get("gross_receipts_rate", 0.0)
    transaction_tax_rate = sc.transaction_tax_rate if sc.transaction_tax_rate > 0 else tax_data.get("transaction_tax_rate", 0.0)
    land_tax_rate = sc.land_tax_usd_ha_year if sc.land_tax_usd_ha_year > 0 else tax_data.get("land_tax_usd_ha_year", 0.0)
    income_tax_rate = sc.income_tax_rate if sc.income_tax_rate > 0 else tax_data.get("income_tax_rate", 0.0)

    # 1. Export duties (retenciones)
    export_duty_usd = 0.0
    fob_revenue = 0.0
    for c, t in crop_tonnes.items():
        if t > 1e-6:
            duty_rate = export_duties_dict.get(c, 0.0)
            c_fas = sum(
                (sc.curve_price(c, p) + sc.basis_usd_t.get(c, 0.0) if sc.curve_price(c, p) is not None
                 else sc.price(c) * (1 + sc.monthly_price_rise) ** ((p - (sc.calendar[c]["harvest"] if hasattr(sc, "calendar") and c in sc.calendar else CALENDAR[c]["harvest"])) / 2))
                * qty for p, qty in r.sales[c].items()
            )
            if 0 < duty_rate < 1.0:
                c_fob = c_fas / (1.0 - duty_rate)
                c_duty = c_fob * duty_rate
            else:
                c_fob = c_fas
                c_duty = 0.0
            export_duty_usd += c_duty
            fob_revenue += c_fob

    gross_revenue = fob_revenue if fob_revenue > 0 else total_sales_revenue
    if gross_revenue < 1e-6:
        gross_revenue = max(r.rent_out_ha * sc.regional_rent_usd_ha, 1.0)

    # 2. Gross receipts tax
    gross_receipts_usd = gross_receipts_rate * total_sales_revenue

    # 3. Transaction tax: sales + payments
    total_payments = 0.0
    for c, ha_c in r.hectares.items():
        if ha_c > 1e-6:
            p_dict = sc.payments_per_ha(c)
            base_payments = sum(p_dict.values()) / (1.0 + sc.transaction_tax_rate if sc.transaction_tax_rate > 0 else 1.0)
            total_payments += base_payments * ha_c
    total_payments += r.rent_in_ha * sc.regional_rent_usd_ha + r.buy_ha * sc.land_price_usd_ha
    transaction_tax_usd = transaction_tax_rate * (total_sales_revenue + total_payments)

    # 4. Land property tax
    land_tax_usd = land_tax_rate * (sc.owned + r.buy_ha)

    # 5. Income tax
    profit = max(0.0, r.final_wealth - sc.own_capital_usd)
    income_tax_usd = income_tax_rate * profit

    total_tax_usd = export_duty_usd + gross_receipts_usd + transaction_tax_usd + land_tax_usd + income_tax_usd

    def pct(val):
        return round((val / gross_revenue) * 100, 2) if gross_revenue > 0 else 0.0

    table = [
        {"name": "Export duties (retenciones)", "rate": export_duties_dict, "usd": round(export_duty_usd, 2), "percent_gross_revenue": pct(export_duty_usd), "source": tax_data.get("export_duties_source", "")},
        {"name": "Gross receipts tax (Ingresos Brutos / Funrural)", "rate": gross_receipts_rate, "usd": round(gross_receipts_usd, 2), "percent_gross_revenue": pct(gross_receipts_usd), "source": tax_data.get("gross_receipts_source", "")},
        {"name": "Transaction tax (bank debits & credits)", "rate": transaction_tax_rate, "usd": round(transaction_tax_usd, 2), "percent_gross_revenue": pct(transaction_tax_usd), "source": tax_data.get("transaction_tax_source", "")},
        {"name": "Land property tax (Inmobiliario Rural / ITR)", "rate": land_tax_rate, "usd": round(land_tax_usd, 2), "percent_gross_revenue": pct(land_tax_usd), "source": tax_data.get("land_tax_source", "")},
        {"name": "Income tax (Ganancias / Corporate)", "rate": income_tax_rate, "usd": round(income_tax_usd, 2), "percent_gross_revenue": pct(income_tax_usd), "source": tax_data.get("income_tax_source", "")},
        {"name": "Total taxes", "rate": None, "usd": round(total_tax_usd, 2), "percent_gross_revenue": pct(total_tax_usd), "source": ""},
    ]

    return {
        "region": sc.region,
        "country": tax_data.get("country", sc.region),
        "gross_revenue_usd": round(gross_revenue, 2),
        "total_taxes_usd": round(total_tax_usd, 2),
        "net_revenue_after_tax_usd": round(gross_revenue - total_tax_usd, 2),
        "tax_wedge_percent": pct(total_tax_usd),
        "taxes": table,
        "disclaimer": f"Orientative guide based on public rates as of {as_of}; not tax advice; consult an accountant.",
        "export_fx_regime": sc.export_fx_regime,
    }


TOOLS = {
    "build_scenario": build_scenario,
    "evaluate_season": evaluate_season,
    "shadow_prices": shadow_prices,
    "sensitivity": sensitivity,
    "refresh_prices": refresh_prices,
    "field_from_map": field_from_map,
    "record_document": record_document,
    "tax_wedge": tax_wedge,
}


def run_tool(name: str, arguments: str | dict) -> str:
    """Agent entry point: takes the arguments the model generated and returns JSON."""
    try:
        args = json.loads(arguments) if isinstance(arguments, str) else arguments
        if name not in TOOLS:
            raise ScenarioError(f"There is no tool '{name}'. Options: {', '.join(TOOLS)}.")
        out = TOOLS[name](**args)
    except (ScenarioError, TypeError, json.JSONDecodeError) as e:
        out = {"error": str(e)}
    return json.dumps(out, ensure_ascii=False)
