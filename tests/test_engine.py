"""Every shadow price is checked against perturbation: the resource is moved one
unit up and one unit down. The NPV is concave in each resource, so the dual must
lie between the right derivative and the left derivative (away from a kink,
both equal the dual)."""
from dataclasses import replace

import pytest

from dora.engine import optimize
from dora.scenario import Scenario


def between_derivatives(sc, field, dual, delta=1.0, tol=1e-4):
    base = optimize(sc).npv
    up = optimize(replace(sc, **{field: getattr(sc, field) + delta})).npv
    down = optimize(replace(sc, **{field: getattr(sc, field) - delta})).npv
    right, left = (up - base) / delta, (base - down) / delta
    return right - tol <= dual <= left + tol


@pytest.fixture
def scarce():
    """Short capital and credit: the capital constraint binds."""
    return Scenario(own_capital_usd=50_000, credit_line_usd=100_000)


def test_capital_against_perturbation(scarce):
    r = optimize(scarce)
    assert r.capital_shadow_price > 0.01
    assert between_derivatives(scarce, "own_capital_usd", r.cash_value[0])


def test_credit_against_perturbation(scarce):
    r = optimize(scarce)
    assert sum(r.credit_shadow_price) > 0.01
    assert between_derivatives(scarce, "credit_line_usd", sum(r.credit_shadow_price))


def test_land_against_perturbation():
    for region, approx_sp in (("iowa", 720.65), ("southeast_buenos_aires", 98.06)):
        sc = Scenario(region=region, owned_ha=500.0, area_ha=500.0, own_capital_usd=2_000_000)
        r = optimize(sc)
        assert r.land_shadow_price == pytest.approx(approx_sp, abs=1.0)
        assert between_derivatives(sc, "owned_ha", r.land_shadow_price)


def test_storage_against_perturbation():
    sc = Scenario(own_capital_usd=2_000_000, storage_capacity_t=200, monthly_price_rise=0.03)
    r = optimize(sc)
    assert sum(r.storage_shadow_price) > 0
    assert between_derivatives(sc, "storage_capacity_t", sum(r.storage_shadow_price))


def test_without_rationing_the_internal_rate_is_the_market_rate():
    sc = Scenario(own_capital_usd=5_000_000)
    r = optimize(sc)
    assert r.capital_shadow_price == pytest.approx(0, abs=1e-9)
    assert all(t == pytest.approx(sc.deposit_rate_annual, abs=1e-9) for t in r.internal_rate_annual)
    assert max(r.debt) == pytest.approx(0, abs=1e-6)


def test_scarce_capital_raises_the_internal_rate(scarce):
    r = optimize(scarce)
    assert max(r.internal_rate_annual) > scarce.deposit_rate_annual + 0.01
    assert r.summary()["fortnights_with_scarce_capital"]


def test_supplier_term_without_surcharge_never_hurts(scarce):
    base = optimize(scarce).npv
    with_term = optimize(replace(scarce, input_payment_delay_fortnights=6)).npv
    assert with_term >= base - 1e-6


def test_respects_rotation_and_sells_everything():
    sc = Scenario(own_capital_usd=2_000_000)
    r = optimize(sc)
    for c, h in r.hectares.items():
        assert h <= sc.max_crop_share * sc.area_ha + 1e-6
        if h > 1e-6:
            assert sum(r.sales[c].values()) == pytest.approx(h * sc.crop_yield(c), rel=1e-6)
