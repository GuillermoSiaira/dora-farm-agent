import json
import pytest
from unittest.mock import patch

from dora.tools import record_document, evaluate_season, _plan_view
from dora.scenario import Scenario, ScenarioError
from dora.engine import optimize


def test_1_two_lines_one_item():
    """1. Two lines, one item: urea 12,300 + MAP 10,200, crop: 'wheat', area_ha: 100 each,
    scenario Balcarce 500 ha -> one proposal wheat.fertilizer with proposed_usd_ha == 225.0,
    apply true, one entry in replaces."""
    items = [
        {"concept": "Urea granulada 46-0-0 a granel", "amount": 12300.0, "crop": "wheat", "area_ha": 100.0},
        {"concept": "Fosfato monoamónico (MAP) 11-52-0 a granel", "amount": 10200.0, "crop": "wheat", "area_ha": 100.0},
    ]
    sc = {"region": "southeast_buenos_aires", "area_ha": 500.0, "own_capital_usd": 50000.0}
    res = record_document(kind="invoice", items=items, scenario=sc)
    assert len(res["proposals"]) == 1
    p = res["proposals"][0]
    assert p["crop"] == "wheat"
    assert p["item"] == "fertilizer"
    assert p["proposed_usd_ha"] == 225.0
    assert p["apply"] is True
    assert len(res["replaces"]) == 1
    assert res["replaces"][0] == "wheat.fertilizer = 225.0 USD/ha"


def test_2_two_items_one_invoice():
    """2. Two items, one invoice: seed 18,194.75 and anhydrous ammonia 27,110.83, crop: 'corn',
    64.75 ha, Iowa -> two proposals, corn.seed == 281.0 and corn.fertilizer == 418.7, both applied."""
    items = [
        {"concept": "Commercial Seed Corn (80,000 kernels/unit)", "amount": 18194.75, "crop": "corn", "area_ha": 64.75},
        {"concept": "Bulk Nitrogen Fertilizer - Anhydrous ammonia", "amount": 27110.83, "crop": "corn", "area_ha": 64.75},
    ]
    sc = {"region": "iowa", "area_ha": 202.34, "own_capital_usd": 150000.0}
    res = record_document(kind="invoice", items=items, scenario=sc)
    assert len(res["proposals"]) == 2
    props = {p["item"]: p for p in res["proposals"]}
    assert "seed" in props and "fertilizer" in props
    assert props["seed"]["proposed_usd_ha"] == 281.0
    assert props["seed"]["apply"] is True
    assert props["fertilizer"]["proposed_usd_ha"] == 418.7
    assert props["fertilizer"]["apply"] is True


def test_3_active_ingredients_without_cost_item():
    """3. Active ingredients without cost_item: 'Glifosato 66,2 % bidón 20 L', 'Atrazina 90 % WG',
    'Dual Gold (S-metolacloro 96 %)' map to crop_protection; 'Urea granulada' and 'Anhydrous ammonia'
    to fertilizer; 'Mapa de rindes' does not map to fertilizer."""
    items = [
        {"concept": "Glifosato 66,2 % bidón 20 L", "amount": 100.0, "crop": "soybean", "area_ha": 10.0},
        {"concept": "Atrazina 90 % WG", "amount": 100.0, "crop": "corn", "area_ha": 10.0},
        {"concept": "Dual Gold (S-metolacloro 96 %)", "amount": 100.0, "crop": "corn", "area_ha": 10.0},
        {"concept": "Urea granulada", "amount": 100.0, "crop": "wheat", "area_ha": 10.0},
        {"concept": "Anhydrous ammonia", "amount": 100.0, "crop": "corn", "area_ha": 10.0},
        {"concept": "Mapa de rindes", "amount": 100.0, "crop": "wheat", "area_ha": 10.0},
    ]
    sc = {"region": "southeast_buenos_aires", "area_ha": 500.0}
    res = record_document(kind="invoice", items=items, scenario=sc)
    line_map = {l["concept"]: l for l in res["lines"]}
    assert line_map["Glifosato 66,2 % bidón 20 L"]["cost_item"] == "crop_protection"
    assert line_map["Atrazina 90 % WG"]["cost_item"] == "crop_protection"
    assert line_map["Dual Gold (S-metolacloro 96 %)"]["cost_item"] == "crop_protection"
    assert line_map["Urea granulada"]["cost_item"] == "fertilizer"
    assert line_map["Anhydrous ammonia"]["cost_item"] == "fertilizer"
    assert line_map["Mapa de rindes"]["cost_item"] != "fertilizer"


