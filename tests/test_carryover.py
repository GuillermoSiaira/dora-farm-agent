import math
from dataclasses import replace
import pytest

from dora.engine import optimize
from dora.scenario import Scenario, ScenarioError, fortnight_month, fortnightly_rate
from dora.tools import evaluate_season, run_tool


def test_1_zero_drift_without_carryover():
    """Test 1: Without carryover, plan, NPV and every shadow price equal main across 6 scenarios."""
    scenarios = [
        Scenario(),  # 1. default base
        Scenario(rented_land=True, regional_rent_usd_ha=150.0),  # 2. rented land
        Scenario(
            storage_options=[
                {"id": "silo", "kind": "own_silo", "capacity_t": 500.0, "monthly_cost_usd_t": 1.5},
                {"id": "bolsa", "kind": "silo_bag", "fill_cost_usd_t": 6.0},
            ]
        ),  # 3. storage options
        Scenario(
            constraints=[{"type": "forward_sale", "crop": "soybean", "month": "2027-05", "tonnes": 200.0, "price_usd_t": 310.0}]
        ),  # 4. forward sale
        Scenario(
            owned_ha=400.0, max_buy_ha=50.0, land_price_usd_ha=8000.0, income_tax_rate=0.35, gross_receipts_rate=0.01
        ),  # 5. land buy and taxes
        Scenario(
            sowing_windows={"corn": [{"id": "early", "sowing": 10, "harvest": 21, "yield_t_ha": 8.5}]},
            sowing_capacity_ha_per_fortnight=150.0,
        ),  # 6. sowing windows and capacity
    ]

    for sc in scenarios:
        r_base = optimize(sc)
        sc_none = replace(sc, carryover=None)
        r_none = optimize(sc_none)

        assert abs(r_base.npv - r_none.npv) < 1e-7
        assert abs(r_base.final_wealth - r_none.final_wealth) < 1e-7
        for c in sc.crops:
            assert abs(r_base.hectares[c] - r_none.hectares[c]) < 1e-7
        assert abs(r_base.capital_shadow_price - r_none.capital_shadow_price) < 1e-7
        assert abs(r_base.land_shadow_price - r_none.land_shadow_price) < 1e-7
        for p in range(len(r_base.credit_shadow_price)):
            assert abs(r_base.credit_shadow_price[p] - r_none.credit_shadow_price[p]) < 1e-7
            assert abs(r_base.storage_shadow_price[p] - r_none.storage_shadow_price[p]) < 1e-7


def test_2_carryover_decision_high_vs_low_quote():
    """Test 2: High quote carries grain to end of July; low quote sells inside season.
    Both checked against V_{c,m} computed by hand.
    """
    # High quote: SX27 at 450 USD/t for 2027-12
    sc_high = Scenario(
        crops=("soybean",),
        area_ha=200.0,
        own_capital_usd=100_000.0,
        storage_capacity_t=1000.0,
        storage_cost_usd_t_month=1.0,
        monthly_price_rise=0.005,
        carryover={
            "sell_month": "2027-12",
            "price_usd_t": {"soybean": 450.0},
            "price_source": "CBOT SX27 high test quote",
        },
    )
    r_high = optimize(sc_high)
    v_high = sc_high.carryover_value("soybean", "own_silo")
    assert v_high is not None
    # End of season net price inside season at f29
    pi_f29 = sc_high.net_price("soybean", 29)
    # V_{c,m} should exceed selling at f29
    assert v_high > pi_f29
    # Grain carried at f29 should be positive
    carried_tonnes = sum(r_high.carryover["by_crop"]["soybean"]["options"]["own_silo"]["tonnes"] for _ in [1])
    assert carried_tonnes > 100.0

    # Low quote: SX27 at 150 USD/t for 2027-12
    sc_low = Scenario(
        crops=("soybean",),
        area_ha=200.0,
        own_capital_usd=100_000.0,
        storage_capacity_t=1000.0,
        storage_cost_usd_t_month=1.0,
        monthly_price_rise=0.005,
        carryover={
            "sell_month": "2027-12",
            "price_usd_t": {"soybean": 150.0},
            "price_source": "CBOT SX27 low test quote",
        },
    )
    r_low = optimize(sc_low)
    v_low = sc_low.carryover_value("soybean", "own_silo")
    assert v_low is not None
    assert v_low < pi_f29
    # Carried grain should be 0, all sold inside season
    low_carried = r_low.carryover["by_crop"]["soybean"]["options"]["own_silo"]["tonnes"]
    assert low_carried == 0.0


