import json
from pathlib import Path
import pytest

from dora.engine import optimize
from dora.prices import (
    BUSHELS_PER_TONNE,
    available_curves,
    cents_per_bushel_to_usd_per_tonne,
    load_curve,
)
from dora.scenario import CALENDAR, FORTNIGHTS, Scenario, fortnight_month
from dora.tools import run_tool


def call(name, **args):
    return json.loads(run_tool(name, json.dumps(args)))


# 1. Conversion: 1000 cents/bu of soybean = 367.44 USD/t (rel 1e-6)
def test_conversion():
    assert cents_per_bushel_to_usd_per_tonne("soybean", 1000) == pytest.approx(367.44, rel=1e-6)
    # Check corn and wheat as well
    assert cents_per_bushel_to_usd_per_tonne("corn", 100) == pytest.approx(39.368, rel=1e-6)
    assert cents_per_bushel_to_usd_per_tonne("wheat", 100) == pytest.approx(36.744, rel=1e-6)
    with pytest.raises(ValueError, match="Unknown crop"):
        cents_per_bushel_to_usd_per_tonne("sunflower", 100)


# 2. Interpolation: with a curve {May: 300, Jul: 320} starting in May,
# fortnight 0 = 300, fortnight 2 (early Jun) = 310, fortnight 4 = 320, fortnight 10 = 320.
def test_interpolation():
    assert fortnight_month("2026-05", 0) == "2026-05"
    assert fortnight_month("2026-05", 1) == "2026-05"
    assert fortnight_month("2026-05", 2) == "2026-06"
    assert fortnight_month("2026-05", 4) == "2026-07"
    assert fortnight_month("2026-05", 24) == "2027-05"

    sc = Scenario(
        season_start="2026-05",
        price_curve={"soybean": {"2026-05": 300.0, "2026-07": 320.0}},
    )
    assert sc.curve_price("soybean", 0) == pytest.approx(300.0)
    assert sc.curve_price("soybean", 1) == pytest.approx(305.0)
    assert sc.curve_price("soybean", 2) == pytest.approx(310.0)
    assert sc.curve_price("soybean", 3) == pytest.approx(315.0)
    assert sc.curve_price("soybean", 4) == pytest.approx(320.0)
    assert sc.curve_price("soybean", 10) == pytest.approx(320.0)

    # Before first month
    sc2 = Scenario(
        season_start="2026-05",
        price_curve={"soybean": {"2026-06": 310.0, "2026-07": 320.0}},
    )
    assert sc2.curve_price("soybean", 0) == pytest.approx(310.0)

    # Crop without curve returns None
    assert sc.curve_price("corn", 0) is None


# 3. Equivalence: a flat curve equal to the MAGyP price for every crop
# gives the same NPV as monthly_price_rise=0 (rel 1e-9).
def test_equivalence():
    sc_base = Scenario(monthly_price_rise=0.0)
    r_base = optimize(sc_base)

    curve = {c: {"2026-05": sc_base.price(c), "2027-07": sc_base.price(c)} for c in sc_base.crops}
    sc_curve = Scenario(price_curve=curve)
    r_curve = optimize(sc_curve)

    assert r_curve.npv == pytest.approx(r_base.npv, rel=1e-9)
    for c in sc_base.crops:
        assert r_curve.hectares[c] == pytest.approx(r_base.hectares[c], rel=1e-9)


# 4. Storage responds to the curve:
# - With plenty of capital, a soybean curve that rises 15 USD/t per month after harvest,
#   and storage_capacity_t=200: storage is used and the total storage shadow price is > 0.
# - With a flat curve, storage is not used.
def test_storage_responds_to_curve():
    # Soybean harvest is fortnight 23 (late April 2027)
    curve_rising = {
        "soybean": {
            "2026-05": 330.0,
            "2027-04": 330.0,
            "2027-05": 345.0,
            "2027-06": 360.0,
            "2027-07": 375.0,
        }
    }
    sc_rising = Scenario(
        own_capital_usd=500_000.0,
        storage_capacity_t=200.0,
        price_curve=curve_rising,
    )
    r_rising = optimize(sc_rising)
    total_stored = sum(sum(st.values()) for st in r_rising.stock.values())
    total_storage_shadow = sum(r_rising.storage_shadow_price)
    assert total_stored > 0
    assert total_storage_shadow > 0

    # Flat curve: storage is not used
    curve_flat = {
        "soybean": {
            "2026-05": 330.0,
            "2027-07": 330.0,
        }
    }
    sc_flat = Scenario(
        own_capital_usd=500_000.0,
        storage_capacity_t=200.0,
        price_curve=curve_flat,
    )
    r_flat = optimize(sc_flat)
    total_stored_flat = sum(sum(st.values()) for st in r_flat.stock.values())
    total_storage_shadow_flat = sum(r_flat.storage_shadow_price)
    assert total_stored_flat == 0
    assert total_storage_shadow_flat == 0


