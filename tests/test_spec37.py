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


def test_5_app_season_line():
    """5. App, season line: with a hand-made calendar block (start 2026-11-01, crops_removed: ['wheat'],
    season to 2027-10) the result markdown contains 1/11/2026, oct 2027, No entran trigo;
    with start 2026-05-01 and today 2026-11-03 it contains Ojo: el plan arranca el 1/5/2026."""
    from app import build_season_line
    cal1 = {
        "season_start": "2026-11",
        "start_date": "2026-11-01",
        "crops_removed": ["wheat"],
    }
    lines1 = "\n".join(build_season_line(cal1, lang="es", today_date="2026-11-03"))
    assert "1/11/2026" in lines1
    assert "oct 2027" in lines1
    assert "No entran trigo" in lines1

    cal2 = {
        "season_start": "2026-05",
        "start_date": "2026-05-01",
    }
    lines2 = "\n".join(build_season_line(cal2, lang="es", today_date="2026-11-03"))
    assert "Ojo: el plan arranca el 1/5/2026" in lines2


def test_6_app_credit():
    """6. App, credit: peak = line gives 'usás toda la línea'; peak below the line does not."""
    import dora.tools
    dora.tools.DEFAULT_PRICE_SOURCE = "magyp_june"
    from app import run_scenario

    res_binding = run_scenario(area_ha=2000, own_capital_usd=500000, credit_line_usd=100000, region="pampas_core", lang="es")
    assert "usás toda la línea; más crédito cambiaría el plan" in res_binding["plan"]

    res_slack = run_scenario(area_ha=2000, own_capital_usd=500000, credit_line_usd=1000000, region="pampas_core", lang="es")
    assert "usás toda la línea" not in res_slack["plan"]


def test_7_app_taxes():
    """7. App, taxes: the table for Argentina has the column '¿Ya está en el VAN?' and the rows
    'Ya descontados en el VAN', 'A descontar: Ganancias', 'VAN después de Ganancias';
    for Iowa the duty row says 'no aplica' and no 'a verificar'."""
    import dora.tools
    dora.tools.DEFAULT_PRICE_SOURCE = "magyp_june"
    from app import run_scenario

    res_ar = run_scenario(area_ha=2000, own_capital_usd=500000, region="pampas_core", lang="es")
    df_ar = res_ar["tax_wedge_table"]
    assert "¿Ya está en el VAN?" in df_ar.columns
    taxes_col = df_ar["Impuesto"].tolist()
    assert "Ya descontados en el VAN" in taxes_col
    assert "A descontar: Ganancias" in taxes_col
    assert "VAN después de Ganancias" in taxes_col

    res_ia = run_scenario(area_ha=2000, own_capital_usd=500000, region="iowa", lang="es")
    df_ia = res_ia["tax_wedge_table"]
    duty_rows = df_ia[df_ia["Impuesto"].str.contains("exportación|retenciones", case=False, na=False)]
    assert len(duty_rows) > 0
    duty_row = duty_rows.iloc[0]
    assert "no aplica" in duty_row["¿Ya está en el VAN?"].lower() or "no aplica" in duty_row["Monto (USD)"].lower()
    assert "a verificar" not in duty_row["Monto (USD)"].lower()


def test_8_app_livestock():
    """8. App, livestock: for Pampas core with no livestock selected the result has 'Ganadería: no incluida';
    for Iowa it does not and the livestock inputs are hidden."""
    import dora.tools
    dora.tools.DEFAULT_PRICE_SOURCE = "magyp_june"
    from app import run_scenario, on_region_change

    res_pc = run_scenario(area_ha=2000, own_capital_usd=500000, region="pampas_core", lang="es")
    assert "Ganadería: no incluida" in res_pc["plan"]

    res_ia = run_scenario(area_ha=2000, own_capital_usd=500000, region="iowa", lang="es")
    assert "Ganadería: no incluida" not in res_ia["plan"]

    crops_upd, btn_upd, ls_upd = on_region_change("iowa", lang="es")
    assert ls_upd.get("visible") is False

    crops_upd, btn_upd, ls_upd_pc = on_region_change("pampas_core", lang="es")
    assert ls_upd_pc.get("visible") is True


def test_9_example_buttons_npvs():
    """9. The three '¿Cómo empiezo?' examples still give the NPVs they give on main (run with start_date=None / season)."""
    import dora.tools
    dora.tools.DEFAULT_PRICE_SOURCE = "magyp_june"
    from app import run_scenario

    ex1 = run_scenario(area_ha=500.0, crops=["wheat", "corn", "soybean", "sunflower"], own_capital_usd=50000.0, credit_line_usd=100000.0, region="southeast_buenos_aires")
    ex2 = run_scenario(area_ha=500.0, crops=["wheat", "corn", "soybean", "sunflower"], own_capital_usd=50000.0, credit_line_usd=100000.0, supplier_delay=6, supplier_surcharge_pct=3.0, region="southeast_buenos_aires")
    ex3 = run_scenario(area_ha=500.0, crops=["wheat", "corn", "soybean", "sunflower"], own_capital_usd=50000.0, credit_line_usd=100000.0, constraints_df=[["min_area", "corn", 150, "", None]], region="southeast_buenos_aires")

    assert ex1["npv_usd"] == pytest.approx(88186.60, abs=0.01)
    assert ex2["npv_usd"] == pytest.approx(92191.18, abs=0.01)
    assert ex3["npv_usd"] == pytest.approx(62091.53, abs=0.01)


