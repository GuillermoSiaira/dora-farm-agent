"""Acceptance tests for SPEC-21: Rotation on the land held, land shadow price, and taxes."""
from dataclasses import replace
import urllib.request
import pytest

from dora.engine import optimize
from dora.scenario import Scenario


@pytest.fixture(autouse=True)
def _block_network(monkeypatch):
    def _fail(*args, **kwargs):
        raise AssertionError("Network access is forbidden during tests")
    monkeypatch.setattr(urllib.request, "urlopen", _fail)


def test_1_unchanged_single_field_without_land_decisions():
    """1. Single field without renting in, buying, or renting out gives the same plan and NPV as main."""
    # Exact main (commit d390cf2) results before SPEC-21
    expected = [
        (
            "balcarce_default",
            Scenario(),
            88186.59678149877,
            {"wheat": 121.7227645367594, "corn": 0.0, "soybean": 250.0, "sunflower": 0.0},
            {},
        ),
        (
            "iowa_2m",
            Scenario(region="iowa", own_capital_usd=2_000_000.0),
            2360789.571565505,
            {"corn": 250.0, "soybean": 250.0},
            {},
        ),
        (
            "pampas_core_2m",
            Scenario(region="pampas_core", own_capital_usd=2_000_000.0),
            2212712.7560548284,
            {"wheat": 0.0, "corn": 250.0, "soybean": 250.0, "sunflower": 0.0},
            {},
        ),
        (
            "livestock_max_share_binding",
            Scenario(
                region="pampas_core",
                area_ha=500.0,
                own_capital_usd=500_000.0,
                crops=("soybean",),
                max_crop_share=1.0,
                livestock=["cow_calf"],
                max_livestock_share=0.4,
                prices={"soybean": 180.0},
            ),
            530733.194611493,
            {"soybean": 0.0},
            {"cow_calf": 200.0},
        ),
        (
            "livestock_seba_max_share",
            Scenario(
                area_ha=500.0,
                region="southeast_buenos_aires",
                livestock=["cow_calf", "steer_fattening"],
                livestock_only_ha=150.0,
                max_livestock_share=0.4,
            ),
            133578.15129736913,
            {"wheat": 66.57349339448079, "corn": 0.0, "soybean": 233.4265066055192, "sunflower": 0.0},
            {"cow_calf": 314.8856371131596, "steer_fattening": 35.1143628868404},
        ),
    ]

    for label, sc, exp_npv, exp_ha, exp_ls in expected:
        r = optimize(sc)
        assert r.npv == pytest.approx(exp_npv, rel=1e-6, abs=1e-6), f"NPV changed in {label}"
        for crop, ha_val in exp_ha.items():
            assert r.hectares[crop] == pytest.approx(ha_val, abs=1e-6), f"Hectares of {crop} changed in {label}"
        for act, ha_val in exp_ls.items():
            assert r.hectares_livestock[act] == pytest.approx(ha_val, abs=1e-6), f"Livestock {act} changed in {label}"


def _assert_owned_perturbation(sc: Scenario, tol: float = 1e-4) -> float:
    r = optimize(sc)
    r_up = optimize(replace(sc, owned_ha=sc.owned + 1.0))
    r_dn = optimize(replace(sc, owned_ha=sc.owned - 1.0))
    right_deriv = r_up.npv - r.npv
    left_deriv = r.npv - r_dn.npv
    assert right_deriv - tol <= r.land_shadow_price <= left_deriv + tol, (
        f"land_shadow_price={r.land_shadow_price} not in [{right_deriv}, {left_deriv}]"
    )
    return r.land_shadow_price


def test_2_rotation_on_land_held():
    """2. Iowa, 500 ha owned, max_rent_in_ha 1,000, rent 677.10, 2,000,000 USD:
    no crop above half of land held; corn == soybean when both pay."""
    sc = Scenario(
        region="iowa",
        owned_ha=500.0,
        area_ha=500.0,
        max_rent_in_ha=1000.0,
        regional_rent_usd_ha=677.10,
        own_capital_usd=2_000_000.0,
    )
    r = optimize(sc)
    land_held = sc.owned + r.rent_in_ha + r.buy_ha - r.rent_out_ha
    assert land_held > 500.0
    for c, h in r.hectares.items():
        assert h <= sc.max_crop_share * land_held + 1e-6, f"{c}={h} exceeds 0.5 * {land_held}"
    assert r.hectares["soybean"] > 0.0
    assert r.hectares["corn"] == pytest.approx(r.hectares["soybean"], abs=1e-4)
    assert r.hectares["corn"] == pytest.approx(0.5 * land_held, abs=1e-4)