def test_4_cost_item_from_model_wins():
    """4. cost_item from the model wins over the keywords (a line 'Producto X' with cost_item: 'seed' is seed)."""
    items = [
        {"concept": "Producto X", "cost_item": "seed", "amount": 1000.0, "crop": "wheat", "area_ha": 50.0}
    ]
    sc = {"region": "southeast_buenos_aires", "area_ha": 500.0}
    res = record_document(kind="invoice", items=items, scenario=sc)
    assert res["lines"][0]["cost_item"] == "seed"
    assert res["proposals"][0]["item"] == "seed"


def test_5_vat_line():
    """5. VAT line: a line 'IVA 10,5 %' adds nothing, appears in lines with excluded == 'tax'."""
    items = [
        {"concept": "Urea granulada", "amount": 12300.0, "crop": "wheat", "area_ha": 100.0},
        {"concept": "IVA 10,5 %", "amount": 1291.5},
    ]
    sc = {"region": "southeast_buenos_aires", "area_ha": 500.0}
    res = record_document(kind="invoice", items=items, scenario=sc)
    vat_lines = [l for l in res["lines"] if "IVA" in l["concept"]]
    assert len(vat_lines) == 1
    assert vat_lines[0]["excluded"] == "tax"
    assert len(res["proposals"]) == 1
    assert res["proposals"][0]["proposed_usd_ha"] == 123.0


def test_6_no_crop_several_crops():
    """6. No crop, several crops: a fertilizer line without crop, scenario with wheat and soybean ->
    no proposal applied, 'missing: crop' in missing, one to_confirm entry; no wheat guess."""
    items = [
        {"concept": "Urea granulada", "amount": 10000.0, "area_ha": 100.0}
    ]
    sc = {"region": "southeast_buenos_aires", "area_ha": 500.0, "crops": ["wheat", "soybean"]}
    res = record_document(kind="invoice", items=items, scenario=sc)
    assert "missing: crop" in res["missing"]
    assert not any(p["apply"] for p in res["proposals"])
    assert len(res["to_confirm"]) == 1
    assert res["proposals"][0]["crop"] is None


def test_7_partial_crop_protection():
    """7. Partial crop protection: herbicide line for corn -> partial true, apply false, to_confirm has
    the es question with 'maíz'; the same with covers_whole_item: true -> applied."""
    sc = {"region": "pampas_core", "area_ha": 350.0, "crops": ["corn", "soybean"]}

    # Without confirmation: partial true, apply false, to_confirm with 'maíz'
    items_partial = [
        {"concept": "Atrazina 90 % WG", "amount": 9000.0, "crop": "corn", "area_ha": 100.0}  # 90 USD/ha vs 91.2 default (-1.3% dev)
    ]
    res_partial = record_document(kind="invoice", items=items_partial, scenario=sc, lang="es")
    assert res_partial["proposals"][0]["partial"] is True
    assert res_partial["proposals"][0]["apply"] is False
    assert len(res_partial["to_confirm"]) == 1
    assert "maíz" in res_partial["to_confirm"][0]

    # With confirmation: covers_whole_item: true -> partial false, apply true
    items_confirmed = [
        {"concept": "Atrazina 90 % WG", "amount": 9000.0, "crop": "corn", "area_ha": 100.0, "covers_whole_item": True}
    ]
    res_confirmed = record_document(kind="invoice", items=items_confirmed, scenario=sc, lang="es")
    assert res_confirmed["proposals"][0]["partial"] is False
    assert res_confirmed["proposals"][0]["apply"] is True


