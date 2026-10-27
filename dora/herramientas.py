"""Herramientas que usa el agente. Entrada y salida en JSON.

El modelo de lenguaje no calcula ni arma ecuaciones: completa los parámetros de
un escenario, que se validan acá, y lee los resultados que devuelve el motor.
Cada parámetro del escenario lleva su origen: lo dijo el productor, sale del
informe del MAGyP o es un supuesto del modelo.
"""
from __future__ import annotations

import json
from dataclasses import fields

from .escenario import CALENDARIO, MESES, QUINCENAS, Escenario, nombre_quincena
from .motor import optimizar

FUENTE_MAGYP = "MAGyP, márgenes jun-2026, sudeste de Buenos Aires"

# nombre -> (tipo, mínimo, máximo, unidad, descripción)
PARAMETROS = {
    "superficie_ha": (float, 1, 100_000, "ha", "Superficie agrícola disponible"),
    "cultivos": (list, None, None, "", f"Cultivos posibles, de esta lista: {', '.join(CALENDARIO)}"),
    "max_fraccion_cultivo": (float, 0.05, 1, "fracción", "Tope de rotación: máximo de la superficie con un mismo cultivo"),
    "tierra_arrendada": (bool, None, None, "", "True si la tierra se alquila (se suma el arrendamiento del MAGyP)"),
    "capital_propio_usd": (float, 0, 100_000_000, "USD", "Capital propio disponible al inicio de la campaña (mayo)"),
    "linea_credito_usd": (float, 0, 100_000_000, "USD", "Tope de la línea de crédito"),
    "tasa_credito_anual": (float, 0, 1, "fracción anual", "Tasa del crédito en dólares (0.10 = 10%)"),
    "tasa_colocacion_anual": (float, 0, 1, "fracción anual", "Lo que rinde la caja sobrante (0.04 = 4%)"),
    "plazo_insumos_quincenas": (int, 0, 12, "quincenas", "Plazo que da el proveedor de insumos (90 días = 6 quincenas)"),
    "recargo_plazo_insumos": (float, 0, 0.5, "fracción", "Recargo del proveedor por ese plazo (0.03 = 3%)"),
    "capacidad_almacenaje_t": (float, 0, 1_000_000, "t", "Capacidad de almacenaje propia (silo o silobolsa)"),
    "costo_almacenaje_usd_t_mes": (float, 0, 50, "USD/t/mes", "Costo de guardar una tonelada un mes"),
    "suba_mensual_precio": (float, -0.05, 0.05, "fracción por mes", "Cuánto sube el precio por mes después de la cosecha"),
    "precios": (dict, 1, 2_000, "USD/t", "Precio a cosecha por cultivo, si el productor lo da"),
    "rindes": (dict, 0.1, 20, "t/ha", "Rinde por cultivo, si el productor lo da"),
}
_SUPUESTOS = {f.name for f in fields(Escenario)} - {"precios", "rindes", "cultivos", "superficie_ha"}

PARAMETROS_SENSIBILIDAD = ("capital_propio_usd", "linea_credito_usd", "tasa_credito_anual", "plazo_insumos_quincenas",
                           "recargo_plazo_insumos", "capacidad_almacenaje_t", "superficie_ha", "suba_mensual_precio")
MAX_VALORES_SENSIBILIDAD = 10


class ErrorEscenario(ValueError):
    pass


