"""Tests for SPEC-42: the plan as a spreadsheet (export, play with it, send it back)."""
from __future__ import annotations

import base64
import dataclasses
import io
import json
import os
from pathlib import Path
import tempfile
from unittest.mock import MagicMock

import openpyxl
import pytest

from dora.engine import fortnightly_rate, optimize
from dora.scenario import Scenario
from dora.spreadsheet import export_plan_xlsx, read_plan_xlsx
from dora.tools import TOOLS, evaluate_season, export_plan_spreadsheet, import_plan_spreadsheet
from dora.version import ENGINE_VERSION, engine_fingerprint
from mcp_server.provenance import sha256_canonical


# -----------------------------------------------------------------------------
# Scenarios for Test 1 & Test 3
# -----------------------------------------------------------------------------
SCENARIOS = {
    "se_ba_500_owned": {
        "region": "southeast_buenos_aires",
        "area_ha": 500,
        "owned_ha": 500,
        "own_capital_usd": 50000,
    },
    "pampas_core_2000_owned": {
        "region": "pampas_core",
        "area_ha": 2000,
        "owned_ha": 2000,
        "own_capital_usd": 500000,
    },
    "se_ba_300_rented_credit": {
        "region": "southeast_buenos_aires",
        "area_ha": 300,
        "rented_land": True,
        "own_capital_usd": 10000,
        "credit_line_usd": 100000,
    },
    "se_ba_500_rent_out": {
        "region": "southeast_buenos_aires",
        "area_ha": 500,
        "owned_ha": 500,
        "own_capital_usd": 50000,
        "allow_rent_out": True,
    },
}


# -----------------------------------------------------------------------------
# Test 1: Ledger identity
# -----------------------------------------------------------------------------
def test_1_ledger_identity():
    """1. S[p] - D[p] = (1+ri)*S[p-1] - (1+rc)*D[p-1] + sum(ledger[p]) (+ opening cash at p=0) within 1e-6 USD."""
    for name, sc_dict in SCENARIOS.items():
        sc = Scenario(**sc_dict)
        res = optimize(sc)
        assert len(res.cash_ledger) == len(res.cash)

        ri = fortnightly_rate(sc.deposit_rate_annual)
        rc = fortnightly_rate(sc.credit_rate_annual)

        for p in range(len(res.cash)):
            s_p = float(res.cash[p])
            d_p = float(res.debt[p])

            s_prev = float(res.cash[p - 1]) if p > 0 else 0.0
            d_prev = float(res.debt[p - 1]) if p > 0 else 0.0

            ledger_sum = sum(sum(crop_dict.values()) for crop_dict in res.cash_ledger[p].values())
            opening = res.opening_cash if p == 0 else 0.0

            expected_net = (1.0 + ri) * s_prev - (1.0 + rc) * d_prev + ledger_sum + opening
            actual_net = s_p - d_p
            diff = abs(actual_net - expected_net)
            assert diff < 1e-6, f"Ledger identity failed for {name} at fortnight {p}: diff={diff}"


# -----------------------------------------------------------------------------
# Test 2: Sheets order and warning text in es/en
# -----------------------------------------------------------------------------
def test_2_sheets_order_and_warning():
    """2. The file has the 6 visible sheets in order plus hidden _dora; names and warning text in es and en."""
    sc_dict = SCENARIOS["se_ba_500_owned"]

    # Spanish
    xlsx_es = export_plan_xlsx(sc_dict, lang="es")
    wb_es = openpyxl.load_workbook(io.BytesIO(xlsx_es))
    expected_es = ["Resumen", "Plan por cultivo", "Caja por quincena", "Supuestos", "Modelo", "Sensibilidad", "Verificación", "_dora", "__OpenSolver__"]
    assert wb_es["__OpenSolver__"].sheet_state == "hidden"
    assert wb_es.sheetnames == expected_es
    assert wb_es["_dora"].sheet_state == "hidden"
    w_text_es = wb_es["Resumen"]["A1"].value
    assert "Este plan era el óptimo con estos supuestos" in w_text_es
    assert "mandá esta planilla por el chat" in w_text_es

    # English
    xlsx_en = export_plan_xlsx(sc_dict, lang="en")
    wb_en = openpyxl.load_workbook(io.BytesIO(xlsx_en))
    expected_en = ["Summary", "Plan by crop", "Cash by fortnight", "Assumptions", "Model", "Sensitivity", "Verification", "_dora", "__OpenSolver__"]
    assert wb_en["__OpenSolver__"].sheet_state == "hidden"
    assert wb_en.sheetnames == expected_en
    assert wb_en["_dora"].sheet_state == "hidden"
    w_text_en = wb_en["Summary"]["A1"].value
    assert "This plan was the best one under these assumptions" in w_text_en
    assert "send this file back in the chat" in w_text_en


