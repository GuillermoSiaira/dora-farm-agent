"""Acceptance tests for SPEC-20: storage options, monthly basis, shrink, window and breakeven.

No network calls.
"""
from __future__ import annotations

import json
import urllib.request
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

import dora.engine as engine_mod
from dora.agent import FULL_SYSTEM_PROMPT, Agent
from dora.engine import optimize
from dora.prices import load_curve
from dora.scenario import FORTNIGHTS, REGIONS, Scenario, fortnightly_rate
from dora.tools import build_scenario, evaluate_season, run_tool, shadow_prices
from eval.build_answers import build_answers, extract_field
from eval.run_eval import run_evaluation

ROOT = Path(__file__).resolve().parent.parent
SPEC20_QUESTIONS = ROOT / "eval" / "questions_spec20.jsonl"
SPEC20_ANSWERS = ROOT / "eval" / "answers_spec20.jsonl"


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def _forbid(*args, **kwargs):
        raise AssertionError("Network access is forbidden in tests/test_storage.py")

    monkeypatch.setattr(urllib.request, "urlopen", _forbid)


def _call_tool(name: str, **kwargs) -> dict:
    return json.loads(run_tool(name, json.dumps(kwargs)))


def _hand_test3_scenario(fill_cost: float, delta_end_usd_t: float) -> tuple[Scenario, float]:
    """Single-crop scenario with plenty of capital and zero sales taxes, where the constant
    monthly_price_rise sets the end-of-window net price to BE(fill=0) + delta_end_usd_t, and
    returns (scenario, hand_breakeven_for_given_fill_cost)."""
    base = Scenario(
        crops=("soybean",),
        own_capital_usd=500_000.0,
        transaction_tax_rate=0.0,
        gross_receipts_rate=0.0,
    )
    h = base.calendar["soybean"]["harvest"]        # 23 (late April)
    last_p = FORTNIGHTS - 1                        # 29 (late July), 6 fortnights = 3 months
    n_f = last_p - h                               # 6
    ri = fortnightly_rate(base.deposit_rate_annual)
    monthly_cost = 2.0

    gross_h = base.price("soybean")
    # For a port price with zero sales taxes and default freight, net_price = gross - full marketing/yield
    full_mkt = base.data["soybean"]["marketing_harvest"] / base.data["soybean"]["yield"]
    pi_h = gross_h - full_mkt

    # Hand breakeven at last_p when lam[p] = (1 + ri)**(-p) and shrink = 0:
    # BE = pi_h * (1+ri)^6 + fill * (1+ri)^6 + (monthly/2) * sum_{p=h}^{T-2} (1+ri)^(T-1-p)
    be_fill0 = pi_h * ((1.0 + ri) ** n_f) + (monthly_cost / 2.0) * sum(
        (1.0 + ri) ** (last_p - p) for p in range(h, last_p)
    )
    hand_be = be_fill0 + fill_cost * ((1.0 + ri) ** n_f)

    target_pi_end = be_fill0 + delta_end_usd_t
    target_gross_end = target_pi_end + full_mkt
    months = n_f / 2.0
    rise = (target_gross_end / gross_h) ** (1.0 / months) - 1.0

    sc = replace(
        base,
        monthly_price_rise=rise,
        storage_options=[{
            "id": "test_opt",
            "kind": "silo_bag",
            "capacity_t": None,
            "fill_cost_usd_t": fill_cost,
            "monthly_cost_usd_t": monthly_cost,
            "shrink_at_entry": 0.0,
            "shrink_monthly": 0.0,
            "max_months": None,
        }],
    )
    return sc, hand_be


