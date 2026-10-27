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


TOOL_SCHEMAS = [
    _tool("build_scenario",
          "Validate the scenario and show every parameter with its value, unit and origin (farmer, MAGyP or "
          "assumption). Use it first, to confirm with the farmer what you understood.",
          {"scenario": SCENARIO}, ["scenario"]),
    _tool("evaluate_season",
          "Optimize the season: hectares per crop, sales per month, credit used, present value and main "
          "shadow prices.",
          {"scenario": SCENARIO}, ["scenario"]),
    _tool("shadow_prices",
          "What each scarce resource is worth (capital, land, storage, credit) and, fortnight by fortnight, "
          "when capital is scarce (internal rate above the market rate).",
          {"scenario": SCENARIO}, ["scenario"]),
    _tool("sensitivity",
          "Re-run the season for several values of one parameter (for example, different supplier payment "
          "terms or different credit amounts).",
          {"scenario": SCENARIO,
           "parameter": {"type": "string", "enum": list(SENSITIVITY_PARAMETERS)},
           "values": {"type": "array", "items": {"type": "number"},
                      "minItems": 1, "maxItems": MAX_SENSITIVITY_VALUES}},
          ["scenario", "parameter", "values"]),
]
