"""Tests for SPEC-37: scenario dates, NPV inclusions, and tax clarity."""
from __future__ import annotations

import pytest
from dora.scenario import Scenario, fortnight_label, round_start_date
from dora.tools import evaluate_season


def test_1_fortnight_label():
    """1. fortnight_label formatting with calendar year."""
    assert fortnight_label("2026-05", 0, "es") == "1ª quinc. may 2026"
    assert fortnight_label("2026-05", 15, "es") == "2ª quinc. dic 2026"
    assert fortnight_label("2026-05", 23, "es") == "2ª quinc. abr 2027"
    assert fortnight_label("2026-05", 0, "en") == "early May 2026"


def test_5b_start_date_engine():
    """5b. Start date, engine.
    (a) start_date equal to the region's base season start gives the same evaluate_season NPV,
        hectares and sales as no start_date (to the cent), for Pampas core and Iowa.
    (b) start_date: '2027-05-10' (rounds to 2027-05-01, k = 24) gives the same plan as the base one
        with every price month a year later; check hectares equal and calendar.season_start == '2027-05'.
    (c) Pampas core, start_date: '2026-11-03' (rounds to 2026-11-01): wheat is in crops_removed with
        'harvest beyond the horizon' (its next sowing is mid-2027 and its harvest falls after Oct 2027),
        corn and soybean are planned, calendar.season_start == '2026-11', and the cash series starts with
        the own capital in that first fortnight.
    (d) start_date: '2026-11-20' rounds to 2026-11-16.
    (e) start: 'today', today: '2026-11-03' gives the same as (c).
    """
    # (a)
    for reg, b_date in [("pampas_core", "2026-05-01"), ("iowa", "2026-04-01")]:
        ev_base = evaluate_season({"region": reg, "area_ha": 2000, "own_capital_usd": 500000, "tenure_comparison": False})
        ev_start = evaluate_season({"region": reg, "area_ha": 2000, "own_capital_usd": 500000, "start_date": b_date, "tenure_comparison": False})
        assert ev_start["npv_usd"] == pytest.approx(ev_base["npv_usd"], abs=0.01)
        assert ev_start["hectares"] == ev_base["hectares"]
        assert ev_start["sales_t_by_month"] == ev_base["sales_t_by_month"]

    # (b)
    ev_base_pampas = evaluate_season({"region": "pampas_core", "area_ha": 2000, "own_capital_usd": 500000, "tenure_comparison": False})
    ev_next_year = evaluate_season({"region": "pampas_core", "area_ha": 2000, "own_capital_usd": 500000, "start_date": "2027-05-10", "tenure_comparison": False})
    assert ev_next_year["hectares"] == ev_base_pampas["hectares"]
    assert ev_next_year["calendar"]["season_start"] == "2027-05"

    # (c)
    ev_nov = evaluate_season({"region": "pampas_core", "area_ha": 2000, "own_capital_usd": 500000, "start_date": "2026-11-03", "tenure_comparison": False})
    assert "wheat" in ev_nov["calendar"]["crops_removed"]
    assert ev_nov["calendar"]["crops_removed"]["wheat"] == "harvest beyond the horizon"
    assert ev_nov["calendar"]["season_start"] == "2026-11"
    assert "corn" in ev_nov["hectares"]
    assert "soybean" in ev_nov["hectares"]
    assert ev_nov["cash"][0] > 0

    # (d)
    assert round_start_date("2026-11-20") == "2026-11-16"

    # (e)
    ev_today = evaluate_season({"region": "pampas_core", "area_ha": 2000, "own_capital_usd": 500000, "start": "today", "today": "2026-11-03", "tenure_comparison": False})
    assert ev_today["npv_usd"] == pytest.approx(ev_nov["npv_usd"], abs=0.01)
    assert ev_today["hectares"] == ev_nov["hectares"]
    assert ev_today["calendar"]["season_start"] == ev_nov["calendar"]["season_start"]
    assert ev_today["calendar"]["crops_removed"] == ev_nov["calendar"]["crops_removed"]
    assert ev_today["cash"][0] == ev_nov["cash"][0]