def _validar(params: dict) -> tuple[Escenario, list[str]]:
    if not isinstance(params, dict):
        raise ErrorEscenario("El escenario tiene que ser un objeto JSON con parámetros.")
    errores = []
    limpio = {}
    for nombre, valor in params.items():
        if nombre not in PARAMETROS:
            errores.append(f"'{nombre}' no es un parámetro. Válidos: {', '.join(PARAMETROS)}.")
            continue
        tipo, minimo, maximo, unidad, _ = PARAMETROS[nombre]
        if tipo is bool:
            if not isinstance(valor, bool):
                errores.append(f"'{nombre}' tiene que ser true o false.")
            else:
                limpio[nombre] = valor
        elif tipo is list:
            if not isinstance(valor, list) or not valor or any(c not in CALENDARIO for c in valor):
                errores.append(f"'cultivos' tiene que ser una lista con elementos de: {', '.join(CALENDARIO)}.")
            else:
                limpio[nombre] = tuple(dict.fromkeys(valor))
        elif tipo is dict:
            if not isinstance(valor, dict):
                errores.append(f"'{nombre}' tiene que ser un objeto cultivo -> valor en {unidad}.")
                continue
            for c, v in valor.items():
                if c not in CALENDARIO:
                    errores.append(f"'{nombre}': '{c}' no es un cultivo conocido.")
                elif not isinstance(v, (int, float)) or isinstance(v, bool) or not minimo <= v <= maximo:
                    errores.append(f"'{nombre}.{c}' tiene que estar entre {minimo} y {maximo} {unidad}.")
            limpio[nombre] = {c: float(v) for c, v in valor.items() if c in CALENDARIO and isinstance(v, (int, float))}
        else:
            if not isinstance(valor, (int, float)) or isinstance(valor, bool):
                errores.append(f"'{nombre}' tiene que ser un número en {unidad}.")
            elif tipo is int and float(valor) != int(valor):
                errores.append(f"'{nombre}' tiene que ser un número entero de {unidad}.")
            elif not minimo <= valor <= maximo:
                errores.append(f"'{nombre}' = {valor} está fuera de rango: entre {minimo} y {maximo} {unidad}.")
            else:
                limpio[nombre] = tipo(valor)
    if errores:
        raise ErrorEscenario(" ".join(errores))
    return Escenario(**limpio), sorted(limpio)


def armar_escenario(escenario: dict) -> dict:
    """Valida el escenario y devuelve cada parámetro con su valor, unidad y origen."""
    esc, dados = _validar(escenario)
    salida = {}
    for nombre, (_, _, _, unidad, _) in PARAMETROS.items():
        if nombre in ("precios", "rindes"):
            continue
        valor = getattr(esc, nombre)
        salida[nombre] = {"valor": list(valor) if isinstance(valor, tuple) else valor, "unidad": unidad,
                          "origen": "productor" if nombre in dados else
                          ("supuesto del modelo" if nombre in _SUPUESTOS else "valor por defecto")}
    for c in esc.cultivos:
        salida[f"precio_{c}"] = {"valor": esc.precio(c), "unidad": "USD/t a cosecha",
                                 "origen": "productor" if c in esc.precios else FUENTE_MAGYP}
        salida[f"rinde_{c}"] = {"valor": esc.rinde(c), "unidad": "t/ha",
                                "origen": "productor" if c in esc.rindes else FUENTE_MAGYP}
        salida[f"cosecha_{c}"] = {"valor": nombre_quincena(CALENDARIO[c]["cosecha"]), "unidad": "quincena",
                                  "origen": "supuesto del modelo"}
    return {"escenario": salida}


def _ventas_por_mes(r) -> dict:
    out = {}
    for c, ventas in r.ventas.items():
        por_mes = {}
        for p, t in ventas.items():
            mes = f"{MESES[(p // 2) % 12]}{'' if p < 24 else ' (año 2)'}"
            por_mes[mes] = por_mes.get(mes, 0) + t
        if por_mes:
            out[c] = {m: round(t, 1) for m, t in por_mes.items()}
    return out


def evaluar_campana(escenario: dict) -> dict:
    """Optimiza la campaña y devuelve el plan y los resultados principales."""
    esc, _ = _validar(escenario)
    r = optimizar(esc)
    res = r.resumen()
    pico = max(range(QUINCENAS), key=lambda p: r.deuda[p])
    res.update({
        "ventas_t_por_mes": _ventas_por_mes(r),
        "credito_maximo_quincena": nombre_quincena(pico) if r.deuda[pico] > 1e-6 else None,
        "hectareas_sin_sembrar": round(esc.superficie_ha - sum(r.hectareas.values()), 1),
        "nota": "VAN y precios sombra en USD de hoy (mayo), descontados a la tasa de colocación.",
    })
    return res