# -----------------------------------------------------------------------------
# Test 3: Formulas reproduce engine within 0.01 USD
# -----------------------------------------------------------------------------
def test_3_formulas_reproduce_engine():
    """3. Formulas reproduce the engine on the four scenarios: cash, debt, margins and NPV within 0.01 USD."""
    import formulas

    value_only_groups_by_scenario = {}

    for name, sc_dict in SCENARIOS.items():
        sc = Scenario(**sc_dict)
        opt = optimize(sc)
        xlsx_bytes = export_plan_xlsx(sc_dict, lang="es")

        wb_inspect = openpyxl.load_workbook(io.BytesIO(xlsx_bytes))
        # Find dynamic NPV row in Resumen
        ws_res = wb_inspect["Resumen"]
        npv_row = [r[0].row for r in ws_res.iter_rows(min_col=1, max_col=1) if r[0].value and ("Valor Neto" in str(r[0].value) or "VNP" in str(r[0].value))][0]

        tf = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
        tf.write(xlsx_bytes)
        tf.close()

        try:
            xl = formulas.ExcelModel().loads(tf.name).finish()
            calc = xl.calculate()
            bname = os.path.basename(tf.name)

            # Check NPV
            npv_key = f"'[{bname}]RESUMEN'!B{npv_row}"
            calc_npv = float(calc[npv_key].value[0, 0])
            assert abs(calc_npv - opt.npv) < 0.01, f"NPV mismatch on {name}: {calc_npv} vs {opt.npv}"

            # Check Cash and Debt
            for p in range(len(opt.cash)):
                c_key = f"'[{bname}]CAJA POR QUINCENA'!N{p + 2}"
                d_key = f"'[{bname}]CAJA POR QUINCENA'!O{p + 2}"
                calc_c = float(calc[c_key].value[0, 0])
                calc_d = float(calc[d_key].value[0, 0])
                assert abs(calc_c - opt.cash[p]) < 0.01, f"Cash mismatch on {name} at {p}: {calc_c} vs {opt.cash[p]}"
                assert abs(calc_d - opt.debt[p]) < 0.01, f"Debt mismatch on {name} at {p}: {calc_d} vs {opt.debt[p]}"

            # Check crop margins in Plan por cultivo
            ws_crops = wb_inspect["Plan por cultivo"]
            active_crops = [c for c in sc.crops if opt.hectares.get(c, 0.0) > 0.01]
            for c in active_crops:
                c_row = [r[0].row for r in ws_crops.iter_rows(min_col=1, max_col=1) if r[0].value == c][0]
                margin_key = f"'[{bname}]PLAN POR CULTIVO'!I{c_row}"
                calc_margin = float(calc[margin_key].value[0, 0])

                ha = opt.hectares[c]
                t_prod = ha * sc.crop_yield(c)
                cost_ha = sum(sc._cost(c, item) for item in ("seed", "fertilizer", "crop_protection", "field_operations", "marketing_harvest"))
                expected_margin = t_prod * sc.price(c) - ha * cost_ha
                assert abs(calc_margin - expected_margin) < 0.01, f"Margin mismatch on {name} for {c}: {calc_margin} vs {expected_margin}"

            value_only_groups_by_scenario[name] = ["credit_decisions", "storage_fill", "storage_monthly"]
        finally:
            try:
                os.unlink(tf.name)
            except Exception:
                pass

    assert len(value_only_groups_by_scenario) == 4


