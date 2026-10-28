"""SPEC-19: supplier terms as a decision, and caps on payments by a date."""
import json

import pytest

from dora.engine import optimize
from dora.scenario import FORTNIGHTS, Scenario
from dora.tools import compare_regions, evaluate_season, run_tool

NINETY = {"id": "90d", "delay_fortnights": 6}


# 1. An option identical to the base term changes nothing.
def test_option_equal_to_base_changes_nothing():
    base = optimize(Scenario())
    same = optimize(Scenario(payment_options=[{"id": "cash2", "delay_fortnights": 0, "surcharge": 0.0}]))
    assert same.npv == pytest.approx(base.npv, abs=0.01)


# 2. The engine takes cheap credit from the supplier and leaves dear credit; more options never hurt.
def test_cheap_term_is_used_dear_term_is_not():
    base = optimize(Scenario()).npv
    npv = {s: optimize(Scenario(payment_options=[dict(NINETY, surcharge=s)])) for s in (0.03, 0.08, 0.15)}
    assert npv[0.03].npv > npv[0.08].npv > base - 0.01
    assert npv[0.15].npv == pytest.approx(base, abs=0.01)
    assert all("90d" not in d for d in npv[0.15].payment_term_ha.values())
    assert sum(d.get("90d", 0.0) for d in npv[0.03].payment_term_ha.values()) > 100


def test_hectares_split_among_terms():
    r = optimize(Scenario(payment_options=[dict(NINETY, surcharge=0.03)]))
    for c, split in r.payment_term_ha.items():
        assert sum(split.values()) == pytest.approx(r.hectares[c], abs=1e-4)


# 3. Installments: same total with the surcharge, on the right dates.
def test_installments_schedule():
    sc = Scenario()
    c = "soybean"
    cash = sc.input_payments_per_ha(c, 0, 0.0)
    plan = sc.input_payments_per_ha(c, 2, 0.04, installments=3, every=2)
    assert sum(plan.values()) == pytest.approx(sum(cash.values()) * 1.04)
    first = min(cash)
    assert min(plan) == first + 2
    assert max(plan) <= FORTNIGHTS - 1


def test_base_term_reproduces_the_old_payments():
    sc = Scenario(input_payment_delay_fortnights=6, input_delay_surcharge=0.03)
    for c in sc.crops:
        total = sum(sc.payments_per_ha(c).values())
        d = sc.data[c]
        expected = d["field_operations"] + d["overhead_owned"] + 1.03 * (d["seed"] + d["fertilizer"] + d["crop_protection"])
        assert total == pytest.approx(expected)


# 4. Payment cap by a date: its shadow price lies between the left and right derivatives.
def test_payment_cap_shadow_price_by_perturbation():
    def npv(usd):
        return optimize(Scenario(constraints=[{"type": "max_payments_by", "month": "2026-09", "usd": usd}])).npv

    x, h = 60_000.0, 100.0
    dual = optimize(Scenario(constraints=[{"type": "max_payments_by", "month": "2026-09", "usd": x}])).constraint_duals[0]
    right, left = (npv(x + h) - npv(x)) / h, (npv(x) - npv(x - h)) / h
    assert dual > 0
    assert min(left, right) - 1e-4 <= dual <= max(left, right) + 1e-4


def test_payment_cap_not_binding_is_zero():
    r = optimize(Scenario(constraints=[{"type": "max_payments_by", "month": "2026-09", "usd": 400_000}]))
    assert r.constraint_duals[0] == 0.0
    assert r.npv == pytest.approx(optimize(Scenario()).npv, abs=0.01)


def test_more_terms_never_hurt_even_under_a_cap():
    """Adding a supplier term only adds choices: with or without a cap, the value cannot fall."""
    cap = {"type": "max_payments_by", "month": "2026-09", "usd": 60_000}
    for constraints in ([], [cap]):
        without = optimize(Scenario(constraints=constraints)).npv
        with_term = optimize(Scenario(payment_options=[dict(NINETY, surcharge=0.08)], constraints=constraints)).npv
        assert with_term >= without - 0.01


# 5. What the agent reads.
def test_evaluate_season_reports_financing_and_cap():
    out = evaluate_season({"payment_options": [{"id": "90_dias", "delay_fortnights": 6, "surcharge": 0.03}],
                           "constraints": [{"type": "max_payments_by", "month": "2026-09", "usd": 60000}]})
    terms = {t["id"]: t for t in out["financing"]["terms"]}
    assert terms["90_dias"]["implied_rate_annual_pct"] == pytest.approx(12.6, abs=0.05)
    assert terms["base"]["implied_rate_annual_pct"] is None
    assert terms["90_dias"]["hectares"]
    cap = out["constraints"][0]
    assert cap["type"] == "max_payments_by" and cap["binding"] and cap["opportunity_cost"] > 0


def test_validation_errors():
    out = json.loads(run_tool("evaluate_season", {"scenario": {"payment_options": [{"id": "base", "delay_fortnights": 6}]}}))
    assert "reserved" in out["error"]
    out = json.loads(run_tool("evaluate_season", {"scenario": {"constraints": [{"type": "max_payments_by", "month": "feb", "usd": 1}]}}))
    assert "YYYY-MM" in out["error"]
    out = json.loads(run_tool("evaluate_season", {"scenario": {"payment_options": [{"id": "x", "delay_fortnights": 6, "surcharge": 0.9}]}}))
    assert "surcharge" in out["error"]


def test_compare_regions_keeps_the_payment_cap():
    cap = {"type": "max_payments_by", "month": "2026-09", "usd": 60000}
    out = compare_regions({"area_ha": 500, "constraints": [cap]}, regions=["southeast_buenos_aires"])
    reports = out["regions"]["southeast_buenos_aires"]["constraints"]
    assert reports and reports[0]["type"] == "max_payments_by"
