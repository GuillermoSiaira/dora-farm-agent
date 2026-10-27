"""Tools the agent calls. JSON in, JSON out.

The language model does not calculate or write equations: it fills in the
parameters of a scenario, which are validated here, and reads the results the
engine returns. Every scenario parameter carries its origin: the farmer said it,
it comes from MAGyP's report, or it is a model assumption.
"""
from __future__ import annotations

import json
from dataclasses import fields

from .engine import optimize
from .scenario import CALENDAR, FORTNIGHTS, MONTHS, Scenario, fortnight_name

SOURCE_MAGYP = "MAGyP margins report, Jun-2026, Southeast Buenos Aires"
FROM_FARMER = "farmer"
ASSUMPTION = "model assumption"

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
}
_ASSUMPTIONS = {f.name for f in fields(Scenario)} - {"prices", "yields", "crops", "area_ha"}

SENSITIVITY_PARAMETERS = ("own_capital_usd", "credit_line_usd", "credit_rate_annual", "input_payment_delay_fortnights",
                          "input_delay_surcharge", "storage_capacity_t", "area_ha", "monthly_price_rise")
MAX_SENSITIVITY_VALUES = 10


class ScenarioError(ValueError):
    pass


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
            if isinstance(value, list) and value and all(c in CALENDAR for c in value):
                clean[name] = tuple(dict.fromkeys(value))
            else:
                errors.append(f"'crops' must be a list with items from: {', '.join(CALENDAR)}.")
        elif kind is dict:
            if not isinstance(value, dict):
                errors.append(f"'{name}' must be an object crop -> value in {unit}.")
                continue
            for c, v in value.items():
                if c not in CALENDAR:
                    errors.append(f"'{name}': '{c}' is not a known crop.")
                elif not _is_number(v) or not lo <= v <= hi:
                    errors.append(f"'{name}.{c}' must be between {lo} and {hi} {unit}.")
            clean[name] = {c: float(v) for c, v in value.items() if c in CALENDAR and _is_number(v)}
        elif not _is_number(value):
            errors.append(f"'{name}' must be a number in {unit}.")
        elif kind is int and float(value) != int(value):
            errors.append(f"'{name}' must be a whole number of {unit}.")
        elif not lo <= value <= hi:
            errors.append(f"'{name}' = {value} is out of range: between {lo} and {hi} {unit}.")
        else:
            clean[name] = kind(value)
    if errors:
        raise ScenarioError(" ".join(errors))
    return Scenario(**clean), sorted(clean)


def build_scenario(scenario: dict) -> dict:
    """Validate the scenario and return every parameter with its value, unit and origin."""
    sc, given = _validate(scenario)
    out = {}
    for name, (_, _, _, unit, _) in PARAMETERS.items():
        if name in ("prices", "yields"):
            continue
        value = getattr(sc, name)
        origin = FROM_FARMER if name in given else (ASSUMPTION if name in _ASSUMPTIONS else "default")
        out[name] = {"value": list(value) if isinstance(value, tuple) else value, "unit": unit, "origin": origin}
    for c in sc.crops:
        out[f"price_{c}"] = {"value": sc.price(c), "unit": "USD/t at harvest",
                             "origin": FROM_FARMER if c in sc.prices else SOURCE_MAGYP}
        out[f"yield_{c}"] = {"value": sc.crop_yield(c), "unit": "t/ha",
                             "origin": FROM_FARMER if c in sc.yields else SOURCE_MAGYP}
        out[f"harvest_{c}"] = {"value": fortnight_name(CALENDAR[c]["harvest"]), "unit": "fortnight",
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
        "note": "NPV and shadow prices in USD of today (May), discounted at the deposit rate.",
    })
    return out


def shadow_prices(scenario: dict) -> dict:
    """What each scarce resource is worth, and fortnight by fortnight when capital is scarce."""
    sc, _ = _validate(scenario)
    r = optimize(sc)
    fortnights = []
    for p in range(FORTNIGHTS - 1):
        row = {"fortnight": fortnight_name(p), "internal_rate_annual": round(r.internal_rate_annual[p], 4)}
        if r.credit_shadow_price[p] > 1e-6:
            row["usd_per_extra_dollar_of_credit"] = round(r.credit_shadow_price[p], 4)
        if r.storage_shadow_price[p] > 1e-6:
            row["usd_per_extra_tonne_of_storage"] = round(r.storage_shadow_price[p], 2)
        fortnights.append(row)
    return {
        "own_capital": {"usd_per_extra_dollar": round(r.capital_shadow_price, 4),
                        "meaning": "what one more dollar of capital is worth beyond depositing it at the market rate"},
        "land": {"usd_per_extra_ha": round(r.land_shadow_price, 2)},
        "storage": {"usd_per_extra_tonne": round(sum(r.storage_shadow_price), 2)},
        "credit_line": {"usd_per_extra_dollar": round(sum(r.credit_shadow_price), 4)},
        "market_rate_annual": sc.deposit_rate_annual,
        "by_fortnight": fortnights,
    }


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


TOOLS = {
    "build_scenario": build_scenario,
    "evaluate_season": evaluate_season,
    "shadow_prices": shadow_prices,
    "sensitivity": sensitivity,
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
