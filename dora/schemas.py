"""Tool definitions for the model, in the OpenAI-compatible function-calling
format (used by Meta's API and by the inference providers)."""
from .prices import available_curves
from .scenario import CALENDAR
from .tools import MAX_SENSITIVITY_VALUES, PARAMETERS, SENSITIVITY_PARAMETERS

_TYPES = {float: "number", int: "integer", bool: "boolean", str: "string"}


def _property(name, kind, lo, hi, unit, description):
    text = f"{description} ({unit})" if unit else description
    if name == "price_curve_source":
        return {"type": "string", "enum": available_curves(), "description": text}
    if name == "region":
        return {"type": "string", "enum": ["southeast_buenos_aires", "pampas_core", "iowa", "mato_grosso"], "description": text}
    if name == "constraints":
        return {
            "type": "array",
            "description": text,
            "items": {
                "oneOf": [
                    {
                        "type": "object",
                        "description": "Minimum hectares under a crop",
                        "properties": {
                            "type": {"type": "string", "enum": ["min_area"]},
                            "crop": {"type": "string", "enum": list(CALENDAR)},
                            "ha": {"type": "number", "minimum": 0},
                            "label": {"type": "string"},
                        },
                        "required": ["type", "crop", "ha"],
                        "additionalProperties": False,
                    },
                    {
                        "type": "object",
                        "description": "Maximum hectares under a crop",
                        "properties": {
                            "type": {"type": "string", "enum": ["max_area"]},
                            "crop": {"type": "string", "enum": list(CALENDAR)},
                            "ha": {"type": "number", "minimum": 0},
                            "label": {"type": "string"},
                        },
                        "required": ["type", "crop", "ha"],
                        "additionalProperties": False,
                    },
                    {
                        "type": "object",
                        "description": "Minimum share of total sown land under a crop",
                        "properties": {
                            "type": {"type": "string", "enum": ["min_share"]},
                            "crop": {"type": "string", "enum": list(CALENDAR)},
                            "share": {"type": "number", "minimum": 0, "maximum": 1},
                            "label": {"type": "string"},
                        },
                        "required": ["type", "crop", "share"],
                        "additionalProperties": False,
                    },
                    {
                        "type": "object",
                        "description": "Forward sale contract: delivery of tonnes in month at fixed price",
                        "properties": {
                            "type": {"type": "string", "enum": ["forward_sale"]},
                            "crop": {"type": "string", "enum": list(CALENDAR)},
                            "month": {"type": "string"},
                            "tonnes": {"type": "number", "minimum": 0},
                            "price_usd_t": {"type": "number", "minimum": 0},
                            "label": {"type": "string"},
                        },
                        "required": ["type", "crop", "month", "tonnes", "price_usd_t"],
                        "additionalProperties": False,
                    },
                    {
                        "type": "object",
                        "description": "Cap on payments for inputs, operations and overhead from the start of the "
                                       "season to the end of a month ('I cannot pay out more than X until February')",
                        "properties": {
                            "type": {"type": "string", "enum": ["max_payments_by"]},
                            "month": {"type": "string", "description": "YYYY-MM, inclusive"},
                            "usd": {"type": "number", "minimum": 0},
                            "label": {"type": "string"},
                        },
                        "required": ["type", "month", "usd"],
                        "additionalProperties": False,
                    },
                ]
            },
        }
    if name == "payment_options":
        return {
            "type": "array",
            "description": text + ". Each option applies to seed, fertilizer and crop protection; the engine "
                                  "chooses, crop by crop, how many hectares to pay under each term or the base one.",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Short name, e.g. '90_days' or '3_installments'"},
                    "delay_fortnights": {"type": "integer", "minimum": 0, "maximum": 24,
                                         "description": "Fortnights after the purchase until the first payment (90 days = 6)"},
                    "surcharge": {"type": "number", "minimum": -0.5, "maximum": 0.5,
                                  "description": "Surcharge on the price (0.03 = 3%; negative = cash discount)"},
                    "installments": {"type": "integer", "minimum": 1, "maximum": 12},
                    "every_fortnights": {"type": "integer", "minimum": 1, "maximum": 12,
                                         "description": "Fortnights between installments (monthly = 2)"},
                },
                "required": ["id", "delay_fortnights", "surcharge"],
                "additionalProperties": False,
            },
        }
    if name == "storage_options":
        return {
            "type": "array",
            "description": text + ". Omitted fields take the regional defaults for that kind.",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Unique name, e.g. 'own_silo', 'silo_bag', 'elevator'"},
                    "kind": {"type": "string", "enum": ["own_silo", "silo_bag", "elevator"]},
                    "capacity_t": {
                        "oneOf": [{"type": "number", "minimum": 0}, {"type": "null"}],
                        "description": "Capacity in tonnes; null = no limit",
                    },
                    "fill_cost_usd_t": {"type": "number", "minimum": 0,
                                        "description": "Paid once in the harvest fortnight per tonne put in (USD/t)"},
                    "monthly_cost_usd_t": {"type": "number", "minimum": 0,
                                           "description": "Paid every fortnight on the stock at half this value (USD/t/month)"},
                    "shrink_at_entry": {"type": "number", "minimum": 0, "maximum": 0.2,
                                        "description": "Share lost when grain goes in (0.005 = 0.5%)"},
                    "shrink_monthly": {"type": "number", "minimum": 0, "maximum": 0.2,
                                       "description": "Share lost per month in storage (0.01 = 1%)"},
                    "max_months": {
                        "oneOf": [{"type": "number", "exclusiveMinimum": 0}, {"type": "null"}],
                        "description": "Longest time in months the grain may stay; null = no limit",
                    },
                },
                "required": ["kind"],
                "additionalProperties": False,
            },
        }
    if name == "basis_usd_t":
        return {
            "type": "object",
            "description": text,
            "properties": {
                c: {
                    "oneOf": [
                        {"type": "number", "minimum": lo, "maximum": hi},
                        {
                            "type": "object",
                            "description": "Monthly basis {'YYYY-MM': USD/t}, linearly interpolated across fortnights",
                            "additionalProperties": {"type": "number", "minimum": lo, "maximum": hi},
                        },
                    ]
                }
                for c in CALENDAR
            },
        }
    if name == "costs_override":
        return {
            "type": "object",
            "description": text,
            "properties": {
                c: {
                    "type": "object",
                    "properties": {
                        item: {"type": "number", "minimum": 0}
                        for item in ("seed", "fertilizer", "crop_protection", "field_operations", "overhead_owned", "overhead_rented")
                    },
                }
                for c in CALENDAR
            },
        }
    if name == "livestock":
        return {
            "type": "array",
            "items": {"type": "string", "enum": ["cow_calf", "cow_calf_herd_purchase", "steer_fattening"]},
            "description": text,
        }
    if name == "routes":
        return {
            "type": "array",
            "items": {"type": "object"},
            "description": text,
        }
    if name == "destination_price_usd_t":
        return {
            "type": "object",
            "description": text,
            "properties": {c: {"type": "number", "minimum": 0} for c in CALENDAR},
        }
    if kind is list:
        return {"type": "array", "items": {"type": "string", "enum": list(CALENDAR)}, "description": text}
    if kind is dict:
        return {"type": "object", "description": text,
                "properties": {c: {"type": "number", "minimum": lo, "maximum": hi} for c in CALENDAR}}
    prop = {"type": _TYPES[kind], "description": text}
    if lo is not None:
        prop.update(minimum=lo, maximum=hi)
    return prop


