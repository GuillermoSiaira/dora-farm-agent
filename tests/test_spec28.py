"""Acceptance tests for SPEC-28: prices, regions, and inputs.

All tests run strictly offline without network access.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from dora import feeds
from dora import prices
from dora import tools
from dora.observatory import run_observatory
from dora.scenario import Scenario, ScenarioError
from dora.tools import compare_regions, evaluate_season, record_document, assess_field_image
from dora.verifier import check_scenario, support

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# 1. Iowa & Mato Grosso in same_budget swap to CBOT curve
# ---------------------------------------------------------------------------
def test_item_1_same_budget_swaps_to_cbot_curve():
    """Item 1: same_budget with price_curve_source: 'argentina_latest' swaps to 'cbot_latest'
    for Iowa and Mato Grosso, matching the numbers of a direct call with cbot_latest."""
    sc_arg = {"own_capital_usd": 100_000, "price_curve_source": "argentina_latest"}
    res_arg = compare_regions(sc_arg, regions=["iowa", "mato_grosso"], mode="same_budget")

    sc_cbot = {"own_capital_usd": 100_000, "price_curve_source": "cbot_latest"}
    res_cbot = compare_regions(sc_cbot, regions=["iowa", "mato_grosso"], mode="same_budget")

    for r in ["iowa", "mato_grosso"]:
        assert res_arg["regions"][r]["npv_usd"] == pytest.approx(res_cbot["regions"][r]["npv_usd"], abs=0.01)
        assert res_arg["regions"][r]["price_source"] == res_cbot["regions"][r]["price_source"]
        assert "CBOT" in res_arg["regions"][r]["price_source"]


# ---------------------------------------------------------------------------
# 2. Snapshot freshness: touch does not refresh, age is checked against as_of
# ---------------------------------------------------------------------------
def test_item_2_snapshot_age_checks_as_of_and_fetched_at(tmp_path):
    """Item 2: Snapshot with as_of 3 days ago triggers refresh when touched now."""
    mock_feed = MagicMock()
    mock_feed.fetch.return_value = {
        "as_of": "2026-10-31",
        "fetched_at": "2026-10-31T12:00:00Z",
        "unit": "cents/bu",
        "source": "CBOT mock",
        "curve": {
            "corn": {"2026-12": 170.0, "2027-03": 175.0},
            "soybean": {"2026-11": 360.0, "2027-01": 365.0},
            "wheat": {"2026-12": 210.0, "2027-03": 215.0},
        },
    }

    snap_data = {
        "as_of": "2026-10-27",
        "fetched_at": "2026-10-27T12:00:00Z",
        "unit": "cents/bu",
        "source": "CBOT",
        "curve": {},
    }
    dummy_file = tmp_path / "cbot_dummy.json"
    dummy_file.write_text(json.dumps(snap_data), encoding="utf-8")

    age = feeds._snapshot_age_hours(snap_data, dummy_file, today="2026-10-31")
    assert age >= 72.0  # 4 days >= 72 hours

    # refresh() calls mock_feed when snapshot is older than 24 hours
    res = feeds.refresh(feed=mock_feed, target_path=dummy_file, today="2026-10-31")
    assert mock_feed.fetch.call_count == 1
    assert res["cbot"] == "updated" or res.get("sources", {}).get("cbot", {}).get("status") == "updated"


# ---------------------------------------------------------------------------
# 3. Network failure flags curve as stale with reason
# ---------------------------------------------------------------------------
def test_item_3_network_failure_flags_stale_with_reason():
    """Item 3: Mock feed raising -> evaluate_season with price_curve_source: 'cbot_latest'
    returns stale: true and stale_reason naming source and saved date."""
    def fake_refresh():
        return {
            "cbot": "kept_last",
            "stale": True,
            "stale_reason": "CBOT no respondió; último dato guardado del 2026-10-27",
        }

    with patch("dora.feeds.refresh", side_effect=fake_refresh):
        res = evaluate_season({"price_curve_source": "cbot_latest"})
        assert res.get("stale") is True
        assert "stale_reason" in res
        assert "CBOT" in res["stale_reason"]
        assert "2026-10-27" in res["stale_reason"]


# ---------------------------------------------------------------------------
# 4. Partial failure: MAGyP fails, Argentine curve marked stale
# ---------------------------------------------------------------------------
def test_item_4_partial_failure_argentina_curve_stale(tmp_path):
    """Item 4: CBOT ok, MAGyP raising -> status magyp: kept_last, Argentine curve flagged stale."""
    mock_feed = MagicMock()
    mock_feed.fetch.return_value = {
        "as_of": "2026-10-31",
        "fetched_at": "2026-10-31T12:00:00Z",
        "unit": "cents/bu",
        "source": "CBOT mock",
        "curve": {
            "corn": {"2026-12": 170.0, "2027-03": 175.0},
            "soybean": {"2026-11": 360.0, "2027-01": 365.0},
            "wheat": {"2026-12": 210.0, "2027-03": 215.0},
        },
    }

    dummy_cbot = tmp_path / "cbot_latest.json"
    dummy_arg = tmp_path / "argentina_latest.json"
    dummy_arg.write_text(feeds.ARGENTINA_LATEST_PATH.read_text(encoding="utf-8"), encoding="utf-8")

    with patch("dora.feeds.MagypPricesFeed") as mock_magyp_cls, \
         patch("dora.feeds.ARGENTINA_LATEST_PATH", dummy_arg):
        mock_magyp_inst = MagicMock()
        mock_magyp_inst.fetch.side_effect = feeds.FeedError("MAGyP connection timeout")
        mock_magyp_cls.return_value = mock_magyp_inst

        status = feeds.refresh(feed=mock_feed, target_path=dummy_cbot, today="2026-10-31")
        assert status.get("sources", {}).get("cbot", {}).get("status") == "updated"
        assert status.get("sources", {}).get("magyp", {}).get("status") == "kept_last"
        assert status.get("stale") is True
        assert "MAGyP connection timeout" in status.get("stale_reason", "")

        # Check Argentine curve file is marked stale
        arg_snap = json.loads(dummy_arg.read_text(encoding="utf-8"))
        assert arg_snap.get("stale") is True


# ---------------------------------------------------------------------------
# 5. Pergamino regional source label
# ---------------------------------------------------------------------------
def test_item_5_pergamino_source_label_mentions_core_not_southeast():
    """Item 5: evaluate_season for pampas_core -> source mentions Zona Núcleo / Pergamino, not Southeast."""
    res = evaluate_season({"region": "pampas_core"})
    src = res.get("source", "")
    assert "Zona Núcleo" in src or "Pergamino" in src
    assert "Southeast" not in src


# ---------------------------------------------------------------------------
# 6. Default price source: latest vs magyp_june
# ---------------------------------------------------------------------------
def test_item_6_default_price_source_latest_vs_magyp_june():
    """Item 6: DEFAULT_PRICE_SOURCE = 'latest' uses curve of the day by default;
    'magyp_june' uses June report."""
    try:
        tools.DEFAULT_PRICE_SOURCE = "latest"
        res_latest = evaluate_season({"region": "southeast_buenos_aires"})
        assert "price_source" in res_latest
        assert "curve" in res_latest["price_source"].lower() or "latest" in str(res_latest.get("price_curve_metadata", {})) or "official spot" in res_latest["price_source"].lower()

        tools.DEFAULT_PRICE_SOURCE = "magyp_june"
        res_june = evaluate_season({"region": "southeast_buenos_aires"})
        assert "price_source" not in res_june
        assert "Southeast" in res_june.get("source", "")
    finally:
        tools.DEFAULT_PRICE_SOURCE = "magyp_june"


# ---------------------------------------------------------------------------
# 7. Provisional marks in compare_regions & observatory
# ---------------------------------------------------------------------------
def test_item_7_provisional_marks_in_compare_regions_and_observatory():
    """Item 7: compare_regions for the 4 regions -> pampas_core and mato_grosso have non-empty
    provisional; the observatory agrees for every region."""
    cr = compare_regions({"area_ha": 500}, regions=["southeast_buenos_aires", "pampas_core", "iowa", "mato_grosso"], mode="same_farm")
    obs = run_observatory(regions=["southeast_buenos_aires", "pampas_core", "iowa", "mato_grosso"], save=False)

    assert len(cr["regions"]["pampas_core"]["provisional"]) > 0
    assert len(cr["regions"]["mato_grosso"]["provisional"]) > 0

    for r in ["southeast_buenos_aires", "pampas_core", "iowa", "mato_grosso"]:
        assert obs["regions"][r]["provisional"] == cr["regions"][r]["provisional"]


# ---------------------------------------------------------------------------
# 8. Observatory NPV equals compare_regions NPV within 0.01 USD
# ---------------------------------------------------------------------------
def test_item_8_observatory_npv_equals_compare_regions():
    """Item 8: For the same scenario, the observatory's NPV per region equals compare_regions' within 0.01 USD."""
    sc = {"area_ha": 500.0, "own_capital_usd": 120_000.0}
    regs = ["southeast_buenos_aires", "pampas_core", "iowa", "mato_grosso"]
    cr = compare_regions(sc, regions=regs, mode="same_farm")
    obs = run_observatory(scenario_template=sc, regions=regs, save=False)

    for r in regs:
        npv_cr = cr["regions"][r]["npv_usd"]
        npv_obs = obs["regions"][r]["npv_usd"]
        assert abs(npv_cr - npv_obs) < 0.01, f"Mismatch for {r}: compare_regions={npv_cr}, observatory={npv_obs}"


# ---------------------------------------------------------------------------
# 9. Observatory commentary uses DORA_MODEL and records commentary_error
# ---------------------------------------------------------------------------
def test_item_9_observatory_commentary_model_and_error(monkeypatch):
    """Item 9: Fake client uses DORA_MODEL; failing client sets commentary_error."""
    monkeypatch.setenv("DORA_MODEL", "custom-gpt-4-audit")

    class FakeClient:
        def __init__(self):
            self.seen_model = None
            self.chat = NS(completions=NS(create=self.create))

        def create(self, model, messages, tools):
            self.seen_model = model
            # Valid numbers from the observatory report
            text = "Southeast Buenos Aires presents a return on capital of 25.0% and freight of 18.0 USD/t to port Quequén."
            msg = NS(content=text, tool_calls=None)
            return NS(choices=[NS(message=msg)])

    client_fake = FakeClient()
    report = run_observatory(regions=["southeast_buenos_aires"], client=client_fake, save=False)
    assert client_fake.seen_model == "custom-gpt-4-audit"

    # Failing client records commentary_error
    class FailingClient:
        def __init__(self):
            self.chat = NS(completions=NS(create=self.create))

        def create(self, model, messages, tools):
            raise RuntimeError("API key invalid or model unavailable")

    report_fail = run_observatory(regions=["southeast_buenos_aires"], client=FailingClient(), save=False)
    assert report_fail["commentary"] is None
    assert "commentary_error" in report_fail
    assert "API key invalid or model unavailable" in report_fail["commentary_error"]


# ---------------------------------------------------------------------------
# 10. Invoices: explicit area_ha, ha line without amount, and accent normalization
# ---------------------------------------------------------------------------
def test_item_10_invoices_hectares_and_accent_normalization():
    """Item 10: Invoices divide by given hectares; 'Agroquímicos' maps to crop_protection;
    without hectares, notes per_ha_basis."""
    # Line with unit: ha and no amount defines invoice hectares
    items_typed = [
        {"concept": "Superficie tratada", "unit": "ha", "qty": 100},
        {"concept": "Agroquímicos para trigo", "unit": "L", "qty": 200, "unit_price": 25.0, "amount": 5000.0, "vat_rate": 0.21, "crop": "wheat"},
    ]
    res = record_document(kind="invoice", items=items_typed, scenario={"area_ha": 500, "region": "southeast_buenos_aires"})
    assert res["proposals"][0]["item"] == "crop_protection"
    # 5000 USD / 100 ha = 50 USD/ha
    assert res["proposals"][0]["proposed_usd_ha"] == 50.0

    # Explicit area_ha per item
    items_explicit = [
        {"concept": "Fertilizante urea", "area_ha": 50.0, "amount": 6000.0, "vat_rate": 0.105, "crop": "corn", "cost_item": "fertilizer"}
    ]
    res_exp = record_document(kind="invoice", items=items_explicit, scenario={"area_ha": 500})
    # 6000 / 50 = 120 USD/ha
    assert res_exp["proposals"][0]["proposed_usd_ha"] == 120.0

    # Missing hectares: divides by farm area and warns in per_ha_basis
    items_no_ha = [
        {"concept": "Semilla de soja", "amount": 10000.0, "vat_rate": 0.105, "crop": "soybean", "cost_item": "seed"}
    ]
    res_no_ha = record_document(kind="invoice", items=items_no_ha, scenario={"area_ha": 500})
    assert res_no_ha["proposals"][0]["proposed_usd_ha"] == 20.0
    assert "superficie del campo (no venía en la factura)" in res_no_ha.get("per_ha_basis", "")


# ---------------------------------------------------------------------------
# 11. Aerial photo: field is the farm (owned_ha), not 500 ha
# ---------------------------------------------------------------------------
def test_item_11_field_image_uses_farm_area_or_warns():
    """Item 11: scenario {'owned_ha': 600} and 4.8% mask -> field_ha: 600.0, affected_ha: 28.8."""
    fake_img = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAAAAAA6fptVAAAACklEQVR4nGNiAAAABgADNjd8qAAAAABJRU5ErkJggg=="
    fake_mask = np.zeros((10, 10), dtype=bool)

    with patch("dora.field_image.measure_damage", return_value={"share": 0.048, "objects": 1, "objects_per_concept": {"flood water": 1}, "mask": fake_mask}):
        # With owned_ha: 600
        res = assess_field_image(
            scenario={"owned_ha": 600.0, "own_capital_usd": 60_000.0},
            image=0,
            _images=[fake_img],
        )
        assert res["field_ha"] == 600.0
        assert res["affected_ha"] == 28.8

        # Without area or owned_ha: returns warning and share only
        res_no_area = assess_field_image(
            scenario={"own_capital_usd": 60_000.0},
            image=0,
            _images=[fake_img],
        )
        assert res_no_area["field_ha"] is None
        assert res_no_area["affected_ha"] is None
        assert "Superficie del campo desconocida" in res_no_area.get("warning", "")


# ---------------------------------------------------------------------------
# 12. Verifier: numbers written as words supported
# ---------------------------------------------------------------------------
def test_item_12_verifier_supports_word_numbers():
    """Item 12: User text 'tengo ochocientas hectáreas y pago a noventa días' supports 800 and 90."""
    text = "tengo ochocientas hectáreas y pago a noventa días"
    supp = support([], [text])
    assert 800.0 in supp
    assert 90.0 in supp

    # English words as well
    text_en = "I have five hundred hectares and four hundred dollars"
    supp_en = support([], [text_en])
    assert 500.0 in supp_en
    assert 400.0 in supp_en


# ---------------------------------------------------------------------------
# 13. Crossed seasons, passed sowings, and Rule 3 relaxation
# ---------------------------------------------------------------------------
def test_item_13_crossed_seasons_and_passed_sowings():
    """Item 13: With today=2026-10-31, Iowa & Pampas Core differ, Iowa next_season_start is in 2027,
    Pampas Core wheat is in crops_sowing_passed; with today=2026-04-01, Iowa next_season_start absent.
    Rule 3 allows omitting wheat when sowing has passed."""
    res_oct = compare_regions({"today": "2026-10-31"}, regions=["pampas_core", "iowa"], mode="same_farm")
    assert res_oct["calendars_differ"] is True
    assert "next_season_start" in res_oct["regions"]["iowa"]["calendar"]
    assert "2027" in res_oct["regions"]["iowa"]["calendar"]["next_season_start"]
    assert "wheat" in res_oct["regions"]["pampas_core"]["calendar"]["crops_sowing_passed"]

    res_apr = compare_regions({"today": "2026-04-01"}, regions=["pampas_core", "iowa"], mode="same_farm")
    assert "next_season_start" not in res_apr["regions"]["iowa"]["calendar"]

    # Rule 3 check_scenario: omitting wheat when sowing passed is allowed without rejection
    eval_tool_res = evaluate_season({"region": "pampas_core", "today": "2026-10-31"})
    # Farmer asks with 500 ha without mentioning wheat, model plans only corn, soybean, sunflower
    sc_model = {"area_ha": 500.0, "crops": ["corn", "soybean", "sunflower"], "region": "pampas_core"}
    farmer_text = "Tengo 500 ha en Pergamino. ¿Cuál es el mejor plan de siembra?"
    problems = check_scenario("evaluate_season", {"scenario": sc_model}, [farmer_text], [eval_tool_res])
    assert len(problems) == 0



# ---------------------------------------------------------------------------
# 14. Starting from today (for the analyst)
# ---------------------------------------------------------------------------
def test_item_14_start_today_iowa_and_pampas_core():
    """Item 14: with today = 2026-10-31:
    - Iowa with start: 'today' has season_start == '2027-04' and the same crops as with 'season';
    - Pampas Core with start: 'today' has no wheat and keeps season_start;
    - with start: 'season' every result equals today's (compare the dicts minus calendar).
    - With a curve that ends before a needed month, price_months_missing is not empty.
    - Scenario check: start: 'today' needs farmer words ('hoy', 'today', etc.)."""
    # 1. Iowa with start: "today"
    res_iowa_today = evaluate_season({"region": "iowa", "start": "today", "today": "2026-10-31"})
    assert res_iowa_today["calendar"]["season_start"] == "2027-04"
    assert set(res_iowa_today["calendar"]["crops"].keys()) == {"corn", "soybean"}

    # 2. Pampas Core with start: "today" has no wheat and keeps season_start == "2026-05"
    res_pampas_today = evaluate_season({"region": "pampas_core", "start": "today", "today": "2026-10-31"})
    assert res_pampas_today["calendar"]["season_start"] == "2026-05"
    assert "wheat" not in res_pampas_today["calendar"]["crops"]
    assert "wheat" not in res_pampas_today["hectares"]

    # 3. With start: "season" every result equals today's default (compare minus calendar)
    res_pampas_def = evaluate_season({"region": "pampas_core", "today": "2026-10-31"})
    res_pampas_season = evaluate_season({"region": "pampas_core", "start": "season", "today": "2026-10-31"})
    d_def = {k: v for k, v in res_pampas_def.items() if k != "calendar"}
    d_season = {k: v for k, v in res_pampas_season.items() if k != "calendar"}
    assert d_def == d_season

    # 4. With curve ending before a needed month, price_months_missing is not empty
    short_curve = {
        "corn": {"2026-12": 180.0},
        "soybean": {"2026-11": 350.0},
        "sunflower": {"2026-11": 400.0},
        "wheat": {"2026-12": 200.0},
    }
    with patch("dora.tools.load_curve") as mock_lc, patch("dora.feeds.refresh") as mock_ref:
        mock_ref.return_value = {"status": "fresh"}
        mock_lc.return_value = {
            "source": "Mock short",
            "as_of": "2026-10-31",
            "unit": "usd/t",
            "curve": short_curve,
        }
        res_short = evaluate_season({"region": "pampas_core", "price_curve_source": "cbot_latest"})
        assert len(res_short["calendar"]["price_months_missing"]) > 0

    # 5. Scenario check: start: "today" requires farmer words
    sc_today = {"area_ha": 500.0, "start": "today"}
    assert len(check_scenario("evaluate_season", {"scenario": sc_today}, ["Tengo 500 ha"], [])) > 0
    assert len(check_scenario("evaluate_season", {"scenario": sc_today}, ["Tengo 500 ha y quiero arrancar hoy"], [])) == 0


# ---------------------------------------------------------------------------
# 15. Livestock only
# ---------------------------------------------------------------------------
def test_item_15_livestock_only():
    """Item 15:
    - evaluate_season with crops: [] and livestock: ['cow_calf'] gives no crop hectares and positive cow_calf area;
    - Balcarce 500 ha, 100,000 USD, crops: [], livestock: ['cow_calf', 'steer_fattening'] gives
      cow_calf 199.9 ha, steer_fattening 300.1 ha, NPV 194,911.37;
    - with crops: [] and no livestock it is still a ScenarioError;
    - the result carries the provisional mark (placeholder: true at 1,050 ARS/USD);
    - scenario check requires farmer words for crops: []."""
    res = evaluate_season({"crops": [], "livestock": ["cow_calf"]})
    assert len(res["hectares"]) == 0
    assert res["hectares_livestock"]["cow_calf"] > 0
    assert any("placeholder" in p or "provisorio" in p for p in res.get("provisional", []))

    # Exact Balcarce 500 ha, 100k USD with cría e invernada
    res_balcarce = evaluate_season({
        "region": "southeast_buenos_aires",
        "owned_ha": 500.0,
        "own_capital_usd": 100_000.0,
        "crops": [],
        "livestock": ["cow_calf", "steer_fattening"],
    })
    assert len(res_balcarce["hectares"]) == 0
    assert res_balcarce["hectares_livestock"]["cow_calf"] == pytest.approx(199.9, abs=0.2)
    assert res_balcarce["hectares_livestock"]["steer_fattening"] == pytest.approx(300.1, abs=0.2)
    assert res_balcarce["npv_usd"] == pytest.approx(194_911.37, abs=1.0)
    assert any("1.050 ARS/USD" in p or "placeholder: true" in p for p in res_balcarce.get("provisional", []))

    # Error without livestock
    with pytest.raises(ScenarioError):
        evaluate_season({"crops": []})

    # Scenario check
    sc_empty = {"area_ha": 500.0, "crops": [], "livestock": ["cow_calf"]}
    assert len(check_scenario("evaluate_season", {"scenario": sc_empty}, ["Tengo 500 ha"], [])) > 0
    assert len(check_scenario("evaluate_season", {"scenario": sc_empty}, ["Tengo 500 ha y solo hago ganadería"], [])) == 0
    assert len(check_scenario("evaluate_season", {"scenario": sc_empty}, ["I have 500 ha and only cattle"], [])) == 0
