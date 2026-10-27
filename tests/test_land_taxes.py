"""Acceptance tests for SPEC-10: Land tenure decisions and tax structure by country.

No network access. Run with:
    .venv/Scripts/python -m pytest tests/test_land_taxes.py -v
"""
import json
import pytest
from dataclasses import replace

from dora.engine import FORTNIGHTS, optimize
from dora.scenario import CALENDAR, Scenario, fortnightly_rate
from dora.tools import run_tool, tax_wedge


# 1. With the defaults (no rent-in, no buy, rent-out allowed), a farm where farming beats
#    renting gives the same plan as before.
def test_defaults_preserve_farming_plan():
    sc_base = Scenario()
    sc_explicit = Scenario(
        owned_ha=500.0,
        max_rent_in_ha=0.0,
        allow_rent_out=True,
        max_buy_ha=0.0,
        regional_rent_usd_ha=0.0,
    )
    r_base = optimize(sc_base)
    r_explicit = optimize(sc_explicit)

    assert r_explicit.rent_in_ha == 0.0
    assert r_explicit.rent_out_ha == 0.0
    assert r_explicit.buy_ha == 0.0

    for c in sc_base.crops:
        assert abs(r_explicit.hectares[c] - r_base.hectares[c]) < 1e-6

    rel_diff = abs(r_explicit.npv - r_base.npv) / abs(r_base.npv)
    assert rel_diff < 1e-12


# 2. When the regional rent exceeds the farming margin, the model rents out owned land.
#    The land shadow price then equals the rent, within a tolerance.
def test_rent_out_when_rent_exceeds_farming_margin():
    # In Balcarce, the farming margin with June 2026 prices is ~$47/ha.
    # At regional rent of 350 USD/ha, renting out beats farming.
    sc = Scenario(regional_rent_usd_ha=350.0)
    r = optimize(sc)

    # The entire owned land is rented out
    assert r.rent_out_ha == pytest.approx(sc.owned, abs=1e-4)
    for c, ha in r.hectares.items():
        assert ha < 1e-4

    # The land shadow price equals the regional rent
    assert r.land_shadow_price == pytest.approx(350.0, abs=1e-4)


# 3. The land shadow price passes the perturbation check of tests/test_engine.py
#    with buy and rent options present.
def test_land_shadow_price_passes_perturbation_with_options():
    # Capital unconstrained so land is the scarce resource
    # Options present: rent-in, rent-out, and buy are all available
    sc = Scenario(
        own_capital_usd=2_000_000,
        max_rent_in_ha=100.0,
        max_buy_ha=100.0,
        land_price_usd_ha=7500.0,
        regional_rent_usd_ha=10.0,  # low rent so farming beats renting out
    )
    r = optimize(sc)
    assert r.land_shadow_price > 0

    tot = sc.owned + sc.max_rent_in_ha + sc.max_buy_ha
    cap = sc.max_crop_share * tot
    npv = {
        a: optimize(replace(sc, owned_ha=a, area_ha=a, max_crop_share=cap / (a + sc.max_rent_in_ha + sc.max_buy_ha))).npv
        for a in (499, 500, 501)
    }

    assert npv[501] - npv[500] - 1e-4 <= r.land_shadow_price <= npv[500] - npv[499] + 1e-4


# 4. buy > 0 only if the land's end value plus farming beats keeping the cash at the deposit rate.
#    Check one case each way.
def test_buy_land_only_when_beating_deposit_rate():
    # Case A: 0% land appreciation, $10,000/ha price, 4% deposit rate.
    # Farming margin in Balcarce (~$47/ha) is ~0.47% return < 4% deposit rate. Model does NOT buy.
    sc_no_buy = Scenario(
        own_capital_usd=500_000,
        max_buy_ha=20.0,
        land_price_usd_ha=10_000.0,
        land_appreciation_annual=0.0,
    )
    r_no_buy = optimize(sc_no_buy)
    assert r_no_buy.buy_ha == 0.0

    # Case B: 10% annual land appreciation, $10,000/ha price, 4% deposit rate.
    # Land appreciation alone is 10% > 4% deposit rate. Model DOES buy.
    sc_buy = Scenario(
        own_capital_usd=500_000,
        max_buy_ha=20.0,
        land_price_usd_ha=10_000.0,
        land_appreciation_annual=0.10,
    )
    r_buy = optimize(sc_buy)
    assert r_buy.buy_ha == pytest.approx(20.0, abs=1e-4)


