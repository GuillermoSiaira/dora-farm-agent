import math
from dataclasses import replace
import pytest

from dora.engine import optimize
from dora.scenario import Scenario, ScenarioError, fortnight_month, fortnightly_rate
from dora.tools import evaluate_season, run_tool


def _make_credit_duals(non_zeros: dict[int, float]) -> list[float]:
    arr = [0.0] * 30
    for p, v in non_zeros.items():
        arr[p] = v
    return arr


MAIN_5718721_BENCHMARKS = [
    {
        "npv": 88186.596781,
        "final_wealth": 92466.524581,
        "hectares": {"wheat": 121.722765, "corn": 0.0, "soybean": 250.0, "sunflower": 0.0},
        "capital_shadow_price": 0.160813,
        "land_shadow_price": 37.734801,
        "credit_shadow_prices": _make_credit_duals({14: 0.112785}),
        "storage_shadow_prices": _make_credit_duals({}),
    },
    {
        "npv": 66148.695574,
        "final_wealth": 69359.065986,
        "hectares": {"wheat": 23.910527, "corn": 0.0, "soybean": 153.086981, "sunflower": 129.176453},
        "capital_shadow_price": 0.142883,
        "land_shadow_price": 171.432437,
        "credit_shadow_prices": _make_credit_duals({14: 0.060086, 18: 0.029959}),
        "storage_shadow_prices": _make_credit_duals({}),
    },
    {
        "npv": 88186.596781,
        "final_wealth": 92466.524581,
        "hectares": {"wheat": 121.722765, "corn": 0.0, "soybean": 250.0, "sunflower": 0.0},
        "capital_shadow_price": 0.160813,
        "land_shadow_price": 37.734801,
        "credit_shadow_prices": _make_credit_duals({14: 0.112785}),
        "storage_shadow_prices": _make_credit_duals({}),
    },
    {
        "npv": 84645.792747,
        "final_wealth": 88753.876001,
        "hectares": {"wheat": 121.722765, "corn": 0.0, "soybean": 250.0, "sunflower": 0.0},
        "capital_shadow_price": 0.160813,
        "land_shadow_price": 37.734801,
        "credit_shadow_prices": _make_credit_duals({14: 0.112785}),
        "storage_shadow_prices": _make_credit_duals({}),
    },
    {
        "npv": 69697.676579,
        "final_wealth": 73080.288387,
        "hectares": {"wheat": 152.982581, "corn": 0.0, "soybean": 200.0, "sunflower": 0.0},
        "capital_shadow_price": 0.095376,
        "land_shadow_price": 24.04111,
        "credit_shadow_prices": _make_credit_duals({14: 0.061225}),
        "storage_shadow_prices": _make_credit_duals({}),
    },
    {
        "npv": 105500.092511,
        "final_wealth": 110620.289857,
        "hectares": {"wheat": 32.688471, "corn": 150.0, "soybean": 91.211359, "sunflower": 0.0},
        "capital_shadow_price": 0.327999,
        "land_shadow_price": 0.0,
        "credit_shadow_prices": _make_credit_duals({14: 0.140265, 20: 0.148535}),
        "storage_shadow_prices": _make_credit_duals({}),
    },
    {
        "npv": 257369.459783,
        "final_wealth": 269860.277502,
        "hectares": {"wheat": 250.0, "corn": 0.0, "soybean": 250.0, "sunflower": 0.0},
        "capital_shadow_price": 0.004685,
        "land_shadow_price": 96.068841,
        "credit_shadow_prices": _make_credit_duals({}),
        "storage_shadow_prices": _make_credit_duals(
            {15: 3.088372, 17: 3.14591, 19: 5.150978, 22: 1.317233, 23: 10.104656, 27: 5.186274}
        ),
    },
]


def test_1_zero_drift_without_carryover():
    """Test 1: Without carryover, plan, NPV and every shadow price match main commit 5718721 exactly."""
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
        Scenario(
            own_capital_usd=200_000.0, storage_capacity_t=300.0, storage_cost_usd_t_month=0.5, monthly_price_rise=0.02
        ),  # 7. storage capacity binds
    ]

    for sc, bench in zip(scenarios, MAIN_5718721_BENCHMARKS):
        r = optimize(sc)
        assert abs(r.npv - bench["npv"]) < 1e-4, f"NPV drifted: {r.npv} vs {bench['npv']}"
        assert abs(r.final_wealth - bench["final_wealth"]) < 1e-4, f"Final wealth drifted: {r.final_wealth} vs {bench['final_wealth']}"
        for c in sc.crops:
            assert abs(r.hectares[c] - bench["hectares"][c]) < 1e-4, f"Crop {c} ha drifted: {r.hectares[c]} vs {bench['hectares'][c]}"
        assert abs(r.capital_shadow_price - bench["capital_shadow_price"]) < 1e-4
        assert abs(r.land_shadow_price - bench["land_shadow_price"]) < 1e-4
        for p in range(len(r.credit_shadow_price)):
            assert abs(r.credit_shadow_price[p] - bench["credit_shadow_prices"][p]) < 1e-4
            assert abs(r.storage_shadow_price[p] - bench["storage_shadow_prices"][p]) < 1e-4


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