# 1. Legacy: without storage_options, the plan and the NPV equal those of main
#    (Balcarce default; test_storage_against_perturbation; test_storage_responds_to_curve).
def test_1_legacy_matches_main_exactly():
    sc_default = Scenario()
    r_default = optimize(sc_default)
    assert r_default.npv == pytest.approx(88186.59678149877, rel=1e-11)
    assert r_default.final_wealth == pytest.approx(92466.5245810224, rel=1e-11)
    assert r_default.hectares["wheat"] == pytest.approx(121.7227645367594, rel=1e-10)
    assert r_default.hectares["soybean"] == pytest.approx(250.0, rel=1e-10)
    assert r_default.hectares["corn"] == pytest.approx(0.0, abs=1e-9)
    assert r_default.hectares["sunflower"] == pytest.approx(0.0, abs=1e-9)
    assert sum(r_default.storage_shadow_price) == pytest.approx(0.0, abs=1e-9)

    sc_pert = Scenario(own_capital_usd=2_000_000, storage_capacity_t=200, monthly_price_rise=0.03)
    r_pert = optimize(sc_pert)
    assert r_pert.npv == pytest.approx(2056478.7243999839, rel=1e-11)
    assert r_pert.final_wealth == pytest.approx(2156285.053058932, rel=1e-11)
    assert r_pert.hectares["wheat"] == pytest.approx(150.49751243781094, rel=1e-10)
    assert r_pert.hectares["soybean"] == pytest.approx(250.0, rel=1e-10)
    assert r_pert.hectares["sunflower"] == pytest.approx(99.50248756218906, rel=1e-10)
    assert sum(r_pert.storage_shadow_price) == pytest.approx(37.23958741641785, rel=1e-10)

    curve_rising = {
        "soybean": {
            "2026-05": 330.0,
            "2027-04": 330.0,
            "2027-05": 345.0,
            "2027-06": 360.0,
            "2027-07": 375.0,
        }
    }
    sc_rising = Scenario(own_capital_usd=500_000.0, storage_capacity_t=200.0, price_curve=curve_rising)
    r_rising = optimize(sc_rising)
    assert r_rising.npv == pytest.approx(560994.1874661223, rel=1e-11)
    assert r_rising.final_wealth == pytest.approx(588220.7128785551, rel=1e-11)
    assert sum(r_rising.storage_shadow_price) == pytest.approx(28.973270126560152, rel=1e-10)
    for p in (23, 24, 25, 26, 27):
        assert r_rising.stock["soybean"][p] == pytest.approx(200.0, abs=1e-6)

    curve_flat = {"soybean": {"2026-05": 330.0, "2027-07": 330.0}}
    sc_flat = Scenario(own_capital_usd=500_000.0, storage_capacity_t=200.0, price_curve=curve_flat)
    r_flat = optimize(sc_flat)
    assert r_flat.npv == pytest.approx(550793.300209304, rel=1e-11)
    assert r_flat.final_wealth == pytest.approx(577524.7496970082, rel=1e-11)
    assert sum(r_flat.storage_shadow_price) == pytest.approx(0.0, abs=1e-9)
    assert all(not st for st in r_flat.stock.values())


# 2. One option equal to the legacy fields gives the same plan and NPV as no option.
def test_2_single_option_equal_to_legacy_matches_no_option():
    scenarios = [
        Scenario(),
        Scenario(own_capital_usd=2_000_000, storage_capacity_t=200, monthly_price_rise=0.03),
        Scenario(
            own_capital_usd=500_000.0,
            storage_capacity_t=200.0,
            price_curve={
                "soybean": {
                    "2026-05": 330.0,
                    "2027-04": 330.0,
                    "2027-05": 345.0,
                    "2027-06": 360.0,
                    "2027-07": 375.0,
                }
            },
        ),
    ]
    for sc in scenarios:
        legacy_opt = {
            "id": "own_silo",
            "kind": "own_silo",
            "capacity_t": sc.storage_capacity_t,
            "fill_cost_usd_t": 0.0,
            "monthly_cost_usd_t": sc.storage_cost_usd_t_month,
            "shrink_at_entry": 0.0,
            "shrink_monthly": 0.0,
            "max_months": None,
        }
        sc_opt = replace(sc, storage_options=[legacy_opt])
        r0 = optimize(sc)
        r1 = optimize(sc_opt)
        assert r1.npv == pytest.approx(r0.npv, rel=1e-12)
        assert r1.final_wealth == pytest.approx(r0.final_wealth, rel=1e-12)
        for c in sc.crops:
            assert r1.hectares[c] == pytest.approx(r0.hectares[c], abs=1e-8)
            assert r1.sales[c].keys() == r0.sales[c].keys()
            for p in r0.sales[c]:
                assert r1.sales[c][p] == pytest.approx(r0.sales[c][p], abs=1e-6)
        assert sum(r1.storage_shadow_price) == pytest.approx(sum(r0.storage_shadow_price), abs=1e-8)