SCENARIO = {
    "type": "object",
    "description": "Season parameters. Only the ones the farmer gave; the rest take their default.",
    "properties": {n: _property(n, *spec) for n, spec in PARAMETERS.items()},
    "additionalProperties": False,
}


def _tool(name, description, properties, required):
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": properties, "required": required,
                       "additionalProperties": False}}}


# The full scenario schema goes only in build_scenario. The other tools take the same object by
# reference: repeating ~9,000 characters in five tools made every model call about 12,000 tokens
# longer. Every tool still validates the scenario in run_tool and returns clear errors.
SCENARIO_REF = {"type": "object", "description": "The same scenario object you passed to build_scenario "
                "(same fields and units; omitted fields take regional defaults)."}

_LANG = {
    "type": "string",
    "enum": ["es", "en"],
    "description": "Language for fortnight and stretch names: 'es' (default, Spanish) or 'en' (English).",
}

TOOL_SCHEMAS = [
    _tool("build_scenario",
          "Validate the scenario and show every parameter with its value, unit and origin (farmer, MAGyP or "
          "assumption). Use it first, to confirm with the farmer what you understood.",
          {"scenario": SCENARIO, "lang": _LANG}, ["scenario"]),
    _tool("evaluate_season",
          "Optimize the season: hectares per crop, sales per month, credit used, present value and main "
          "shadow prices.",
          {"scenario": SCENARIO_REF, "lang": _LANG}, ["scenario"]),
    _tool("shadow_prices",
          "What each scarce resource is worth (capital, land, storage, credit) and, fortnight by fortnight, "
          "when capital is scarce (internal rate above the market rate).",
          {"scenario": SCENARIO_REF, "lang": _LANG}, ["scenario"]),
    _tool("sensitivity",
          "Re-run the season for several values of one parameter (for example, different supplier payment "
          "terms or different credit amounts).",
          {"scenario": SCENARIO_REF,
           "parameter": {"type": "string", "enum": list(SENSITIVITY_PARAMETERS)},
           "values": {"type": "array", "items": {"type": "number"},
                      "minItems": 1, "maxItems": MAX_SENSITIVITY_VALUES},
           "lang": _LANG},
          ["scenario", "parameter", "values"]),
    _tool("record_document",
          "Record extracted items from a farmer document (invoice, cost sheet, quote) and return a reconciliation against regional defaults.",
          {
              "kind": {
                  "type": "string",
                  "enum": ["invoice", "cost_sheet", "quote", "other"],
                  "description": "Type of document",
              },
              "items": {
                  "type": "array",
                  "description": "List of extracted line items",
                  "items": {
                      "type": "object",
                      "properties": {
                          "concept": {"type": "string", "description": "Concept description (e.g. fertilizer, seed, operations)"},
                          "amount": {"type": "number", "description": "Numeric amount"},
                          "currency": {"type": "string", "description": "Currency code (USD, ARS)", "default": "USD"},
                          "unit": {"type": "string", "description": "Unit (total, USD/ha, ha, etc.)"},
                          "date": {"type": "string", "description": "Date of transaction (YYYY-MM-DD or YYYY-MM)"},
                          "payment_terms": {"type": "string", "description": "Payment terms (e.g. 90 days, cash)"},
                          "crop": {"type": "string", "description": "Target crop name if specific"},
                      },
                      "required": ["concept", "amount"],
                  },
              },
              "scenario": {
                  "type": "object",
                  "description": "Current scenario context to reconcile against (optional)",
              },
          },
          ["kind", "items"]),
    _tool("tax_wedge",
          "Breakdown of taxes by form (export duties, gross receipts, transaction, property and income tax) in USD and % of gross revenue.",
          {"scenario": SCENARIO_REF, "lang": _LANG}, ["scenario"]),
    _tool("compare_regions",
          "Compare farm plans across regions or under the same investment budget.",
          {
              "scenario": SCENARIO_REF,
              "regions": {
                  "type": "array",
                  "items": {"type": "string", "enum": ["southeast_buenos_aires", "pampas_core", "iowa", "mato_grosso"]},
                  "description": "List of regions to compare (defaults to all supported regions)",
              },
              "mode": {
                  "type": "string",
                  "enum": ["same_farm", "same_budget"],
                  "description": "Comparison mode: 'same_farm' (same area and capital) or 'same_budget' (same money, optimize buying/renting land)",
              },
              "lang": _LANG,
          },
          ["scenario"]),
    _tool("assess_field_image",
          "Measure the damaged area in a vertical aerial photo of the field that the farmer sent (drone "
          "straight down or satellite) with Meta's SAM 3.1, and re-plan the season with the hectares already "
          "sown and the yield lost on that area: hectares affected, new present value, new cash stretches.",
          {
              "scenario": SCENARIO_REF,
              "image": {"type": "integer", "minimum": 0,
                        "description": "Position of the photo in the farmer's latest message (0 = first)."},
              "damage": {"type": "string", "enum": ["flooding"],
                         "description": "What to look for: 'flooding' (standing water)."},
              "crops": {"type": "array", "items": {"type": "string"},
                        "description": "Crops on the photographed field (default: every crop in the plan)."},
              "loss_share": {"type": "number", "minimum": 0, "maximum": 1,
                             "description": "Share of the yield lost where the damage is (default 1: total loss)."},
              "lang": _LANG,
          },
          ["scenario"]),

]

CLIMATE_TOOL_SCHEMAS = [
    _tool("climate_outlook",
          "Seasonal climate outlook from national meteorological services (SMN in Argentina, NOAA CPC in US, "
          "INMET in Brazil): probabilities for dry, normal, and wet conditions (below, near, above normal rainfall).",
          {
              "region": {
                  "type": "string",
                  "enum": ["southeast_buenos_aires", "pampas_core", "iowa", "mato_grosso"],
                  "description": "Region to query outlook for (optional, defaults to scenario region or southeast_buenos_aires)",
              },
              "scenario": SCENARIO_REF,
              "lang": _LANG,
          },
          []),
    _tool("climate_scenarios",
          "Evaluate the farm plan across 3 climate scenarios (dry, normal, wet) using official outlook probabilities: "
          "returns payoff matrix, expected NPV, worst-case NPV, and minimax regret.",
          {
              "scenario": SCENARIO_REF,
              "lang": _LANG,
          },
          ["scenario"]),
]

ALL_TOOL_SCHEMAS = TOOL_SCHEMAS + CLIMATE_TOOL_SCHEMAS


