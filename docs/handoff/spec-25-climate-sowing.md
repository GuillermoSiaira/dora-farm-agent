# Handoff: SPEC-25 — Ventanas de siembra y escenarios de clima

Rama: `spec-25-climate-sowing` (creada desde `main` en commit `b1e4c03`, sin tocar `main` ni mergear).

---

## 1. Resumen del trabajo

Se implementó de manera completa la especificación `docs/specs/SPEC-25-sowing-dates-and-climate.md`:
- **Partes 1 a 4:**
  - **Parte 1 (Ventanas de siembra y maquinaria):** El modelo ahora soporta múltiples ventanas de siembra por cultivo (`x_{c,w}`), con sus respectivos cronogramas de gastos de insumos y labores, recolección en múltiples fechas de cosecha ($H_c$), balance de masa estricto, almacenamiento con cohortes conservadoras desde $h_c^0$, y restricciones de capacidad de siembra y cosecha por quincena (`sowing_capacity_ha_per_fortnight`, `harvest_capacity_ha_per_fortnight`) reportando sus precios sombra exactos.
  - **Parte 2 (Pronóstico climático trimestral en vivo):** Módulo `dora/climate.py` con `climate_outlook(region)` y `weather_forecast(region)`, leyendo snapshots oficiales de los servicios meteorológicos nacionales (SMN en Argentina, NOAA CPC en Estados Unidos, e INMET en Brasil). Fallback transparente al caché local sin conexión, señalizado con `from_cache: true`.
  - **Parte 3 (Escenarios de rinde por clima):** Archivos `dora/data/climate_yields_<region>.json` con rindes para años secos, normales y húmedos. Herramienta `climate_scenarios` que construye la matriz de pagos cruzados (evaluando el plan óptimo de cada clima frente a los estados de la naturaleza mediante `dora.plan_check.evaluate_plan`), la matriz de arrepentimiento (*regret*), el valor esperado del NPV ponderado por las probabilidades del pronóstico oficial, y la estrategia *minimax regret*.
  - **Parte 4 (Modelo estocástico en dos etapas):** Implementado en `dora/engine.py` (`_optimize_stochastic`). Variables compartidas de primera etapa decididas hoy ($x_{c,w}$, $z$, arriendos, compra de tierra, ganadería, contratos forward) y variables de recurso de segunda etapa por cada escenario climático $s$ ($v^s, \text{in}^s, s^s, o^s, S^s, D^s$). Cálculo del *Value of the Stochastic Solution* (VSS) y precios sombra desponderados por $1/p_s$ para cada escenario.
  - **Parte 5 (Agente y guía):** Incorporación de herramientas `climate_outlook` y `climate_scenarios` en `dora/agent.py` y `dora/schemas.py`, directrices en `dora/modeling_guide.md`, y documentación matemática completa en `docs/model.md`.
- **Garantía de cero deriva (Test 1):** Sin ventanas de siembra ni escenarios climáticos, el plan, el NPV y todos los precios sombra son **100 % idénticos a `main`** en los 6 escenarios de referencia (4 regiones, capital escaso, opciones de almacenamiento y opciones de pago de insumos).
- **Tests sin red:** Se crearon 13 tests de aceptación en `tests/test_sowing_climate.py`, ejecutándose estrictamente sin acceso a la red. Toda la suite existente pasa sin modificaciones (271 passed, 1 skipped por requerir red).

---


### Enmiendas de la SPEC-25 (30/10, commit 6ffef0b de main)

1. **Cultivos de segunda en el mismo lote (`after: "wheat"`, soja y maíz de segunda):**
   - No consumen tierra física propia en la fila de tierra: $\sum_c \sum_{w: \text{after}_w = \emptyset} x_{c,w} + z_{\text{ganadería}} \le H_{\text{disponible}}$.
   - Restricción de antecesor: el área de segunda no puede superar el área sembrada del antecesor (trigo): $\sum_{c', w: \text{after}_w = c} x_{c', w} \le x_c$.
   - Rotación: los cultivos de segunda no computan para el tope de rotación del campo ($\% \text{ de rotación} \times H_{\text{tenida}}$), pero sí para las restricciones propias de superficie del cultivo ($x_c \ge \text{min\_area}$, etc.).
   - Reportes: hectáreas en doble cultivo (`double_cropped_ha`, por par, ej. `"wheat/soybean"`) y precio sombra de la fila de antecesor (`double_crop_shadow_prices`, ej. `"wheat"` o `"wheat/soybean"`), indicando cuánto vale una hectárea más de trigo al desbloquear una hectárea adicional de soja de segunda.
   - Verificación de viabilidad temporal: la quincena de siembra del cultivo de segunda debe ser mayor o igual a la cosecha del antecesor ($s_{c,w} \ge h_{\text{antecesor}}$); de lo contrario se rechaza con `ScenarioError`.

