"""Acceptance tests for SPEC-34: real-price invoices, photos, and comparison metrics."""
from __future__ import annotations

import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
E3 = ROOT / "eval" / "e3"
REAL_MEDIA = E3 / "media" / "real_invoices"


def test_real_prices_and_references():
    """1. Every price in real_prices.json has url, published_on, read_on and a non-empty quote;

    every case's prices_from ids exist there.
    """
    prices_file = E3 / "real_prices.json"
    assert prices_file.is_file(), "eval/e3/real_prices.json missing"
    prices = json.loads(prices_file.read_text(encoding="utf-8"))
    assert len(prices) >= 5, f"Expected at least 5 prices, got {len(prices)}"

    price_ids = set()
    for p in prices:
        assert p.get("id"), f"Price missing id: {p}"
        price_ids.add(p["id"])
        assert p.get("url") and (p["url"].startswith("http") or p["url"].startswith("file://")), f"{p['id']} invalid url"
        assert p.get("published_on"), f"{p['id']} missing published_on"
        assert p.get("read_on"), f"{p['id']} missing read_on"
        assert p.get("quote") and len(str(p["quote"]).strip()) > 0, f"{p['id']} empty quote"
        assert p.get("price") is not None, f"{p['id']} missing price"
        assert p.get("currency") in ("USD", "ARS"), f"{p['id']} invalid currency"

    cases_file = E3 / "real_cases.json"
    assert cases_file.is_file(), "eval/e3/real_cases.json missing"
    cases = json.loads(cases_file.read_text(encoding="utf-8"))
    invoice_cases = cases.get("invoices", cases) if isinstance(cases, dict) else cases

    for c in invoice_cases:
        assert "prices_from" in c, f"Case {c['id']} missing prices_from"
        for p_id in c["prices_from"]:
            assert p_id in price_ids, f"Case {c['id']} references unknown price id '{p_id}'"


def test_real_cases_math():
    """2. For each case: line amounts = quantity x unit price; net = sum of lines;

    total = net + VAT (0 for Iowa); all to the cent.
    """
    cases_file = E3 / "real_cases.json"
    cases = json.loads(cases_file.read_text(encoding="utf-8"))
    invoice_cases = cases.get("invoices", cases) if isinstance(cases, dict) else cases

    for c in invoice_cases:
        cid = c["id"]
        line_sum = 0.0
        for line in c["lines"]:
            expected_amount = round(line["qty"] * line["unit_price"], 2)
            assert abs(line["amount"] - expected_amount) < 0.015, (
                f"{cid} line {line['concept']}: {line['amount']} != {line['qty']} * {line['unit_price']}"
            )
            line_sum += line["amount"]
        line_sum = round(line_sum, 2)
        assert abs(c["net"] - line_sum) < 0.015, f"{cid} net {c['net']} != sum of lines {line_sum}"

        if c.get("region") == "iowa" or c.get("crop") and "iowa" in str(c.get("region", "")):
            assert c.get("vat", 0.0) == 0.0, f"{cid} Iowa invoice should have 0 VAT (Ag exempt)"
            assert abs(c["total"] - c["net"]) < 0.015, f"{cid} Iowa total should equal net"
        else:
            expected_total = round(c["net"] + c.get("vat", 0.0), 2)
            assert abs(c["total"] - expected_total) < 0.015, (
                f"{cid} total {c['total']} != net {c['net']} + vat {c.get('vat')}"
            )