# 5. Basis: a basis of −20 on soybean lowers net_price by exactly 20 at every fortnight.
def test_basis():
    curve = {"soybean": {"2026-05": 300.0, "2027-07": 350.0}}
    sc_nobasis = Scenario(price_curve=curve)
    sc_basis = Scenario(price_curve=curve, basis_usd_t={"soybean": -20.0})

    for p in range(FORTNIGHTS):
        assert sc_basis.net_price("soybean", p) == pytest.approx(
            sc_nobasis.net_price("soybean", p) - 20.0, rel=1e-9
        )
    assert sc_basis.price("soybean") == pytest.approx(sc_nobasis.price("soybean") - 20.0, rel=1e-9)


# 6. Validation: an unknown price_curve_source returns an error naming the available ones;
# a basis out of range is rejected.
def test_validation(tmp_path):
    avail = available_curves()
    err_unknown = call("evaluate_season", scenario={"price_curve_source": "nonexistent"})["error"]
    assert "Unknown price_curve_source" in err_unknown
    for a in avail:
        assert a in err_unknown

    err_basis_hi = call("evaluate_season", scenario={"basis_usd_t": {"soybean": 300}})["error"]
    assert "between -200 and 200" in err_basis_hi

    err_basis_lo = call("evaluate_season", scenario={"basis_usd_t": {"soybean": -250}})["error"]
    assert "between -200 and 200" in err_basis_lo

    # Months not in YYYY-MM format or prices <= 0 inside a snapshot -> error at load time
    bad_month_file = tmp_path / "bad_month.json"
    bad_month_file.write_text(
        json.dumps({
            "source": "Test",
            "as_of": "2026-10-27",
            "unit": "usd/t",
            "curve": {"corn": {"2026/12": 150.0}},
        }),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="YYYY-MM"):
        load_curve(bad_month_file)

    bad_price_file = tmp_path / "bad_price.json"
    bad_price_file.write_text(
        json.dumps({
            "source": "Test",
            "as_of": "2026-10-27",
            "unit": "usd/t",
            "curve": {"corn": {"2026-12": 0.0}},
        }),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="must be > 0"):
        load_curve(bad_price_file)


def test_build_scenario_price_curve():
    r = call("build_scenario", scenario={"price_curve_source": "cbot_2026-10-27"})["scenario"]
    # Corn has curve from CBOT (delayed, placeholder)
    assert "CBOT settlement prices" in r["price_corn"]["origin"]
    assert "as of 2026-10-27" in r["price_corn"]["origin"]
    assert "placeholder" in r["price_corn"]["origin"]
    assert "price_curve_corn" in r
    assert "2026-12" in r["price_curve_corn"]["value"]

    # Sunflower is not in CBOT, so it keeps MAGyP origin
    assert r["price_sunflower"]["origin"].startswith("MAGyP")
    assert "price_curve_sunflower" not in r


def test_available_curves_list():
    curves = available_curves()
    assert "cbot_2026-10-27" in curves
    assert "rosario_2026-10-27" in curves


def test_evaluate_season_warns_about_placeholder_prices():
    out = json.loads(run_tool("evaluate_season", json.dumps({"scenario": {"price_curve_source": "cbot_2026-10-27"}})))
    assert "placeholder" in out["warning"] and "CBOT" in out["price_source"]
    plain = json.loads(run_tool("evaluate_season", json.dumps({"scenario": {}})))
    assert "warning" not in plain and "price_source" not in plain
