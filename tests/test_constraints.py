import json
import pytest

from dora.engine import optimize
from dora.scenario import Scenario, ScenarioError
from dora.tools import run_tool


def call(name, **args):
    return json.loads(run_tool(name, json.dumps(args)))


# 1. Binding min_area: with plenty of capital, min_area of corn = 150 ha
# (corn is not chosen without it). The opportunity cost is > 0 and lies between
# the one-sided derivatives when ha moves ±1.
def test_binding_min_area():
    sc = Scenario(
        own_capital_usd=2_000_000,
        constraints=[{"type": "min_area", "crop": "corn", "ha": 150.0, "label": "corn quota"}],
    )
    r = optimize(sc)
    assert r.hectares["corn"] == pytest.approx(150.0)
    cost = r.constraint_duals[0]
    assert cost > 0

    sc_up = Scenario(
        own_capital_usd=2_000_000,
        constraints=[{"type": "min_area", "crop": "corn", "ha": 151.0}],
    )
    sc_down = Scenario(
        own_capital_usd=2_000_000,
        constraints=[{"type": "min_area", "crop": "corn", "ha": 149.0}],
    )
    base = r.npv
    up = optimize(sc_up).npv
    down = optimize(sc_down).npv

    right = base - up       # loss from tightening 1 ha
    left = down - base      # gain from loosening 1 ha
    assert right - 1e-4 <= cost <= left + 1e-4

    # Check via evaluate_season
    ev = call("evaluate_season", scenario={
        "own_capital_usd": 2_000_000,
        "constraints": [{"type": "min_area", "crop": "corn", "ha": 150.0, "label": "corn quota"}],
    })
    c_rep = ev["constraints"][0]
    assert c_rep["type"] == "min_area"
    assert c_rep["label"] == "corn quota"
    assert c_rep["binding"] is True
    assert c_rep["opportunity_cost"] == round(cost, 2)
    assert c_rep["unit"] == "USD/ha"
    assert "meeting this costs" in c_rep["meaning"]


# 2. Non-binding min_area: min_area soybean = 50 ha when the optimum already
# sows 250 ha -> binding false, cost 0.
def test_non_binding_min_area():
    sc = Scenario(
        own_capital_usd=2_000_000,
        constraints=[{"type": "min_area", "crop": "soybean", "ha": 50.0}],
    )
    r = optimize(sc)
    assert r.hectares["soybean"] == pytest.approx(250.0)
    assert r.constraint_duals[0] == pytest.approx(0.0, abs=1e-6)

    ev = call("evaluate_season", scenario={
        "own_capital_usd": 2_000_000,
        "constraints": [{"type": "min_area", "crop": "soybean", "ha": 50.0}],
    })
    c_rep = ev["constraints"][0]
    assert c_rep["binding"] is False
    assert c_rep["opportunity_cost"] == 0.0
    assert "not binding" in c_rep["meaning"]


# 3. max_area on soybean below its optimum -> binding, cost > 0, perturbation check.
def test_binding_max_area():
    sc = Scenario(
        own_capital_usd=2_000_000,
        constraints=[{"type": "max_area", "crop": "soybean", "ha": 150.0}],
    )
    r = optimize(sc)
    assert r.hectares["soybean"] == pytest.approx(150.0)
    cost = r.constraint_duals[0]
    assert cost > 0

    sc_up = Scenario(
        own_capital_usd=2_000_000,
        constraints=[{"type": "max_area", "crop": "soybean", "ha": 151.0}],  # loosened
    )
    sc_down = Scenario(
        own_capital_usd=2_000_000,
        constraints=[{"type": "max_area", "crop": "soybean", "ha": 149.0}],  # tightened
    )
    base = r.npv
    up = optimize(sc_up).npv
    down = optimize(sc_down).npv

    loosening_gain = up - base
    tightening_loss = base - down
    assert loosening_gain - 1e-4 <= cost <= tightening_loss + 1e-4

    ev = call("evaluate_season", scenario={
        "own_capital_usd": 2_000_000,
        "constraints": [{"type": "max_area", "crop": "soybean", "ha": 150.0}],
    })
    assert ev["constraints"][0]["binding"] is True
    assert ev["constraints"][0]["opportunity_cost"] == round(cost, 2)


# 4. min_share wheat 0.4 -> perturbation check moving share by ±0.01.
def test_min_share_perturbation():
    sc = Scenario(constraints=[{"type": "min_share", "crop": "wheat", "share": 0.40}])
    r = optimize(sc)
    total_sown = sum(r.hectares.values())
    assert r.hectares["wheat"] / total_sown == pytest.approx(0.40, abs=1e-5)
    cost = r.constraint_duals[0]
    assert cost > 0

    sc_up = Scenario(constraints=[{"type": "min_share", "crop": "wheat", "share": 0.41}])
    sc_down = Scenario(constraints=[{"type": "min_share", "crop": "wheat", "share": 0.39}])
    base = r.npv
    up = optimize(sc_up).npv
    down = optimize(sc_down).npv

    tightening_loss = base - up
    loosening_gain = down - base
    assert tightening_loss - 1e-4 <= cost <= loosening_gain + 1e-4

    ev = call("evaluate_season", scenario={
        "constraints": [{"type": "min_share", "crop": "wheat", "share": 0.40}],
    })
    assert ev["constraints"][0]["unit"] == "USD/share point"
    assert ev["constraints"][0]["binding"] is True


