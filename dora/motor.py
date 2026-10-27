"""Motor de la campaña: un programa lineal por quincena.

Decide cuántas hectáreas sembrar de cada cultivo, cuándo vender, cuánto guardar
y cuánto crédito tomar, para maximizar el valor presente de la riqueza al final
de la campaña. Los duales de las restricciones son los precios sombra:

- caja de la quincena p (λ_p): cuánto vale hoy un dólar más disponible en p.
  Si no hay restricción de capital, λ_p = 1/(1+r)^p con r la tasa de colocación.
  La tasa interna entre p y p+1 es λ_p/λ_{p+1} - 1.
- capital propio: λ_0 - 1, lo que vale un dólar más de capital por encima de colocarlo.
- tierra, almacenaje y línea de crédito: lo que vale una unidad más de cada uno.

Se resuelve con HiGHS (scipy.optimize.linprog), que devuelve los duales de todas
las restricciones, incluidas las de una sola variable.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import linprog

from .escenario import CALENDARIO, QUINCENAS, Escenario, nombre_quincena, tasa_quincenal


@dataclass
class Resultado:
    estado: str
    van: float                                  # valor presente de la riqueza final, USD
    riqueza_final: float
    hectareas: dict[str, float]
    ventas: dict[str, dict[int, float]]         # cultivo -> quincena -> toneladas
    stock: dict[str, dict[int, float]]
    caja: list[float]                           # sobrante al final de cada quincena
    deuda: list[float]                          # crédito usado al final de cada quincena
    valor_caja: list[float]                     # λ_p
    tasa_interna_anual: list[float]             # tasa implícita entre p y p+1, anualizada
    precio_sombra_capital: float
    precio_sombra_tierra: float                 # USD de hoy por hectárea más
    precio_sombra_almacenaje: list[float]       # USD de hoy por tonelada más de capacidad, por quincena
    precio_sombra_credito: list[float]          # USD de hoy por dólar más de línea, por quincena

    def resumen(self) -> dict:
        def r(x, n=2):
            return round(float(x), n)
        q = range(len(self.caja))
        return {
            "estado": self.estado,
            "van_usd": r(self.van),
            "riqueza_final_usd": r(self.riqueza_final),
            "hectareas": {c: r(h, 1) for c, h in self.hectareas.items() if h > 1e-6},
            "credito_maximo_usd": r(max(self.deuda)),
            "precio_sombra_capital": r(self.precio_sombra_capital, 4),
            "precio_sombra_tierra_usd_ha": r(self.precio_sombra_tierra),
            "precio_sombra_almacenaje_usd_t": r(sum(self.precio_sombra_almacenaje)),
            "precio_sombra_credito": r(sum(self.precio_sombra_credito), 4),
            "quincenas_con_capital_escaso": [nombre_quincena(p) for p in q[:-1]
                                             if self.tasa_interna_anual[p] > 1e-3 + self._tasa_mercado],
        }


class _Indices:
    def __init__(self):
        self.n = 0
        self.nombres: list[str] = []

    def nueva(self, nombre: str) -> int:
        self.nombres.append(nombre)
        self.n += 1
        return self.n - 1


def optimizar(esc: Escenario) -> Resultado:
    T = QUINCENAS
    ri, rc = tasa_quincenal(esc.tasa_colocacion_anual), tasa_quincenal(esc.tasa_credito_anual)
    alm = esc.costo_almacenaje_usd_t_mes / 2
    idx = _Indices()

    ha = {c: idx.nueva(f"ha_{c}") for c in esc.cultivos}
    venta, stock = {}, {}
    for c in esc.cultivos:
        h = CALENDARIO[c]["cosecha"]
        for p in range(h, T):
            venta[c, p] = idx.nueva(f"venta_{c}_{p}")
            stock[c, p] = idx.nueva(f"stock_{c}_{p}")
    S = [idx.nueva(f"caja_{p}") for p in range(T)]
    D = [idx.nueva(f"deuda_{p}") for p in range(T)]

    # Objetivo: maximizar el valor presente de la riqueza final (linprog minimiza).
    descuento = (1 + ri) ** -(T - 1)
    obj = np.zeros(idx.n)
    obj[S[-1]], obj[D[-1]] = -descuento, descuento

    # Igualdades: caja de cada quincena y balance de stock de cada cultivo.
    A_eq, b_eq = [], []
    egresos = {c: esc.egresos_ha(c) for c in esc.cultivos}
    for p in range(T):
        fila = np.zeros(idx.n)
        fila[S[p]], fila[D[p]] = 1, -1
        if p > 0:
            fila[S[p - 1]], fila[D[p - 1]] = -(1 + ri), 1 + rc
        for c in esc.cultivos:
            fila[ha[c]] += egresos[c].get(p, 0.0)
            if (c, p) in venta:
                fila[venta[c, p]] = -esc.precio_neto(c, p)
                fila[stock[c, p]] = alm
        A_eq.append(fila)
        b_eq.append(esc.capital_propio_usd if p == 0 else 0.0)
    for c in esc.cultivos:
        h = CALENDARIO[c]["cosecha"]
        for p in range(h, T):
            fila = np.zeros(idx.n)
            fila[stock[c, p]], fila[venta[c, p]] = 1, 1
            if p == h:
                fila[ha[c]] = -esc.rinde(c)
            else:
                fila[stock[c, p - 1]] = -1
            A_eq.append(fila)
            b_eq.append(0.0)

    # Desigualdades: tierra, almacenaje por quincena, línea de crédito por quincena.
    A_ub, b_ub = [], []
    fila = np.zeros(idx.n)
    for c in esc.cultivos:
        fila[ha[c]] = 1
    A_ub.append(fila); b_ub.append(esc.superficie_ha)
    fila_alm = len(A_ub)
    for p in range(T):
        fila = np.zeros(idx.n)
        for c in esc.cultivos:
            if (c, p) in stock:
                fila[stock[c, p]] = 1
        A_ub.append(fila); b_ub.append(esc.capacidad_almacenaje_t)
    fila_cred = len(A_ub)
    for p in range(T):
        fila = np.zeros(idx.n)
        fila[D[p]] = 1
        A_ub.append(fila); b_ub.append(esc.linea_credito_usd)

    cotas = [(0, None)] * idx.n
    for c in esc.cultivos:
        cotas[ha[c]] = (0, esc.max_fraccion_cultivo * esc.superficie_ha)
        cotas[stock[c, T - 1]] = (0, 0)       # al final de la campaña no queda grano
    cotas[D[-1]] = (0, 0)                     # y el crédito está devuelto

    res = linprog(obj, A_ub=np.array(A_ub), b_ub=b_ub, A_eq=np.array(A_eq), b_eq=b_eq,
                  bounds=cotas, method="highs")
    if res.status != 0:
        raise RuntimeError(f"El programa no tiene solución: {res.message}")

    x = res.x
    # Los marginales son d(objetivo)/d(lado derecho); el objetivo es -VAN.
    lam = [-m for m in res.eqlin.marginals[:T]]
    ub = [-m for m in res.ineqlin.marginals]
    tasa = [(lam[p] / lam[p + 1]) ** 24 - 1 if lam[p + 1] > 1e-12 else float("inf") for p in range(T - 1)]

    resultado = Resultado(
        estado="optimo",
        van=-res.fun,
        riqueza_final=x[S[-1]] - x[D[-1]],
        hectareas={c: x[ha[c]] for c in esc.cultivos},
        ventas={c: {p: x[venta[c, p]] for (cc, p) in venta if cc == c and x[venta[c, p]] > 1e-6} for c in esc.cultivos},
        stock={c: {p: x[stock[c, p]] for (cc, p) in stock if cc == c and x[stock[c, p]] > 1e-6} for c in esc.cultivos},
        caja=[x[i] for i in S],
        deuda=[x[i] for i in D],
        valor_caja=lam,
        tasa_interna_anual=tasa,
        precio_sombra_capital=lam[0] - 1,
        precio_sombra_tierra=ub[0],
        precio_sombra_almacenaje=ub[fila_alm:fila_alm + T],
        precio_sombra_credito=ub[fila_cred:fila_cred + T],
    )
    resultado._tasa_mercado = esc.tasa_colocacion_anual
    return resultado