# -----------------------------------------------------------------------------
# Test 4: Editing moves the formulas
# -----------------------------------------------------------------------------
def test_4_editing_moves_formulas():
    """4. Editing soybean price +10 % in the file moves margins and cash in the arithmetic direction and amount."""
    import formulas

    sc_dict = SCENARIOS["se_ba_500_owned"]
    xlsx_bytes = export_plan_xlsx(sc_dict, lang="es")

    # Evaluate baseline
    tf_base = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    tf_base.write(xlsx_bytes)
    tf_base.close()

    try:
        xl_base = formulas.ExcelModel().loads(tf_base.name).finish()
        calc_base = xl_base.calculate()
        bname_base = os.path.basename(tf_base.name)
        base_margin = float(calc_base[f"'[{bname_base}]PLAN POR CULTIVO'!I3"].value[0, 0])
        base_cash_end = float(calc_base[f"'[{bname_base}]CAJA POR QUINCENA'!N31"].value[0, 0])
    finally:
        try:
            os.unlink(tf_base.name)
        except Exception:
            pass

    # Edit soybean price +10%
    wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes))
    ws = wb["Supuestos"]
    p_row = [r[0].row for r in ws.iter_rows(min_col=1, max_col=1) if r[0].value == "prices.soybean"][0]
    old_p = float(ws.cell(row=p_row, column=3).value)
    delta_p = old_p * 0.10
    new_p = old_p + delta_p
    ws.cell(row=p_row, column=3, value=new_p)

    tf_edit = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    wb.save(tf_edit.name)
    tf_edit.close()

    try:
        xl_edit = formulas.ExcelModel().loads(tf_edit.name).finish()
        calc_edit = xl_edit.calculate()
        bname_edit = os.path.basename(tf_edit.name)

        new_margin = float(calc_edit[f"'[{bname_edit}]PLAN POR CULTIVO'!I3"].value[0, 0])
        new_cash_end = float(calc_edit[f"'[{bname_edit}]CAJA POR QUINCENA'!N31"].value[0, 0])

        # Soybean tonnes = 250 ha * 2.44 t/ha = 610 t -> delta = 610 * 32.7 = 19947.0 USD
        expected_delta = 610.0 * delta_p
        assert abs((new_margin - base_margin) - expected_delta) < 0.01
        assert (new_cash_end - base_cash_end) > 0.0
    finally:
        try:
            os.unlink(tf_edit.name)
        except Exception:
            pass