def test_invoice_metrics_computation():
    """3. invoice_usd_ha and diff_pct are computed as in 4 (unit test on hand-made cases, incl. ARS)."""
    import sys
    sys.path.insert(0, str(ROOT / "eval"))
    from run_e3 import compute_invoice_metrics

    # Case A: USD invoice
    # Net $22,000, 100 ha -> $220.00/ha. Model baseline: $214.20/ha.
    # diff_pct = (220.0 - 214.2) / 214.2 = +0.027077 -> +0.0271 (+2.71%)
    inv_usd_ha, diff_pct = compute_invoice_metrics(
        net=22000.0, covers_ha=100.0, currency="USD", rate=None, model_usd_ha=214.2
    )
    assert inv_usd_ha == 220.0
    assert diff_pct == 0.0271

    # Case B: ARS invoice
    # Net 9,928,292 ARS, 80 ha, FX 1545.50 ARS/USD -> 6,424.00 USD -> 80.30 USD/ha.
    # Model baseline: 61.80 USD/ha.
    # diff_pct = (80.30 - 61.80) / 61.80 = 0.29935 -> 0.2994 (+29.94%)
    inv_usd_ha_ars, diff_pct_ars = compute_invoice_metrics(
        net=9928292.0, covers_ha=80.0, currency="ARS", rate=1545.50, model_usd_ha=61.8
    )
    assert inv_usd_ha_ars == 80.30
    assert diff_pct_ars == 0.2994

    # Edge cases
    assert compute_invoice_metrics(100.0, 0, "USD", None, 50.0) == (None, None)
    assert compute_invoice_metrics(100.0, 10, "ARS", None, 50.0) == (None, None)


def test_run_e3_default_cases():
    """4. run_e3.py without --cases behaves as before (same case ids loaded)."""
    cases_default = json.loads((E3 / "cases.json").read_text(encoding="utf-8"))
    assert "invoices" in cases_default
    ids = [c["id"] for c in cases_default["invoices"]]
    assert ids == ["f1", "f2", "f3", "f4", "f5", "f6"]


def test_real_invoice_images_exist():
    """5. The images listed in real_cases.json exist (rN.png); photos are optional."""
    cases_file = E3 / "real_cases.json"
    cases = json.loads(cases_file.read_text(encoding="utf-8"))
    invoice_cases = cases.get("invoices", cases) if isinstance(cases, dict) else cases

    for c in invoice_cases:
        cid = c["id"]
        png_path = REAL_MEDIA / f"{cid}.png"
        assert png_path.is_file(), f"Missing clean invoice image: {png_path}"


def test_saved_source_evidence_and_verbatim_quotes():
    """6. For every entry of real_prices.json, the saved source exists in eval/e3/sources/

    and contains quote verbatim (after collapsing whitespace). Offline test.
    """
    import re
    sources_dir = E3 / "sources"
    assert sources_dir.is_dir(), "eval/e3/sources directory missing"
    index_file = sources_dir / "index.json"
    assert index_file.is_file(), "eval/e3/sources/index.json missing"
    index_records = {r["id"]: r for r in json.loads(index_file.read_text(encoding="utf-8"))}

    prices_file = E3 / "real_prices.json"
    prices = json.loads(prices_file.read_text(encoding="utf-8"))

    def _collapse(s: str) -> str:
        return re.sub(r"\s+", " ", s).strip()

    for p in prices:
        pid = p["id"]
        assert pid in index_records, f"Price {pid} not found in sources/index.json"
        rec = index_records[pid]
        assert rec.get("status") == 200, f"Source for {pid} status is {rec.get('status')} != 200"

        saved_path = ROOT / rec["saved_file"]
        assert saved_path.is_file(), f"Source file {saved_path} does not exist on disk"

        content = _collapse(saved_path.read_text(encoding="utf-8", errors="ignore"))
        quote = _collapse(p["quote"])
        assert quote in content, f"Verbatim quote for {pid} not found in saved source file {saved_path.name}: {quote[:60]}..."


def test_last_npv_extraction_prefers_override_call():
    """7. last_npv correctly extracts the evaluate_season call with costs_override

    rather than the baseline comparison call. Verified on r1's saved answer.
    """
    import sys
    sys.path.insert(0, str(ROOT / "eval"))
    from run_e3 import last_npv

    results_path = ROOT / "eval" / "results" / "e3_real_prices.json"
    assert results_path.is_file(), "eval/results/e3_real_prices.json missing"
    results = json.loads(results_path.read_text(encoding="utf-8"))
    r1 = next(rec for rec in results["invoices"] if rec["id"] == "r1")

    # r1 answer text quotes 86710 USD
    answer_text = r1["media_run"]["answers"][0]
    assert "86710" in answer_text or "86.710" in answer_text

    # last_npv should return 86709.57 (matching expected), not the baseline 88186.60
    npv = last_npv(r1["media_run"])
    assert npv == 86709.57, f"last_npv extracted {npv} instead of 86709.57"



