"""Verificador de números de las respuestas del agente.

Regla: todo número de la respuesta tiene que estar en lo que devolvieron las
herramientas o en lo que escribió el productor. El modelo explica; no calcula.

Reconoce cómo se escriben los números en castellano y en inglés ("1.250,5",
"1,250.5", "16%", "92 mil", "1,2 millones", "16 centavos") y los compara con la
precisión con que están escritos: "88 mil" respalda 88.186,6.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

_NUM = r"\d{1,3}(?:[.,]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?"
_PATRON = re.compile(
    rf"(?<![\w.,])(?P<num>{_NUM})(?![ºª°])\s*(?P<escala>millones|millón|mil\b|M\b|k\b|centavos?)?\s*(?P<pct>%)?",
    re.IGNORECASE)
_ESCALAS = {"millones": 1e6, "millón": 1e6, "m": 1e6, "mil": 1e3, "k": 1e3, "centavos": 0.01, "centavo": 0.01}


@dataclass
class NumeroSinRespaldo:
    texto: str
    contexto: str


def _numeros_de(valor, salida: list[float]) -> None:
    if isinstance(valor, bool):
        return
    if isinstance(valor, (int, float)):
        salida.append(abs(float(valor)))
    elif isinstance(valor, str):
        for m in re.finditer(r"\d+(?:\.\d+)?", valor):
            salida.append(float(m.group()))
    elif isinstance(valor, dict):
        for k, v in valor.items():
            _numeros_de(k, salida)
            _numeros_de(v, salida)
    elif isinstance(valor, (list, tuple)):
        for v in valor:
            _numeros_de(v, salida)


def respaldo(resultados: list, textos_usuario: list[str]) -> list[float]:
    """Todos los números disponibles: salidas de herramientas (JSON o dict) y mensajes del productor."""
    numeros: list[float] = []
    for r in resultados:
        if isinstance(r, str):
            try:
                r = json.loads(r)
            except json.JSONDecodeError:
                pass
        _numeros_de(r, numeros)
    for t in textos_usuario:
        for m in _PATRON.finditer(t):
            numeros.extend(v * _ESCALAS.get((m.group("escala") or "").lower(), 1) for v, _ in _lecturas(m.group("num")))
    return numeros


def _lecturas(s: str) -> list[tuple[float, int]]:
    """Valores posibles de un número escrito y cuántos decimales muestra."""
    if "." in s and "," in s:                       # el último separador es el decimal
        dec = "," if s.rfind(",") > s.rfind(".") else "."
        entero, _, frac = s.replace("." if dec == "," else ",", "").partition(dec)
        return [(float(f"{entero}.{frac}"), len(frac))]
    sep = "." if "." in s else "," if "," in s else None
    if sep is None:
        return [(float(s), 0)]
    partes = s.split(sep)
    opciones = []
    if all(len(p) == 3 for p in partes[1:]):        # 1.250 o 1,250: miles
        opciones.append((float("".join(partes)), 0))
    if len(partes) == 2:                            # 0,16 o 0.16: decimal
        opciones.append((float(f"{partes[0]}.{partes[1]}"), len(partes[1])))
    return opciones


def _es_numeracion(texto: str, ini: int, fin: int) -> bool:
    inicio_linea = texto.rfind("\n", 0, ini) + 1
    return texto[inicio_linea:ini].strip(" *#>-") == "" and re.match(r"[.)]\s", texto[fin:fin + 2]) is not None


def verificar(texto: str, resultados: list, textos_usuario: list[str]) -> list[NumeroSinRespaldo]:
    disponibles = respaldo(resultados, textos_usuario)
    problemas = []
    for m in _PATRON.finditer(texto):
        ini, fin = m.start("num"), m.end("num")
        crudo = m.group("num")
        if _es_numeracion(texto, ini, fin):
            continue
        if re.fullmatch(r"(19|20)\d{2}", crudo) and not m.group("escala") and not m.group("pct"):
            continue                                # un año
        factor = _ESCALAS.get((m.group("escala") or "").lower(), 1)
        ok = False
        for valor, decimales in _lecturas(crudo):
            v = valor * factor
            tol = 10 ** -decimales * factor         # una unidad del último dígito escrito (redondeo o truncado)
            candidatos = [(v, tol), (v / 100, tol / 100)] if m.group("pct") else [(v, tol)]
            if any(abs(n - c) <= t + 1e-9 for c, t in candidatos for n in disponibles):
                ok = True
                break
        if not ok:
            problemas.append(NumeroSinRespaldo(m.group().strip(),
                                               texto[max(0, ini - 40):fin + 40].replace("\n", " ").strip()))
    return problemas


def mensaje_para_el_modelo(problemas: list[NumeroSinRespaldo]) -> str:
    lista = "\n".join(f'- "{p.texto}" en: …{p.contexto}…' for p in problemas)
    return ("Tu respuesta tiene números que no salen de ninguna herramienta ni de lo que dijo el productor:\n"
            f"{lista}\nNo calcules: usá solo números que devolvieron las herramientas (podés redondearlos), "
            "o llamá a una herramienta que los calcule. Reescribí la respuesta.")