def test_4b_editing_cost_moves_cash_and_npv():
    """Claude review 6/11: raise one crop's cost by 10% in Supuestos, evaluate with formulas,
    and check that the cash sheet's input outflows for that crop change by exactly 10%
    (to 0.01 USD) and that the NPV moves in the same direction.
    """
    import formulas

    sc_dict = SCENARIOS["se_ba_500_owned"]
    xlsx_bytes = export_plan_xlsx(sc_dict, lang="es")

    # Evaluate baseline
    tf_base = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    tf_base.write(xlsx_bytes)
    tf_base.close()

    try:
        xl_base = formulas.ExcelModel().loads(tf_base.name).finish()
        calc_base = xl_base.calculate()
        bname_base = os.path.basename(tf_base.name)

        wb_inspect = openpyxl.load_workbook(io.BytesIO(xlsx_bytes))
        ws_res = wb_inspect["Resumen"]
        npv_row = [
            r[0].row for r in ws_res.iter_rows(min_col=1, max_col=1)
            if r[0].value and ("Valor Neto" in str(r[0].value) or "VNP" in str(r[0].value))
        ][0]
        base_npv = float(calc_base[f"'[{bname_base}]RESUMEN'!B{npv_row}"].value[0, 0])

        # Baseline input flows across all fortnights
        base_all_input_flows = [
            float(calc_base[f"'[{bname_base}]CAJA POR QUINCENA'!C{p + 2}"].value[0, 0])
            for p in range(30)
        ]
        # In fortnights 16..23, only soybean has input payments
        base_soy_only_flows = [
            float(calc_base[f"'[{bname_base}]CAJA POR QUINCENA'!C{p + 2}"].value[0, 0])
            for p in range(16, 24)
        ]
    finally:
        try:
            os.unlink(tf_base.name)
        except Exception:
            pass

    # Edit soybean cost in Supuestos +10%
    wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes))
    ws = wb["Supuestos"]
    soy_cost_rows = [
        r[0].row for r in ws.iter_rows(min_col=1, max_col=1)
        if r[0].value and str(r[0].value).startswith("costs.soybean.")
    ]
    for r_idx in soy_cost_rows:
        cell = ws.cell(row=r_idx, column=3)
        cell.value = float(cell.value) * 1.10

    tf_edit = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    tf_edit.close()
    wb.save(tf_edit.name)

    try:
        xl_edit = formulas.ExcelModel().loads(tf_edit.name).finish()
        calc_edit = xl_edit.calculate()
        bname_edit = os.path.basename(tf_edit.name)

        new_npv = float(calc_edit[f"'[{bname_edit}]RESUMEN'!B{npv_row}"].value[0, 0])

        new_soy_only_flows = [
            float(calc_edit[f"'[{bname_edit}]CAJA POR QUINCENA'!C{p + 2}"].value[0, 0])
            for p in range(16, 24)
        ]
        new_all_input_flows = [
            float(calc_edit[f"'[{bname_edit}]CAJA POR QUINCENA'!C{p + 2}"].value[0, 0])
            for p in range(30)
        ]

        # 1. Soybean-only fortnights (16..23) change by exactly 10% (to 0.01 USD)
        for b_val, n_val in zip(base_soy_only_flows, new_soy_only_flows):
            diff = abs(n_val - (b_val * 1.10))
            assert diff < 0.01, f"Fortnight flow mismatch: base={b_val}, new={n_val}, diff={diff}"

        # 2. Total input outflow across all fortnights changes by exactly 10% of total soybean inputs
        total_delta = sum(new_all_input_flows) - sum(base_all_input_flows)
        # Total soybean inputs in baseline was 118,675.0 USD; 10% is 11,867.50 USD
        assert abs(total_delta - (-11867.50)) < 0.01

        # 3. NPV moves in the same direction (higher cost -> lower NPV)
        assert (new_npv - base_npv) < 0.0
    finally:
        try:
            os.unlink(tf_edit.name)
        except Exception:
            pass

# -----------------------------------------------------------------------------
# Test 5: Origins in Supuestos
# -----------------------------------------------------------------------------
def test_5_origins_in_assumptions():
    """5. In Supuestos: farmer input -> 'lo dijo el productor', invoice -> invoice origin, regional -> source & date."""
    sc_dict = dict(SCENARIOS["se_ba_500_owned"])
    sc_dict["own_capital_usd"] = 75000
    sc_dict["costs_override"] = {"soybean": {"fertilizer": 45.0}}
    sc_dict["costs_origin"] = {"soybean.fertilizer": "factura 2026-05-12"}

    xlsx_bytes = export_plan_xlsx(sc_dict, lang="es")
    wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes))
    ws = wb["Supuestos"]

    origins = {r[0].value: r[4].value for r in ws.iter_rows(min_row=2, values_only=False) if r and r[0].value}

    # Farmer input
    assert origins.get("own_capital_usd") == "lo dijo el productor"

    # Invoice input
    assert "factura 2026-05-12" in str(origins.get("costs.soybean.fertilizer", ""))

    # Regional default
    wheat_seed_origin = str(origins.get("costs.wheat.seed", ""))
    assert "MAGyP" in wheat_seed_origin and "2026" in wheat_seed_origin


