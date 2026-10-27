"""Escenario de una campaña agrícola, por quincena.

La campaña empieza la primera quincena de mayo (quincena 0) y dura 30 quincenas
(hasta julio del año siguiente), para que la cosecha de gruesa tenga tiempo de
guardarse y venderse.

Los costos y rindes son los del informe de márgenes del MAGyP (ver
datos/magyp_sudeste_2026-06.json). El calendario de pagos y cosechas es un
supuesto razonable para el sudeste bonaerense y se puede cambiar por escenario.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

DATOS = Path(__file__).parent / "datos" / "magyp_sudeste_2026-06.json"
QUINCENAS = 30
MESES = ["may", "jun", "jul", "ago", "sep", "oct", "nov", "dic", "ene", "feb", "mar", "abr"]


def nombre_quincena(p: int) -> str:
    mes = MESES[(p // 2) % 12]
    return f"{'1ª' if p % 2 == 0 else '2ª'} {mes}"


# Calendario supuesto (quincena en que se paga cada rubro y en que se cosecha).
# Las fracciones de un rubro suman 1.
CALENDARIO = {
    "trigo":   {"siembra": 3,  "cosecha": 15, "fertilizantes": {3: 0.5, 8: 0.5},   "fitosanitarios": {10: 1.0}},
    "maiz":    {"siembra": 11, "cosecha": 22, "fertilizantes": {11: 0.5, 14: 0.5}, "fitosanitarios": {12: 1.0}},
    "soja":    {"siembra": 13, "cosecha": 23, "fertilizantes": {13: 1.0},          "fitosanitarios": {16: 1.0}},
    "girasol": {"siembra": 11, "cosecha": 19, "fertilizantes": {11: 1.0},          "fitosanitarios": {13: 1.0}},
}
INSUMOS = ("semillas", "fertilizantes", "fitosanitarios")


def tasa_quincenal(anual: float) -> float:
    return (1 + anual) ** (1 / 24) - 1


@dataclass
class Escenario:
    superficie_ha: float = 500.0
    cultivos: tuple[str, ...] = ("trigo", "maiz", "soja", "girasol")
    max_fraccion_cultivo: float = 0.5          # rotación: ningún cultivo más de la mitad
    tierra_arrendada: bool = False             # con los márgenes de jun-2026, ningún cultivo paga el alquiler
    capital_propio_usd: float = 50_000.0
    linea_credito_usd: float = 100_000.0
    tasa_credito_anual: float = 0.10           # préstamo en dólares
    tasa_colocacion_anual: float = 0.04        # lo que rinde la caja sobrante
    plazo_insumos_quincenas: int = 0           # el proveedor cobra los insumos k quincenas después
    recargo_plazo_insumos: float = 0.0         # recargo por ese plazo (0.03 = 3%)
    capacidad_almacenaje_t: float = 1_000.0
    costo_almacenaje_usd_t_mes: float = 2.0
    suba_mensual_precio: float = 0.008         # el precio sube después de la cosecha (supuesto)
    precios: dict[str, float] = field(default_factory=dict)   # USD/t a cosecha; si falta, el del MAGyP
    rindes: dict[str, float] = field(default_factory=dict)    # t/ha; si falta, el del MAGyP

    def __post_init__(self):
        datos = json.loads(DATOS.read_text(encoding="utf-8"))["cultivos"]
        desconocidos = set(self.cultivos) - set(datos)
        if desconocidos:
            raise ValueError(f"Cultivos sin datos: {sorted(desconocidos)}. Disponibles: {sorted(datos)}")
        self.datos = {c: datos[c] for c in self.cultivos}

    # ------------------------------------------------------------------
    def precio(self, c: str) -> float:
        return self.precios.get(c, self.datos[c]["precio"])

    def rinde(self, c: str) -> float:
        return self.rindes.get(c, self.datos[c]["rinde"])

    def precio_neto(self, c: str, p: int) -> float:
        """USD/t que cobra el productor si vende en la quincena p (descontada la comercialización)."""
        meses = (p - CALENDARIO[c]["cosecha"]) / 2
        comercializacion_t = self.datos[c]["comercializacion_cosecha"] / self.datos[c]["rinde"]
        return self.precio(c) * (1 + self.suba_mensual_precio) ** meses - comercializacion_t

    def egresos_ha(self, c: str) -> dict[int, float]:
        """USD por hectárea que se pagan en cada quincena (sin comercialización)."""
        d, cal = self.datos[c], CALENDARIO[c]
        egresos: dict[int, float] = {}

        def sumar(p: int, monto: float):
            egresos[p] = egresos.get(p, 0.0) + monto

        plazo = self.plazo_insumos_quincenas
        recargo = 1 + self.recargo_plazo_insumos if plazo else 1.0
        sumar(cal["siembra"], d["labores"])
        sumar(min(cal["siembra"] + plazo, QUINCENAS - 1), d["semillas"] * recargo)
        for rubro in ("fertilizantes", "fitosanitarios"):
            for p, frac in cal[rubro].items():
                sumar(min(p + plazo, QUINCENAS - 1), d[rubro] * frac * recargo)
        if self.tierra_arrendada:
            sumar(0, d["arrendamiento"])           # el alquiler se paga por adelantado
            estructura = d["estructura_arrendado"]
        else:
            estructura = d["estructura_propio"]
        meses_campana = range(0, cal["cosecha"] + 1)
        for p in meses_campana:
            sumar(p, estructura / len(meses_campana))
        return egresos
