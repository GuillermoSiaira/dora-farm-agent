"""SPEC-50 Problems: 12 reference LP formulations and dataset generator.

All problem statements and numerical values are original.
Problems inspired by classic textbook or microeconomic types (e.g. Tow 1999)
state the source in 'source'.
Expected values are ALWAYS solved via HiGHS, never typed by hand.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import numpy as np
from scipy.optimize import linprog


def _solve_lp_dict(lp_def: dict[str, Any]) -> dict[str, Any]:
    """Solve an LP definition dict using HiGHS."""
    c = np.array(lp_def["c"], dtype=float)
    sense = lp_def.get("sense", "max").lower()
    c_hi = -c if sense == "max" else c

    A_ub = np.array(lp_def["A_ub"], dtype=float) if lp_def.get("A_ub") is not None and len(lp_def["A_ub"]) > 0 else None
    b_ub = np.array(lp_def["b_ub"], dtype=float) if lp_def.get("b_ub") is not None and len(lp_def["b_ub"]) > 0 else None
    A_eq = np.array(lp_def["A_eq"], dtype=float) if lp_def.get("A_eq") is not None and len(lp_def["A_eq"]) > 0 else None
    b_eq = np.array(lp_def["b_eq"], dtype=float) if lp_def.get("b_eq") is not None and len(lp_def["b_eq"]) > 0 else None
    bounds = lp_def.get("bounds", [(0, None)] * len(c))

    res = linprog(
        c_hi,
        A_ub=A_ub,
        b_ub=b_ub,
        A_eq=A_eq,
        b_eq=b_eq,
        bounds=bounds,
        method="highs",
    )

    if not res.success:
        return {
            "status": "infeasible" if res.status == 2 else "unbounded" if res.status == 3 else "error",
            "objective": None,
            "solution": None,
        }

    obj_val = float(-res.fun if sense == "max" else res.fun)
    sol_dict = {}
    var_names = lp_def.get("var_names", [f"x{i+1}" for i in range(len(c))])
    for name, val in zip(var_names, res.x):
        sol_dict[name] = round(float(val), 8)

    marginals_ub = [round(float(m), 8) for m in res.ineqlin.marginals] if hasattr(res, "ineqlin") and res.ineqlin is not None else []
    
    return {
        "status": "optimal",
        "objective": round(obj_val, 6),
        "solution": sol_dict,
        "marginals_ub": marginals_ub,
    }


# Problem 1: Dos cultivos, tierra y trabajo
def _lp_prob_01() -> dict[str, Any]:
    # x1: trigo, x2: maiz
    # max 300 x1 + 400 x2
    # s.t. x1 + x2 <= 100 (tierra)
    #      x1 + 2 x2 <= 160 (trabajo)
    return {
        "c": [300.0, 400.0],
        "sense": "max",
        "A_ub": [[1.0, 1.0], [1.0, 2.0]],
        "b_ub": [100.0, 160.0],
        "bounds": [(0, None), (0, None)],
        "var_names": ["x_trigo", "x_maiz"],
        "con_names": ["tierra", "trabajo"],
    }


# Problem 2: Dieta de costo mínimo
def _lp_prob_02() -> dict[str, Any]:
    # x1: forraje A, x2: forraje B
    # min 0.20 x1 + 0.30 x2
    # s.t. 2 x1 + 4 x2 >= 12 (proteina)
    #      3 x1 + 2 x2 >= 12 (energia)
    #      1 x1 + 2 x2 >= 6  (fibra)
    # In standard <= form for linprog:
    return {
        "c": [0.20, 0.30],
        "sense": "min",
        "A_ub": [[-2.0, -4.0], [-3.0, -2.0], [-1.0, -2.0]],
        "b_ub": [-12.0, -12.0, -6.0],
        "bounds": [(0, None), (0, None)],
        "var_names": ["x_forraje_a", "x_forraje_b"],
        "con_names": ["proteina", "energia", "fibra"],
    }


# Problem 3: Transporte 3x3
def _lp_prob_03() -> dict[str, Any]:
    # 9 variables: x11, x12, x13, x21, x22, x23, x31, x32, x33
    # min sum c_ij * x_ij
    # Supply: O1 <= 150, O2 <= 200, O3 <= 250
    # Demand: D1 >= 100, D2 >= 200, D3 >= 300
    c = [8.0, 14.0, 12.0, 10.0, 9.0, 15.0, 13.0, 11.0, 7.0]
    A_ub = [
        # Supplies <=
        [1.0, 1.0, 1.0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 1.0, 1.0, 1.0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 1.0, 1.0, 1.0],
        # Demands >= (written as <= -D)
        [-1.0, 0, 0, -1.0, 0, 0, -1.0, 0, 0],
        [0, -1.0, 0, 0, -1.0, 0, 0, -1.0, 0],
        [0, 0, -1.0, 0, 0, -1.0, 0, 0, -1.0],
    ]
    b_ub = [150.0, 200.0, 250.0, -100.0, -200.0, -300.0]
    return {
        "c": c,
        "sense": "min",
        "A_ub": A_ub,
        "b_ub": b_ub,
        "bounds": [(0, None)] * 9,
        "var_names": ["x11", "x12", "x13", "x21", "x22", "x23", "x31", "x32", "x33"],
        "con_names": ["oferta_o1", "oferta_o2", "oferta_o3", "demanda_d1", "demanda_d2", "demanda_d3"],
    }


# Problem 4: Venta inmediata vs almacenamiento
def _lp_prob_04() -> dict[str, Any]:
    # vars: [v_s1, v_c1, s_sA, s_sB, s_sC, s_cA, s_cB, s_cC]
    # max 300 v_s1 + 180 v_c1 + 340 s_sA + 335 s_sB + 325 s_sC + 210 s_cA + 205 s_cB + 195 s_cC
    c = [300.0, 180.0, 340.0, 335.0, 325.0, 210.0, 205.0, 195.0]
    A_ub = [
        [1.0, 0, 1.0, 1.0, 1.0, 0, 0, 0],  # cosech_soja <= 400
        [0, 1.0, 0, 0, 0, 1.0, 1.0, 1.0],  # cosech_maiz <= 600
        [0, 0, 1.0, 0, 0, 1.0, 0, 0],      # silo_a <= 300
        [0, 0, 0, 1.0, 0, 0, 1.0, 0],      # silo_b <= 250
        [0, 0, 0, 0, 1.0, 0, 0, 1.0],      # silo_c <= 400
    ]
    b_ub = [400.0, 600.0, 300.0, 250.0, 400.0]
    return {
        "c": c,
        "sense": "max",
        "A_ub": A_ub,
        "b_ub": b_ub,
        "bounds": [(0, None)] * 8,
        "var_names": ["v_s1", "v_c1", "s_sA", "s_sB", "s_sC", "s_cA", "s_cB", "s_cC"],
        "con_names": ["cosecha_soja", "cosecha_maiz", "cap_silo_a", "cap_silo_b", "cap_silo_c"],
    }


# Problem 5: Producción porcina y grano
def _lp_prob_05() -> dict[str, Any]:
    # vars: [ha_maiz, sold_maiz, fed_maiz, cerdos, hire_horas]
    # max -200 ha + 150 sold + 130 cerdos - 8 hire
    c = [-200.0, 150.0, 0.0, 130.0, -8.0]
    A_ub = [
        [1.0, 0, 0, 0, 0],          # tierra <= 80
        [-6.0, 1.0, 1.0, 0, 0],      # balance grano: sold + fed <= 6 ha
        [0, 0, -1.0, 0.5, 0],       # balance alimentacion: 0.5 cerdos <= fed
        [10.0, 0, 0, 4.0, -1.0],    # mano de obra: 10 ha + 4 cerdos - hire <= 900
        [0, 0, 0, 0, 1.0],          # contratacion extra <= 200
    ]
    b_ub = [80.0, 0.0, 0.0, 900.0, 200.0]
    return {
        "c": c,
        "sense": "max",
        "A_ub": A_ub,
        "b_ub": b_ub,
        "bounds": [(0, None)] * 5,
        "var_names": ["ha_maiz", "sold_maiz", "fed_maiz", "cerdos", "hire_horas"],
        "con_names": ["tierra", "balance_grano", "alimento_cerdos", "mano_obra", "limite_contratacion"],
    }


# Problem 6: Rotación en 3 períodos
def _lp_prob_06() -> dict[str, Any]:
    # vars: [w1, s1, w2, s2, w3, s3]
    c = [280.0, 320.0, 290.0, 310.0, 300.0, 330.0]
    A_ub = [
        [1.0, 1.0, 0, 0, 0, 0],  # tierra 1 <= 200
        [0, 0, 1.0, 1.0, 0, 0],  # tierra 2 <= 200
        [0, 0, 0, 0, 1.0, 1.0],  # tierra 3 <= 200
        [0, 1.0, 0, 0, 0, 0],    # s1 <= 80 (40%)
        [0, 0, 0, 1.0, 0, 0],    # s2 <= 80 (40%)
        [0, 0, 0, 0, 0, 1.0],    # s3 <= 80 (40%)
        [0, 1.0, 0, 1.0, 0, 0],  # s1 + s2 <= 120
        [0, 0, 0, 1.0, 0, 1.0],  # s2 + s3 <= 120
    ]
    b_ub = [200.0, 200.0, 200.0, 80.0, 80.0, 80.0, 120.0, 120.0]
    return {
        "c": c,
        "sense": "max",
        "A_ub": A_ub,
        "b_ub": b_ub,
        "bounds": [(0, None)] * 6,
        "var_names": ["w1", "s1", "w2", "s2", "w3", "s3"],
        "con_names": ["tierra_1", "tierra_2", "tierra_3", "cap_girasol_1", "cap_girasol_2", "cap_girasol_3", "rotacion_1_2", "rotacion_2_3"],
    }


# Problem 7: Producto intermedio: fabricar o comprar
def _lp_prob_07() -> dict[str, Any]:
    # vars: [x1, x2, c_make, c_buy]
    c = [120.0, 160.0, -15.0, -25.0]
    A_ub = [
        [3.0, 2.0, 0, 0],    # ensamblado <= 450
        [0, 0, 1.0, 0],      # maquinado <= 250
        [2.0, 3.0, -1.0, -1.0], # componentes C: 2 x1 + 3 x2 - make - buy <= 0
    ]
    b_ub = [450.0, 250.0, 0.0]
    return {
        "c": c,
        "sense": "max",
        "A_ub": A_ub,
        "b_ub": b_ub,
        "bounds": [(0, None)] * 4,
        "var_names": ["x_p1", "x_p2", "c_make", "c_buy"],
        "con_names": ["horas_ensamblado", "horas_maquinado", "balance_componente_c"],
    }


# Problem 8: Aserradero y muebles con 2 tramos de crédito
def _lp_prob_08() -> dict[str, Any]:
    # vars: [L, P_sell, T, K1, K2]
    # max -40 L + 110 P_sell + 40 T - 0.05 K1 - 0.12 K2
    c = [-40.0, 110.0, 40.0, -0.05, -0.12]
    A_ub = [
        [1.0, 0, 0, 0, 0],           # aserrado <= 500
        [-0.6, 1.0, 0.15, 0, 0],     # balance tablas: P_sell + 0.15 T <= 0.6 L
        [0, 0, 2.0, 0, 0],           # carpinteria <= 800
        [40.0, 0, 10.0, -1.0, -1.0], # caja: 40 L + 10 T - K1 - K2 <= 5000
        [0, 0, 0, 1.0, 0],           # credito 1 <= 8000
        [0, 0, 0, 0, 1.0],           # credito 2 <= 10000
    ]
    b_ub = [500.0, 0.0, 800.0, 5000.0, 8000.0, 10000.0]
    return {
        "c": c,
        "sense": "max",
        "A_ub": A_ub,
        "b_ub": b_ub,
        "bounds": [(0, None)] * 5,
        "var_names": ["rollizos_L", "tablas_sell", "mesas_T", "credito_K1", "credito_K2"],
        "con_names": ["cap_aserrado", "balance_tablas", "cap_carpinteria", "caja_propia", "limite_credito_1", "limite_credito_2"],
    }


# Problem 9: Pergamino 500 ha propio (datos completos)
def _lp_prob_09() -> dict[str, Any]:
    # vars: [s1, m, ts]
    # max 450 s1 + 650 m + 520 ts
    c = [450.0, 650.0, 520.0]
    A_ub = [
        [1.0, 1.0, 1.0],       # tierra <= 500
        [380.0, 600.0, 500.0], # capital <= 260000
        [0, 1.0, 0],           # maiz <= 200 (40%)
        [1.0, 0, 0],           # soja1 <= 250 (50%)
    ]
    b_ub = [500.0, 260000.0, 200.0, 250.0]
    return {
        "c": c,
        "sense": "max",
        "A_ub": A_ub,
        "b_ub": b_ub,
        "bounds": [(0, None)] * 3,
        "var_names": ["soja_1ra", "maiz", "trigo_soja2da"],
        "con_names": ["tierra", "capital", "rotacion_maiz", "rotacion_soja1"],
    }


# Problem 10: Pergamino 500 ha arrendado (datos completos)
def _lp_prob_10() -> dict[str, Any]:
    # vars: [s1, m, ts]
    # max 450 s1 + 650 m + 520 ts - 150000 rent
    # Capital for crops: 350000 - 150000 = 200000
    c = [450.0, 650.0, 520.0]
    A_ub = [
        [1.0, 1.0, 1.0],       # tierra <= 500
        [380.0, 600.0, 500.0], # capital <= 200000
        [0, 1.0, 0],           # maiz <= 200
        [1.0, 0, 0],           # soja1 <= 250
    ]
    b_ub = [500.0, 200000.0, 200.0, 250.0]
    return {
        "c": c,
        "sense": "max",
        "A_ub": A_ub,
        "b_ub": b_ub,
        "bounds": [(0, None)] * 3,
        "var_names": ["soja_1ra", "maiz", "trigo_soja2da"],
        "con_names": ["tierra", "capital_cultivos", "rotacion_maiz", "rotacion_soja1"],
        "fixed_cost": 150000.0,
    }


# Problem 11: Incompleto: Gemini Pergamino
def _lp_prob_11() -> dict[str, Any]:
    # Missing capital, rent, land split.
    # Nominal reference LP assuming standard Pergamino owned parameters for baseline
    nominal = _lp_prob_09()
    return nominal


# Problem 12: Incompleto: Transporte con demanda destino faltante
def _lp_prob_12() -> dict[str, Any]:
    # Supply A1: 300, A2: 400. P1 demand: 250. P2 demand missing.
    # Nominal reference assuming P2 demand = 450 (balance 700 t total)
    c = [12.0, 18.0, 15.0, 14.0]
    A_ub = [
        [1.0, 1.0, 0, 0],      # A1 <= 300
        [0, 0, 1.0, 1.0],      # A2 <= 400
        [-1.0, 0, -1.0, 0],    # P1 >= 250
        [0, -1.0, 0, -1.0],    # P2 >= 450 (nominal)
    ]
    b_ub = [300.0, 400.0, -250.0, -450.0]
    return {
        "c": c,
        "sense": "min",
        "A_ub": A_ub,
        "b_ub": b_ub,
        "bounds": [(0, None)] * 4,
        "var_names": ["x_A1_P1", "x_A1_P2", "x_A2_P1", "x_A2_P2"],
        "con_names": ["oferta_A1", "oferta_A2", "demanda_P1", "demanda_P2_nominal"],
    }


PROBLEMS: list[dict[str, Any]] = [
    {
        "id": "prob_01",
        "title": "Dos cultivos, tierra y trabajo",
        "statement_es": (
            "Un productor tiene 100 hectáreas de tierra y 160 horas de mano de obra disponibles para la campaña. "
            "Puede sembrar trigo o maíz. El trigo rinde un margen neto de 300 USD/ha y requiere 1 hora de trabajo por hectárea. "
            "El maíz rinde 400 USD/ha y requiere 2 horas de trabajo por hectárea. "
            "Plantear el programa lineal para maximizar el margen total, asegurando no exceder la tierra ni el trabajo disponible."
        ),
        "statement_en": (
            "A farmer has 100 hectares of land and 160 hours of labour available for the season. "
            "He can plant wheat or corn. Wheat yields a net margin of 300 USD/ha and requires 1 hour of labour per hectare. "
            "Corn yields 400 USD/ha and requires 2 hours of labour per hectare. "
            "Formulate the linear program to maximize total margin without exceeding available land or labour."
        ),
        "domain": "agriculture",
        "difficulty": 1,
        "source": "inspired by: standard microeconomic model / Tow 1999",
        "asks_dual": True,
        "asks_reading": [
            {
                "q": 0,
                "kind": "shadow_price",
                "target": "tierra",
                "text_es": "¿Cuánto vale disponer de una hectárea adicional de tierra?",
                "text_en": "How much is an additional hectare of land worth?",
                "expected_unit": "USD/ha",
            },
            {
                "q": 1,
                "kind": "shadow_price",
                "target": "trabajo",
                "text_es": "¿Cuánto vale disponer de una hora adicional de mano de obra?",
                "text_en": "How much is an additional hour of labour worth?",
                "expected_unit": "USD/hora",
            },
            {
                "q": 2,
                "kind": "rhs_range",
                "target": "tierra",
                "text_es": "¿Hasta qué límite puede crecer la tierra antes de que su precio sombra cambie?",
                "text_en": "Up to what limit can land grow before its shadow price changes?",
                "expected_unit": "ha",
            },
        ],
        "statement_numbers": [100.0, 160.0, 300.0, 1.0, 400.0, 2.0],
        "percentage_numbers": [],
        "allowed_extra": [],
        "incomplete": None,
        "_lp_builder": _lp_prob_01,
    },
    {
        "id": "prob_02",
        "title": "Dieta de costo mínimo",
        "statement_es": (
            "Se debe preparar una ración diaria para ganado combinando forraje A y forraje B al mínimo costo. "
            "Cada kg de forraje A cuesta 0.20 USD y aporta 2 unidades de proteína, 3 unidades de energía y 1 unidad de fibra. "
            "Cada kg de forraje B cuesta 0.30 USD y aporta 4 unidades de proteína, 2 unidades de energía y 2 unidades de fibra. "
            "La ración debe contener al menos 12 unidades de proteína, 12 unidades de energía y 6 unidades de fibra."
        ),
        "statement_en": (
            "A daily feed ration for livestock must be prepared combining feed A and feed B at minimum cost. "
            "Each kg of feed A costs 0.20 USD and provides 2 units of protein, 3 units of energy, and 1 unit of fiber. "
            "Each kg of feed B costs 0.30 USD and provides 4 units of protein, 2 units of energy, and 2 units of fiber. "
            "The ration must contain at least 12 units of protein, 12 units of energy, and 6 units of fiber."
        ),
        "domain": "diet",
        "difficulty": 1,
        "source": "inspired by: Stigler diet problem / Tow 1999",
        "asks_dual": False,
        "asks_reading": [],
        "statement_numbers": [0.20, 2.0, 3.0, 1.0, 0.30, 4.0, 2.0, 2.0, 12.0, 12.0, 6.0],
        "percentage_numbers": [],
        "allowed_extra": [],
        "incomplete": None,
        "_lp_builder": _lp_prob_02,
    },
    {
        "id": "prob_03",
        "title": "Transporte: 3 orígenes y 3 destinos",
        "statement_es": (
            "Una cooperativa dispone de grano en 3 acopios: O1 (150 toneladas), O2 (200 toneladas) y O3 (250 toneladas). "
            "Debe abastecer a 3 molinos: D1 (100 toneladas), D2 (200 toneladas) y D3 (300 toneladas). "
            "Los costos unitarios de flete (USD/t) son: "
            "desde O1: 8 a D1, 14 a D2, 12 a D3; "
            "desde O2: 10 a D1, 9 a D2, 15 a D3; "
            "desde O3: 13 a D1, 11 a D2, 7 a D3. "
            "Determinar el plan de transporte de costo mínimo que satisfaga la demanda sin superar las ofertas."
        ),
        "statement_en": (
            "A cooperative stores grain at 3 facilities: O1 (150 tons), O2 (200 tons), and O3 (250 tons). "
            "It must supply 3 mills: D1 (100 tons), D2 (200 tons), and D3 (300 tons). "
            "Unit freight costs (USD/t) are: "
            "from O1: 8 to D1, 14 to D2, 12 to D3; "
            "from O2: 10 to D1, 9 to D2, 15 to D3; "
            "from O3: 13 to D1, 11 to D2, 7 to D3. "
            "Determine the minimum-cost transportation plan meeting demand without exceeding supply."
        ),
        "domain": "transport",
        "difficulty": 1,
        "source": "inspired by: Hitchcock transport formulation",
        "asks_dual": False,
        "asks_reading": [],
        "statement_numbers": [150.0, 200.0, 250.0, 100.0, 200.0, 300.0, 8.0, 14.0, 12.0, 10.0, 9.0, 15.0, 13.0, 11.0, 7.0],
        "percentage_numbers": [],
        "allowed_extra": [],
        "incomplete": None,
        "_lp_builder": _lp_prob_03,
    },
    {
        "id": "prob_04",
        "title": "Venta inmediata vs almacenamiento",
        "statement_es": (
            "Un establecimiento cosecha 400 toneladas de soja y 600 toneladas de maíz. "
            "En cosecha (momento 1), el precio es 300 USD/t para soja y 180 USD/t para maíz. "
            "Puede vender inmediatamente o almacenar en silos para vender 6 meses después (momento 2) a 350 USD/t para soja y 220 USD/t para maíz. "
            "Dispone de tres tipos de almacenamiento: "
            "Silo A propio: capacidad máxima 300 t, costo de conservación 10 USD/t; "
            "Silo B propio: capacidad máxima 250 t, costo de conservación 15 USD/t; "
            "Silo C tercerizado: capacidad máxima 400 t, costo de conservación 25 USD/t. "
            "Cualquier grano puede ir a cualquier silo. Maximizar el ingreso neto total."
        ),
        "statement_en": (
            "A farm harvests 400 tons of soybean and 600 tons of corn. "
            "At harvest (time 1), price is 300 USD/t for soybean and 180 USD/t for corn. "
            "It can sell immediately or store in silos to sell 6 months later (time 2) at 350 USD/t for soybean and 220 USD/t for corn. "
            "Three storage options are available: "
            "Owned silo A: maximum capacity 300 t, holding cost 10 USD/t; "
            "Owned silo B: maximum capacity 250 t, holding cost 15 USD/t; "
            "Third-party silo C: maximum capacity 400 t, holding cost 25 USD/t. "
            "Any grain can be stored in any silo. Maximize total net revenue."
        ),
        "domain": "agriculture",
        "difficulty": 2,
        "source": "inspired by: Tow 1999, production-storage-sale type",
        "asks_dual": True,
        "asks_reading": [
            {
                "q": 0,
                "kind": "shadow_price",
                "target": "cap_silo_a",
                "text_es": "¿Cuánto vale una tonelada adicional de capacidad en el Silo A?",
                "text_en": "How much is an additional ton of storage capacity in Silo A worth?",
                "expected_unit": "USD/t",
            },
            {
                "q": 1,
                "kind": "indifference_price",
                "target": "v_s1",
                "text_es": "¿A qué precio en cosecha (momento 1) convendría empezar a vender soja en lugar de almacenarla?",
                "text_en": "At what harvest price (time 1) would it become attractive to sell soybean immediately instead of storing it?",
                "expected_unit": "USD/t",
            },
        ],
        "statement_numbers": [400.0, 600.0, 300.0, 180.0, 6.0, 350.0, 220.0, 300.0, 10.0, 250.0, 15.0, 400.0, 25.0],
        "percentage_numbers": [],
        "allowed_extra": [
            340.0, # 350 - 10 (net deferred revenue soy in Silo A)
            335.0, # 350 - 15 (net deferred revenue soy in Silo B)
            325.0, # 350 - 25 (net deferred revenue soy in Silo C)
            210.0, # 220 - 10 (net deferred revenue corn in Silo A)
            205.0, # 220 - 15 (net deferred revenue corn in Silo B)
            195.0, # 220 - 25 (net deferred revenue corn in Silo C)
        ],
        "incomplete": None,
        "_lp_builder": _lp_prob_04,
    },
    {
        "id": "prob_05",
        "title": "Producción porcina y grano",
        "statement_es": (
            "Un productor tiene 80 hectáreas y 900 horas de mano de obra familiar disponible. "
            "Puede sembrar maíz, que rinde 6 toneladas por hectárea y requiere 10 horas de trabajo por hectárea, con costo directo de 200 USD/ha. "
            "El maíz puede venderse a 150 USD/t o usarse para alimentar cerdos. "
            "Cada cerdo requiere 0.5 toneladas de maíz, 4 horas de trabajo y 50 USD en otros gastos, vendiéndose terminado a 180 USD. "
            "Si la mano de obra familiar no alcanza, puede contratar hasta 200 horas extra a 8 USD por hora. "
            "Maximizar el beneficio neto total respetando tierra y trabajo."
        ),
        "statement_en": (
            "A farmer has 80 hectares and 900 hours of family labour available. "
            "He can plant corn, which yields 6 tons per hectare and requires 10 hours of labour per hectare, with direct cost of 200 USD/ha. "
            "Produced corn can be sold at 150 USD/t or fed to pigs. "
            "Each pig requires 0.5 tons of corn, 4 hours of labour, and 50 USD in other expenses, selling finished at 180 USD. "
            "If family labour is insufficient, up to 200 hours of extra labour can be hired at 8 USD per hour. "
            "Maximize total net profit respecting land and labour constraints."
        ),
        "domain": "livestock",
        "difficulty": 2,
        "source": "inspired by: Tow 1999, agrarian economy with livestock",
        "asks_dual": True,
        "asks_reading": [],
        "statement_numbers": [80.0, 900.0, 6.0, 10.0, 200.0, 150.0, 0.5, 4.0, 50.0, 180.0, 200.0, 8.0],
        "percentage_numbers": [],
        "allowed_extra": [
            130.0, # 180 - 50 (margin per pig excluding grain)
        ],
        "incomplete": None,
        "_lp_builder": _lp_prob_05,
    },
    {
        "id": "prob_06",
        "title": "Rotación en 3 períodos",
        "statement_es": (
            "Se planifica la siembra de un campo de 200 hectáreas durante 3 campañas consecutivas (t=1, 2, 3) entre trigo y girasol. "
            "En t=1: margen de trigo 280 USD/ha, girasol 320 USD/ha. "
            "En t=2: margen de trigo 290 USD/ha, girasol 310 USD/ha. "
            "En t=3: margen de trigo 300 USD/ha, girasol 330 USD/ha. "
            "En cada campaña el total sembrado es a lo sumo 200 ha. "
            "Regla agronómica de rotación: el girasol no puede superar el 40% del área en ninguna campaña (máximo 80 ha), "
            "y en dos campañas consecutivas el girasol acumulado no puede superar 120 ha. "
            "Maximizar el margen acumulado en los 3 períodos."
        ),
        "statement_en": (
            "Planting for a 200-hectare field is planned over 3 consecutive seasons (t=1, 2, 3) between wheat and sunflower. "
            "Season 1: wheat margin 280 USD/ha, sunflower 320 USD/ha. "
            "Season 2: wheat margin 290 USD/ha, sunflower 310 USD/ha. "
            "Season 3: wheat margin 300 USD/ha, sunflower 330 USD/ha. "
            "In each season total planted area is at most 200 ha. "
            "Agronomic rotation rule: sunflower cannot exceed 40% of the area in any season (max 80 ha), "
            "and in two consecutive seasons cumulative sunflower cannot exceed 120 ha. "
            "Maximize total cumulative margin over the 3 periods."
        ),
        "domain": "agriculture",
        "difficulty": 2,
        "source": "inspired by: Tow 1999, multi-period rotation",
        "asks_dual": False,
        "asks_reading": [],
        "statement_numbers": [200.0, 3.0, 1.0, 2.0, 280.0, 320.0, 290.0, 310.0, 300.0, 330.0, 40.0, 80.0, 120.0],
        "percentage_numbers": [40.0],
        "allowed_extra": [],
        "incomplete": None,
        "_lp_builder": _lp_prob_06,
    },
    {
        "id": "prob_07",
        "title": "Producto intermedio: fabricar o comprar",
        "statement_es": (
            "Una fábrica elabora dos productos finales: P1 y P2. "
            "Cada unidad de P1 se vende a 120 USD y requiere 2 unidades de un componente intermedio C y 3 horas de ensamblado. "
            "Cada unidad de P2 se vende a 160 USD y requiere 3 unidades de C y 2 horas de ensamblado. "
            "La empresa dispone de 450 horas de ensamblado. El componente C puede fabricarse internamente o comprarse externamente: "
            "Fabricación interna de C: costo de 15 USD por unidad, requiere 1 hora de maquinado (capacidad 250 horas). "
            "Compra externa de C: precio de 25 USD por unidad, sin límite. "
            "Maximizar el margen neto total sin superar horas de ensamblado ni de maquinado."
        ),
        "statement_en": (
            "A factory produces two final products: P1 and P2. "
            "Each unit of P1 sells for 120 USD and requires 2 units of an intermediate component C and 3 assembly hours. "
            "Each unit of P2 sells for 160 USD and requires 3 units of C and 2 assembly hours. "
            "The plant has 450 assembly hours available. Component C can be made in-house or bought externally: "
            "In-house manufacturing of C: cost of 15 USD per unit, requires 1 machining hour (capacity 250 hours). "
            "External purchase of C: price of 25 USD per unit, unlimited availability. "
            "Maximize total net margin without exceeding assembly or machining hours."
        ),
        "domain": "industry",
        "difficulty": 2,
        "source": "inspired by: microeconomic production / supply chain models",
        "asks_dual": False,
        "asks_reading": [],
        "statement_numbers": [120.0, 2.0, 3.0, 160.0, 3.0, 2.0, 450.0, 15.0, 1.0, 250.0, 25.0],
        "percentage_numbers": [],
        "allowed_extra": [],
        "incomplete": None,
        "_lp_builder": _lp_prob_07,
    },
    {
        "id": "prob_08",
        "title": "Aserradero y muebles con 2 tramos de crédito",
        "statement_es": (
            "Un aserradero procesa rollizos de pino para obtener tablas (1 m³ de rollizo rinde 0.6 m³ de tablas y cuesta 40 USD). "
            "Las tablas pueden venderse directamente a 110 USD/m³ o destinarse a carpintería para fabricar mesas. "
            "Cada mesa requiere 0.15 m³ de tablas, 2 horas de mano de obra y se vende a 50 USD (insumos extra: 10 USD/mesa). "
            "La capacidad mensual de aserrado es 500 m³ de rollizos y la de carpintería es 800 horas. "
            "Cuenta con 5000 USD de capital propio. Dispone de dos tramos de crédito: "
            "Tramo 1: hasta 8000 USD al 5% mensual; "
            "Tramo 2: hasta 10000 USD al 12% mensual. "
            "Maximizar el beneficio neto mensual respetando capacidades físicas y caja."
        ),
        "statement_en": (
            "A sawmill processes pine logs into planks (1 m³ of logs yields 0.6 m³ of planks and costs 40 USD). "
            "Planks can be sold directly at 110 USD/m³ or sent to carpentry to manufacture tables. "
            "Each table requires 0.15 m³ of planks, 2 labour hours, and sells for 50 USD (extra inputs: 10 USD/table). "
            "Monthly sawing capacity is 500 m³ of logs and carpentry capacity is 800 labour hours. "
            "Own capital is 5000 USD. Two credit tiers are available: "
            "Tier 1: up to 8000 USD at 5% monthly interest; "
            "Tier 2: up to 10000 USD at 12% monthly interest. "
            "Maximize monthly net profit respecting physical capacities and cash."
        ),
        "domain": "forestry",
        "difficulty": 3,
        "source": "inspired by: FAMASA / Tow 1999 Problem XIV",
        "asks_dual": True,
        "asks_reading": [],
        "statement_numbers": [1.0, 0.6, 40.0, 110.0, 0.15, 2.0, 50.0, 10.0, 500.0, 800.0, 5000.0, 8000.0, 5.0, 10000.0, 12.0],
        "percentage_numbers": [5.0, 12.0],
        "allowed_extra": [
            40.0, # 50 - 10 (margin per table before plank cost)
        ],
        "incomplete": None,
        "_lp_builder": _lp_prob_08,
    },
    {
        "id": "prob_09",
        "title": "Pergamino 500 ha propio (datos completos)",
        "statement_es": (
            "Establecimiento agrícola en Pergamino con 500 hectáreas propias y capital de trabajo de 260.000 USD. "
            "Puede sembrar tres cultivos: "
            "Soja 1ra: margen bruto de 450 USD/ha, costo de implantación de 380 USD/ha; "
            "Maíz: margen bruto de 650 USD/ha, costo de implantación de 600 USD/ha; "
            "Trigo/Soja 2da: margen bruto de 520 USD/ha, costo de implantación de 500 USD/ha. "
            "Restricciones de rotación: el maíz no puede superar el 40% del área (máximo 200 ha), y la soja 1ra no puede superar el 50% (máximo 250 ha). "
            "Maximizar el margen bruto total sin superar tierra ni capital."
        ),
        "statement_en": (
            "Agricultural farm in Pergamino with 500 owned hectares and working capital of 260,000 USD. "
            "Can plant three crops: "
            "Soybean 1st: gross margin 450 USD/ha, cost 380 USD/ha; "
            "Corn: gross margin 650 USD/ha, cost 600 USD/ha; "
            "Wheat/Soybean 2nd: gross margin 520 USD/ha, cost 500 USD/ha. "
            "Rotation limits: corn max 40% (200 ha), soybean 1st max 50% (250 ha). "
            "Maximize total gross margin without exceeding land or capital."
        ),
        "domain": "agriculture",
        "difficulty": 2,
        "source": "DORA benchmark / Pergamino standard case",
        "asks_dual": True,
        "asks_reading": [
            {
                "q": 0,
                "kind": "shadow_price",
                "target": "tierra",
                "text_es": "¿Cuánto vale disponer de una hectárea adicional de tierra propia?",
                "text_en": "How much is an additional hectare of owned land worth?",
                "expected_unit": "USD/ha",
            },
            {
                "q": 1,
                "kind": "indifference_price",
                "target": "soja_1ra",
                "text_es": "¿A qué margen bruto la soja 1ra alcanzaría su tope de rotación de 250 ha?",
                "text_en": "At what gross margin would soybean 1st reach its 250 ha rotation cap?",
                "expected_unit": "USD/ha",
            },
            {
                "q": 2,
                "kind": "rhs_range",
                "target": "capital",
                "text_es": "¿Hasta cuánto puede crecer el capital propio antes de que cambie su precio sombra?",
                "text_en": "Up to how much can working capital grow before its shadow price changes?",
                "expected_unit": "USD",
            },
        ],
        "statement_numbers": [500.0, 260000.0, 450.0, 380.0, 650.0, 600.0, 520.0, 500.0, 40.0, 200.0, 50.0, 250.0],
        "percentage_numbers": [40.0, 50.0],
        "allowed_extra": [],
        "incomplete": None,
        "_lp_builder": _lp_prob_09,
    },
    {
        "id": "prob_10",
        "title": "Pergamino 500 ha arrendado (datos completos)",
        "statement_es": (
            "Establecimiento agrícola en Pergamino que arrienda 500 hectáreas a un costo fijo de arrendamiento de 150.000 USD (300 USD/ha). "
            "Dispone de un capital propio de 350.000 USD para pagar el arriendo y financiar los cultivos: "
            "Soja 1ra: margen bruto de 450 USD/ha, costo de implantación de 380 USD/ha; "
            "Maíz: margen bruto de 650 USD/ha, costo de implantación de 600 USD/ha; "
            "Trigo/Soja 2da: margen bruto de 520 USD/ha, costo de implantación de 500 USD/ha. "
            "Restricciones de rotación: maíz máximo 200 ha (40%) y soja 1ra máximo 250 ha (50%). "
            "Maximizar el margen neto final (margen bruto de cultivos menos arriendo de 150.000 USD) asegurando no superar el capital de 350.000 USD."
        ),
        "statement_en": (
            "Farm in Pergamino renting 500 hectares at a fixed cash rent of 150,000 USD (300 USD/ha). "
            "Has 350,000 USD capital to pay rent and finance crop expenses: "
            "Soybean 1st: gross margin 450 USD/ha, cost 380 USD/ha; "
            "Corn: gross margin 650 USD/ha, cost 600 USD/ha; "
            "Wheat/Soybean 2nd: gross margin 520 USD/ha, cost 500 USD/ha. "
            "Rotation limits: corn max 200 ha (40%), soybean 1st max 250 ha (50%). "
            "Maximize net margin (gross crop margin minus 150,000 USD rent) ensuring total expenditure does not exceed 350,000 USD capital."
        ),
        "domain": "agriculture",
        "difficulty": 2,
        "source": "DORA benchmark / Gemini Sheets case with complete data",
        "asks_dual": True,
        "asks_reading": [
            {
                "q": 0,
                "kind": "shadow_price",
                "target": "tierra",
                "text_es": "¿Cuánto vale disponer de una hectárea adicional arrendada en este escenario?",
                "text_en": "How much is an additional rented hectare worth in this scenario?",
                "expected_unit": "USD/ha",
            },
            {
                "q": 1,
                "kind": "indifference_price",
                "target": "soja_1ra",
                "text_es": "¿A qué margen bruto la soja 1ra dejaría de sembrarse en su tope de 250 ha?",
                "text_en": "At what gross margin would soybean 1st drop below its 250 ha cap?",
                "expected_unit": "USD/ha",
            },
            {
                "q": 2,
                "kind": "rhs_range",
                "target": "capital_cultivos",
                "text_es": "¿Hasta cuánto capital para cultivos puede absorberse antes de que cambie su precio sombra?",
                "text_en": "Up to how much crop working capital can be absorbed before its shadow price changes?",
                "expected_unit": "USD",
            },
        ],
        "statement_numbers": [500.0, 150000.0, 300.0, 350000.0, 450.0, 380.0, 650.0, 600.0, 520.0, 500.0, 200.0, 40.0, 250.0, 50.0],
        "percentage_numbers": [40.0, 50.0],
        "allowed_extra": [
            200000.0, # 350000 - 150000 (capital remaining for crops after rent)
        ],
        "incomplete": None,
        "_lp_builder": _lp_prob_10,
    },
    {
        "id": "prob_11",
        "title": "Incompleto: Pergamino sin capital, arriendo ni reparto",
        "statement_es": (
            "Tengo 500 hectáreas en Pergamino para hacer soja, maíz o trigo/soja. "
            "Armame el plan de siembra óptimo en una planilla para resolver con OpenSolver."
        ),
        "statement_en": (
            "I have 500 hectares in Pergamino to grow soybean, corn, or wheat/soybean. "
            "Build the optimal planting plan in a spreadsheet to solve with OpenSolver."
        ),
        "domain": "agriculture",
        "difficulty": 2,
        "source": "Gemini Sheets case as asked by Guillermo (incomplete data)",
        "asks_dual": False,
        "asks_reading": [],
        "statement_numbers": [500.0],
        "percentage_numbers": [],
        "allowed_extra": [],
        "incomplete": ["capital", "rent", "land_split"],
        "_lp_builder": _lp_prob_11,
    },
    {
        "id": "prob_12",
        "title": "Incompleto: Transporte con demanda destino faltante",
        "statement_es": (
            "Se debe enviar grano desde dos centros de acopio A1 (oferta 300 t) y A2 (oferta 400 t) hacia dos puertos P1 y P2. "
            "El flete desde A1 cuesta 12 USD/t a P1 y 18 USD/t a P2. Desde A2 cuesta 15 USD/t a P1 y 14 USD/t a P2. "
            "El puerto P1 requiere exactamente 250 toneladas de grano. "
            "Diseñar el plan de transporte de costo mínimo."
        ),
        "statement_en": (
            "Grain must be shipped from two storage hubs A1 (300 t) and A2 (400 t) to two ports P1 and P2. "
            "Freight from A1 costs 12 USD/t to P1 and 18 USD/t to P2. From A2 costs 15 USD/t to P1 and 14 USD/t to P2. "
            "Port P1 requires exactly 250 tons of grain. "
            "Design the minimum cost transportation plan."
        ),
        "domain": "transport",
        "difficulty": 1,
        "source": "incomplete transport formulation (missing P2 demand)",
        "asks_dual": False,
        "asks_reading": [],
        "statement_numbers": [300.0, 400.0, 12.0, 18.0, 15.0, 14.0, 250.0],
        "percentage_numbers": [],
        "allowed_extra": [],
        "incomplete": ["destination_demand"],
        "_lp_builder": _lp_prob_12,
    },
]


def get_problem_dict(prob: dict[str, Any], include_callables: bool = False) -> dict[str, Any]:
    """Return serializable problem dict with deterministic 'expected' computed by HiGHS."""
    lp_builder = prob.get("_lp_builder")
    lp_def = lp_builder() if lp_builder is not None else None
    
    expected = _solve_lp_dict(lp_def) if lp_def is not None else {
        "status": "optimal",
        "objective": None,
        "solution": None,
    }
    
    # In P10, adjust objective by fixed cost
    if prob["id"] == "prob_10" and expected.get("objective") is not None:
        expected["objective"] = round(expected["objective"] - 150000.0, 6)

    out = {
        "id": prob["id"],
        "title": prob["title"],
        "statement_es": prob["statement_es"],
        "statement_en": prob["statement_en"],
        "domain": prob["domain"],
        "difficulty": prob["difficulty"],
        "source": prob["source"],
        "asks_dual": prob["asks_dual"],
        "asks_reading": prob.get("asks_reading", []),
        "statement_numbers": prob.get("statement_numbers", []),
        "percentage_numbers": prob.get("percentage_numbers", []),
        "allowed_extra": prob.get("allowed_extra", []),
        "incomplete": prob.get("incomplete"),
        "con_names": lp_def.get("con_names", []) if lp_def else [],
        "var_names": lp_def.get("var_names", []) if lp_def else [],
        "expected": expected,
    }
    if include_callables and lp_builder is not None:
        out["_lp_builder"] = lp_builder
        out["reference_lp"] = lp_builder
    return out


def dump_problems_jsonl(filepath: str | Path = "eval/sheets/data/problems.jsonl") -> Path:
    """Dump all problems with HiGHS-solved expectations to JSONL deterministically."""
    p = Path(filepath)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for prob in PROBLEMS:
        d = get_problem_dict(prob, include_callables=False)
        # Dump with sort_keys=True for strict determinism
        lines.append(json.dumps(d, ensure_ascii=False, sort_keys=True))
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def load_problems(filepath: str | Path | None = None) -> list[dict[str, Any]]:
    """Load problems from JSONL or from python definitions."""
    prob_map = {p["id"]: p.get("_lp_builder") for p in PROBLEMS}
    if filepath is not None and Path(filepath).exists():
        probs = []
        for line in Path(filepath).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                item = json.loads(line)
                if item["id"] in prob_map and prob_map[item["id"]] is not None:
                    item["_lp_builder"] = prob_map[item["id"]]
                    item["reference_lp"] = prob_map[item["id"]]
                probs.append(item)
        return probs
    return [get_problem_dict(p, include_callables=True) for p in PROBLEMS]