def precios_sombra(escenario: dict) -> dict:
    """Valor de cada recurso escaso, y por quincena cuándo escasea el capital."""
    esc, _ = _validar(escenario)
    r = optimizar(esc)
    quincenas = []
    for p in range(QUINCENAS - 1):
        fila = {"quincena": nombre_quincena(p) + (" (año 2)" if p >= 24 else ""),
                "tasa_interna_anual": round(r.tasa_interna_anual[p], 4)}
        if r.precio_sombra_credito[p] > 1e-6:
            fila["valor_usd_por_dolar_extra_de_credito"] = round(r.precio_sombra_credito[p], 4)
        if r.precio_sombra_almacenaje[p] > 1e-6:
            fila["valor_usd_por_tonelada_extra_de_silo"] = round(r.precio_sombra_almacenaje[p], 2)
        quincenas.append(fila)
    return {
        "capital_propio": {"valor_usd_por_dolar_extra": round(r.precio_sombra_capital, 4),
                           "lectura": "lo que vale un dólar más de capital, por encima de colocarlo a la tasa de mercado"},
        "tierra": {"valor_usd_por_ha_extra": round(r.precio_sombra_tierra, 2)},
        "almacenaje": {"valor_usd_por_tonelada_extra": round(sum(r.precio_sombra_almacenaje), 2)},
        "linea_credito": {"valor_usd_por_dolar_extra": round(sum(r.precio_sombra_credito), 4)},
        "tasa_de_mercado_anual": esc.tasa_colocacion_anual,
        "por_quincena": quincenas,
    }


def sensibilidad(escenario: dict, parametro: str, valores: list) -> dict:
    """Recalcula la campaña para varios valores de un parámetro."""
    if parametro not in PARAMETROS_SENSIBILIDAD:
        raise ErrorEscenario(f"'{parametro}' no admite sensibilidad. Opciones: {', '.join(PARAMETROS_SENSIBILIDAD)}.")
    if not isinstance(valores, list) or not 1 <= len(valores) <= MAX_VALORES_SENSIBILIDAD:
        raise ErrorEscenario(f"'valores' tiene que ser una lista de 1 a {MAX_VALORES_SENSIBILIDAD} números.")
    esc, _ = _validar(escenario)
    filas = []
    for v in valores:
        variante, _ = _validar({**escenario, parametro: v})
        r = optimizar(variante)
        filas.append({parametro: v, "van_usd": round(r.van, 2),
                      "hectareas": {c: round(h, 1) for c, h in r.hectareas.items() if h > 1e-6},
                      "credito_maximo_usd": round(max(r.deuda), 2),
                      "precio_sombra_capital": round(r.precio_sombra_capital, 4)})
    return {"parametro": parametro, "resultados": filas}


HERRAMIENTAS = {
    "armar_escenario": armar_escenario,
    "evaluar_campana": evaluar_campana,
    "precios_sombra": precios_sombra,
    "sensibilidad": sensibilidad,
}


def ejecutar(nombre: str, argumentos: str | dict) -> str:
    """Punto de entrada del agente: recibe los argumentos que generó el modelo y devuelve JSON."""
    try:
        args = json.loads(argumentos) if isinstance(argumentos, str) else argumentos
        if nombre not in HERRAMIENTAS:
            raise ErrorEscenario(f"No existe la herramienta '{nombre}'. Opciones: {', '.join(HERRAMIENTAS)}.")
        salida = HERRAMIENTAS[nombre](**args)
    except (ErrorEscenario, TypeError, json.JSONDecodeError) as e:
        salida = {"error": str(e)}
    return json.dumps(salida, ensure_ascii=False)