# 3. Fill cost, by hand: constant price rise just above monthly cost + interest (+0.40 USD/t at T-1).
#    With fill_cost = 0, storage is used; with fill_cost = 1 USD/t, it is not.
def test_3_fill_cost_by_hand():
    sc_free_entry, _ = _hand_test3_scenario(fill_cost=0.0, delta_end_usd_t=0.40)
    r_free = optimize(sc_free_entry)
    assert r_free.storage_by_option["test_opt"]["peak_tonnes"] > 100.0
    assert 29 in r_free.sales["soybean"] and 23 not in r_free.sales["soybean"]

    sc_paid_entry, _ = _hand_test3_scenario(fill_cost=1.0, delta_end_usd_t=0.40)
    r_paid = optimize(sc_paid_entry)
    assert r_paid.storage_by_option["test_opt"]["peak_tonnes"] == pytest.approx(0.0, abs=1e-9)
    assert 23 in r_paid.sales["soybean"] and 29 not in r_paid.sales["soybean"]


# 4. Shrink: with shrink_monthly = 0.01 and grain held 4 fortnights,
#    tonnes sold == tonnes put in * (0.99)^2 (to 1e-6); harvest == sales + shrink.
def test_4_shrink_held_four_fortnights():
    # Corn in Balcarce harvests at p = 22 (early Apr 2027-04). Peak at p = 26 (early Jun 2027-06)
    # holds grain for exactly 4 fortnights (p = 22, 23, 24, 25 -> sold at p = 26).
    sc = Scenario(
        crops=("corn",),
        own_capital_usd=500_000.0,
        price_curve={
            "corn": {
                "2027-04": 180.0,
                "2027-06": 240.0,
                "2027-07": 180.0,
            }
        },
        storage_options=[{
            "id": "bag",
            "kind": "silo_bag",
            "capacity_t": None,
            "fill_cost_usd_t": 0.0,
            "monthly_cost_usd_t": 0.0,
            "shrink_at_entry": 0.0,
            "shrink_monthly": 0.01,
            "max_months": None,
        }],
    )
    r = optimize(sc)
    opt_rep = r.storage_by_option["bag"]
    put_in_t = opt_rep["tonnes_put_in"]["corn"]
    harvest_t = r.hectares["corn"] * sc.crop_yield("corn")
    sold_t = sum(r.sales["corn"].values())
    shrink_t = opt_rep["shrink_tonnes"]

    assert put_in_t == pytest.approx(harvest_t, rel=1e-9)
    assert list(r.sales["corn"].keys()) == [26]
    assert sold_t == pytest.approx(put_in_t * (0.99 ** 2), abs=1e-6)
    assert harvest_t == pytest.approx(sold_t + shrink_t, abs=1e-6)


# 5. Life: a silo bag with max_months = 2 has no stock after h + 4,
#    even with a price rise that pays storing until the end.
def test_5_max_months_life_bound():
    sc = Scenario(
        crops=("wheat",),
        own_capital_usd=500_000.0,
        monthly_price_rise=0.05,
        storage_options=[{
            "id": "short_bag",
            "kind": "silo_bag",
            "capacity_t": None,
            "fill_cost_usd_t": 2.0,
            "monthly_cost_usd_t": 0.0,
            "shrink_at_entry": 0.0,
            "shrink_monthly": 0.0,
            "max_months": 2,
        }],
    )
    h = sc.calendar["wheat"]["harvest"]  # 15 -> h + 4 = 19
    r = optimize(sc)
    stock = r.storage_by_option["short_bag"]["stock_by_crop"]["wheat"]
    assert r.storage_by_option["short_bag"]["peak_tonnes"] > 100.0
    assert stock.get(h + 4, 0.0) > 100.0
    for p in range(h + 5, FORTNIGHTS):
        assert stock.get(p, 0.0) == 0.0
        assert r.stock["wheat"].get(p, 0.0) == 0.0


