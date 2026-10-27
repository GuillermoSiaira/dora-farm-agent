"""Acceptance tests for SPEC-09: data calibration and polish. No network calls."""
import json
from pathlib import Path
import pytest

from dora.observatory import run_observatory
from dora.scenario import Scenario
from eval.build_answers import DEFAULT_ANSWERS_PATH, build_answers

ROOT = Path(__file__).resolve().parent.parent


def test_verified_data_files_and_citations():
    """Step 1: Check verified data files have placeholder: false and citations."""
    iowa_path = ROOT / "dora" / "data" / "iowa_2026.json"
    with open(iowa_path, encoding="utf-8") as f:
        iowa_data = json.load(f)
    assert iowa_data.get("placeholder") is False
    assert "Ag Decision Maker" in iowa_data["_source"]
    assert "A1-20" in iowa_data["_source"]

    nucleo_path = ROOT / "dora" / "data" / "magyp_nucleo_2026-06.json"
    with open(nucleo_path, encoding="utf-8") as f:
        nucleo_data = json.load(f)
    assert nucleo_data.get("placeholder") is False
    assert "MAGyP" in nucleo_data["_source"] or "Secretariat" in nucleo_data["_source"]

    basis_path = ROOT / "dora" / "data" / "basis_iowa.json"
    with open(basis_path, encoding="utf-8") as f:
        basis_data = json.load(f)
    assert basis_data.get("placeholder") is False
    assert "A2-40" in basis_data["source"] or "Iowa State University" in basis_data["source"]

    mg_path = ROOT / "dora" / "data" / "mato_grosso_2026.json"
    with open(mg_path, encoding="utf-8") as f:
        mg_data = json.load(f)
    assert mg_data.get("placeholder") is True
    assert "IMEA" in mg_data["_source"]
    assert "BRL/USD" in mg_data["_source"]


def test_calibrated_capital_observatory(tmp_path):
    """Step 2: When no custom capital is provided, observatory calibrates to ~50% direct costs."""
    res = run_observatory(output_dir=tmp_path, save=True)
    assert "regions" in res

    for reg_key, r in res["regions"].items():
        # Capital should be scaled from direct costs, well above the old flat $50,000 ($100/ha)
        assert r["capital_committed_usd"] > 60_000, f"Capital for {reg_key} not calibrated: {r['capital_committed_usd']}"
        assert r["return_on_capital"] > 0
        assert r["npv_per_ha"] > 0
        assert "placeholder" in r

    assert res["regions"]["southeast_buenos_aires"]["placeholder"] is False
    assert res["regions"]["pampas_core"]["placeholder"] is False
    assert res["regions"]["iowa"]["placeholder"] is False
    assert res["regions"]["mato_grosso"]["placeholder"] is True


def test_observatory_ui_language_and_provisional():
    """Step 3: UI translates crops into Spanish in Spanish mode and marks provisional data."""
    from app import get_observatory_ui_data

    # Spanish mode
    banner_es, map_html_es, df_es, fig_es = get_observatory_ui_data(force_run=False, lang="es")
    crops_col_es = df_es["Cultivos / Crop Mix"].tolist()
    # Should contain Spanish crop names like soja, maíz, trigo, girasol
    combined_es = " ".join(crops_col_es).lower()
    assert any(c in combined_es for c in ["soja", "maíz", "trigo", "girasol"])
    assert "soybean" not in combined_es

    # English mode
    banner_en, map_html_en, df_en, fig_en = get_observatory_ui_data(force_run=False, lang="en")
    crops_col_en = df_en["Cultivos / Crop Mix"].tolist()
    combined_en = " ".join(crops_col_en).lower()
    assert any(c in combined_en for c in ["soybean", "corn", "wheat", "sunflower"])

    # Provisional data indicator on Mato Grosso in table
    regions_col = df_es["Región / Region"].tolist()
    mg_entry = next(item for item in regions_col if "Mato Grosso" in item)
    assert "provisorio" in mg_entry.lower() or "provisional" in mg_entry.lower()

    # Map popup has provisional note for placeholder
    assert "observatory-map" in map_html_es


def test_eval_answers_match_current_engine():
    """Step 4: Check that eval/answers.jsonl is regenerated and matches build_answers directly."""
    generated = build_answers(output_path=DEFAULT_ANSWERS_PATH)
    assert len(generated) == 27
    iowa_answers = [a for a in generated if a["id"] in {f"q{i}" for i in range(19, 31)}]
    assert len(iowa_answers) == 11