# -----------------------------------------------------------------------------
# Test 6: Verification sheet hashes and EAS record status
# -----------------------------------------------------------------------------
def test_6_verification_sheet_provenance():
    """6. Verification sheet hashes match SPEC-40 provenance; EAS record shows UID / explorer / unconfigured."""
    from dora.tools import _validate
    from mcp_server.provenance import build_provenance

    sc_dict = SCENARIOS["se_ba_500_owned"]
    sc_obj, _ = _validate(sc_dict)
    sc_val = dataclasses.asdict(sc_obj)
    res_eval = evaluate_season(sc_dict, lang="es")
    prov = build_provenance("solve_plan", sc_val, res_eval, [])

    # Case A: Without record (not configured)
    xlsx_unconf = export_plan_xlsx(sc_dict, lang="es", record=None)
    wb_unconf = openpyxl.load_workbook(io.BytesIO(xlsx_unconf))
    ws_unconf = wb_unconf["Verificación"]
    v_dict_unconf = {str(r[0]): str(r[1]) for r in ws_unconf.iter_rows(values_only=True) if r and r[0]}

    assert v_dict_unconf.get("Hash del escenario") == prov["scenario_hash"]
    assert v_dict_unconf.get("Hash del resultado") == prov["result_hash"]
    assert v_dict_unconf.get("Versión del motor") == ENGINE_VERSION
    assert v_dict_unconf.get("Huella digital del motor") == engine_fingerprint()
    assert v_dict_unconf.get("Estado") == "sin registro on-chain"

    # Case B: With published record
    fake_record = {
        "status": "published",
        "attestation_uid": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        "record_hash": "0xabcdef",
    }
    xlsx_pub = export_plan_xlsx(sc_dict, lang="es", record=fake_record)
    wb_pub = openpyxl.load_workbook(io.BytesIO(xlsx_pub))
    ws_pub = wb_pub["Verificación"]
    v_dict_pub = {str(r[0]): str(r[1]) for r in ws_pub.iter_rows(values_only=True) if r and r[0]}

    assert v_dict_pub.get("Estado") == "Publicado en Base Sepolia"
    assert v_dict_pub.get("UID Atestación") == fake_record["attestation_uid"]
    assert "https://base-sepolia.easscan.org/attestation/view/" in str(v_dict_pub.get("EAS Scan"))


# -----------------------------------------------------------------------------
# Test 7: Round trip, no edits
# -----------------------------------------------------------------------------
def test_7_round_trip_no_edits():
    """7. Round trip, no edits: export -> read -> changes empty, plan identical."""
    sc_dict = SCENARIOS["se_ba_500_owned"]
    xlsx_bytes = export_plan_xlsx(sc_dict, lang="es")

    res = read_plan_xlsx(xlsx_bytes, lang="es")
    assert res.get("changes") == []
    assert res.get("rejected") == []
    assert res.get("plan_before") == res.get("plan_after")
    assert res.get("what_changed", {}).get("npv_diff_usd") == 0.0


# -----------------------------------------------------------------------------
# Test 8: Round trip with edits
# -----------------------------------------------------------------------------
def test_8_round_trip_with_edits():
    """8. Round trip with edits: soybean price -20 % and own capital * 2 -> changes, evaluate_season matches."""
    sc_dict = SCENARIOS["se_ba_500_owned"]
    xlsx_bytes = export_plan_xlsx(sc_dict, lang="es")

    wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes))
    ws = wb["Supuestos"]

    # Soybean price -20%
    p_row = [r[0].row for r in ws.iter_rows(min_col=1, max_col=1) if r[0].value == "prices.soybean"][0]
    ws.cell(row=p_row, column=3, value=327.0 * 0.8)

    # Own capital * 2
    c_row = [r[0].row for r in ws.iter_rows(min_col=1, max_col=1) if r[0].value == "own_capital_usd"][0]
    ws.cell(row=c_row, column=3, value=100000.0)

    buf = io.BytesIO()
    wb.save(buf)

    res = read_plan_xlsx(buf.getvalue(), lang="es")
    changes_dict = {c["key"]: c for c in res["changes"]}

    assert "prices.soybean" in changes_dict
    assert abs(changes_dict["prices.soybean"]["after"] - 261.6) < 1e-4

    assert "own_capital_usd" in changes_dict
    assert abs(changes_dict["own_capital_usd"]["after"] - 100000.0) < 1e-4

    # The new plan matches evaluate_season on edited scenario
    expected_eval = evaluate_season(res["scenario"], lang="es")
    assert res["plan_after"]["npv"] == pytest.approx(expected_eval["npv_usd"], rel=1e-4)
    assert res["plan_after"]["hectares"] == expected_eval["hectares"]

    # What changed reports the difference
    wc = res["what_changed"]
    assert "soybean" in wc["crops_out"]
    assert wc["hectares_moved"]["soybean"] == -250.0
    assert wc["npv_diff_usd"] != 0.0


