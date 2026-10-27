import json

import pytest

from dora.schemas import TOOL_SCHEMAS
from dora.tools import run_tool
from dora.verifier import verify

BASE = {"area_ha": 500, "own_capital_usd": 50000, "credit_line_usd": 100000}


def call(name, **args):
    return json.loads(run_tool(name, json.dumps(args)))


def test_build_scenario_marks_the_origin():
    r = call("build_scenario", scenario={**BASE, "yields": {"soybean": 3.1}})["scenario"]
    assert r["own_capital_usd"] == {"value": 50000.0, "unit": "USD", "origin": "farmer"}
    assert r["yield_soybean"]["origin"] == "farmer" and r["yield_soybean"]["value"] == 3.1
    assert r["yield_wheat"]["origin"].startswith("MAGyP")
    assert r["monthly_price_rise"]["origin"] == "model assumption"


@pytest.mark.parametrize("scenario, text", [
    ({"area_ha": -5}, "out of range"),
    ({"hectares": 500}, "is not a parameter"),
    ({"crops": ["rice"]}, "crops"),
    ({"input_payment_delay_fortnights": 2.5}, "whole number"),
    ({"rented_land": "yes"}, "true or false"),
    ({"yields": {"soybean": 50}}, "between"),
])
def test_rejects_invalid_input(scenario, text):
    assert text in call("evaluate_season", scenario=scenario)["error"]


def test_unknown_tool_and_broken_json():
    assert "no tool" in json.loads(run_tool("calculate", "{}"))["error"]
    assert "error" in json.loads(run_tool("evaluate_season", "{not json"))


def test_evaluate_and_shadow_prices_agree():
    ev = call("evaluate_season", scenario=BASE)
    sp = call("shadow_prices", scenario=BASE)
    assert ev["capital_shadow_price"] == sp["own_capital"]["usd_per_extra_dollar"]
    assert ev["max_credit_usd"] > 0 and ev["max_credit_fortnight"]
    assert len(sp["by_fortnight"]) == 29


def test_shadow_prices_usd_today_per_dollar():
    from dora.scenario import fortnightly_rate
    # With plenty of capital, cash value equals (1 + r)^(-p)
    sp = call("shadow_prices", scenario={"own_capital_usd": 10_000_000, "credit_line_usd": 10_000_000})
    r = fortnightly_rate(sp["market_rate_annual"])
    for p, row in enumerate(sp["by_fortnight"]):
        assert "usd_today_per_dollar" in row
        expected = (1.0 + r) ** (-p)
        assert row["usd_today_per_dollar"] == pytest.approx(expected, rel=1e-9)


def test_sensitivity_limits_values_and_parameters():
    r = call("sensitivity", scenario=BASE, parameter="own_capital_usd", values=[50000, 150000])
    assert r["results"][1]["npv_usd"] > r["results"][0]["npv_usd"]
    assert "does not support" in call("sensitivity", scenario=BASE, parameter="crops", values=[1])["error"]
    assert "list" in call("sensitivity", scenario=BASE, parameter="area_ha", values=list(range(11)))["error"]


def test_schemas_cover_the_tools():
    assert {t["function"]["name"] for t in TOOL_SCHEMAS} == {
        "build_scenario", "evaluate_season", "shadow_prices", "sensitivity"}


# ------------------------------------------------------------------ verifier
OUTPUT = {"npv_usd": 88186.6, "capital_shadow_price": 0.1608, "max_credit_usd": 100000.0,
          "hectares": {"wheat": 121.7, "soybean": 250.0}, "market_rate_annual": 0.04, "yield": 1.6}


@pytest.mark.parametrize("text", [
    "El valor presente es de USD 88.186,6.",
    "El valor presente es de 88.187 dólares.",
    "Unos 88 mil dólares de valor presente.",
    "The present value is about 88k dollars.",
    "Cada dólar extra de capital vale 16% más: 16 centavos.",
    "Sembrá 121,7 ha de trigo y 250 de soja; el crédito llega a 100.000 USD.",
    "La tasa de mercado es 4%.",
    "El rinde es 1,6 t/ha.",
    "1. Sembrá trigo.\n2. Guardá la soja.",
    "En la 1ª quincena de julio de 2026 falta capital.",
    "Vos dijiste 300 hectáreas.",
])
def test_verifier_accepts_supported_numbers(text):
    assert verify(text, [json.dumps(OUTPUT)], ["Tengo 300 hectáreas"]) == []


@pytest.mark.parametrize("text, invented", [
    ("El valor presente es de USD 95.000.", "95.000"),
    ("Cada dólar de capital rinde 22%.", "22%"),
    ("Sembrá 130 ha de trigo.", "130"),
    ("Sumando, trigo y soja dan 371,7 ha.", "371,7"),
    ("El rinde es 2 t/ha.", "2"),                      # 1.6 written as 2: not accepted
    ("El valor presente es de 88.190 dólares.", "88.190"),
])
def test_verifier_flags_invented_numbers(text, invented):
    assert [p.text for p in verify(text, [OUTPUT], [])] == [invented]