# 5. Gross-receipts tax of 1% lowers every net price coefficient by 1% of price.
#    The transaction tax applies to both sales and payments.
def test_gross_receipts_and_transaction_tax():
    sc0 = Scenario()

    # Gross receipts tax of 1%
    sc_gr = Scenario(gross_receipts_rate=0.01)
    for c in sc0.crops:
        h = CALENDAR[c]["harvest"]
        for p in range(h, FORTNIGHTS):
            gross_p = sc0.price(c) * (1 + sc0.monthly_price_rise) ** ((p - h) / 2)
            expected_diff = 0.01 * gross_p
            actual_diff = sc0.net_price(c, p) - sc_gr.net_price(c, p)
            assert actual_diff == pytest.approx(expected_diff, abs=1e-6)

    # Transaction tax of 1.2% (Argentina's bank debits and credits)
    sc_tx = Scenario(transaction_tax_rate=0.012)
    for c in sc0.crops:
        h = CALENDAR[c]["harvest"]
        for p in range(h, FORTNIGHTS):
            gross_p = sc0.price(c) * (1 + sc0.monthly_price_rise) ** ((p - h) / 2)
            expected_diff = 0.012 * gross_p
            actual_diff = sc0.net_price(c, p) - sc_tx.net_price(c, p)
            assert actual_diff == pytest.approx(expected_diff, abs=1e-6)

        # Check payments increased by exactly 1.2%
        p0 = sc0.payments_per_ha(c)
        p_tx = sc_tx.payments_per_ha(c)
        for k in p0:
            assert p_tx[k] == pytest.approx(p0[k] * 1.012, abs=1e-6)


# 6. The income tax rate scales the reported NPV by (1 - t) on the profit, and the plan does not change.
def test_income_tax_scales_npv_on_profit_without_altering_plan():
    sc0 = Scenario()
    r0 = optimize(sc0)

    t = 0.35  # Argentina corporate income tax rate 35%
    sc_tax = Scenario(income_tax_rate=t)
    r_tax = optimize(sc_tax)

    # Optimal plan is identical
    for c in sc0.crops:
        assert r_tax.hectares[c] == pytest.approx(r0.hectares[c], abs=1e-6)
    for c in r0.sales:
        for p in r0.sales[c]:
            assert r_tax.sales[c][p] == pytest.approx(r0.sales[c][p], abs=1e-6)

    # Profit is scaled by (1 - t)
    profit0 = r0.final_wealth - sc0.own_capital_usd
    profit_tax = r_tax.final_wealth - sc_tax.own_capital_usd
    assert profit_tax == pytest.approx((1.0 - t) * profit0, abs=1e-4)

    # NPV on profit is discounted and scaled
    discount = (1.0 + fortnightly_rate(sc0.deposit_rate_annual)) ** -(FORTNIGHTS - 1)
    expected_npv_tax = r0.npv - discount * (t * profit0)
    assert r_tax.npv == pytest.approx(expected_npv_tax, abs=1e-4)


# 7. Export duty is reported in the tax wedge and not deducted again from Argentina's FAS-based prices.
def test_export_duty_reported_in_tax_wedge_not_deducted_again():
    sc = Scenario(region="southeast_buenos_aires")
    # FAS price paid to farmer is not lowered by export duties in net_price
    # (FAS already reflects export duties netted at port)
    marketing_wheat = sc.data["wheat"]["marketing_harvest"] / sc.data["wheat"]["yield"]
    assert sc.net_price("wheat", CALENDAR["wheat"]["harvest"]) == pytest.approx(
        sc.price("wheat") - sc.freight_usd_t - marketing_wheat, abs=1e-6
    )

    # Tax wedge reports export duties
    raw = run_tool("tax_wedge", json.dumps({"scenario": {"region": "southeast_buenos_aires"}}))
    wedge = json.loads(raw)

    assert "taxes" in wedge
    duty_entry = next((e for e in wedge["taxes"] if "Export duties" in e["name"]), None)
    assert duty_entry is not None
    assert duty_entry["usd"] > 0
    assert duty_entry["percent_gross_revenue"] > 0
    assert "disclaimer" in wedge
    assert "Orientative guide based on public rates as of 2026-06; not tax advice; consult an accountant." in wedge["disclaimer"]


# 8. All existing tests still pass, and Balcarce's base case is unchanged when every new option is at its default.
def test_balcarce_base_case_unchanged():
    sc = Scenario()
    r = optimize(sc)

    assert round(r.npv, 2) == 88186.60
    assert round(r.final_wealth, 2) == 92466.52
    assert r.rent_in_ha == 0.0
    assert r.rent_out_ha == 0.0
    assert r.buy_ha == 0.0
    assert r.land_price_usd_ha == 0.0
    assert r.regional_rent_usd_ha == 0.0
