"""Tool definitions for the model, in the OpenAI-compatible function-calling
format (used by Meta's API and by the inference providers)."""
from .scenario import CALENDAR
from .tools import MAX_SENSITIVITY_VALUES, PARAMETERS, SENSITIVITY_PARAMETERS

_TYPES = {float: "number", int: "integer", bool: "boolean"}


def _property(kind, lo, hi, unit, description):
    text = f"{description} ({unit})" if unit else description
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
    "properties": {n: _property(*spec) for n, spec in PARAMETERS.items()},
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