# 6. Capacity shadow price: for an option with a capacity that binds, the sum of its duals
#    lies between the left and right derivatives (±1 t), as in test_engine.py.
def test_6_capacity_shadow_price_matches_finite_differences():
    def _make(cap: float) -> Scenario:
        return Scenario(
            own_capital_usd=2_000_000.0,
            monthly_price_rise=0.03,
            storage_options=[{
                "id": "yard_bag",
                "kind": "silo_bag",
                "capacity_t": cap,
                "fill_cost_usd_t": 3.0,
                "monthly_cost_usd_t": 0.4,
                "shrink_at_entry": 0.002,
                "shrink_monthly": 0.002,
                "max_months": None,
            }],
        )

    r0 = optimize(_make(200.0))
    r_minus = optimize(_make(199.0))
    r_plus = optimize(_make(201.0))

    sp = r0.storage_by_option["yard_bag"]["shadow_price_usd_t"]
    assert sp > 0.0
    left_deriv = r0.npv - r_minus.npv
    right_deriv = r_plus.npv - r0.npv
    assert right_deriv - 1e-6 <= sp <= left_deriv + 1e-6


# 7. No limit: an option with capacity_t = null adds no row and reports no shadow price.
def test_7_null_capacity_adds_no_row_and_reports_no_shadow_price(monkeypatch):
    seen_shapes: list[tuple[int, int]] = []
    real_linprog = engine_mod.linprog

    def _wrapped_linprog(c, *args, **kwargs):
        a_ub = kwargs.get("A_ub")
        seen_shapes.append(a_ub.shape)
        return real_linprog(c, *args, **kwargs)

    monkeypatch.setattr(engine_mod, "linprog", _wrapped_linprog)

    sc_finite = Scenario(
        own_capital_usd=500_000.0,
        monthly_price_rise=0.03,
        storage_options=[{"id": "silo", "kind": "own_silo", "capacity_t": 300.0}],
    )
    sc_unlimited = Scenario(
        own_capital_usd=500_000.0,
        monthly_price_rise=0.03,
        storage_options=[{"id": "bag", "kind": "silo_bag", "capacity_t": None}],
    )
    sc_two_unlimited = Scenario(
        own_capital_usd=500_000.0,
        monthly_price_rise=0.03,
        storage_options=[
            {"id": "bag_1", "kind": "silo_bag", "capacity_t": None},
            {"id": "bag_2", "kind": "silo_bag", "capacity_t": None},
        ],
    )

    optimize(sc_finite)
    r_unlim = optimize(sc_unlimited)
    optimize(sc_two_unlimited)

    rows_finite, _ = seen_shapes[0]
    rows_unlim, _ = seen_shapes[1]
    rows_two_unlim, _ = seen_shapes[2]

    assert rows_finite - rows_unlim == FORTNIGHTS
    assert rows_two_unlim == rows_unlim

    bag_info = r_unlim.storage_by_option["bag"]
    assert "shadow_price_usd_t" not in bag_info
    assert "shadow_price_by_fortnight" not in bag_info

    ev = evaluate_season({"own_capital_usd": 500_000.0, "storage_options": [{"kind": "silo_bag", "capacity_t": None}]})
    sp = shadow_prices({"own_capital_usd": 500_000.0, "storage_options": [{"kind": "silo_bag", "capacity_t": None}]})
    assert "shadow_price_usd_t" not in ev["storage"]["by_option"]["silo_bag"]
    assert "shadow_price_usd_t" not in sp["storage"]["by_option"]["silo_bag"]