def test_additions_1_fuentes_four_regions():
    """Addition 1: Fuentes for all 4 regions: Mato Grosso names IMEA / Sorriso, Iowa names Iowa State,
    none says 'sudeste' or 'MAGyP' unless it is an Argentine region."""
    import dora.tools
    dora.tools.DEFAULT_PRICE_SOURCE = "magyp_june"
    from app import run_scenario

    r_mt = run_scenario(area_ha=5000, own_capital_usd=5000000, region="mato_grosso", lang="es")
    assert "IMEA" in r_mt["plan"] or "Sorriso" in r_mt["plan"]
    assert "sudeste" not in r_mt["plan"].lower()
    assert "magyp" not in r_mt["plan"].lower()

    r_ia = run_scenario(area_ha=2000, own_capital_usd=500000, region="iowa", lang="es")
    assert "Iowa State" in r_ia["plan"]
    assert "sudeste" not in r_ia["plan"].lower()
    assert "magyp" not in r_ia["plan"].lower()

    r_pc = run_scenario(area_ha=2000, own_capital_usd=500000, region="pampas_core", lang="es")
    assert "Pergamino" in r_pc["plan"] or "Zona Núcleo" in r_pc["plan"]
    assert "sudeste" not in r_pc["plan"].lower()

    r_se = run_scenario(area_ha=500, own_capital_usd=50000, region="southeast_buenos_aires", lang="es")
    assert "Sudeste de Buenos Aires" in r_se["plan"]


def test_additions_2_local_elevator_freight():
    """Addition 2: When price point is local_elevator and plan freight is 0,
    write 'Precio puesto en {lugar} (el flete al puerto ya está descontado en la base: {basis} USD/t)'."""
    import dora.tools
    dora.tools.DEFAULT_PRICE_SOURCE = "magyp_june"
    from app import run_scenario

    r_mt = run_scenario(area_ha=5000, own_capital_usd=5000000, credit_line_usd=1000000, region="mato_grosso", lang="es")
    assert "Precio puesto en Sorriso (el flete al puerto ya está descontado en la base:" in r_mt["plan"]


def test_additions_3_abundant_capital_chart_a():
    """Addition 3: Chart A with abundant capital: both series present, subtitle says
    'El capital sobra: un dólar vale lo mismo en el campo que en el banco.'"""
    from app import create_internal_rate_chart

    sp_abundant = {
        "by_fortnight": [{"p": p, "usd_today_per_dollar": 1.0 / (1.0016 ** p), "rate_annual": 0.04} for p in range(24)],
        "market_rate_annual": 0.04,
    }
    fig = create_internal_rate_chart(sp_abundant, lang="es")
    assert len(fig.data) >= 2
    assert "El capital sobra: un dólar vale lo mismo en el campo que en el banco." in fig.layout.title.text


def test_additions_4_slack_duals_chart_b():
    """Addition 4: Chart B when both duals are 0 displays
    'Capital y crédito sobran: un dólar más no agrega valor.'"""
    from app import create_resource_shadow_prices_chart

    sp_slack = {
        "own_capital": {"usd_per_extra_dollar": 0.0},
        "credit_line": {"usd_per_extra_dollar": 0.0},
    }
    fig = create_resource_shadow_prices_chart(sp_slack, lang="es")
    assert any("Capital y crédito sobran: un dólar más no agrega valor." in a.text for a in fig.layout.annotations)


def test_additions_5_constraints_headers_and_empty():
    """Addition 5: Constraints table empty state and headers."""
    import dora.tools
    dora.tools.DEFAULT_PRICE_SOURCE = "magyp_june"
    from app import run_scenario

    r_empty = run_scenario(area_ha=500, own_capital_usd=50000, region="southeast_buenos_aires", lang="es")
    df_empty = r_empty["constraints"]
    assert list(df_empty.columns) == ["Restricción", "Límite", "Usado", "Costo de oportunidad"]
    assert len(df_empty) == 0

    r_c = run_scenario(area_ha=500, own_capital_usd=50000, constraints_df=[["min_area", "corn", 150, "", None]], region="southeast_buenos_aires", lang="es")
    df_c = r_c["constraints"]
    assert list(df_c.columns) == ["Restricción", "Límite", "Usado", "Costo de oportunidad"]
    assert len(df_c) > 0


def test_additions_7_no_duplicate_comparison_under_tenure():
    """Addition 7: 'Comparación: una hectárea más te vale ...' not repeated under tenure."""
    import dora.tools
    dora.tools.DEFAULT_PRICE_SOURCE = "magyp_june"
    from app import run_scenario

    r = run_scenario(area_ha=2000, own_capital_usd=500000, region="pampas_core", lang="es")
    assert "Comparación:" not in r["land_card"]


def test_section_6_10_no_sombra_no_shadow():
    """Section 6.10: Rendered Scenario tab texts (es and en) contain no 'sombra' and no 'shadow'."""
    import dora.tools
    dora.tools.DEFAULT_PRICE_SOURCE = "magyp_june"
    from app import run_scenario

    for lang in ("es", "en"):
        r = run_scenario(area_ha=2000, own_capital_usd=500000, region="pampas_core", lang=lang)
        forbidden = "sombra" if lang == "es" else "shadow"
        assert forbidden not in r["plan"].lower()
        assert forbidden not in r["land_card"].lower()
        assert forbidden not in r["resource_cards"].lower()
        for col in r["constraints"].columns:
            assert forbidden not in str(col).lower()
        for col in r["tax_wedge_table"].columns:
            assert forbidden not in str(col).lower()
