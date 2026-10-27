"""Definición de las herramientas para el modelo, en el formato de llamadas a
funciones compatible con OpenAI (lo usan la API de Meta y los proveedores)."""
from .escenario import CALENDARIO
from .herramientas import MAX_VALORES_SENSIBILIDAD, PARAMETROS, PARAMETROS_SENSIBILIDAD

_TIPOS = {float: "number", int: "integer", bool: "boolean"}


def _propiedad(tipo, minimo, maximo, unidad, descripcion):
    texto = f"{descripcion} ({unidad})" if unidad else descripcion
    if tipo is list:
        return {"type": "array", "items": {"type": "string", "enum": list(CALENDARIO)}, "description": texto}
    if tipo is dict:
        return {"type": "object", "description": texto,
                "properties": {c: {"type": "number", "minimum": minimo, "maximum": maximo} for c in CALENDARIO}}
    prop = {"type": _TIPOS[tipo], "description": texto}
    if minimo is not None:
        prop.update(minimum=minimo, maximum=maximo)
    return prop


ESCENARIO = {
    "type": "object",
    "description": "Parámetros de la campaña. Solo los que dio el productor; el resto toma el valor por defecto.",
    "properties": {n: _propiedad(*spec) for n, spec in PARAMETROS.items()},
    "additionalProperties": False,
}


def _herramienta(nombre, descripcion, propiedades, requeridos):
    return {"type": "function", "function": {
        "name": nombre, "description": descripcion,
        "parameters": {"type": "object", "properties": propiedades, "required": requeridos,
                       "additionalProperties": False}}}


HERRAMIENTAS_ESQUEMA = [
    _herramienta("armar_escenario",
                 "Valida el escenario y muestra cada parámetro con su valor, unidad y origen (productor, MAGyP o "
                 "supuesto). Usala primero, para confirmar con el productor lo que entendiste.",
                 {"escenario": ESCENARIO}, ["escenario"]),
    _herramienta("evaluar_campana",
                 "Optimiza la campaña: hectáreas por cultivo, ventas por mes, crédito usado, valor presente y "
                 "precios sombra principales.",
                 {"escenario": ESCENARIO}, ["escenario"]),
    _herramienta("precios_sombra",
                 "Cuánto vale cada recurso escaso (capital, tierra, silo, crédito) y, quincena por quincena, "
                 "cuándo escasea el capital (tasa interna por encima de la de mercado).",
                 {"escenario": ESCENARIO}, ["escenario"]),
    _herramienta("sensibilidad",
                 "Recalcula la campaña para varios valores de un parámetro (por ejemplo, distintos plazos del "
                 "proveedor o distintos montos de crédito).",
                 {"escenario": ESCENARIO,
                  "parametro": {"type": "string", "enum": list(PARAMETROS_SENSIBILIDAD)},
                  "valores": {"type": "array", "items": {"type": "number"},
                              "minItems": 1, "maxItems": MAX_VALORES_SENSIBILIDAD}},
                 ["escenario", "parametro", "valores"]),
]