# 8. Choice between options: own silo of 200 t (cheap/month) + unlimited silo bag (fill cost).
#    Own silo fills first; overflow goes into the bag iff price beats the bag's breakeven.
def test_8_choice_between_own_silo_and_silo_bag():
    opts = [
        {
            "id": "own_silo",
            "kind": "own_silo",
            "capacity_t": 200.0,
            "fill_cost_usd_t": 0.0,
            "monthly_cost_usd_t": 0.30,
            "shrink_at_entry": 0.0,
            "shrink_monthly": 0.0,
            "max_months": None,
        },
        {
            "id": "silo_bag",
            "kind": "silo_bag",
            "capacity_t": None,
            "fill_cost_usd_t": 8.0,
            "monthly_cost_usd_t": 0.30,
            "shrink_at_entry": 0.0,
            "shrink_monthly": 0.0,
            "max_months": None,
        },
    ]
    base = Scenario(
        crops=("soybean",),
        own_capital_usd=500_000.0,
        transaction_tax_rate=0.0,
        gross_receipts_rate=0.0,
        storage_options=opts,
    )
    h = base.calendar["soybean"]["harvest"]
    last_p = FORTNIGHTS - 1
    ri = fortnightly_rate(base.deposit_rate_annual)
    gross_h = base.price("soybean")
    full_mkt = base.data["soybean"]["marketing_harvest"] / base.data["soybean"]["yield"]
    pi_h = gross_h - full_mkt

    be_silo = pi_h * ((1.0 + ri) ** 6) + 0.15 * sum((1.0 + ri) ** (last_p - p) for p in range(h, last_p))
    be_bag = be_silo + 8.0 * ((1.0 + ri) ** 6)

    # Case A: end net price halfway between BE(own_silo) and BE(silo_bag) -> silo fills, bag stays empty
    mid_pi = 0.5 * (be_silo + be_bag)
    rise_mid = ((mid_pi + full_mkt) / gross_h) ** (1.0 / 3.0) - 1.0
    r_mid = optimize(replace(base, monthly_price_rise=rise_mid))
    assert r_mid.storage_by_option["own_silo"]["peak_tonnes"] == pytest.approx(200.0, abs=1e-6)
    assert r_mid.storage_by_option["silo_bag"]["peak_tonnes"] == pytest.approx(0.0, abs=1e-9)

    # Case B: end net price 2 USD/t above BE(silo_bag) -> silo fills 200 t first, rest overflows to bag
    high_pi = be_bag + 2.0
    rise_high = ((high_pi + full_mkt) / gross_h) ** (1.0 / 3.0) - 1.0
    r_high = optimize(replace(base, monthly_price_rise=rise_high))
    harvest_t = r_high.hectares["soybean"] * base.crop_yield("soybean")
    assert r_high.storage_by_option["own_silo"]["peak_tonnes"] == pytest.approx(200.0, abs=1e-6)
    assert r_high.storage_by_option["silo_bag"]["tonnes_put_in"]["soybean"] == pytest.approx(harvest_t - 200.0, abs=1e-5)
    # Shadow price of own_silo equals the 8 USD/t bag fill cost saved at harvest (discounted to p=0)
    assert r_high.storage_by_option["own_silo"]["shadow_price_usd_t"] == pytest.approx(
        8.0 * ((1.0 + ri) ** (-h)), rel=1e-6
    )


# 9. Monthly basis: constant monthly dict equals scalar number; synthetic harvest-weak / later-strong
#    basis makes Iowa store with the CBOT snapshot of 27/10, and a flat basis does not.
def test_9_monthly_basis_equivalence_and_iowa_cbot_snapshot():
    cbot_curve = load_curve("cbot_2026-10-27")["curve"]

    sc_scalar = Scenario(
        region="iowa",
        own_capital_usd=500_000.0,
        price_curve=cbot_curve,
        basis_usd_t={"corn": -15.0, "soybean": -25.0},
    )
    sc_const_dict = Scenario(
        region="iowa",
        own_capital_usd=500_000.0,
        price_curve=cbot_curve,
        basis_usd_t={
            "corn": {"2026-04": -15.0, "2026-10": -15.0, "2027-06": -15.0},
            "soybean": {"2026-04": -25.0, "2026-10": -25.0, "2027-06": -25.0},
        },
    )
    r_scalar = optimize(sc_scalar)
    r_const = optimize(sc_const_dict)
    assert r_const.npv == pytest.approx(r_scalar.npv, rel=1e-12)
    for c in sc_scalar.crops:
        assert r_const.hectares[c] == pytest.approx(r_scalar.hectares[c], abs=1e-8)

    # Flat basis with CBOT 27/10 snapshot: Iowa does not store
    assert all(not st for st in r_scalar.stock.values())

    # Synthetic basis weak at harvest (Oct 2026) and stronger later (Jun 2027): Iowa stores
    sc_recovering = Scenario(
        region="iowa",
        own_capital_usd=500_000.0,
        price_curve=cbot_curve,
        basis_usd_t={
            "corn": {"2026-10": -35.0, "2027-06": -5.0},
            "soybean": {"2026-10": -45.0, "2027-06": -10.0},
        },
    )
    r_rec = optimize(sc_recovering)
    total_stored = sum(sum(st.values()) for st in r_rec.stock.values())
    assert total_stored > 100.0

    # Also verify regional basis_iowa.json basis_by_month + ISU own_silo stores offline
    basis_iowa = json.loads(REGIONS["iowa"]["basis_file"].read_text(encoding="utf-8"))
    sc_iowa_real = Scenario(
        region="iowa",
        own_capital_usd=500_000.0,
        price_curve=cbot_curve,
        basis_by_month=basis_iowa["basis_by_month"],
        storage_options=[{"kind": "own_silo", "capacity_t": 500.0}],
    )
    r_iowa_real = optimize(sc_iowa_real)
    assert r_iowa_real.storage_by_option["own_silo"]["peak_tonnes"] == pytest.approx(500.0, abs=1e-6)