def test_3_renting_out_shrinks_crop_caps():
    """3. Renting out part of owned land shrinks each crop cap to share * (owned - rented out)."""
    sc = Scenario(
        region="southeast_buenos_aires",
        owned_ha=500.0,
        area_ha=500.0,
        own_capital_usd=60_000.0,
        credit_line_usd=0.0,
        regional_rent_usd_ha=80.0,
        allow_rent_out=True,
    )
    r = optimize(sc)
    assert 10.0 < r.rent_out_ha < sc.owned - 10.0
    kept_ha = sc.owned - r.rent_out_ha
    for c, h in r.hectares.items():
        assert h <= sc.max_crop_share * kept_ha + 1e-6, f"{c}={h} exceeds {sc.max_crop_share * kept_ha}"
    assert r.hectares["soybean"] == pytest.approx(sc.max_crop_share * kept_ha, abs=1e-4)


def test_4_land_shadow_price_against_owned_perturbation():
    """4. Iowa and Balcarce with 2,000,000 USD: land_shadow_price matches dNPV/downed_ha (~720.65 and ~98.06)."""
    sc_iowa = Scenario(region="iowa", owned_ha=500.0, area_ha=500.0, own_capital_usd=2_000_000.0)
    sp_iowa = _assert_owned_perturbation(sc_iowa)
    assert sp_iowa == pytest.approx(720.65, abs=0.5)

    sc_balcarce = Scenario(region="southeast_buenos_aires", owned_ha=500.0, area_ha=500.0, own_capital_usd=2_000_000.0)
    sp_balcarce = _assert_owned_perturbation(sc_balcarce)
    assert sp_balcarce == pytest.approx(98.06, abs=0.5)


def test_5_land_shadow_price_with_land_tax_and_rent():
    """5. Perturbation check holds with land_tax_usd_ha_year = 75 and with regional rent."""
    cases = [
        # Plenty of capital + land tax 75
        Scenario(region="iowa", owned_ha=500.0, area_ha=500.0, own_capital_usd=2_000_000.0, land_tax_usd_ha_year=75.0),
        # Scarce capital (lam[0] > 1) + land tax 75
        Scenario(region="iowa", owned_ha=500.0, area_ha=500.0, own_capital_usd=200_000.0, credit_line_usd=100_000.0, land_tax_usd_ha_year=75.0),
        # Land tax 75 + regional rent with active rent-in
        Scenario(
            region="iowa",
            owned_ha=500.0,
            area_ha=500.0,
            own_capital_usd=2_000_000.0,
            land_tax_usd_ha_year=75.0,
            regional_rent_usd_ha=677.10,
            max_rent_in_ha=1000.0,
        ),
        # Land tax 75 + regional rent with partial rent-out
        Scenario(
            region="southeast_buenos_aires",
            owned_ha=500.0,
            area_ha=500.0,
            own_capital_usd=80_000.0,
            credit_line_usd=0.0,
            land_tax_usd_ha_year=75.0,
            regional_rent_usd_ha=80.0,
            allow_rent_out=True,
        ),
        # Land tax 75 + regional rent with full rent-out (rent_out == owned bound active)
        Scenario(
            region="southeast_buenos_aires",
            owned_ha=500.0,
            area_ha=500.0,
            own_capital_usd=2_000_000.0,
            land_tax_usd_ha_year=75.0,
            regional_rent_usd_ha=250.0,
            allow_rent_out=True,
        ),
        # Land tax 75 + regional rent with allow_rent_out=False
        Scenario(
            region="southeast_buenos_aires",
            owned_ha=500.0,
            area_ha=500.0,
            own_capital_usd=2_000_000.0,
            land_tax_usd_ha_year=75.0,
            regional_rent_usd_ha=250.0,
            allow_rent_out=False,
        ),
    ]
    for sc in cases:
        _assert_owned_perturbation(sc)


