"""Cada precio sombra se verifica contra la perturbación: se mueve el recurso una
unidad hacia arriba y hacia abajo. El VAN es cóncavo en cada recurso, así que el
dual tiene que quedar entre la derivada por derecha y la derivada por izquierda
(si el óptimo no está en un quiebre, las dos coinciden con el dual)."""
from dataclasses import replace

import pytest

from dora.escenario import Escenario
from dora.motor import optimizar


def entre_derivadas(esc, campo, dual, delta=1.0, tol=1e-4):
    base = optimizar(esc).van
    arriba = optimizar(replace(esc, **{campo: getattr(esc, campo) + delta})).van
    abajo = optimizar(replace(esc, **{campo: getattr(esc, campo) - delta})).van
    por_derecha, por_izquierda = (arriba - base) / delta, (base - abajo) / delta
    return por_derecha - tol <= dual <= por_izquierda + tol


@pytest.fixture
def escaso():
    """Capital y crédito cortos: la restricción de capital muerde."""
    return Escenario(capital_propio_usd=50_000, linea_credito_usd=100_000)


def test_capital_contra_perturbacion(escaso):
    r = optimizar(escaso)
    assert r.precio_sombra_capital > 0.01
    assert entre_derivadas(escaso, "capital_propio_usd", r.valor_caja[0])


def test_credito_contra_perturbacion(escaso):
    r = optimizar(escaso)
    assert sum(r.precio_sombra_credito) > 0.01
    assert entre_derivadas(escaso, "linea_credito_usd", sum(r.precio_sombra_credito))


def test_tierra_contra_perturbacion():
    esc = Escenario(capital_propio_usd=2_000_000)     # capital de sobra: lo escaso es la tierra
    r = optimizar(esc)
    assert r.precio_sombra_tierra > 0
    # El tope de rotación es una fracción de la superficie: se mantiene fijo en hectáreas
    # para mover solo la restricción de tierra.
    tope = esc.max_fraccion_cultivo * esc.superficie_ha
    van = {s: optimizar(replace(esc, superficie_ha=s, max_fraccion_cultivo=tope / s)).van for s in (499, 500, 501)}
    assert van[501] - van[500] - 1e-4 <= r.precio_sombra_tierra <= van[500] - van[499] + 1e-4


def test_almacenaje_contra_perturbacion():
    esc = Escenario(capital_propio_usd=2_000_000, capacidad_almacenaje_t=200, suba_mensual_precio=0.03)
    r = optimizar(esc)
    assert sum(r.precio_sombra_almacenaje) > 0
    assert entre_derivadas(esc, "capacidad_almacenaje_t", sum(r.precio_sombra_almacenaje))


def test_sin_racionamiento_la_tasa_interna_es_la_de_mercado():
    esc = Escenario(capital_propio_usd=5_000_000)
    r = optimizar(esc)
    assert r.precio_sombra_capital == pytest.approx(0, abs=1e-9)
    assert all(t == pytest.approx(esc.tasa_colocacion_anual, abs=1e-9) for t in r.tasa_interna_anual)
    assert max(r.deuda) == pytest.approx(0, abs=1e-6)


def test_capital_escaso_sube_la_tasa_interna(escaso):
    r = optimizar(escaso)
    assert max(r.tasa_interna_anual) > escaso.tasa_colocacion_anual + 0.01
    assert r.resumen()["quincenas_con_capital_escaso"]


def test_plazo_de_insumos_sin_recargo_no_empeora(escaso):
    base = optimizar(escaso).van
    con_plazo = optimizar(replace(escaso, plazo_insumos_quincenas=6)).van
    assert con_plazo >= base - 1e-6


def test_respeta_rotacion_y_vende_todo():
    esc = Escenario(capital_propio_usd=2_000_000)
    r = optimizar(esc)
    for c, h in r.hectareas.items():
        assert h <= esc.max_fraccion_cultivo * esc.superficie_ha + 1e-6
        if h > 1e-6:
            assert sum(r.ventas[c].values()) == pytest.approx(h * esc.rinde(c), rel=1e-6)