# 10. Window: soybean in Balcarce: harvest fortnight 23, window of 3 months;
#     safrinha corn in Mato Grosso: 1 month.
def test_10_storage_window_by_crop():
    ev_balc = evaluate_season({"region": "southeast_buenos_aires"})
    sp_balc = shadow_prices({"region": "southeast_buenos_aires"})
    soy_w = ev_balc["storage"]["window_by_crop"]["soybean"]
    assert soy_w["harvest_fortnight"] == 23
    assert soy_w["window_months"] == 3
    assert soy_w["months_in_between"] == 3
    assert sp_balc["storage"]["window_by_crop"]["soybean"]["window_months"] == 3

    ev_mt = evaluate_season({"region": "mato_grosso"})
    corn_w = ev_mt["storage"]["window_by_crop"]["corn"]
    assert corn_w["harvest_fortnight"] == 27
    assert corn_w["window_months"] == 1
    assert corn_w["months_in_between"] == 1


# 11. Breakeven: in test 3's scenario the reported breakeven equals the hand computation
#     (to 0.01 USD/t), and storage is used exactly when the price is above it.
def test_11_reported_breakeven_matches_hand_and_governs_storage():
    for fill_c in (0.0, 1.0):
        sc_above, hand_be = _hand_test3_scenario(fill_cost=fill_c, delta_end_usd_t=fill_c * 1.05 + 0.25)
        ev_above = evaluate_season({
            "crops": list(sc_above.crops),
            "own_capital_usd": sc_above.own_capital_usd,
            "transaction_tax_rate": 0.0,
            "gross_receipts_rate": 0.0,
            "monthly_price_rise": sc_above.monthly_price_rise,
            "storage_options": sc_above.storage_options,
        })
        be_rep = ev_above["storage"]["breakeven_by_crop"]["soybean"]["by_option"]["test_opt"]
        assert be_rep["breakeven_net_price_usd_t"] == pytest.approx(hand_be, abs=0.01)
        assert be_rep["model_end_net_price_usd_t"] > be_rep["breakeven_net_price_usd_t"]
        assert be_rep["pays_to_store_until_end"] is True
        assert ev_above["storage"]["by_option"]["test_opt"]["peak_tonnes"] > 100.0

        sc_below, hand_be_below = _hand_test3_scenario(fill_cost=fill_c, delta_end_usd_t=fill_c * 0.95 - 0.25)
        ev_below = evaluate_season({
            "crops": list(sc_below.crops),
            "own_capital_usd": sc_below.own_capital_usd,
            "transaction_tax_rate": 0.0,
            "gross_receipts_rate": 0.0,
            "monthly_price_rise": sc_below.monthly_price_rise,
            "storage_options": sc_below.storage_options,
        })
        be_rep_b = ev_below["storage"]["breakeven_by_crop"]["soybean"]["by_option"]["test_opt"]
        assert be_rep_b["breakeven_net_price_usd_t"] == pytest.approx(hand_be_below, abs=0.01)
        assert be_rep_b["model_end_net_price_usd_t"] < be_rep_b["breakeven_net_price_usd_t"]
        assert be_rep_b["pays_to_store_until_end"] is False
        assert ev_below["storage"]["by_option"]["test_opt"]["peak_tonnes"] == pytest.approx(0.0, abs=1e-9)