# -----------------------------------------------------------------------------
# Test 9: Rejected and ignored values
# -----------------------------------------------------------------------------
def test_9_rejected_and_ignored():
    """9. A negative yield is rejected with its reason; a formula with no cached value is ignored; other edits go through."""
    sc_dict = SCENARIOS["se_ba_500_owned"]
    xlsx_bytes = export_plan_xlsx(sc_dict, lang="es")

    wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes))
    ws = wb["Supuestos"]

    # Negative yield -> rejected
    y_row = [r[0].row for r in ws.iter_rows(min_col=1, max_col=1) if r[0].value == "yields.soybean"][0]
    ws.cell(row=y_row, column=3, value=-1.5)

    # Formula without cached value -> ignored
    f_row = [r[0].row for r in ws.iter_rows(min_col=1, max_col=1) if r[0].value == "costs.soybean.fertilizer"][0]
    ws.cell(row=f_row, column=3, value="=10+20")

    # Valid edit -> applied
    c_row = [r[0].row for r in ws.iter_rows(min_col=1, max_col=1) if r[0].value == "own_capital_usd"][0]
    ws.cell(row=c_row, column=3, value=80000.0)

    buf = io.BytesIO()
    wb.save(buf)

    res = read_plan_xlsx(buf.getvalue(), lang="es")
    assert any(rej["key"] == "yields.soybean" for rej in res["rejected"])
    assert any(ign["key"] == "costs.soybean.fertilizer" for ign in res["ignored"])
    assert any(chg["key"] == "own_capital_usd" for chg in res["changes"])


# -----------------------------------------------------------------------------
# Test 10: Not a DORA file, tampered _dora, .xlsm and .csv
# -----------------------------------------------------------------------------
def test_10_invalid_and_tampered_files():
    """10. Not a DORA file / tampered _dora -> clear message, no solve. .xlsm and .csv rejected."""
    # CSV rejected
    res_csv = read_plan_xlsx(b"col1,col2\n1,2", lang="es")
    assert res_csv.get("error") == "invalid_format"

    # XLSM rejected
    import zipfile
    zf_buf = io.BytesIO()
    with zipfile.ZipFile(zf_buf, "w") as zf:
        zf.writestr("xl/vbaProject.bin", b"macro code")
    res_xlsm = read_plan_xlsx(zf_buf.getvalue(), lang="es")
    assert res_xlsm.get("error") == "xlsm_not_allowed"

    # Non-DORA xlsx (missing _dora)
    wb = openpyxl.Workbook()
    wb_buf = io.BytesIO()
    wb.save(wb_buf)
    res_no_dora = read_plan_xlsx(wb_buf.getvalue(), lang="es")
    assert res_no_dora.get("error") == "not_dora_file"

    # Tampered _dora (hash mismatch)
    sc_dict = SCENARIOS["se_ba_500_owned"]
    xlsx_bytes = export_plan_xlsx(sc_dict, lang="es")
    wb_tamper = openpyxl.load_workbook(io.BytesIO(xlsx_bytes))
    wb_tamper["_dora"]["A1"] = '{"scenario": {"tampered": 1}, "scenario_hash": "bad"}'
    wb_buf_t = io.BytesIO()
    wb_tamper.save(wb_buf_t)
    res_tamper = read_plan_xlsx(wb_buf_t.getvalue(), lang="es")
    assert res_tamper.get("error") == "tampered_dora"


