"""Tests for SPEC-37: scenario dates, NPV inclusions, and tax clarity."""
from __future__ import annotations

import pytest
from dora.scenario import Scenario, fortnight_label, round_start_date
from dora.tools import evaluate_season, tax_wedge, compare_regions, load_taxes_data


def test_1_fortnight_label():
    """1. fortnight_label formatting with calendar year."""
    assert fortnight_label("2026-05", 0, "es") == "1ª quinc. may 2026"
    assert fortnight_label("2026-05", 15, "es") == "2ª quinc. dic 2026"
    assert fortnight_label("2026-05", 23, "es") == "2ª quinc. abr 2027"
    assert fortnight_label("2026-05", 0, "en") == "early May 2026"


def test_2_tax_wedge_pampas_core():
    """2. tax_wedge for Pampas core 2,000 ha, 500,000 USD:
    in_npv is True for export duties, gross receipts, transaction and land, False for income;
    npv_usd equals evaluate_season(...)['npv_usd'];
    npv_after_income_tax_usd == npv_usd - income_tax_npv_usd to the cent;
    taxes_in_npv_usd + taxes_not_in_npv_usd == total_taxes_usd to the cent.
    """
    sc_dict = {"region": "pampas_core", "area_ha": 2000, "own_capital_usd": 500000, "tenure_comparison": False}
    ev = evaluate_season(sc_dict)
    tw = tax_wedge(sc_dict)

    by_key = {tx["key"]: tx for tx in tw["taxes"]}
    assert by_key["export_duties"]["in_npv"] is True
    assert by_key["gross_receipts"]["in_npv"] is True
    assert by_key["transaction"]["in_npv"] is True
    assert by_key["land"]["in_npv"] is True
    assert by_key["income"]["in_npv"] is False

    assert tw["npv_usd"] == ev["npv_usd"]
    assert round(tw["npv_after_income_tax_usd"], 2) == round(tw["npv_usd"] - tw["income_tax_npv_usd"], 2)
    assert round(tw["taxes_in_npv_usd"] + tw["taxes_not_in_npv_usd"], 2) == round(tw["total_taxes_usd"], 2)


def test_3_tax_wedge_iowa():
    """3. Same for Iowa: export duty row in_npv is None and usd 0."""
    sc_dict = {"region": "iowa", "area_ha": 2000, "own_capital_usd": 500000, "tenure_comparison": False}
    tw = tax_wedge(sc_dict)
    by_key = {tx["key"]: tx for tx in tw["taxes"]}
    assert by_key["export_duties"]["in_npv"] is None
    assert by_key["export_duties"]["usd"] == 0.0


def test_4_compare_regions_income_tax_helper():
    """4. compare_regions npv_after_income_tax_usd unchanged after moving the formula to the helper."""
    # Stored regression value from main for Pampas core 500 ha, 500k USD
    comp = compare_regions({"area_ha": 500, "own_capital_usd": 500000}, regions=["pampas_core"])
    p_core = comp["regions"]["pampas_core"]
    assert p_core["npv_usd"] == 775790.0
    assert p_core["npv_after_income_tax_usd"] == 671163.41


def test_tax_table_sources_es():
    """Section 6: The Spanish tax table has no English source sentences (no 'rate', 'engine', 'company')."""
    sc_dict = {"region": "pampas_core", "area_ha": 2000, "own_capital_usd": 500000, "tenure_comparison": False}
    tw_es = tax_wedge(sc_dict, lang="es")
    for tx in tw_es["taxes"]:
        src = tx.get("source", "").lower()
        assert "rate" not in src, f"English word 'rate' found in source: {src}"
        assert "engine" not in src, f"English word 'engine' found in source: {src}"
        assert "company" not in src, f"English word 'company' found in source: {src}"


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


def test_10_export_duties_decree_if_changed():
    """10. If section 5 changed the file: the saved source exists and contains export_duties_quote (whitespace collapsed)."""
    tax_data = load_taxes_data("pampas_core")
    if "export_duties_quote" in tax_data:
        import os, re
        source_file = tax_data.get("export_duties_source_file")
        assert source_file and os.path.exists(source_file), f"Source file {source_file} must exist"
        with open(source_file, encoding="utf-8", errors="ignore") as f:
            src_text = re.sub(r"\s+", " ", f.read())
        quote = re.sub(r"\s+", " ", tax_data["export_duties_quote"])
        assert quote in src_text