def test_11b_scarce_capital_breakeven_equals_price_and_pays_is_true():
    ev = evaluate_season({
        "area_ha": 500,
        "own_capital_usd": 100000,
        "region": "southeast_buenos_aires",
        "storage_options": [{"kind": "silo_bag"}],
        "monthly_price_rise": 0.03,
    })
    soy_opt = ev["storage"]["breakeven_by_crop"]["soybean"]["by_option"]["silo_bag"]
    put_in_soy = ev["storage"]["by_option"]["silo_bag"]["tonnes_put_in"]["soybean"]
    assert put_in_soy > 500.0
    assert soy_opt["stored_tonnes"] == pytest.approx(put_in_soy, abs=0.01)
    assert soy_opt["pays_to_store_until_end"] is True
    assert abs(soy_opt["breakeven_net_price_usd_t"] - soy_opt["model_end_net_price_usd_t"]) < 0.01


def test_11c_max_months_breakeven_at_last_sellable_fortnight():
    # Wheat in Balcarce harvests at h = 15. Regional silo_bag has max_months = 6,
    # so stock may stay up to h + 12 = 27 and the last fortnight it can be sold is 28 (early July), not 29.
    scen_dict = {
        "area_ha": 500,
        "own_capital_usd": 500_000,
        "region": "southeast_buenos_aires",
        "storage_options": [{"kind": "silo_bag"}],
    }
    ev = evaluate_season(scen_dict, lang="es")
    wheat_opt = ev["storage"]["breakeven_by_crop"]["wheat"]["by_option"]["silo_bag"]
    assert wheat_opt["end_fortnight"] == 28
    assert wheat_opt["end_month_name"] == "julio"
    assert wheat_opt["can_hold_until_end"] is False

    sc = Scenario(
        area_ha=500,
        own_capital_usd=500_000,
        region="southeast_buenos_aires",
        storage_options=[{"kind": "silo_bag"}],
    )
    opt = sc.effective_storage_options()[0]
    h = sc.calendar["wheat"]["harvest"]  # 15
    end_p = 28
    ri = fortnightly_rate(sc.deposit_rate_annual)
    lam = [(1.0 + ri) ** (-p) for p in range(FORTNIGHTS)]
    retain_f = (1.0 - opt["shrink_monthly"]) ** 0.5
    hold_pv = sum(
        (opt["monthly_cost_usd_t"] / 2.0) * lam[p] * (1.0 - opt["shrink_at_entry"]) * (retain_f ** (p - h))
        for p in range(h, end_p)
    )
    kept_end = (1.0 - opt["shrink_at_entry"]) * (retain_f ** (end_p - h))
    hand_be = (sc.net_price("wheat", h) * lam[h] + opt["fill_cost_usd_t"] * lam[h] + hold_pv) / (
        lam[end_p] * kept_end
    )

    assert wheat_opt["breakeven_net_price_usd_t"] == pytest.approx(hand_be, abs=0.01)
    assert wheat_opt["model_end_net_price_usd_t"] == pytest.approx(sc.net_price("wheat", end_p), abs=0.01)
    assert wheat_opt["model_end_net_price_usd_t"] != round(sc.net_price("wheat", 29), 2)


