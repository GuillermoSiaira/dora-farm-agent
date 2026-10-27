import datetime
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from dora.feeds import (
    CBOT_CROPS,
    MagypPricesFeed,
    RateLimitError,
    YahooCbotFeed,
    build_argentine_curve,
    compute_argentine_basis,
    http_get,
    refresh,
)
from dora.prices import cents_per_bushel_to_usd_per_tonne, load_curve
from dora.scenario import Scenario
from dora.tools import build_scenario, run_tool

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_MAGYP_HTML = FIXTURES_DIR / "magyp_precios.html"


# 1. Symbols built for corn from Oct 2026
def test_cbot_symbols_built_for_corn_from_oct_2026():
    feed = YahooCbotFeed()
    symbols = feed.build_symbols(start_year=2026, start_month=10, months_ahead=18)
    corn_symbols = [s for s, _ in symbols["corn"]]
    assert corn_symbols[:4] == ["ZCZ26.CBT", "ZCH27.CBT", "ZCK27.CBT", "ZCN27.CBT"]
    corn_months = [m for _, m in symbols["corn"]]
    assert corn_months[:4] == ["2026-12", "2027-03", "2027-05", "2027-07"]


# 2. Mocked response with regularMarketPrice 454.25 for ZCZ26.CBT
def test_mocked_contract_response_and_usd_conversion(tmp_path):
    mock_yahoo_response = {
        "chart": {
            "result": [
                {
                    "meta": {
                        "currency": "USX",
                        "symbol": "ZCZ26.CBT",
                        "regularMarketPrice": 454.25,
                    }
                }
            ],
            "error": None,
        }
    }

    feed = YahooCbotFeed()
    with patch("dora.feeds.http_get", return_value=json.dumps(mock_yahoo_response)):
        price = feed.fetch_contract_price("ZCZ26.CBT")
        assert price == 454.25

        snapshot = feed.fetch(start_year=2026, start_month=10, as_of="2026-10-27")
        assert snapshot["curve"]["corn"]["2026-12"] == 454.25

        # Save to file and verify load_curve returns 178.83 USD/t (rel 1e-4)
        snap_path = tmp_path / "test_cbot.json"
        snap_path.write_text(json.dumps(snapshot), encoding="utf-8")
        loaded = load_curve(snap_path)
        assert loaded["curve"]["corn"]["2026-12"] == pytest.approx(178.83, rel=1e-4)


# 3. Partial fetch does not overwrite an existing good file
def test_partial_fetch_does_not_overwrite_good_file(tmp_path):
    target_file = tmp_path / "cbot_latest.json"
    good_snapshot = {
        "source": "CBOT futures via Yahoo Finance (delayed)",
        "as_of": "2026-10-26",
        "unit": "cents/bu",
        "placeholder": False,
        "curve": {
            "corn": {"2026-12": 430.0, "2027-03": 445.0},
            "soybean": {"2027-01": 1010.0, "2027-03": 1022.0},
            "wheat": {"2026-12": 545.0, "2027-03": 560.0},
        },
    }
    target_file.write_text(json.dumps(good_snapshot), encoding="utf-8")
    initial_content = target_file.read_text(encoding="utf-8")

    # Mock feed returning only 1 contract for corn (partial)
    partial_snapshot = {
        "source": "CBOT futures via Yahoo Finance (delayed)",
        "as_of": "2026-10-27",
        "unit": "cents/bu",
        "placeholder": False,
        "curve": {
            "corn": {"2026-12": 450.0},
            "soybean": {},
            "wheat": {},
        },
    }
    mock_feed = MagicMock()
    mock_feed.fetch.return_value = partial_snapshot

    res = refresh(feed=mock_feed, max_age_hours=0, target_path=target_file)
    assert res["status"] == "kept_last"
    assert res["as_of"] == "2026-10-26"
    assert res["contracts"] == 6
    assert target_file.read_text(encoding="utf-8") == initial_content


# 4. Network error -> status kept_last, file is unchanged
def test_network_error_keeps_last_file(tmp_path):
    target_file = tmp_path / "cbot_latest.json"
    good_snapshot = {
        "source": "CBOT futures via Yahoo Finance (delayed)",
        "as_of": "2026-10-26",
        "unit": "cents/bu",
        "placeholder": False,
        "curve": {
            "corn": {"2026-12": 430.0, "2027-03": 445.0},
            "soybean": {"2027-01": 1010.0, "2027-03": 1022.0},
            "wheat": {"2026-12": 545.0, "2027-03": 560.0},
        },
    }
    target_file.write_text(json.dumps(good_snapshot), encoding="utf-8")
    initial_content = target_file.read_text(encoding="utf-8")

    mock_feed = MagicMock()
    mock_feed.fetch.side_effect = ConnectionError("Network down")

    res = refresh(feed=mock_feed, max_age_hours=0, target_path=target_file)
    assert res["status"] == "kept_last"
    assert res["as_of"] == "2026-10-26"
    assert res["contracts"] == 6
    assert target_file.read_text(encoding="utf-8") == initial_content


