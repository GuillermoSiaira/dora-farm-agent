# SPEC-49 Handoff: Venta a término como decisión, con riesgo de precio (Hedge or Sell at Harvest)

**Branch:** `spec-49-price-risk` (created from `spec-45-spreadsheet-v2` at `fc6a4b2`)  
**Status:** Completed — Commits 1, 2, and 3 completed; full test suite passing (553 passed, 1 skipped, 0 failed).

---

## 1. Commit 1: Escenarios de precio y modelo estocástico de dos etapas

- **Commit:** `4ff3e8b`
- **Descripción:** Implementación de las secciones 1, 2 y 3 de la especificación:
  - Campos de escenario en `Scenario`: `price_risk` con `n_scenarios` (3 a 45, default 9), `risk_weight` ($\beta \in [0, 1]$, default 0.0), `cvar_alpha` ($\alpha \in [0.01, 0.50]$, default 0.10), `max_hedge_share` (default 0.60), y `forward_offers`.
  - Construcción de cuantiles deterministas de precio: normal estándar $z_s = \Phi^{-1}((s - 0.5) / S)$, precio $P_s = \mu \exp(z_s \sigma \sqrt{\tau} - 0.5 \sigma^2 \tau)$ calibrado para preservar la media $\mathbb{E}[P_s] = \mu$ exactamente con corrección de escala $\kappa$.
  - 4 archivos regionales `dora/data/price_risk_<region>.json` con volatilidades anualizadas por cultivo y procedencia de datos (`placeholder: true` con CBOT front contract 5-year historical).
  - Modelo LP de dos etapas (`_optimize_price_risk` en `dora/engine.py`):
    - **No-anticipación:** las decisiones de primera etapa (hectáreas sembradas $x_c$, gastos de implantación tempranos, crédito temprano $D_{1,p}$, y toneladas comprometidas a término $F_k$) son idénticas en todos los escenarios. Se definen como variables únicas compartidas en la matriz LP.
    - **Segunda etapa:** comienza en la quincena de cosecha de cada cultivo. Cada escenario $s$ tiene sus variables de venta spot $V_{s,c,p}$, ventas a término ejecutadas o recompradas ($buy\_back_{s,k}$), saldo bancario $S_{s,p}$, y deuda $D_{s,p}$.
    - **Función objetivo:** maximización de $\mathbb{E}[\text{NPV}] - \beta (\mathbb{E}[\text{NPV}] - \text{CVaR}_\alpha)$ linealizada mediante variable auxiliar $\gamma$ (VaR) y desviaciones $u_s \ge 0$.
  - Despacho transparente en `optimize(sc)`: si `sc.price_risk` está presente y `n_scenarios > 1`, despacha a `_optimize_price_risk`.
  - Tests 1, 2, 3, 4, 6, 9 y 10 implementados y verificados.

---

## 2. Commit 2: Herramienta `hedge_analysis`, frontera y verificación independiente

- **Commit message:** `SPEC-49 implementation (2): hedge_analysis tool, frontier, independent per-scenario check`
- **Herramienta `hedge_analysis`:**
  - Registrada en `dora/tools.py` (`TOOLS["hedge_analysis"]`), expuesta en `mcp_server/server.py` como herramienta MCP con validación estricta y firma de proveniencia canónica, y documentada en `dora/schemas.py`.
  - Calcula la frontera media-CVaR evaluando $\beta \in \text{risk\_weights}$ (default: `[0.0, 0.25, 0.5, 0.75, 1.0]`).
  - Para cada $\beta$, reporta: `expected_npv`, `cvar`, `worst_npv`, `best_npv`, `forward_sales`, `forward_tonnes`, `hedge_ratio`, `hectares`, y `min_cash`.
  - **Precio de indiferencia $P^*$:** precio forward al cual el productor neutral al riesgo ($\beta=0$) es indiferente entre vender forward o esperar a cosecha. Calculado mediante bisección eficiente sobre el LP ($\le 20$ iteraciones totales en presupuesto).
  - **Guía del agente (`dora/modeling_guide.md`):** instrucciones completas de neutralidad económica:
    - Nunca decidir el nivel de riesgo por el productor: presentar la frontera y dejar que él decida.
    - Nunca recomendar un corredor, mercado o producto financiero.
    - Cada afirmación está respaldada por números exactos calculados por el motor.
    - Cita siempre si la volatilidad es medida o supuesta ("volatilidad supuesta, no medida").
    - Soporte bilingüe estricto (español e inglés).