# 5. forward_sale of soybean in May of year 2 at a price below the market net price
# -> cost > 0, perturbation on tonnes ±1. At a price well above it, the cost is negative.
def test_forward_sale_perturbation():
    # Price 200 USD/t is well below market net price (~252 USD/t)
    sc = Scenario(constraints=[
        {"type": "forward_sale", "crop": "soybean", "month": "2027-05", "tonnes": 100.0, "price_usd_t": 200.0}
    ])
    r = optimize(sc)
    cost = r.constraint_duals[0]
    assert cost > 0

    sc_up = Scenario(constraints=[
        {"type": "forward_sale", "crop": "soybean", "month": "2027-05", "tonnes": 101.0, "price_usd_t": 200.0}
    ])
    sc_down = Scenario(constraints=[
        {"type": "forward_sale", "crop": "soybean", "month": "2027-05", "tonnes": 99.0, "price_usd_t": 200.0}
    ])
    base = r.npv
    up = optimize(sc_up).npv
    down = optimize(sc_down).npv

    tightening_loss = base - up     # delivering 1 tonne more at 200
    loosening_gain = down - base    # delivering 1 tonne less at 200
    assert tightening_loss - 1e-4 <= cost <= loosening_gain + 1e-4

    # High price (500 USD/t) -> cost is negative (contract worth more than market)
    sc_high = Scenario(constraints=[
        {"type": "forward_sale", "crop": "soybean", "month": "2027-05", "tonnes": 100.0, "price_usd_t": 500.0}
    ])
    r_high = optimize(sc_high)
    assert r_high.constraint_duals[0] < 0

    ev = call("evaluate_season", scenario={
        "constraints": [{"type": "forward_sale", "crop": "soybean", "month": "2027-05", "tonnes": 100.0, "price_usd_t": 500.0}]
    })
    assert "benefits the farm" in ev["constraints"][0]["meaning"]


# 6. Infeasible: min_area corn 300 + min_area soybean 300 on 500 ha -> ScenarioError naming both.
def test_infeasible_constraints():
    with pytest.raises(ScenarioError) as exc:
        optimize(Scenario(area_ha=500.0, constraints=[
            {"type": "min_area", "crop": "corn", "ha": 300.0},
            {"type": "min_area", "crop": "soybean", "ha": 300.0},
        ]))
    msg = str(exc.value)
    assert "corn" in msg and "soybean" in msg
    assert "300" in msg

    ev = call("evaluate_season", scenario={
        "area_ha": 500.0,
        "constraints": [
            {"type": "min_area", "crop": "corn", "ha": 300.0},
            {"type": "min_area", "crop": "soybean", "ha": 300.0},
        ],
    })
    assert "error" in ev
    assert "corn" in ev["error"] and "soybean" in ev["error"]


# 7. Without constraints, results are identical to the current engine (NPV rel 1e-12).
def test_without_constraints_identical():
    sc_none = Scenario()
    sc_empty = Scenario(constraints=[])
    r_none = optimize(sc_none)
    r_empty = optimize(sc_empty)
    assert abs(r_none.npv - r_empty.npv) / r_none.npv < 1e-12
    for c in sc_none.crops:
        assert r_none.hectares[c] == pytest.approx(r_empty.hectares[c], rel=1e-12)


# 8. Validation and build_scenario checks
def test_constraints_validation():
    # Unknown constraint type
    err = call("evaluate_season", scenario={"constraints": [{"type": "fixed_crop", "crop": "corn"}]})["error"]
    assert "unknown type" in err

    # Unknown crop
    err = call("evaluate_season", scenario={"constraints": [{"type": "min_area", "crop": "rice", "ha": 100}]})["error"]
    assert "unknown crop" in err

    # Negative number
    err = call("evaluate_season", scenario={"constraints": [{"type": "min_area", "crop": "corn", "ha": -10}]})["error"]
    assert "non-negative" in err

    # Share outside (0, 1]
    err = call("evaluate_season", scenario={"constraints": [{"type": "min_share", "crop": "corn", "share": 1.5}]})["error"]
    assert "between 0 and 1" in err

    err0 = call("evaluate_season", scenario={"constraints": [{"type": "min_share", "crop": "corn", "share": 0.0}]})["error"]
    assert "between 0 and 1" in err0

    # Badly formed month
    err = call("evaluate_season", scenario={"constraints": [{"type": "forward_sale", "crop": "corn", "month": "2027/05", "tonnes": 50, "price_usd_t": 200}]})["error"]
    assert "YYYY-MM" in err

    # Price <= 0
    err = call("evaluate_season", scenario={"constraints": [{"type": "forward_sale", "crop": "corn", "month": "2027-05", "tonnes": 50, "price_usd_t": 0}]})["error"]
    assert "price_usd_t" in err

    # Forward sale month before harvest
    err = call("evaluate_season", scenario={"constraints": [{"type": "forward_sale", "crop": "soybean", "month": "2026-10", "tonnes": 50, "price_usd_t": 250}]})["error"]
    assert "before harvest" in err


def test_build_scenario_echoes_constraints():
    c_list = [
        {"type": "min_area", "crop": "corn", "ha": 100.0, "label": "contract A"},
        {"type": "forward_sale", "crop": "soybean", "month": "2027-05", "tonnes": 50.0, "price_usd_t": 280.0},
    ]
    res = call("build_scenario", scenario={"constraints": c_list})["scenario"]
    assert "constraints" in res
    assert res["constraints"]["origin"] == "farmer"
    echoed = res["constraints"]["value"]
    assert len(echoed) == 2
    assert echoed[0]["type"] == "min_area"
    assert echoed[0]["label"] == "contract A"
    assert echoed[0]["origin"] == "farmer"
    assert echoed[1]["origin"] == "farmer"