def test_6_rotation_shadow_price_decomposition_and_reporting():
    """6. In test 4's Iowa case, corn and soybean rotation duals are positive and decompose land_shadow_price."""
    from dora.tools import evaluate_season

    sc = Scenario(region="iowa", owned_ha=500.0, area_ha=500.0, own_capital_usd=2_000_000.0)
    r = optimize(sc)

    rot_corn = r.rotation_shadow_price["corn"]
    rot_soy = r.rotation_shadow_price["soybean"]
    assert rot_corn > 0.0
    assert rot_soy > 0.0

    reconstructed = (
        r.land_row_shadow_price
        + sc.max_crop_share * (rot_corn + rot_soy)
        + (sc.max_livestock_share or 0.0) * r.livestock_share_shadow_price
        + r.rent_out_bound_shadow_price
        - sc.land_tax_usd_ha_year * r.cash_value[0]
    )
    assert reconstructed == pytest.approx(r.land_shadow_price, abs=1e-9)

    ev = evaluate_season({"region": "iowa", "area_ha": 500.0, "own_capital_usd": 2_000_000.0})
    assert "rotation" in ev
    assert ev["rotation"]["soybean"]["meaning"] == (
        f"the rotation costs you {round(rot_soy, 2)} USD per hectare of soybean you cannot add"
    )
    assert ev["rotation"]["corn"]["meaning"] == (
        f"the rotation costs you {round(rot_corn, 2)} USD per hectare of corn you cannot add"
    )


def test_7_taxes_in_region_comparison():
    """7. compare_regions applies regional land, gross receipts, and transaction taxes in the engine;
    farmer overrides win over the regional tax file."""
    from dora.tools import compare_regions

    base_sc = {"area_ha": 500.0, "own_capital_usd": 500_000.0}
    comp = compare_regions(base_sc)
    comp_no_tax = compare_regions(
        {
            **base_sc,
            "gross_receipts_rate": 0.0,
            "transaction_tax_rate": 0.0,
            "land_tax_usd_ha_year": 0.0,
        }
    )

    # Iowa: 500 * 75 = 37,500 USD paid in fortnight 0, valued today
    iowa = comp["regions"]["iowa"]
    iowa_nt = comp_no_tax["regions"]["iowa"]
    land_tax_p0 = 500.0 * 75.0
    comp_reduced_cap = compare_regions(
        {
            "area_ha": 500.0,
            "own_capital_usd": 500_000.0 - land_tax_p0,
            "gross_receipts_rate": 0.0,
            "transaction_tax_rate": 0.0,
            "land_tax_usd_ha_year": 0.0,
        },
        regions=["iowa"],
    )
    assert iowa["npv_usd"] == pytest.approx(comp_reduced_cap["regions"]["iowa"]["npv_usd"], abs=0.01)
    diff_iowa = iowa_nt["npv_usd"] - iowa["npv_usd"]
    lam0_before = 1.0 + iowa_nt["capital_shadow_price"]
    lam0_after = 1.0 + iowa["capital_shadow_price"]
    assert land_tax_p0 * lam0_before - 0.05 <= diff_iowa <= land_tax_p0 * lam0_after + 0.05

    # With ample capital (lam[0] == 1), the difference is 500 * 75 = 37,500.00 USD
    c_rich = compare_regions({"area_ha": 500.0, "own_capital_usd": 2_000_000.0}, regions=["iowa"])
    c_rich_nt = compare_regions(
        {
            "area_ha": 500.0,
            "own_capital_usd": 2_000_000.0,
            "gross_receipts_rate": 0.0,
            "transaction_tax_rate": 0.0,
            "land_tax_usd_ha_year": 0.0,
        },
        regions=["iowa"],
    )
    assert c_rich_nt["regions"]["iowa"]["npv_usd"] - c_rich["regions"]["iowa"]["npv_usd"] == pytest.approx(37_500.0, abs=0.01)

    # Argentina: both gross receipts (1%) and transaction tax (0.6%) enter the cash rows
    ar_no_gr = compare_regions({**base_sc, "gross_receipts_rate": 0.0}, regions=["pampas_core", "southeast_buenos_aires"])
    ar_no_tx = compare_regions({**base_sc, "transaction_tax_rate": 0.0}, regions=["pampas_core", "southeast_buenos_aires"])
    assert comp["regions"]["pampas_core"]["farming_only"]["npv_usd"] < ar_no_gr["regions"]["pampas_core"]["farming_only"]["npv_usd"]
    assert comp["regions"]["pampas_core"]["farming_only"]["npv_usd"] < ar_no_tx["regions"]["pampas_core"]["farming_only"]["npv_usd"]
    assert comp["regions"]["southeast_buenos_aires"]["npv_usd"] < ar_no_tx["regions"]["southeast_buenos_aires"]["npv_usd"]

    # taxes_applied lists each tax with name, rate, source, and placeholder flag
    for reg in ("southeast_buenos_aires", "pampas_core", "iowa", "mato_grosso"):
        applied = comp["regions"][reg]["taxes_applied"]
        assert len(applied) == 3
        by_field = {t["field"]: t for t in applied}
        assert set(by_field) == {"gross_receipts_rate", "transaction_tax_rate", "land_tax_usd_ha_year"}
        for t in applied:
            assert t["name"]
            assert isinstance(t["rate"], float)
            assert t["source"]
            assert isinstance(t["placeholder"], bool)

    # A rate the farmer gives wins over the file
    comp_farmer = compare_regions({**base_sc, "land_tax_usd_ha_year": 10.0}, regions=["iowa"])
    iowa_f = comp_farmer["regions"]["iowa"]
    lt_entry = next(t for t in iowa_f["taxes_applied"] if t["field"] == "land_tax_usd_ha_year")
    assert lt_entry["rate"] == 10.0
    assert lt_entry["source"] == "farmer"
    assert lt_entry["placeholder"] is False
    assert iowa_f["npv_usd"] > iowa["npv_usd"]