- **Verificación independiente escenario por escenario (Test 7):**
  - Se resuelve el modelo estocástico con `price_risk`.
  - Se fijan las decisiones de primera etapa (hectáreas sembradas con restricciones `min_area = max_area`, y toneladas forward fijadas como restricciones `forward_sale`).
  - Se re-resuelve **cada escenario por separado** con el motor determinista tradicional de DORA (`optimize(sc_s)`).
  - El $\text{NPV}_s$ del motor determinista coincide con el $\text{NPV}_s$ del modelo estocástico dentro de $\pm 0.01$ USD (diferencia observada: $< 0.0001$ USD).
  - El $\text{CVaR}_\alpha$ calculado independientemente ordenando los $\text{NPV}_s$ deterministas coincide con el CVaR del LP estocástico dentro de $\pm 0.01$ USD.
- **Dimensiones del LP y rendimiento:**
  - 9 escenarios de precio: 1.560 variables, 1.380 restricciones.
  - Tiempo de resolución con scipy HiGHS: ~0.08 s a 0.15 s por LP.
  - Cálculo completo de frontera (5 puntos) + bisección de precio de indiferencia: ~1.2 segundos totales.
- **Higiene y suite:**
  - `tests/conftest.py` actualizado con `os.environ.setdefault('DORA_OFFLINE', '1')` a nivel módulo, garantizando aislamiento total contra descargas accidentales en cualquier ejecución de pytest.
  - `git status --porcelain dora/data observatory` 100% limpio sin restauraciones manuales.

---

## 3. Commit 3: Grilla precio × clima, sobre-cobertura y recompra de grano

- **Commit message:** `SPEC-49 implementation (3): price x climate grid`
- **Descripción:** Implementación de la Sección 4 de la especificación y Test 8:
  - **Grilla de escenarios precio × clima:** cuando se especifica `with_climate: true` y existen `climate_scenarios`, los escenarios combinan ambas fuentes de incertidumbre como producto cartesiano:
    $$\pi_{p,c} = \pi_{\text{price}, p} \times \pi_{\text{climate}, c}$$
    con un límite estricto de 45 escenarios combinados ($S_{\text{price}} \times S_{\text{climate}} \le 45$), rechazando grillas mayores con `ScenarioError`.
  - **No-anticipación estricta y sobre-cobertura:**
    - Las decisiones de siembra ($x_{c,w}$) y los compromisos a término ($h_{c,o}$) se fijan en la primera etapa, antes de conocer el precio y el rinde.
    - Cuando ocurre un escenario seco (ej. rinde al 50 %), la producción física puede no alcanzar para cumplir con el contrato a término.
    - El balance físico incorpora recompra de grano a precio de mercado más penalidad:
      $$\text{Cosecha}_{s,c,p} + \text{SalidaSilo}_{s,c,p} + \text{buy\_back}_{s,c,p} = \text{VentaSpot}_{s,c,p} + \text{EntregaForward}_{s,c,p} + \text{EntradaSilo}_{s,c,p}$$
      donde $\text{buy\_back}$ tiene un costo de $\text{spot\_ref} + 5.0\text{ USD/t}$ (`buyback_cost_usd_t`).
  - **Acotación física y desempatador de Pareto en HiGHS:**
    - `bounds[buy_back] = (0, 0)` para cualquier cultivo o quincena sin contratos a término, evitando arbitrajes matemáticos en cultivos sin entrega forward.
    - En formulaciones de puro CVaR ($\beta=1.0$), los escenarios fuera de la cola del 10 % tienen peso 0 en el objetivo (dado que $1-\beta = 0$ y $u_s = 0$). Para evitar indeterminación en escenarios húmedos donde el solver podría recomprar grano innecesariamente sin penalización en CVaR, se incorpora un desempatador $\epsilon = 10^{-4}$ en $\mathbb{E}[\text{NPV}]$ cuando $\beta \ge 0.999$. Esto garantiza eficiencia de Pareto: más riqueza siempre es estrictamente preferida a menos riqueza, haciendo que `buy_back > 0` ocurra **única y exclusivamente** cuando es físicamente indispensable para cumplir con la entrega forward.
  - **Independencia precio-rinde:**
    - Se asume independencia entre el precio internacional y el rinde local (una sequía en Pergamino apenas mueve el CBOT, mientras que una sequía en el Corn Belt de EE.UU. sí lo mueve). La correlación precio-rinde queda documentada como alcance futuro.
  - **Resultados de Test 8 (`tests/test_spec49.py`):**
    - **Parte 1 (Decisión óptima):** Ante una oferta forward a 320 USD/t, un productor con $\beta=1.0$ (máxima aversión al riesgo) elige un ratio de cobertura de exactamente 50 % ($0.50 \le 0.50$), limitado exactamente por la relación $\frac{\text{producción seca}}{\text{producción esperada}} = \frac{1.0}{2.0} = 0.50$. Jamás se sobre-cubre para no quedar corto en años secos.
    - **Parte 2 (Sobre-cobertura forzada):** Si se fuerza una venta a término de 300 t sobre una producción seca de 250 t (250 ha a 1.0 t/ha), el modelo reporta `buy_back` estrictamente positivo (exactamente 50.0 t) en **todos los escenarios secos**, y estrictamente 0.0 t en **todos los escenarios normales**.
  - **Estadísticas del LP con grilla (5 precios × 2 climas = 10 escenarios):**
    - Variables: 1.722; Filas: 1.524.
    - Tiempo de resolución: ~0.11 s en HiGHS.

