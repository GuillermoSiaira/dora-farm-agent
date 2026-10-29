"""Acceptance tests for SPEC-13: Regional comparison and saved runs."""
import pytest

from app import (
    build_comparison_table,
    create_comparison_price_decomposition_chart,
    create_comparison_rates_chart,
    create_comparison_roc_chart,
    save_run,
)
from dora.tools import _validate, compare_regions, evaluate_season, optimize

BASE_SCENARIO = {
    "area_ha": 500.0,
    "own_capital_usd": 50000.0,
    "credit_line_usd": 100000.0,
    "region": "southeast_buenos_aires",
}


def test_1_same_farm_one_region_matches_evaluate_season():
    """1. same_farm over one region returns exactly the numbers of evaluate_season for that scenario,
    once the scenario carries the region's land price, rent, freight and routes (every region in a
    comparison gets them, the farmer's own region included), and its taxes (SPEC-21)."""
    from dora.scenario import REGIONS, load_land_data, load_routes_data, load_taxes_data
    reg = "southeast_buenos_aires"
    land = load_land_data(reg)
    taxes = load_taxes_data(reg)
    full = dict(BASE_SCENARIO, region=reg,
                land_price_usd_ha=land["land_price_usd_ha"], regional_rent_usd_ha=land["regional_rent_usd_ha"],
                freight_usd_t=REGIONS[reg]["default_freight_usd_t"], routes=load_routes_data(reg)["routes"],
                gross_receipts_rate=taxes["gross_receipts_rate"], transaction_tax_rate=taxes["transaction_tax_rate"],
                land_tax_usd_ha_year=taxes["land_tax_usd_ha_year"])
    eval_res = evaluate_season(full)
    comp_res = compare_regions(full, regions=[reg], mode="same_farm")

    reg_data = comp_res["southeast_buenos_aires"]
    assert reg_data["npv_usd"] == eval_res["npv_usd"]
    assert reg_data["hectares"] == eval_res["hectares"]
    assert reg_data["max_credit_usd"] == eval_res["max_credit_usd"]
    assert reg_data["return_on_capital"] == eval_res["land_tenure"]["return_on_capital"]
    assert reg_data["return_on_capital_and_land"] == eval_res["land_tenure"]["return_on_capital_and_land"]


def test_2_same_farm_all_regions_returns_placeholder_flags():
    """2. same_farm over all regions returns one entry per region, each with its placeholder flags."""
    comp_res = compare_regions(BASE_SCENARIO, mode="same_farm")
    expected_regions = {"southeast_buenos_aires", "pampas_core", "iowa", "mato_grosso"}
    assert set(comp_res["regions"].keys()) == expected_regions

    for r, data in comp_res["regions"].items():
        assert "placeholder" in data
        assert "placeholder_flags" in data
        flags = data["placeholder_flags"]
        assert "region_data" in flags
        assert "land" in flags
        assert "taxes" in flags
        assert "price_curve" in flags
        assert isinstance(data["placeholder"], bool)
        assert data["npv_usd"] > 0


def test_3_same_budget_high_and_low_land_prices():
    """3. same_budget: with land price and rent high, keeps cash at deposit rate; with them low, buys or rents."""
    # High land price and rent: keeps cash at deposit rate (buys 0, rents 0, npv == own_capital)
    sc_high = {
        "own_capital_usd": 50000.0,
        "region": "southeast_buenos_aires",
        "land_price_usd_ha": 150000.0,
        "regional_rent_usd_ha": 30000.0,
    }
    res_high = compare_regions(sc_high, regions=["southeast_buenos_aires"], mode="same_budget")
    entry_high = res_high["southeast_buenos_aires"]
    assert entry_high["land_tenure"]["buy_ha"] == 0.0
    assert entry_high["land_tenure"]["rent_in_ha"] == 0.0
    assert abs(entry_high["npv_usd"] - 50000.0) < 1e-4

    # Low land price and rent: buys or rents
    sc_low = {
        "own_capital_usd": 50000.0,
        "region": "southeast_buenos_aires",
        "land_price_usd_ha": 500.0,
        "regional_rent_usd_ha": 30.0,
    }
    res_low = compare_regions(sc_low, regions=["southeast_buenos_aires"], mode="same_budget")
    entry_low = res_low["southeast_buenos_aires"]
    assert entry_low["land_tenure"]["buy_ha"] > 0.0 or entry_low["land_tenure"]["rent_in_ha"] > 0.0
    assert entry_low["npv_usd"] > 50000.0