def test_8_signed_deviation():
    """8. Signed deviation: an invoice at 100 USD/ha against a zone value of 200 gives deviation_pct == -50.0
    and deviation_flag false; at 90 gives -55.0 and flag true, not applied."""
    sc = {"region": "southeast_buenos_aires", "area_ha": 500.0, "costs_override": {"wheat": {"fertilizer": 200.0}}}

    # Case 1: 100 USD/ha against 200 -> dev -50.0%, flag False, apply True
    items_100 = [{"concept": "Urea", "crop": "wheat", "amount": 10000.0, "area_ha": 100.0, "cost_item": "fertilizer"}]
    res_100 = record_document(kind="invoice", items=items_100, scenario=sc)
    p_100 = res_100["proposals"][0]
    assert p_100["deviation_pct"] == -50.0
    assert p_100["deviation_flag"] is False
    assert p_100["apply"] is True

    # Case 2: 90 USD/ha against 200 -> dev -55.0%, flag True, apply False
    items_90 = [{"concept": "Urea", "crop": "wheat", "amount": 9000.0, "area_ha": 100.0, "cost_item": "fertilizer"}]
    res_90 = record_document(kind="invoice", items=items_90, scenario=sc)
    p_90 = res_90["proposals"][0]
    assert p_90["deviation_pct"] == -55.0
    assert p_90["deviation_flag"] is True
    assert p_90["apply"] is False


def test_9_before_and_after():
    """9. Before and after: with test 1's scenario, plan_before.npv_usd equals evaluate_season(scenario)['npv_usd'],
    plan_after.npv_usd equals evaluate_season(dict(scenario, costs_override={'wheat': {'fertilizer': 225.0}}))['npv_usd']
    (both to the cent), and npv_change_usd is their difference."""
    items = [
        {"concept": "Urea granulada", "amount": 12300.0, "crop": "wheat", "area_ha": 100.0},
        {"concept": "Fosfato monoamónico (MAP)", "amount": 10200.0, "crop": "wheat", "area_ha": 100.0},
    ]
    sc = {"region": "southeast_buenos_aires", "area_ha": 500.0, "own_capital_usd": 50000.0}
    res = record_document(kind="invoice", items=items, scenario=sc)

    exp_before = evaluate_season(sc)["npv_usd"]
    exp_after = evaluate_season(dict(sc, costs_override={"wheat": {"fertilizer": 225.0}}))["npv_usd"]

    assert res["plan_before"]["npv_usd"] == exp_before
    assert res["plan_after"]["npv_usd"] == exp_after
    assert res["npv_change_usd"] == round(exp_after - exp_before, 2)


def test_10_earlier_override_kept():
    """10. Earlier override kept: a scenario that already has costs_override = {'soybean': {'seed': 70.0}}
    keeps it in scenario_after.costs_override next to the new wheat fertilizer, and the wheat fertilizer's
    default_source is 'zone'."""
    items = [
        {"concept": "Urea granulada", "amount": 12300.0, "crop": "wheat", "area_ha": 100.0},
        {"concept": "Fosfato monoamónico (MAP)", "amount": 10200.0, "crop": "wheat", "area_ha": 100.0},
    ]
    sc = {
        "region": "southeast_buenos_aires",
        "area_ha": 500.0,
        "own_capital_usd": 50000.0,
        "costs_override": {"soybean": {"seed": 70.0}}
    }
    res = record_document(kind="invoice", items=items, scenario=sc)

    assert res["scenario_after"]["costs_override"]["soybean"]["seed"] == 70.0
    assert res["scenario_after"]["costs_override"]["wheat"]["fertilizer"] == 225.0
    assert res["proposals"][0]["default_source"] == "zone"