def test_8_income_tax_only_reported():
    """8. In compare_regions, the plan and ranking do not depend on income_tax_rate;
    npv_after_income_tax_usd matches the hand calculation."""
    from dora.scenario import FORTNIGHTS, fortnightly_rate
    from dora.tools import compare_regions

    base_sc = {"area_ha": 500.0, "own_capital_usd": 500_000.0}
    c_default = compare_regions(base_sc)
    c_zero = compare_regions({**base_sc, "income_tax_rate": 0.0})
    c_high = compare_regions({**base_sc, "income_tax_rate": 0.45})

    assert c_default["ranking"] == c_zero["ranking"] == c_high["ranking"]
    for reg in ("southeast_buenos_aires", "pampas_core", "iowa", "mato_grosso"):
        for key in ("npv_usd", "hectares", "rent_in_ha", "rent_out_ha", "buy_ha"):
            assert c_default["regions"][reg][key] == c_zero["regions"][reg][key] == c_high["regions"][reg][key]

    # Hand-computed after-income-tax NPV for Iowa (25% company rate in taxes_united_states.json)
    iowa = c_default["regions"]["iowa"]
    assert iowa["income_tax_rate"] == pytest.approx(0.25)
    assert "company" in iowa["income_tax_note"].lower()
    ri = fortnightly_rate(iowa["deposit_rate_annual"])
    discount = (1.0 + ri) ** -(FORTNIGHTS - 1)
    profit = max(0.0, iowa["final_wealth_usd"] - 500_000.0)
    hand_after_tax_npv = round(iowa["npv_usd"] - discount * 0.25 * profit, 2)
    assert iowa["npv_after_income_tax_usd"] == pytest.approx(hand_after_tax_npv, abs=0.02)


def test_9_annual_returns():
    """9. return_on_capital_and_land_annual = (1 + r)**(24/29) - 1 (Balcarce review case: 3.46% -> 2.86%)."""
    from dora.tools import compare_regions

    # Pre-tax Balcarce review case (3.46% over 14.5 months -> 2.86% annualized)
    comp_pre_tax = compare_regions(
        {
            "area_ha": 500.0,
            "own_capital_usd": 500_000.0,
            "gross_receipts_rate": 0.0,
            "transaction_tax_rate": 0.0,
            "land_tax_usd_ha_year": 0.0,
        },
        regions=["southeast_buenos_aires"],
    )
    seba = comp_pre_tax["regions"]["southeast_buenos_aires"]
    assert seba["season_months"] == 14.5
    assert seba["return_on_capital_and_land"] == pytest.approx(0.0346, abs=1e-4)
    assert seba["return_on_capital_and_land_annual"] == pytest.approx(0.0286, abs=1e-4)
    assert seba["return_on_capital_and_land_annual"] < seba["deposit_rate_annual"]

    # Exact formula check directly on Result
    sc = Scenario(region="southeast_buenos_aires", area_ha=500.0, own_capital_usd=500_000.0, land_price_usd_ha=7600.0)
    r = optimize(sc)
    assert r.season_months == 14.5
    assert r.return_on_capital_annual == pytest.approx((1.0 + r.return_on_capital) ** (24.0 / 29.0) - 1.0, abs=1e-12)
    assert r.return_on_capital_and_land_annual == pytest.approx(
        (1.0 + r.return_on_capital_and_land) ** (24.0 / 29.0) - 1.0, abs=1e-12
    )


def test_10_tax_placeholders_flagged():
    """10. compare_regions flags the taxes of Brazil and the United States as provisional."""
    from dora.tools import compare_regions

    comp = compare_regions({"area_ha": 500.0, "own_capital_usd": 500_000.0})
    for reg in ("mato_grosso", "iowa"):
        entry = comp["regions"][reg]
        assert entry["placeholder_flags"]["taxes"] is True
        assert entry["placeholder"] is True
        assert all(t["placeholder"] is True for t in entry["taxes_applied"])
