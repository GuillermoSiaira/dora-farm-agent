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
                ]
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

TOOL_SCHEMAS = [
    _tool("build_scenario",
          "Validate the scenario and show every parameter with its value, unit and origin (farmer, MAGyP or "
          "assumption). Use it first, to confirm with the farmer what you understood.",
          {"scenario": SCENARIO}, ["scenario"]),
    _tool("evaluate_season",
          "Optimize the season: hectares per crop, sales per month, credit used, present value and main "
          "shadow prices.",
          {"scenario": SCENARIO_REF}, ["scenario"]),
    _tool("shadow_prices",
          "What each scarce resource is worth (capital, land, storage, credit) and, fortnight by fortnight, "
          "when capital is scarce (internal rate above the market rate).",
          {"scenario": SCENARIO_REF}, ["scenario"]),
    _tool("sensitivity",
          "Re-run the season for several values of one parameter (for example, different supplier payment "
          "terms or different credit amounts).",
          {"scenario": SCENARIO_REF,
           "parameter": {"type": "string", "enum": list(SENSITIVITY_PARAMETERS)},
           "values": {"type": "array", "items": {"type": "number"},
                      "minItems": 1, "maxItems": MAX_SENSITIVITY_VALUES}},
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
          {"scenario": SCENARIO_REF}, ["scenario"]),
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
          },
          ["scenario"]),
]