def test_11_infeasible_after(monkeypatch):
    """11. Infeasible after: monkeypatch optimize to raise ScenarioError on the second call ->
    plan_after_error present, no exception."""
    items = [
        {"concept": "Urea granulada", "amount": 12300.0, "crop": "wheat", "area_ha": 100.0},
        {"concept": "Fosfato monoamónico (MAP)", "amount": 10200.0, "crop": "wheat", "area_ha": 100.0},
    ]
    sc = {"region": "southeast_buenos_aires", "area_ha": 500.0, "own_capital_usd": 50000.0}

    import dora.tools as dt
    original_optimize = dt.optimize
    call_count = 0

    def mock_optimize(s):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise ScenarioError("Simulated infeasible after plan")
        return original_optimize(s)

    monkeypatch.setattr(dt, "optimize", mock_optimize)
    res = record_document(kind="invoice", items=items, scenario=sc)
    assert "plan_after_error" in res
    assert "plan_after" not in res
    assert "plan_before" in res


def test_12_app_reconciliation_markdown():
    """12. App: with a hand-made tool result (tests 2 and 7 combined), the reconciliation markdown
    has the three blocks, 'no: es solo parte de los agroquímicos' for the herbicide, and the NPV difference line;
    with two record_document results the last one is used."""
    from app import respond

    tool_res = {
        "kind": "invoice",
        "lines": [
            {"concept": "Commercial Seed Corn", "crop": "corn", "cost_item": "seed", "amount": 18194.75, "currency": "USD", "amount_usd": 18194.75, "area_ha": 64.75, "usd_ha": 281.0, "excluded": None},
            {"concept": "Atrazina 90 % WG", "crop": "corn", "cost_item": "crop_protection", "amount": 1500.0, "currency": "USD", "amount_usd": 1500.0, "area_ha": 64.75, "usd_ha": 23.17, "excluded": None},
        ],
        "proposals": [
            {"crop": "corn", "item": "seed", "concepts": ["Commercial Seed Corn"], "proposed_usd_ha": 281.0, "default_usd_ha": 281.0, "deviation_pct": 0.0, "apply": True, "reason": None},
            {"crop": "corn", "item": "crop_protection", "concepts": ["Atrazina 90 % WG"], "proposed_usd_ha": 23.17, "default_usd_ha": 85.0, "deviation_pct": -72.7, "apply": False, "partial": True, "reason": "partial crop protection"},
        ],
        "completeness": {"farmer_coefficients": ["corn.seed"], "default_coefficients": [], "ratio_farmer": 0.5},
        "plan_before": {"npv_usd": 200000.0, "hectares": {"corn": 100.0}, "max_credit_usd": 10000.0},
        "plan_after": {"npv_usd": 205000.0, "hectares": {"corn": 100.0}, "max_credit_usd": 10000.0},
        "npv_change_usd": 5000.0,
    }
    dummy_first_res = {"proposals": [], "completeness": {}}

    class DummyReply:
        text = "Aquí está tu respuesta."
        tool_calls = [{"tool": "record_document", "arguments": "{}"}]
        verified = True

    class DummyAgent:
        tool_results = [json.dumps(dummy_first_res), json.dumps(tool_res)]
        usage = {}
        user_texts = []

        def ask(self, *args, **kwargs):
            return DummyReply()

    agent = DummyAgent()
    _, _, _, history, _ = respond(
        user_text="hola",
        files=None,
        audio=None,
        history=[],
        agent_instance=agent,
        lang="es",
        screen_scenario=None,
    )
    bot_msg = history[-1]["content"]

    assert "Renglones:" in bot_msg
    assert "Comparación con la zona:" in bot_msg
    assert "Antes y después:" in bot_msg
    assert "no: es solo parte de los agroquímicos" in bot_msg
    assert "Diferencia de VAN:" in bot_msg