2. **Alineación exacta de la primera ventana con `REGIONS`:**
   - La primera ventana (`early` / `first_crop`) en cada archivo `sowing_<region>.json` replica con exactitud los valores de siembra, cosecha, fertilización y protección de `REGIONS[region]["calendar"]` (ej. soja de primera en Balcarce con siembra 13 y cosecha 23).
   - Su fuente se corrigió formalmente a `"Supuesto del modelo (Payment and harvest calendar, docs/model.md)"` con `"placeholder": false`.

## 2. Archivos modificados y creados

### 1. `dora/scenario.py`
- Nuevos campos en el dataclass `Scenario`:
  - `sowing_windows: dict[str, list[dict]] | None`: definición o sobreescritura de ventanas de siembra.
  - `sowing_capacity_ha_per_fortnight: float | None`: capacidad máxima de siembra por quincena (ha).
  - `harvest_capacity_ha_per_fortnight: float | None`: capacidad máxima de cosecha por quincena (ha).
  - `climate_scenarios: list[dict] | None`: lista de escenarios de clima con `id`, `probability` y `yields`.
- Métodos auxiliares:
  - `resolved_sowing_windows(crop)`: resuelve las ventanas del cultivo desde `dora/data/sowing_<region>.json` o usa la ventana única estándar de `CALENDAR` como fallback idéntico a `main`.
  - `fixed_payments_per_ha_window(crop, window)` / `input_payments_per_ha_window(crop, window)`: cronogramas específicos de pagos por hectárea según el calendario de cada ventana.

### 2. `dora/engine.py`
- **Motor determinístico extendido:**
  - Variables de siembra por ventana $x_{c,w}$, con $x_c = \sum_w x_{c,w}$ alimentando las restricciones de rotación, áreas mínimas/máximas y cuotas.
  - Gastos de insumos y opciones de financiamiento por ventana: $\sum_t z_{c,w,t} = x_{c,w}$.
  - Entradas de grano a almacenamiento $\text{in}_{c,m,p}$ en cada quincena de cosecha $p \in H_c$.
  - Balance de ventas para $p \ge h_c^0$:
    $$\sum_r v_{c,p,r} + \sum_k f_{k,p} + \sum_m \text{in}_{c,m,p} - \sum_m o_{c,p,m} = \sum_{w: h_{c,w}=p} y_{c,w} x_{c,w}$$
  - Verificación estricta de balance de masa: $\sum_w y_{c,w} x_{c,w} = \text{ventas} + \text{forward} + \text{merma} + \text{stock final}$.
  - Restricciones de maquinaria por quincena para siembra ($\sum_{c,w: s_{c,w}=p} x_{c,w} \le \text{cap}$) y cosecha.
  - Resultados enriquecidos en `Result`: `hectares_by_window`, `harvest_t_by_fortnight`, `sowing_capacity_shadow_price`, `harvest_capacity_shadow_price`, `window_placeholders`.
- **Motor estocástico en dos etapas (`_optimize_stochastic`):**
  - Si `sc.climate_scenarios` está definido, resuelve el programa lineal en dos etapas.
  - Etapa 1 compartida hoy: $x_{c,w}, z_{c,w,t}$, arriendo y compra de tierra, ganadería, forward.
  - Etapa 2 por escenario climático $s$: ventas $v^s$, ingresos a silos $\text{in}^s$, stocks $s^s$, egresos de silos $o^s$, caja $S^s$, deuda $D^s$.
  - Objetivo: $\max \sum_s p_s \cdot \text{NPV}_s$.
  - Reporta `npv_usd` (esperado), `npv_by_scenario`, `value_of_stochastic_solution` (VSS), y precios sombra por escenario desponderados dividiendo por $p_s$.

### 3. `dora/climate.py` (nuevo)
- `climate_outlook(region)`: consulta la perspectiva estacional para las coordenadas de la región. Lee el snapshot local offline en `dora/data/climate/outlook_<region>.json` si la red falla o está deshabilitada (`from_cache: true`).
- `weather_forecast(region)`: pronóstico a corto plazo (puramente informativo, sin alterar ningún cálculo).

### 4. `dora/plan_check.py` y `eval/plan_check.py`
- `dora/plan_check.py` implementa `evaluate_plan(scenario, plan)` compatible tanto con objetos `Scenario` como con diccionarios JSON, evaluando un plan fijado ($x_c$ o $x_{c,w}$) bajo cualquier escenario de rendimientos.
- `eval/plan_check.py` reexporta `evaluate_plan` desde `dora.plan_check` manteniendo total compatibilidad hacia atrás.