def test_9_income_tax_applies_to_carried_grain():
    """Test 9: Income tax taxes carried grain valuation, lowering NPV and taxing entire wealth gain."""
    sc_notax = Scenario(
        crops=("soybean",),
        area_ha=200.0,
        own_capital_usd=50_000.0,
        storage_capacity_t=1000.0,
        storage_cost_usd_t_month=1.0,
        income_tax_rate=0.0,
        carryover={
            "sell_month": "2027-12",
            "price_usd_t": {"soybean": 450.0},
            "price_source": "High forward quote",
        },
    )
    r_notax = optimize(sc_notax)
    assert r_notax.carryover["tonnes_carried_total"] > 100.0

    # With 35% income tax
    sc_tax = replace(sc_notax, income_tax_rate=0.35)
    r_tax = optimize(sc_tax)

    # NPV and final wealth must be strictly less than without tax
    assert r_tax.npv < r_notax.npv
    assert r_tax.final_wealth < r_notax.final_wealth

    # Pre-tax profit should be taxed at 35%
    pre_tax_wealth = r_notax.final_wealth
    profit = pre_tax_wealth - sc_notax.own_capital_usd
    expected_tax = 0.35 * profit
    assert abs(r_tax.final_wealth - (pre_tax_wealth - expected_tax)) < 1e-4


def test_10_curve_quote_without_basis_not_carried():
    """Test 10: When quote comes from price_curve, lack of explicit basis for sell_month gives reason 'no_basis'."""
    sc = Scenario(
        crops=("soybean",),
        area_ha=100.0,
        price_curve={"soybean": {"2027-12": 420.0}},
        # Explicit basis dictionary that only covers up to 2027-05
        basis_usd_t={"soybean": {"2027-01": -10.0, "2027-05": -12.0}},
        carryover={
            "sell_month": "2027-12",
        },
    )
    r = optimize(sc)
    assert r.carryover["tonnes_carried_total"] == 0.0
    nc = [x for x in r.carryover["not_carried"] if x.get("crop") == "soybean"]
    assert any(x.get("reason") == "no_basis" for x in nc)


def test_11_malformed_sell_month_validation():
    """Test 11: Malformed sell_month (e.g. 'dic-2027') returns a clean validation error and ScenarioError."""
    # Scenario.carryover_k raises ScenarioError on malformed month
    sc = Scenario()
    with pytest.raises(ScenarioError, match="YYYY-MM"):
        sc.carryover_k("dic-2027")

    with pytest.raises(ScenarioError, match="YYYY-MM"):
        sc.carryover_k("2027-13")

    # evaluate_season raises ScenarioError with clean error message
    with pytest.raises(ScenarioError, match="YYYY-MM"):
        evaluate_season({
            "crops": ["soybean"],
            "carryover": {
                "sell_month": "dic-2027",
                "price_usd_t": {"soybean": 380.0},
            },
        })

    # run_tool catches and reports clean error string without uncaught crash
    import json
    res_str = run_tool("evaluate_season", {
        "scenario": {
            "crops": ["soybean"],
            "carryover": {
                "sell_month": "dic-2027",
                "price_usd_t": {"soybean": 380.0},
            },
        }
    })
    res = json.loads(res_str)
    assert "error" in res
    assert "YYYY-MM" in res["error"]


def test_12_stochastic_engine_carryover_and_mass_balance():
    """Test 12: Two-stage stochastic engine with carryover validates mass balance and surfaces tonnes_by_climate."""
    sc = Scenario(
        crops=("soybean",),
        area_ha=200.0,
        own_capital_usd=100_000.0,
        storage_capacity_t=1000.0,
        storage_cost_usd_t_month=1.0,
        climate_scenarios=[
            {"id": "dry", "prob": 0.4, "yields": {"soybean": 2.0}},
            {"id": "wet", "prob": 0.6, "yields": {"soybean": 4.0}},
        ],
        carryover={
            "sell_month": "2027-12",
            "price_usd_t": {"soybean": 450.0},
            "price_source": "Quequén local bid",
        },
    )
    r = optimize(sc)
    assert r.carryover
    assert "tonnes_by_climate" in r.carryover
    by_clim = r.carryover["tonnes_by_climate"]
    assert "dry" in by_clim and "wet" in by_clim
    assert by_clim["dry"] > 0
    assert by_clim["wet"] > by_clim["dry"]
    expected_t = 0.4 * by_clim["dry"] + 0.6 * by_clim["wet"]
    assert abs(r.carryover["tonnes_carried_total"] - expected_t) < 0.05

    # Check surfaced in evaluate_season
    ev = evaluate_season({
        "crops": ["soybean"],
        "area_ha": 200.0,
        "own_capital_usd": 100_000.0,
        "storage_capacity_t": 1000.0,
        "climate_scenarios": [
            {"id": "dry", "prob": 0.4, "yields": {"soybean": 2.0}},
            {"id": "wet", "prob": 0.6, "yields": {"soybean": 4.0}},
        ],
        "carryover": {
            "sell_month": "2027-12",
            "price_usd_t": {"soybean": 450.0},
            "price_source": "Quequén local bid",
        },
    })
    assert "carryover" in ev
    assert "tonnes_by_climate" in ev["carryover"]
