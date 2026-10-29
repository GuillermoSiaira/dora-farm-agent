"""Income-tax scaling of shadow prices and capital-stretch key rename (SPEC-22).

Offline test suite: no network access allowed.
"""
from dataclasses import replace
import urllib.request

import pytest

from dora.engine import optimize
from dora.scenario import FORTNIGHTS, Scenario, fortnightly_rate


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def _blocked(*args, **kwargs):
        raise AssertionError("Network calls are forbidden in tests/test_income_tax_duals.py")

    monkeypatch.setattr(urllib.request, "urlopen", _blocked)


def _base_scenario(income_tax_rate: float) -> Scenario:
    return Scenario(
        owned_ha=500.0,
        area_ha=500.0,
        own_capital_usd=50_000.0,
        credit_line_usd=100_000.0,
        storage_capacity_t=200.0,
        monthly_price_rise=0.03,
        income_tax_rate=income_tax_rate,
    )


def _between_derivatives(sc: Scenario, field: str, dual: float, delta: float = 1.0, tol: float = 1e-4) -> bool:
    base = optimize(sc).npv
    up = optimize(replace(sc, **{field: getattr(sc, field) + delta})).npv
    down = optimize(replace(sc, **{field: getattr(sc, field) - delta})).npv
    right, left = (up - base) / delta, (base - down) / delta
    return right - tol <= dual <= left + tol


@pytest.mark.parametrize("tax_rate", [0.0, 0.35])
def test_credit_silo_capital_and_land_duals_match_perturbation(tax_rate: float):
    sc = _base_scenario(tax_rate)
    r = optimize(sc)

    # 1. Credit line: sum(credit_shadow_price) between left and right derivatives in credit_line_usd (±1)
    credit_sp = sum(r.credit_shadow_price)
    assert credit_sp > 0
    assert _between_derivatives(sc, "credit_line_usd", credit_sp, delta=1.0, tol=1e-4)

    # 2. Own silo: sum(storage_shadow_price) between left and right derivatives in storage_capacity_t (±1)
    silo_sp = sum(r.storage_shadow_price)
    assert silo_sp > 0
    assert r.storage_by_option["own_silo"]["shadow_price_usd_t"] == pytest.approx(silo_sp, abs=1e-12)
    assert _between_derivatives(sc, "storage_capacity_t", silo_sp, delta=1.0, tol=1e-4)

    # 3. Own capital: capital_shadow_price = dNPV/dK - (1 - t + t*d), tolerance 1e-4
    d = (1.0 + fortnightly_rate(sc.deposit_rate_annual)) ** -(FORTNIGHTS - 1)
    deposit_after_tax_pv = 1.0 - tax_rate + tax_rate * d
    npv_base = r.npv
    npv_up = optimize(replace(sc, own_capital_usd=sc.own_capital_usd + 1.0)).npv
    npv_down = optimize(replace(sc, own_capital_usd=sc.own_capital_usd - 1.0)).npv
    right_excess = (npv_up - npv_base) - deposit_after_tax_pv
    left_excess = (npv_base - npv_down) - deposit_after_tax_pv
    assert right_excess - 1e-4 <= r.capital_shadow_price <= left_excess + 1e-4
    central_excess = 0.5 * (npv_up - npv_down) - deposit_after_tax_pv
    assert r.capital_shadow_price == pytest.approx(central_excess, abs=1e-4)

    # 4. Land: land_shadow_price between left and right derivatives in owned_ha (±1)
    assert r.land_shadow_price > 0
    assert _between_derivatives(sc, "owned_ha", r.land_shadow_price, delta=1.0, tol=1e-4)