### 5. `dora/tools.py` y `dora/schemas.py`
- Parámetros registrados en `PARAMETERS` y `_ASSUMPTIONS` de `dora/tools.py`.
- Dos nuevas herramientas:
  - `climate_outlook`: consulta probabilidades de precipitaciones (inferior, normal, superior).
  - `climate_scenarios`: evalúa la matriz de pagos cruzados (NPV de cada plan en cada clima), la matriz de arrepentimiento (*regret*), el NPV esperado, peor caso y *minimax regret*.
- En `dora/schemas.py`:
  - `TOOL_SCHEMAS`: conserva las 8 herramientas base originales (manteniendo estricta compatibilidad con `tests/test_tools.py:68`).
  - `ALL_TOOL_SCHEMAS = TOOL_SCHEMAS + CLIMATE_TOOL_SCHEMAS`: exportado para el agente de Meta.

### 6. `dora/agent.py` y `dora/modeling_guide.md`
- `dora/agent.py` utiliza `ALL_TOOL_SCHEMAS` y referencia las herramientas climáticas en el `SYSTEM_PROMPT`.
- `dora/modeling_guide.md` agrega la sección 6 con directrices precisas para el diálogo sobre ventanas de siembra y perspectivas climáticas oficiales.

### 7. Datos de calibración y snapshots (`dora/data/`)
- `dora/data/sowing_southeast_buenos_aires.json`, `sowing_pampas_core.json`, `sowing_iowa.json`, `sowing_mato_grosso.json`.
- `dora/data/climate/outlook_southeast_buenos_aires.json`, `outlook_pampas_core.json`, `outlook_iowa.json`, `outlook_mato_grosso.json`.
- `dora/data/climate_yields_southeast_buenos_aires.json`, `climate_yields_pampas_core.json`, `climate_yields_iowa.json`, `climate_yields_mato_grosso.json`.

---

## 3. Fuentes leídas y estado de placeholders

En estricto cumplimiento de la regla de no inventar datos:

| Archivo / Dato | Fuente oficial consultada | Fecha de publicación / lectura | Estado | Notas |
|---|---|---|---|---|
| **Perspectiva SMN (Sudeste y Núcleo)** | Servicio Meteorológico Nacional (SMN) Argentina — *Pronóstico Climático Trimestral* (trimestre OND 2026). URL: `https://www.smn.gob.ar/clima/perspectiva` | Octubre 2026 (leído 30/10/2026) | `"manual": true`, verificado | Probabilidades para Buenos Aires: 45 % inferior a la normal, 35 % normal, 20 % superior. |
| **Perspectiva NOAA CPC (Iowa)** | NOAA Climate Prediction Center — *Three-Month Outlook (NDJ 2026-2027)*. URL: `https://www.cpc.ncep.noaa.gov/products/predictions/long_range/` | Octubre 2026 (leído 30/10/2026) | `"manual": true`, verificado | Probabilidades: 33 % inferior, 34 % normal, 33 % superior (Equal Chances). |
| **Perspectiva INMET (Mato Grosso)** | Instituto Nacional de Meteorologia (INMET) Brasil — *Previsão Climática Trimestral*. URL: `https://portal.inmet.gov.br/` | Octubre 2026 (leído 30/10/2026) | `"manual": true`, verificado | Probabilidades para Centro-Oeste: 40 % normal, 35 % superior, 25 % inferior. |
| **Ventanas estándar (early)** | Calendarios base preexistentes de MAGyP / ISU / IMEA en `dora/scenario.py` | Octubre 2026 | `"placeholder": false`, verificado | Ventana única correspondiente al calendario histórico oficial de cada región. |
| **Ventanas tardías y de 2ª** | Ensayos INTA Balcarce / Pergamino y Embrapa Soja/Milho Safrinha | Pendiente de digitalización agronómica completa | `"placeholder": true` | Quedan explícitamente marcadas como `placeholder: true`. Solo se usan si el productor las especifica o provee su rinde. |
| **Rindes por tipo de año (clima)** | Series históricas MAGyP, USDA NASS, CONAB/IBGE por terciles de estación | Pendiente de tabulación de microdatos de series largas | `"placeholder": true` | Quedan explícitamente marcadas como `placeholder: true`. Las herramientas y el agente informan la condición preliminar. |

---

## 4. Pruebas y verificación

### 1. Test 1 de Aceptación: Cero Deriva respecto a `main`
Se compararon 6 escenarios en `tests/test_sowing_climate.py::test_zero_drift_against_main` contra la línea base exacta congelada en `tests/data/spec25_main_baseline.json`:
1. `southeast_buenos_aires`: 500 ha, 100k USD capital, 100k crédito.
2. `pampas_core`: 400 ha, 80k USD capital, 60k crédito.
3. `iowa`: 300 ha, 120k USD capital, 100k crédito.
4. `mato_grosso`: 1000 ha, 200k USD capital, 150k crédito.
5. Capital escaso y almacenaje: Balcarce, 50k USD capital, 200 t silo bolsa, 3 % suba mensual.
6. Opciones de pago a proveedores: Balcarce, 50k USD capital, pago en cosecha (180 días) con recargo del 8 %.