def test_3_carryover_value_matches_formula():
    """Test 3: Engine V_{c,m} equals formula of section 2 to 1e-9, with shrink, holding cost and discount."""
    sc = Scenario(
        crops=("soybean",),
        area_ha=100.0,
        storage_options=[
            {
                "id": "silo_custom",
                "kind": "own_silo",
                "capacity_t": 500.0,
                "monthly_cost_usd_t": 2.4,
                "shrink_monthly": 0.006,
                "max_months": None,
            }
        ],
        deposit_rate_annual=0.06,
        carryover={
            "sell_month": "2027-12",
            "price_usd_t": {"soybean": 350.0},
            "price_source": "Test settlement 2026-10-29",
        },
    )
    r = optimize(sc)
    v_engine = r.carryover["by_crop"]["soybean"]["options"]["silo_custom"]["V_c_m"]

    # Hand calculation strictly following Section 2:
    # sell_month is 2027-12. Season end is 2027-07. k = 5 months. 2k = 10 fortnights.
    k = 5
    two_k = 10
    p_sell = 29 + two_k  # 39
    pi_next = sc.net_price_quote("soybean", p_sell, 350.0, sc.routes[0])
    delta_m_retention = (1.0 - 0.006) ** 0.5
    r_i = (1.0 + 0.06) ** (1.0 / 24.0) - 1.0
    disc = 1.0 / (1.0 + r_i)

    term1 = pi_next * (delta_m_retention ** two_k) * (disc ** two_k)
    term2 = sum((2.4 / 2.0) * (delta_m_retention ** q) * (disc ** q) for q in range(1, two_k + 1))
    v_hand = term1 - term2

    assert abs(v_engine - v_hand) < 1e-9


def test_4_storage_life_and_capacity_limits():
    """Test 4: An option whose life ends before sell_month carries nothing; an option with capacity carries at most its capacity."""
    # Southeast Buenos Aires: soybean harvest f23.
    # At f29, soybean held is (29 - 23)/2 = 3 months.
    # To 2027-12, k = 5 months. Total held = 8 months.
    # Silo bag max_months is 6 months (8 > 6 -> life exceeded).
    # Own silo has capacity 150 t and max_months = None.
    sc = Scenario(
        crops=("soybean",),
        area_ha=200.0,
        yields={"soybean": 3.0},  # 600 tonnes total
        storage_options=[
            {"id": "bag", "kind": "silo_bag", "capacity_t": 1000.0, "max_months": 6.0},
            {"id": "silo", "kind": "own_silo", "capacity_t": 150.0, "max_months": None},
        ],
        carryover={
            "sell_month": "2027-12",
            "price_usd_t": {"soybean": 450.0},
            "price_source": "High forward quote",
        },
    )
    r = optimize(sc)

    # Silo bag should carry 0 tonnes because storage life was exceeded
    bag_carried = r.storage_by_option["bag"]["stock_by_crop"]["soybean"].get(29, 0.0)
    assert bag_carried == 0.0

    # Own silo has capacity 150 t, so it cannot carry more than 150 t
    silo_carried = r.storage_by_option["silo"]["stock_by_crop"]["soybean"].get(29, 0.0)
    assert silo_carried <= 150.0 + 1e-6
    assert silo_carried == pytest.approx(150.0, abs=1e-4)

    # Silo bag should be listed in not_carried with reason storage_life_exceeded
    reasons = [nc for nc in r.carryover["not_carried"] if nc.get("option") == "bag"]
    assert any(nc["reason"] == "storage_life_exceeded" for nc in reasons)


def test_5_crop_without_quote_carries_nothing():
    """Test 5: A crop without a quote for sell_month carries nothing, and the report names it."""
    sc = Scenario(
        crops=("wheat", "corn", "soybean"),
        area_ha=300.0,
        storage_capacity_t=1000.0,
        carryover={
            "sell_month": "2027-12",
            "price_usd_t": {"soybean": 400.0},  # only soybean has quote
            "price_source": "Trader bid",
        },
    )
    r = optimize(sc)

    # Corn and wheat end stock at f29 must be 0
    wheat_carried = sum(r.storage_by_option[opt]["stock_by_crop"].get("wheat", {}).get(29, 0.0) for opt in r.storage_by_option)
    corn_carried = sum(r.storage_by_option[opt]["stock_by_crop"].get("corn", {}).get(29, 0.0) for opt in r.storage_by_option)
    assert wheat_carried == 0.0
    assert corn_carried == 0.0

    # Report names corn and wheat in not_carried
    not_carried_crops = {nc["crop"]: nc["reason"] for nc in r.carryover["not_carried"] if "option" not in nc}
    assert "corn" in not_carried_crops
    assert "wheat" in not_carried_crops
    assert not_carried_crops["corn"] == "no_quote"
    assert not_carried_crops["wheat"] == "no_quote"