def test_4_same_budget_cash_constraint_fortnight_zero():
    """4. same_budget: own capital is the only money at start: bought land * price + first-fortnight payments <= capital + credit line."""
    capital = 80000.0
    credit = 50000.0
    sc = {
        "own_capital_usd": capital,
        "credit_line_usd": credit,
        "region": "southeast_buenos_aires",
    }
    res = compare_regions(sc, regions=["southeast_buenos_aires"], mode="same_budget")
    entry = res["southeast_buenos_aires"]

    sc_obj, _ = _validate({
        "region": "southeast_buenos_aires",
        "own_capital_usd": capital,
        "credit_line_usd": credit,
        "owned_ha": 0.0,
        "rented_land": False,
        "allow_rent_out": False,
        "max_buy_ha": 50000.0,
        "max_rent_in_ha": 50000.0,
    })
    opt = optimize(sc_obj)

    bought_ha = opt.buy_ha
    land_price = sc_obj.land_price_usd_ha
    land_payment = bought_ha * land_price

    first_fn_operating_costs = sum(
        opt.hectares[c] * sc_obj.costs[c]["sowing"]
        for c in sc_obj.crops
        if sc_obj.calendar[c]["sowing"] == 0
    )
    rent_upfront = (opt.rent_in_ha * sc_obj.regional_rent_usd_ha) if getattr(sc_obj, "rent_upfront", False) else 0.0

    total_first_fn_payments = land_payment + first_fn_operating_costs + rent_upfront
    assert total_first_fn_payments <= (capital + credit) + 1e-4


def test_5_saving_9_runs_keeps_last_8():
    """5. Saving 9 runs keeps the last 8."""
    saved = []
    for i in range(1, 10):
        run = {"name": f"Run {i}", "npv_usd": 1000 * i, "region": "southeast_buenos_aires"}
        saved = save_run(saved, run, name=f"Run {i}")

    assert len(saved) == 8
    assert [r["name"] for r in saved] == [f"Run {i}" for i in range(2, 10)]


def test_6_chart_a_and_chart_b_structure():
    """6. Chart A has one line per run plus the market-rate line; chart B has two bars per run."""
    runs = [
        {
            "name": f"Run {i}",
            "region": "southeast_buenos_aires",
            "internal_rate_annual": [0.08] * 24,
            "return_on_capital": 0.25,
            "return_on_capital_and_land": 0.15,
            "freight_usd_t": 25.0,
            "npv_usd": 70000.0,
            "npv_per_ha": 140.0,
        }
        for i in range(1, 4)
    ]

    fig_a = create_comparison_rates_chart(runs)
    lines = [trace for trace in fig_a.data if getattr(trace, "mode", None) and "lines" in trace.mode]
    assert len(lines) == len(runs) + 1
    market_traces = [t for t in lines if "mercado" in t.name.lower() or "market" in t.name.lower()]
    assert len(market_traces) == 1

    fig_b = create_comparison_roc_chart(runs)
    bar_traces = [trace for trace in fig_b.data if trace.type == "bar"]
    assert len(bar_traces) == 2
    for bt in bar_traces:
        assert len(bt.x) == len(runs)
    total_bars = sum(len(bt.x) for bt in bar_traces)
    assert total_bars == 2 * len(runs)

    table_df = build_comparison_table(runs)
    assert len(table_df) > 5
    assert len(table_df.columns) == len(runs) + 1