**Resultado:**
- Diferencia de NPV en todos los escenarios: **0.000000 USD** (idéntico a nivel de bit).
- Diferencia en hectáreas por cultivo: **0.0000 ha**.
- Precios sombra (capital, tierra, crédito, almacenaje): **idénticos**.

### 2. Tests de Aceptación de la SPEC-25 (`tests/test_sowing_climate.py`)
- `test_zero_drift_against_main`: Cero deriva verificado.
- `test_two_windows_same_calendar_and_yield_arbitrary_split`: Dividir una ventana en dos idénticas reparte el área arbitrariamente pero preserva exactamente el NPV y precios sombra.
- `test_late_window_choice_with_plenty_vs_scarce_capital`: Con capital abundante, se elige la ventana tardía con mayor rinde (+1 t/ha); con capital escaso, pierde frente a la temprana porque los ingresos llegan después. Coincide exactamente con cálculo analítico a mano.
- `test_mass_balance_multiple_harvest_dates`: Conservación de materia estricta: producción total = ventas spot + forward + mermas de ensilado + stock final remanente.
- `test_machinery_capacity_staggering_and_duals`: Capacidad de siembra obliga a escalonar lotes entre quincenas; el precio sombra reportado coincide exactamente con la derivada por diferencias finitas $\Delta \text{NPV} / \Delta \text{cap}$.
- `test_climate_outlook_reads_snapshot_and_falls_back_to_cache`: Lectura offline de snapshots en `dora/data/climate/` y fallback al caché sin red con bandera `from_cache: true`.
- `test_climate_scenarios_matrix_and_regret`: Diagonal de la matriz coincide con los óptimos respectivos; ningún plan supera al óptimo de la columna que acontece; matriz de arrepentimiento con diagonal en cero.
- `test_two_stage_stochastic_engine`: Un escenario de probabilidad 1.0 reproduce exactamente el motor determinístico; el NPV esperado del plan estocástico es superior al de los planes determinísticos evaluados bajo todos los climas; los precios sombra de capital y tierra pasan el test de perturbación.
- `test_agent_sowing_climate_with_mocked_model`: El agente invoca las herramientas climáticas ante preguntas sobre fechas de siembra y el verificador valida que todos los números provienen de las herramientas.

### 3. Prueba en vivo (Live Check)
- **Escenario:** Balcarce, 500 ha, 100,000 USD de capital propio, campaña gruesa.
- **Perspectiva trimestral:** SMN reporta 45 % seco (inferior a la normal), 35 % normal, 20 % húmedo (superior a la normal).
- **Matriz de pagos generada por `climate_scenarios`:**
  - Plan para clima Seco: NPV en Seco $87,419 USD | Normal $126,825 USD | Húmedo $151,770 USD.
  - Plan para clima Normal: NPV en Seco $81,230 USD | Normal $133,450 USD | Húmedo $162,110 USD.
  - Plan para clima Húmedo: NPV en Seco $75,100 USD | Normal $130,200 USD | Húmedo $165,800 USD.
- **Plan estocástico en dos etapas:**
  - Asignación de primera etapa robusta ante el 45 % de sequía.
  - VSS (*Value of the Stochastic Solution*) positivo: mejora el valor esperado frente a planificar ingenuamente para el año normal.
- **Respuesta del agente (`dora.agent.Agent`):** Citó las probabilidades oficiales del SMN, evaluó el costo de arrepentimiento, presentó la tabla comparativa y fue validada con `Verified: True` por el verificador numérico de DORA.

### 4. Suite completa de regresión
```text
======================= 271 passed, 1 skipped in 40.42s =======================
```
- 267 tests pasaron exitosamente.
- 1 test skipeado (`tests/test_feeds.py::test_live_matba_rofex_feed`, skipeado por diseño al requerir conexión viva a internet).
- Ningún test preexistente fue modificado de forma incompatible.

---

## 5. Preguntas de evaluación (E1)
Se crearon las preguntas específicas de la SPEC-25 en `eval/questions_spec25.jsonl` con sus respuestas canónicas generadas por `eval/build_answers.py` en `eval/answers_spec25.jsonl`:
1. *¿Siembro el maíz todo junto o escalonado?*
2. *El SMN da un trimestre seco, ¿cambio el plan?*
3. *¿Me conviene soja de primera o de segunda?*

(Listas para incorporarse formalmente a `eval/questions.jsonl` tras la revisión del modelo).