# -----------------------------------------------------------------------------
# Test 11: Climate scenarios returns clean error message
# -----------------------------------------------------------------------------
def test_11_climate_scenarios_clean_message():
    """11. Climate scenarios -> 'not available' message, no unhandled exception."""
    sc_dict = dict(SCENARIOS["se_ba_500_owned"])
    sc_dict["climate_scenarios"] = True

    # export_plan_spreadsheet returns error dict
    res = export_plan_spreadsheet(sc_dict, lang="es")
    assert res.get("error") == "not_available"
    assert "no está disponible" in res.get("message", "")

    # export_plan_xlsx raises ValueError with clean message
    with pytest.raises(ValueError) as exc:
        export_plan_xlsx(sc_dict, lang="es")
    assert "no está disponible" in str(exc.value)


# -----------------------------------------------------------------------------
# Test 12: Tools and MCP integration
# -----------------------------------------------------------------------------
def test_12_tools_and_mcp_integration():
    """12. Tools and MCP integration test for export_plan_spreadsheet, export_plan_xlsx, and import_plan_xlsx."""
    import asyncio
    from mcp_server.server import mcp

    sc_dict = SCENARIOS["se_ba_500_owned"]

    # 1. dora.tools registration
    assert "export_plan_spreadsheet" in TOOLS
    assert "import_plan_spreadsheet" in TOOLS

    # Run tool export
    tool_exp = TOOLS["export_plan_spreadsheet"](sc_dict, lang="es")
    assert Path(tool_exp["file"]).exists()
    assert tool_exp["file_name"].endswith(".xlsx")

    # 2. MCP list tools includes both
    async def _check_mcp():
        tl = await mcp.list_tools()
        names = [t.name for t in tl]
        assert "export_plan_xlsx" in names
        assert "import_plan_xlsx" in names

    asyncio.run(_check_mcp())

    # 3. MCP export & import round trip
    from mcp_server.server import export_plan_xlsx as mcp_export, import_plan_xlsx as mcp_import
    mcp_res = mcp_export(sc_dict, lang="es")
    assert "result" in mcp_res
    b64_blob = mcp_res["result"]["resource"]["blob"]
    raw_data = base64.b64decode(b64_blob)
    wb = openpyxl.load_workbook(io.BytesIO(raw_data))
    assert "_dora" in wb.sheetnames

    # Import back via MCP
    import_res = mcp_import(b64_blob, lang="es")
    assert "result" in import_res
    assert import_res["result"]["changes"] == []


# -----------------------------------------------------------------------------
# Test 13: App Scenario button and chat upload
# -----------------------------------------------------------------------------
def test_13_app_scenario_button_and_chat_upload():
    """13. App Scenario button produces a file, and an uploaded .xlsx in chat goes through read_plan_xlsx."""
    import app as app_module

    sc_dict = SCENARIOS["se_ba_500_owned"]

    # 1. Direct call to Scenario button handler
    exported_file = app_module.build_app().on_download_plan_xlsx(sc_dict, "es")
    assert exported_file is not None
    assert Path(exported_file).exists()
    wb = openpyxl.load_workbook(exported_file)
    assert "_dora" in wb.sheetnames

    # 2. Upload .xlsx in chat (agent mocked)
    raw_bytes = export_plan_xlsx(sc_dict, lang="es")
    tf = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    tf.write(raw_bytes)
    tf.close()

    try:
        mock_agent = MagicMock()
        mock_agent.usage = {"requests": 1}
        mock_agent.user_texts = []
        mock_reply = MagicMock()
        mock_reply.text = "Explicación del plan: no hubo cambios."
        mock_reply.verified = True
        mock_reply.tool_calls = []
        mock_reply.unsupported = []
        mock_agent.ask.return_value = mock_reply

        history = []
        clean_text, f_out, a_out, new_history, ag_out = app_module.respond(
            user_text="",
            files=[tf.name],
            audio=None,
            history=history,
            agent_instance=mock_agent,
            lang="es",
            screen_scenario=sc_dict,
        )

        assert len(new_history) == 2
        assistant_reply = new_history[1]["content"]
        assert "Descargar nueva planilla del plan (.xlsx)" in assistant_reply
        assert mock_agent.ask.called
    finally:
        try:
            os.unlink(tf.name)
        except Exception:
            pass
