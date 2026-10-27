import json

import pytest

from dora.esquemas import HERRAMIENTAS_ESQUEMA
from dora.herramientas import ejecutar
from dora.verificador import verificar

BASE = {"superficie_ha": 500, "capital_propio_usd": 50000, "linea_credito_usd": 100000}


def llamar(nombre, **args):
    return json.loads(ejecutar(nombre, json.dumps(args)))


def test_armar_escenario_marca_el_origen():
    r = llamar("armar_escenario", escenario={**BASE, "rindes": {"soja": 3.1}})["escenario"]
    assert r["capital_propio_usd"] == {"valor": 50000.0, "unidad": "USD", "origen": "productor"}
    assert r["rinde_soja"]["origen"] == "productor" and r["rinde_soja"]["valor"] == 3.1
    assert r["rinde_trigo"]["origen"].startswith("MAGyP")
    assert r["suba_mensual_precio"]["origen"] == "supuesto del modelo"


@pytest.mark.parametrize("escenario, texto", [
    ({"superficie_ha": -5}, "fuera de rango"),
    ({"hectareas": 500}, "no es un parámetro"),
    ({"cultivos": ["arroz"]}, "cultivos"),
    ({"plazo_insumos_quincenas": 2.5}, "entero"),
    ({"tierra_arrendada": "si"}, "true o false"),
    ({"rindes": {"soja": 50}}, "entre"),
])
def test_rechaza_entradas_invalidas(escenario, texto):
    r = llamar("evaluar_campana", escenario=escenario)
    assert texto in r["error"]


def test_herramienta_inexistente_y_json_roto():
    assert "No existe" in json.loads(ejecutar("calcular", "{}"))["error"]
    assert "error" in json.loads(ejecutar("evaluar_campana", "{no es json"))


def test_evaluar_y_precios_sombra_coinciden():
    ev = llamar("evaluar_campana", escenario=BASE)
    ps = llamar("precios_sombra", escenario=BASE)
    assert ev["precio_sombra_capital"] == ps["capital_propio"]["valor_usd_por_dolar_extra"]
    assert ev["credito_maximo_usd"] > 0 and ev["credito_maximo_quincena"]
    assert len(ps["por_quincena"]) == 29


def test_sensibilidad_limita_valores_y_parametros():
    r = llamar("sensibilidad", escenario=BASE, parametro="capital_propio_usd", valores=[50000, 150000])
    assert r["resultados"][1]["van_usd"] > r["resultados"][0]["van_usd"]
    assert "no admite" in llamar("sensibilidad", escenario=BASE, parametro="cultivos", valores=[1])["error"]
    assert "lista" in llamar("sensibilidad", escenario=BASE, parametro="superficie_ha", valores=list(range(11)))["error"]


def test_esquemas_cubren_las_herramientas():
    nombres = {h["function"]["name"] for h in HERRAMIENTAS_ESQUEMA}
    assert nombres == {"armar_escenario", "evaluar_campana", "precios_sombra", "sensibilidad"}


# ---------------------------------------------------------------- verificador
SALIDA = {"van_usd": 88186.6, "precio_sombra_capital": 0.1608, "credito_maximo_usd": 100000.0,
          "hectareas": {"trigo": 121.7, "soja": 250.0}, "tasa_de_mercado_anual": 0.04}


@pytest.mark.parametrize("texto", [
    "El valor presente es de USD 88.186,6.",
    "El valor presente es de 88.187 dólares.",
    "Unos 88 mil dólares de valor presente.",
    "Each extra dollar of capital is worth 16% more; that is 16 centavos.",
    "Sembrá 121,7 ha de trigo y 250 de soja; el crédito llega a 100.000 USD.",
    "La tasa de mercado es 4%.",
    "1. Sembrá trigo.\n2. Guardá la soja.",
    "En la 1ª quincena de julio de 2026 falta capital.",
    "Vos dijiste 300 hectáreas.",
])
def test_verificador_acepta_numeros_con_respaldo(texto):
    assert verificar(texto, [json.dumps(SALIDA)], ["Tengo 300 hectáreas"]) == []


@pytest.mark.parametrize("texto, inventado", [
    ("El valor presente es de USD 95.000.", "95.000"),
    ("Cada dólar de capital rinde 22%.", "22%"),
    ("Sembrá 130 ha de trigo.", "130"),
    ("Sumando, trigo y soja dan 371,7 ha.", "371,7"),
])
def test_verificador_detecta_numeros_inventados(texto, inventado):
    problemas = verificar(texto, [SALIDA], [])
    assert [p.texto for p in problemas] == [inventado]