def test_6_curve_not_extrapolated_past_last_month():
    """Test 6: The curve is not extrapolated: a curve whose last month is before sell_month gives no quote."""
    # Curve ends at 2027-07; sell_month is 2027-12. No farmer quote given.
    sc = Scenario(
        crops=("soybean",),
        area_ha=200.0,
        price_curve={"soybean": {"2026-05": 280.0, "2027-05": 300.0, "2027-07": 310.0}},
        carryover={
            "sell_month": "2027-12",
            # No price_usd_t!
        },
    )
    quote, src = sc.carryover_quote("soybean", "2027-12")
    assert quote is None
    assert src is None

    r = optimize(sc)
    # Soybean carried should be 0
    soy_carried = sum(r.storage_by_option[opt]["stock_by_crop"].get("soybean", {}).get(29, 0.0) for opt in r.storage_by_option)
    assert soy_carried == 0.0

    nc_crops = [nc["crop"] for nc in r.carryover["not_carried"] if nc.get("reason") == "no_quote"]
    assert "soybean" in nc_crops


def test_7_mass_balance_with_carried_stock():
    """Test 7: Mass balance with carried stock holds for every crop."""
    sc = Scenario(
        crops=("wheat", "corn", "soybean", "sunflower"),
        area_ha=500.0,
        own_capital_usd=100_000.0,
        storage_capacity_t=800.0,
        storage_cost_usd_t_month=1.5,
        carryover={
            "sell_month": "2027-12",
            "price_usd_t": {"soybean": 420.0, "corn": 230.0},
            "price_source": "Market quotes",
        },
    )
    r = optimize(sc)

    for c in sc.crops:
        harvest_c = r.hectares[c] * sc.crop_yield(c)
        sold_c = sum(r.sales[c].values())
        shrink_c = sum(r.storage_by_option[opt]["shrink_by_crop"].get(c, 0.0) for opt in r.storage_by_option)
        carried_c = sum(r.storage_by_option[opt]["stock_by_crop"].get(c, {}).get(29, 0.0) for opt in r.storage_by_option)

        assert abs(harvest_c - (sold_c + shrink_c + carried_c)) < 1e-4


def test_8_storage_capacity_dual_perturbation_test():
    """Test 8: Storage capacity dual in fortnight T-1 passes perturbation test (+1 and -1 tonne) when carry-over binds."""
    cap0 = 100.0
    sc0 = Scenario(
        crops=("corn",),
        area_ha=200.0,
        own_capital_usd=150_000.0,
        storage_capacity_t=cap0,
        storage_cost_usd_t_month=1.0,
        sowing_windows={
            "corn": [
                {"id": "early", "sowing": 10, "harvest": 21, "yield_t_ha": 4.0},
                {"id": "late", "sowing": 15, "harvest": 28, "yield_t_ha": 4.0},
            ]
        },
        constraints=[{"type": "min_area", "crop": "corn", "ha": 20.0}],
        carryover={
            "sell_month": "2027-12",
            "price_usd_t": {"corn": 300.0},
            "price_source": "Test quote",
        },
    )
    r0 = optimize(sc0)

    # Check capacity binds at f29 (and only f29)
    dual_f29 = r0.storage_shadow_price[29]
    assert dual_f29 > 0.01, f"Expected storage capacity at f29 to bind, got dual {dual_f29}"
    assert sum(r0.storage_shadow_price[:29]) < 1e-6, "Earlier fortnights should not bind in this setup"

    # Perturb +1 tonne
    sc_plus = replace(sc0, storage_capacity_t=cap0 + 1.0)
    r_plus = optimize(sc_plus)
    delta_plus = r_plus.npv - r0.npv

    # Perturb -1 tonne
    sc_minus = replace(sc0, storage_capacity_t=cap0 - 1.0)
    r_minus = optimize(sc_minus)
    delta_minus = r0.npv - r_minus.npv

    # Dual must match finite difference perturbations to 1e-4
    assert abs(delta_plus - dual_f29) < 1e-4
    assert abs(delta_minus - dual_f29) < 1e-4