def test_expected_numbers_at_35_pct_tax_and_control_matches_main():
    r0 = optimize(_base_scenario(0.0))
    r35 = optimize(_base_scenario(0.35))

    # Approximate expected numbers from SPEC-22 at t = 0.35
    assert sum(r35.credit_shadow_price) == pytest.approx(0.07942, abs=1e-4)
    assert sum(r35.storage_shadow_price) == pytest.approx(21.335, abs=1e-2)
    assert r35.capital_shadow_price == pytest.approx(0.1057, abs=1e-4)
    assert r35.land_shadow_price == pytest.approx(23.4354, abs=1e-3)

    # Control (t = 0) matches pre-change main values to 1e-9
    assert r0.npv == pytest.approx(94_940.70287404656, abs=1e-9)
    assert r0.final_wealth == pytest.approx(99_548.42523058265, abs=1e-9)
    assert sum(r0.credit_shadow_price) == pytest.approx(0.12219043351030867, abs=1e-9)
    assert sum(r0.storage_shadow_price) == pytest.approx(32.82302965941751, abs=1e-9)
    assert r0.capital_shadow_price == pytest.approx(0.16259571271859286, abs=1e-9)
    assert r0.land_shadow_price == pytest.approx(36.054535910405194, abs=1e-9)
    assert r0.cash_value[0] == pytest.approx(1.1625957127185929, abs=1e-9)

    # Every shadow price at t = 0.35 is (1 - 0.35) times t = 0.0 to 1e-9
    mult = 1.0 - 0.35
    assert r35.capital_shadow_price == pytest.approx(r0.capital_shadow_price * mult, abs=1e-9)
    assert r35.land_shadow_price == pytest.approx(r0.land_shadow_price * mult, abs=1e-9)
    for sp35, sp0 in zip(r35.credit_shadow_price, r0.credit_shadow_price):
        assert sp35 == pytest.approx(sp0 * mult, abs=1e-9)
    for sp35, sp0 in zip(r35.storage_shadow_price, r0.storage_shadow_price):
        assert sp35 == pytest.approx(sp0 * mult, abs=1e-9)

    # Pre-tax cash_value (lam_p), internal_rate_annual, and stretch rates do NOT change with income tax
    for lam35, lam0 in zip(r35.cash_value, r0.cash_value):
        assert lam35 == pytest.approx(lam0, abs=1e-12)
    for ir35, ir0 in zip(r35.internal_rate_annual, r0.internal_rate_annual):
        assert ir35 == pytest.approx(ir0, abs=1e-12)

    stretches0 = r0.get_capital_stretches()
    stretches35 = r35.get_capital_stretches()
    assert stretches0 and len(stretches35) == len(stretches0)
    for st0, st35 in zip(stretches0, stretches35):
        assert "usd_today_per_extra_dollar" not in st0
        assert "usd_today_per_extra_dollar" not in st35
        assert st0["rate_for_stretch"] == st35["rate_for_stretch"]
        assert st0["capital_shadow_price_today"] == round(float(r0.capital_shadow_price), 4)
        assert st35["capital_shadow_price_today"] == round(float(r35.capital_shadow_price), 4)
        assert st35["capital_shadow_price_meaning"] == (
            "what one more dollar of own capital is worth today, for the whole season; "
            "the stretch's own figure is rate_for_stretch"
        )


@pytest.mark.parametrize("tax_rate", [0.0, 0.35])
def test_binding_min_area_and_max_payments_by_duals_with_income_tax(tax_rate: float):
    # Binding min_area (same sign convention as tests/test_constraints.py: loss from +1 ha <= dual <= gain from -1 ha)
    def run_min_area(ha_val: float):
        return optimize(
            Scenario(
                own_capital_usd=2_000_000.0,
                income_tax_rate=tax_rate,
                constraints=[{"type": "min_area", "crop": "corn", "ha": ha_val}],
            )
        )

    r_min = run_min_area(150.0)
    dual_min = r_min.constraint_duals[0]
    assert dual_min > 0
    right_min = r_min.npv - run_min_area(151.0).npv
    left_min = run_min_area(149.0).npv - r_min.npv
    assert right_min - 1e-4 <= dual_min <= left_min + 1e-4

    # Binding max_payments_by (same sign convention as tests/test_financing.py: gain per extra USD of cap)
    def run_pay_cap(usd_val: float):
        return optimize(
            Scenario(
                income_tax_rate=tax_rate,
                constraints=[{"type": "max_payments_by", "month": "2026-09", "usd": usd_val}],
            )
        )

    x_cap, h = 60_000.0, 100.0
    r_cap = run_pay_cap(x_cap)
    dual_cap = r_cap.constraint_duals[0]
    assert dual_cap > 0
    right_cap = (run_pay_cap(x_cap + h).npv - r_cap.npv) / h
    left_cap = (r_cap.npv - run_pay_cap(x_cap - h).npv) / h
    assert min(left_cap, right_cap) - 1e-4 <= dual_cap <= max(left_cap, right_cap) + 1e-4


@pytest.mark.parametrize("tax_rate", [0.0, 0.35])
def test_spec20_storage_option_with_capacity_dual_matches_perturbation(tax_rate: float):
    def make_sc(cap_t: float) -> Scenario:
        return Scenario(
            own_capital_usd=50_000.0,
            credit_line_usd=100_000.0,
            monthly_price_rise=0.03,
            income_tax_rate=tax_rate,
            storage_options=[{"id": "bag_cap", "kind": "silo_bag", "capacity_t": cap_t}],
        )

    r = optimize(make_sc(200.0))
    opt_rep = r.storage_by_option["bag_cap"]
    sp_opt = opt_rep["shadow_price_usd_t"]
    assert sp_opt > 0
    assert sp_opt == pytest.approx(sum(opt_rep["shadow_price_by_fortnight"]), abs=1e-12)

    npv_up = optimize(make_sc(201.0)).npv
    npv_down = optimize(make_sc(199.0)).npv
    right = npv_up - r.npv
    left = r.npv - npv_down
    assert right - 1e-4 <= sp_opt <= left + 1e-4