# 5. Fresh file (age < 24 h) -> status fresh, no HTTP calls made
def test_fresh_file_skips_fetch(tmp_path):
    target_file = tmp_path / "cbot_latest.json"
    good_snapshot = {
        "source": "CBOT futures via Yahoo Finance (delayed)",
        "as_of": "2026-10-27",
        "unit": "cents/bu",
        "placeholder": False,
        "curve": {
            "corn": {"2026-12": 430.0, "2027-03": 445.0},
            "soybean": {"2027-01": 1010.0, "2027-03": 1022.0},
            "wheat": {"2026-12": 545.0, "2027-03": 560.0},
        },
    }
    target_file.write_text(json.dumps(good_snapshot), encoding="utf-8")

    mock_feed = MagicMock()
    res = refresh(feed=mock_feed, max_age_hours=24.0, target_path=target_file)

    assert res["status"] == "fresh"
    assert res["as_of"] == "2026-10-27"
    assert res["contracts"] == 6
    mock_feed.fetch.assert_not_called()


# 6. refresh_prices through run_tool returns valid JSON with status
def test_refresh_prices_tool():
    out_str = run_tool("refresh_prices", "{}")
    out = json.loads(out_str)
    assert "status" in out
    assert out["status"] in ("updated", "fresh", "kept_last")
    assert "as_of" in out
    assert "contracts" in out
    assert isinstance(out["contracts"], int)


# 7. MAGyP HTML parser extracts FOB 488 and FAS 577,334 for 26/10/2026, and basis
def test_magyp_html_parser_and_basis_calculation():
    assert SAMPLE_MAGYP_HTML.is_file(), f"Fixture missing at {SAMPLE_MAGYP_HTML}"
    html = SAMPLE_MAGYP_HTML.read_text(encoding="utf-8", errors="replace")

    feed = MagypPricesFeed()
    parsed = feed.parse(html)

    assert parsed["date"] == "2026-10-26"
    assert parsed["quotes"]["soybean"]["fob_usd_t"] == 488.0
    assert parsed["quotes"]["soybean"]["fas_ars_t"] == 577334.0
    assert parsed["quotes"]["wheat"]["fob_usd_t"] == 245.0
    assert parsed["quotes"]["wheat"]["fas_ars_t"] == 324248.0
    assert parsed["quotes"]["corn"]["fob_usd_t"] == 210.0
    assert parsed["quotes"]["corn"]["fas_ars_t"] == 273263.0
    assert parsed["quotes"]["sunflower"]["fob_usd_t"] == 603.0
    assert parsed["quotes"]["sunflower"]["fas_ars_t"] == 631858.0

    # Basis calculation test: FAS / fx_rate - nearest CBOT
    fx_rate = 1540.4751
    mock_cbot_snapshot = {
        "curve": {
            "soybean": {"2027-01": 1010.0, "2027-03": 1022.0},
            "corn": {"2026-12": 430.0, "2027-03": 445.0},
            "wheat": {"2026-12": 545.0, "2027-03": 560.0},
        }
    }
    basis = compute_argentine_basis(parsed, fx_rate, mock_cbot_snapshot)

    # Expected soybean: 577334 / 1540.4751 - (1010/100 * 36.744) = 374.7765 - 371.1144 = 3.66 USD/t
    expected_soybean_basis = round((577334.0 / fx_rate) - cents_per_bushel_to_usd_per_tonne("soybean", 1010.0), 2)
    assert basis["soybean"] == pytest.approx(expected_soybean_basis, abs=0.02)
    assert basis["sunflower"] == 0.0

    # Test error on changed table structure
    broken_html = "<html><body><h1>Precios cambiados</h1><p>No hay cotizaciones</p></body></html>"
    with pytest.raises(ValueError, match="table structure may have changed"):
        feed.parse(broken_html)


# 8. build_scenario and Scenario with cbot_latest and Argentina region
def test_scenario_with_cbot_latest_and_argentina_region():
    sc = Scenario(
        area_ha=500,
        price_curve_source="cbot_latest",
        region="Argentina",
    )
    # basis_usd_t loaded from basis_argentina.json
    assert sc.basis_usd_t != {}
    assert "soybean" in sc.basis_usd_t
    assert sc.price_curve_source == "cbot_latest"


# 9. Optional live test, marked @pytest.mark.live and skipped by default
@pytest.mark.live
@pytest.mark.skip(reason="Live network test skipped by default")
def test_live_cbot_fetch():
    feed = YahooCbotFeed()
    price = feed.fetch_contract_price("ZCZ26.CBT")
    assert price is not None
    assert price > 0