# 12. Validation: negative capacity, shrink of 0.5, unknown kind and repeated ids
#     give errors the model can read.
def test_12_validation_errors_are_readable():
    err_neg_cap = _call_tool(
        "evaluate_season",
        scenario={"storage_options": [{"kind": "own_silo", "capacity_t": -50}]},
    )["error"]
    assert "capacity_t" in err_neg_cap and ">= 0" in err_neg_cap

    err_shrink = _call_tool(
        "evaluate_season",
        scenario={"storage_options": [{"kind": "silo_bag", "shrink_monthly": 0.5}]},
    )["error"]
    assert "shrink_monthly" in err_shrink and "0.2" in err_shrink

    err_entry_shrink = _call_tool(
        "evaluate_season",
        scenario={"storage_options": [{"kind": "silo_bag", "shrink_at_entry": 0.5}]},
    )["error"]
    assert "shrink_at_entry" in err_entry_shrink and "0.2" in err_entry_shrink

    err_kind = _call_tool(
        "evaluate_season",
        scenario={"storage_options": [{"kind": "bunker"}]},
    )["error"]
    assert "bunker" in err_kind and "own_silo" in err_kind

    err_dup = _call_tool(
        "evaluate_season",
        scenario={"storage_options": [
            {"id": "s1", "kind": "own_silo", "capacity_t": 100},
            {"id": "s1", "kind": "silo_bag"},
        ]},
    )["error"]
    assert "repeated" in err_dup.lower() and "s1" in err_dup

    err_max_m = _call_tool(
        "evaluate_season",
        scenario={"storage_options": [{"kind": "silo_bag", "max_months": 0}]},
    )["error"]
    assert "max_months" in err_max_m

    # build_scenario origin tracking when farmer overrides a regional default cost
    built = build_scenario({
        "storage_options": [{"kind": "silo_bag", "fill_cost_usd_t": 9.5}]
    })["scenario"]
    opt_built = built["storage_options"]["value"][0]
    assert opt_built["fill_cost_usd_t"] == 9.5
    assert opt_built["origins"]["fill_cost_usd_t"] == "farmer"
    assert opt_built["origins"]["shrink_monthly"] != "farmer"


def test_spec20_eval_questions_and_end_of_season_rule(tmp_path):
    assert SPEC20_QUESTIONS.is_file()
    assert SPEC20_ANSWERS.is_file()
    assert "cannot evaluate" in FULL_SYSTEM_PROMPT

    rebuilt = build_answers(questions_path=SPEC20_QUESTIONS, output_path=tmp_path / "ans.jsonl")
    saved = [json.loads(line) for line in SPEC20_ANSWERS.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert rebuilt == saved
    assert len(saved) == 3

    questions = [json.loads(line) for line in SPEC20_QUESTIONS.read_text(encoding="utf-8").splitlines() if line.strip()]
    for q, ans in zip(questions, saved):
        payload = q["check"].get("payload") or {"scenario": q["scenario"]}
        res = json.loads(run_tool(q["check"]["tool"], json.dumps(payload)))
        assert extract_field(res, q["check"]["field"]) == ans["expected_value"]

    def _tc(name, args, i=1):
        return NS(id=f"call_{i}", function=NS(name=name, arguments=json.dumps(args)))

    class _Scripted:
        def __init__(self, steps):
            self.steps = list(steps)
            self.chat = NS(completions=NS(create=self._create))

        def _create(self, model, messages, tools):
            step = self.steps.pop(0)
            msg = NS(content=None, tool_calls=step) if isinstance(step, list) else NS(content=step, tool_calls=None)
            return NS(choices=[NS(message=msg)])

    script = [
        [_tc("evaluate_season", {"scenario": questions[0]["scenario"], "lang": "es"})],
        "Para embolsar la soja hasta julio (ventana de 3 meses), el precio neto de equilibrio es 264,9 USD/t y el precio neto del modelo en julio es 258,93 USD/t: no conviene embolsar.",
        [_tc("evaluate_season", {"scenario": questions[1]["scenario"], "lang": "es"})],
        "El silo propio de 500 t se llena y cada tonelada adicional vale 5,96 USD de hoy.",
        [_tc("evaluate_season", {"scenario": questions[2]["scenario"], "lang": "es"})],
        "El modelo termina en julio (quincena 29, 3 meses después de cosecha) y no puede evaluar guardar la soja hasta la cosecha que viene.",
    ]
    eval_out = tmp_path / "spec20_eval_results.json"
    run_evaluation(
        client=_Scripted(script),
        model="scripted-spec20",
        runs=1,
        questions_path=SPEC20_QUESTIONS,
        answers_path=SPEC20_ANSWERS,
        output_path=eval_out,
    )
    report = json.loads(eval_out.read_text(encoding="utf-8"))
    assert report["aggregated"]["tool_accuracy"]["mean"] == 1.0
    assert report["aggregated"]["answer_correctness"]["mean"] == 1.0
    assert report["aggregated"]["formulation_accuracy"]["mean"] == 1.0
    assert report["aggregated"]["verified_rate"]["mean"] == 1.0