def test_13_assess_field_image_unchanged():
    """13. assess_field_image output unchanged after moving _plan_view (run its existing tests)."""
    sc = Scenario()
    res = optimize(sc)
    view = _plan_view(res, sc, "es")
    assert "npv_usd" in view
    assert "profit_usd" in view
    assert "hectares" in view
    assert "max_credit_usd" in view
    assert "debt_left_at_end_usd" in view
    assert "capital_stretches" in view


def test_14_real_cases_math():
    """14. real_cases.json: each expected_groups.usd_ha equals the lines' sum / hectares
    (ARS at the bcra_fx_20261102 rate) to the cent."""
    with open("eval/e3/real_cases.json", "r", encoding="utf-8") as f:
        cases = json.load(f)

    # rate from real_prices.json
    with open("eval/e3/real_prices.json", "r", encoding="utf-8") as f:
        prices = json.load(f)
    rate = next(x["price"] for x in prices if x["id"] == "bcra_fx_20261102")

    for c in cases:
        ha = c["covers_ha"]
        curr = c["currency"]
        exp_groups = {f"{g['crop']}.{g['item']}": g["usd_ha"] for g in c["expected_groups"]}

        # Group lines by item and verify usd_ha
        for g in c["expected_groups"]:
            # find corresponding lines
            if c["id"] == "r1":
                lines_sum = sum(l["amount"] for l in c["lines"])
                calc_usd_ha = round(lines_sum / ha, 2)
                assert calc_usd_ha == g["usd_ha"]
            elif c["id"] == "r2":
                if g["item"] == "seed":
                    line_amt = c["lines"][0]["amount"]
                    calc_usd_ha = round(line_amt / rate / ha, 2)
                    assert calc_usd_ha == g["usd_ha"]
                elif g["item"] == "crop_protection":
                    line_amt = c["lines"][1]["amount"]
                    calc_usd_ha = round(line_amt / rate / ha, 2)
                    assert calc_usd_ha == g["usd_ha"]
            elif c["id"] == "r3":
                lines_sum = sum(l["amount"] for l in c["lines"])
                calc_usd_ha = round(lines_sum / ha, 2)
                assert calc_usd_ha == g["usd_ha"]
            elif c["id"] == "r4":
                if g["item"] == "fertilizer":
                    calc_usd_ha = round(c["lines"][0]["amount"] / ha, 2)
                    assert calc_usd_ha == g["usd_ha"]
                elif g["item"] == "seed":
                    calc_usd_ha = round(c["lines"][1]["amount"] / ha, 2)
                    assert calc_usd_ha == g["usd_ha"]
            elif c["id"] == "r5":
                calc_usd_ha = round(c["lines"][0]["amount"] / ha, 2)
                assert calc_usd_ha == g["usd_ha"]


def test_15_farmer_confirmation_wins_over_50pct_rule():
    """15. The farmer's confirmation wins over the 50 % rule.
    A corn crop-protection group at 28.99 USD/ha (zone 91.2) with covers_whole_item: true
    is applied, reason == 'confirmed by the farmer', deviation_pct == -68.2.
    """
    sc = {"region": "pampas_core", "area_ha": 350.0}
    items = [
        {"concept": "Atrazina 90 % WG", "amount": 1560.0, "crop": "corn", "area_ha": 120.0, "covers_whole_item": True},
        {"concept": "Dual Gold (S-metolacloro)", "amount": 1918.80, "crop": "corn", "area_ha": 120.0, "covers_whole_item": True},
    ]
    res = record_document(kind="invoice", items=items, scenario=sc)
    prop = res["proposals"][0]
    assert prop["crop"] == "corn"
    assert prop["item"] == "crop_protection"
    assert prop["proposed_usd_ha"] == 28.99
    assert prop["default_usd_ha"] == 91.2
    assert prop["deviation_pct"] == -68.2
    assert prop["apply"] is True
    assert prop["reason"] == "confirmed by the farmer"
