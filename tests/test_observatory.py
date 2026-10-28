"""Acceptance tests for SPEC-07: regional observatory and freight to port. No network calls."""
import json
from pathlib import Path
from types import SimpleNamespace as NS
import pytest

from dora.engine import FORTNIGHTS, optimize
from dora.observatory import run_observatory
from dora.scenario import Scenario

ROOT = Path(__file__).resolve().parent.parent


class ScriptedModel:
    """Returns scripted messages in order for agent completions."""

    def __init__(self, script):
        self.script = list(script)
        self.seen = []
        self.chat = NS(completions=NS(create=self.create))

    def create(self, model, messages, tools):
        self.seen.append(list(messages))
        step = self.script.pop(0)
        msg = NS(content=None, tool_calls=step) if isinstance(step, list) else NS(content=step, tool_calls=None)
        return NS(choices=[NS(message=msg)])


# 1. 10 USD/t more of farmer's freight lowers net_price by exactly 10 at every fortnight,
#    for a crop with and without a price curve. (SPEC-17: freight_usd_t = 0 no longer means "no
#    freight": it means "use the freight inside the source's marketing cost", so the test compares
#    two freights given by the farmer.)
def test_freight_lowers_net_price_by_exact_amount():
    # Without price curve
    sc0 = Scenario(freight_usd_t=10.0)
    sc10 = Scenario(freight_usd_t=20.0)
    for crop in sc0.crops:
        h = sc0.calendar[crop]["harvest"]
        for p in range(h, FORTNIGHTS):
            diff = sc0.net_price(crop, p) - sc10.net_price(crop, p)
            assert diff == pytest.approx(10.0), f"Mismatch without curve for {crop} at p={p}: {diff}"

    # With price curve
    sc_c0 = Scenario(freight_usd_t=10.0, price_curve_source="argentina_latest")
    sc_c10 = Scenario(freight_usd_t=20.0, price_curve_source="argentina_latest")
    for crop in sc_c0.crops:
        h = sc_c0.calendar[crop]["harvest"]
        for p in range(h, FORTNIGHTS):
            diff = sc_c0.net_price(crop, p) - sc_c10.net_price(crop, p)
            assert diff == pytest.approx(10.0), f"Mismatch with curve for {crop} at p={p}: {diff}"


# 2. With all else equal, a region with higher freight has a lower or equal NPV.
def test_higher_freight_lowers_or_equals_npv():
    sc_low_freight = Scenario(freight_usd_t=5.0)
    sc_high_freight = Scenario(freight_usd_t=25.0)
    res_low = optimize(sc_low_freight)
    res_high = optimize(sc_high_freight)
    assert res_low.npv >= res_high.npv, f"Expected {res_low.npv} >= {res_high.npv}"


# 3. run_observatory over Southeast and Pergamino with mocked prices
#    returns both regions with every field.
def test_run_observatory_southeast_and_pergamino(tmp_path):
    res = run_observatory(
        regions=["southeast_buenos_aires", "pampas_core"],
        output_dir=tmp_path,
        save=True,
    )
    assert "regions" in res
    assert "southeast_buenos_aires" in res["regions"]
    assert "pampas_core" in res["regions"]

    required_fields = [
        "name", "port", "distance_km", "freight_usd_t", "npv_usd", "npv_per_ha",
        "return_on_capital", "return_on_capital_pct", "capital_shadow_price",
        "scarce_fortnights", "land_shadow_price_usd_ha", "storage_shadow_price_usd_t",
        "crop_mix", "price_source", "internal_rates", "coords"
    ]

    for reg_key in ("southeast_buenos_aires", "pampas_core"):
        reg_data = res["regions"][reg_key]
        for field in required_fields:
            assert field in reg_data, f"Missing field '{field}' in region '{reg_key}'"
        assert reg_data["npv_usd"] > 0
        assert reg_data["return_on_capital"] > 0
        assert len(reg_data["internal_rates"]) == FORTNIGHTS - 1


# 4. The output JSON is valid and has a date and the source of every price.
def test_output_json_valid_with_date_and_sources(tmp_path):
    run_observatory(
        regions=["southeast_buenos_aires", "pampas_core"],
        output_dir=tmp_path,
        save=True,
    )
    latest_path = tmp_path / "latest.json"
    assert latest_path.is_file(), "latest.json must be created"

    with open(latest_path, encoding="utf-8") as f:
        data = json.load(f)

    assert "date" in data
    assert "timestamp" in data
    assert "regions" in data

    for reg_key, reg_data in data["regions"].items():
        assert "price_source" in reg_data
        assert len(reg_data["price_source"]) > 0


# 5. With the scripted model, a commentary with an invented number is not published,
#    and the numbers still are.
def test_scripted_model_commentary_with_invented_number_blocks_publication(tmp_path):
    # Model introduces a hallucinated percentage 999.9%
    bad_script = ["In Southeast Buenos Aires return is 999.9% which is unrealistic."]
    client_bad = ScriptedModel(bad_script)

    res_bad = run_observatory(
        regions=["southeast_buenos_aires", "pampas_core"],
        client=client_bad,
        output_dir=tmp_path,
        save=False,
    )
    # Commentary must be blocked
    assert res_bad["commentary"] is None
    # Numbers are still published
    assert "southeast_buenos_aires" in res_bad["regions"]
    assert res_bad["regions"]["southeast_buenos_aires"]["npv_usd"] > 0

    # Model using strictly valid numbers from the report
    se_data = res_bad["regions"]["southeast_buenos_aires"]
    valid_ret = se_data["return_on_capital_pct"]
    good_script = [f"Southeast Buenos Aires presents a return on capital of {valid_ret}% with port Quequén."]
    client_good = ScriptedModel(good_script)

    res_good = run_observatory(
        regions=["southeast_buenos_aires", "pampas_core"],
        client=client_good,
        output_dir=tmp_path,
        save=False,
    )
    assert res_good["commentary"] is not None
    assert str(valid_ret) in res_good["commentary"]