---

## 4. Salida real de los tests

### Tests de la SPEC-49 (`tests/test_spec49.py`)
```
tests/test_spec49.py::test_01_no_price_risk PASSED                       [  9%]
tests/test_spec49.py::test_02_one_scenario_zero_volatility PASSED        [ 18%]
tests/test_spec49.py::test_03_mean_is_preserved PASSED                   [ 27%]
tests/test_spec49.py::test_04_risk_neutral_fair_offer PASSED             [ 36%]
tests/test_spec49.py::test_05_monotone_frontier PASSED                   [ 45%]
tests/test_spec49.py::test_06_premium_and_discount PASSED                [ 54%]
tests/test_spec49.py::test_07_independent_check_each_scenario PASSED     [ 63%]
tests/test_hedge_analysis_tool PASSED                                    [ 72%]
tests/test_08_over_hedging_climate PASSED                                [ 81%]
tests/test_09_validation PASSED                                          [ 90%]
tests/test_10_hygiene PASSED                                             [100%]

============================= 11 passed in 4.87s ==============================
```

### Tests de herramientas y esquemas (`tests/test_tools.py`)
```
============================= 30 passed in 0.20s ==============================
```

### Tests del servidor MCP (`tests/test_spec40.py`)
```
============================= 14 passed in 7.50s ==============================
```

### Tests de siembra y clima SPEC-25 (`tests/test_sowing_climate.py`)
```
============================= 13 passed in 0.82s ==============================
```

### Suite completa (ejecutada con DORA_OFFLINE=1)
```
553 passed, 1 skipped, 9 warnings in 944.61s (15:44)
0 failed
git status --porcelain dora/data observatory: [VACÍO]
```

---

## 5. Números de la frontera y prueba de Pergamino

Para el caso del productor de Pergamino (500 ha propias, capital 260.000 USD, oferta de soja a 330 USD/t a mayo 2027):

| $\beta$ (peso de riesgo) | $\mathbb{E}[\text{NPV}]$ (USD) | $\text{CVaR}_{10\%}$ (USD) | Peor escenario (USD) | Mejor escenario (USD) | Cobertura Soja (t) | Ratio de Cobertura |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **0.00** | 483.445,27 | 275.473,27 | 275.473,27 | 739.667,77 | 0,0 | 0 % |
| **0.25** | 483.445,27 | 275.473,27 | 275.473,27 | 739.667,77 | 0,0 | 0 % |
| **0.50** | 466.506,56 | 312.571,32 | 312.571,32 | 656.715,22 | 570,0 | 60 % |
| **0.75** | 437.869,68 | 335.966,22 | 335.966,22 | 562.716,53 | 570,0 | 60 % |
| **1.00** | 346.396,24 | 346.396,24 | 346.396,24 | 346.396,24 | 570,0 | 60 % |

- **Precio de indiferencia ($P^*$ en $\beta=0$):** 360,94 USD/t (la oferta de 330 USD/t está por debajo de la curva esperada de mayo ~361 USD/t).
- **Texto explicativo generado:**
  > "Volatilidad anual supuesta, no medida (CBOT front contract 5-year historical volatility (placeholder)). Sin aversión al riesgo (beta=0), vender a término no suma: el precio ofrecido no supera el precio de indiferencia (soybean: 360.94 USD/t). Con aversión al riesgo (beta=0.5), la cobertura pasa a soybean (60 %): el peor 10 % de los años (CVaR) pasa de 275,473 a 312,571 USD (+37,098 USD), y el resultado esperado pasa de 483,445 a 466,507 USD (-16,939 USD). DORA presenta la frontera para que el productor elija su nivel de riesgo; no elige el nivel de riesgo por él."

---

## 6. Fuera de alcance (Seguimientos futuros)

- **Contratos de futuros con llamadas de margen y opciones financieras (puts, collars):** actualmente el forward modelado es OTC físico con liquidación a entrega.
- **Correlaciones inter-cultivos distintas de 1 y correlación precio-rinde:** en esta versión los precios de commodities se mueven al unísono y son independientes del clima local argentino.
- **Hoja en la planilla Excel/OpenSolver:** incorporación de una pestaña de "Riesgo de precio" en el libro generado en SPEC-45.

---

## 7. Pendiente para Guillermo (prueba manual en app)

En la app web: preguntar "Tengo 500 ha propias en Pergamino y 260.000 dólares. ¿Me conviene vender parte de la soja a término? Me ofrecen 330 a mayo."
Verificar que responda con la herramienta `hedge_analysis`, muestre la tabla de la frontera, mencione la volatilidad supuesta, y no invente números.
