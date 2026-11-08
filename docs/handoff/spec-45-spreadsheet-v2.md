# SPEC-45 Handoff: Planilla v2 (Fase A Completa)

**Rama:** `spec-45-spreadsheet-v2`  
**Base:** `spec-46-satellite-ndvi` (commit `04d2646`)  
**Fecha:** 8 de noviembre de 2026  
**Estado:** Fase A (secciones A1 a A13) 100 % implementada y verificada. Suite completa en 0 fallados.

---

## 1. Resumen de lo implementado (Fase A: A1 a A13)

### A1. Nombres de variables y filas (`dora/engine.py`)
- Se implementó `@dataclass class LPModel` con matrices completas (`c`, `A_ub`, `b_ub`, `A_eq`, `b_eq`, `bounds`, `var_labels`, `row_labels`, `x`, `obj_constant`, `duals_eq`, `duals_ub`, `reduced_costs`).
- Se agregó el campo opcional `lp: LPModel | None = None` a `Result`.
- Se instrumentó `_Index` con `self.labels: list[dict[str, str]]` y se etiquetaron las 15 familias de variables (`ha`, `ha_w`, `z`, `rent_in`, `rent_out`, `buy`, `heads`, `grass_ha`, `grass_low_ha`, `put_in`, `stock_opt`, `take_out`, `sell`, `S`, `D`, `f_k`) con clave de máquina, descripción en español y descripción en inglés.
- Se etiquetaron todas las restricciones de igualdad ($A_{eq}$, 7 grupos) y de desigualdad ($A_{ub}$, 19 grupos) con `group`, `key`, `desc_es`, `desc_en` y `sense`.
- Parámetro `optimize(sc, keep_lp=True)` que preserva la estructura del LP sin alterar ningún cálculo ni tiempo del motor.

### A2. Coeficientes que son fórmulas vs. valores (`dora/spreadsheet.py`)
- Se definieron `FORMULA_LINKED_INPUTS` y `VALUE_ONLY_INPUTS`, junto con el predicado `is_formula_linked(key)`.
- En la hoja **Supuestos**, se generan celdas auxiliares (`helper.net_price.<crop>.p<fortnight>`) con fórmula lineal exacta:
  $$\text{factor} = (1 + \text{monthly\_price\_rise})^{\text{months}} \times (1 - \text{gross\_receipts\_rate} - \text{tx\_tax\_rate})$$
  $$\text{ded} = \text{route\_cost} + \text{marketing\_per\_t}$$
  $$\text{Fórmula: } ={factor} \times C\{\text{row\_precio}\} - \{ded\}$$
- En la hoja **Modelo**, los coeficientes que corresponden a precios netos, rindes y pagos de insumos apuntan por fórmula a las celdas de Supuestos.
- Los lados derechos (RHS) de capital inicial, tierra propia, línea de crédito y rotación apuntan por fórmula a Supuestos.
- Todo coeficiente que no es fórmula exacta queda como valor estático con la nota "valor del motor".

### A3. Hoja Modelo (`dora/spreadsheet.py`)
- Estructura en bloque:
  - Fila 1: Descripciones de variables (`Descripción` / `Description`).
  - Fila 2: Claves de variables (`Clave` / `Key`).
  - **Fila 3:** Celdas de decisión amarillas con la solución de DORA (`dora_vars`).
  - Fila 4: Cotas inferiores (`0.0`).
  - Fila 5: Cotas superiores (vacías salvo límites finitos).
  - Fila 6: Coeficientes de la función objetivo ($-c_j$ para maximización con SUMPRODUCT).
  - Fila 7: Costo reducido de cada variable (solución de DORA).
  - Fila 8: Celda objetivo $B8$ con `=SUMPRODUCT(C6:<col_end>6, dora_vars)` (`dora_objective`).
  - Fila 8 (D8): Recuadro de instrucciones para OpenSolver en Google Sheets y Excel.
  - Fila 10: Encabezados de restricciones.
  - Filas 11+: **Igualdades primero, luego desigualdades $\le$**, garantizando rangos contiguos para los solvers.
  - Columna de precio sombra (duales de la solución de DORA).
  - LHS: `=SUMPRODUCT(C{r}:<col_end>{r}, dora_vars)`.
  - Sentido: `=` o `<=`.
  - RHS: Valor o fórmula atada a Supuestos.
- Nombres de libro creados:
  - `dora_vars`, `dora_objective`, `dora_eq_lhs`, `dora_eq_rhs`, `dora_le_lhs`, `dora_le_rhs`.
  - Nombres del Solver de Excel: `solver_opt`, `solver_typ`, `solver_adj`, `solver_neg`, `solver_lin`, `solver_eng`, `solver_num`, `solver_lhs1`, `solver_rel1`, `solver_rhs1`, `solver_lhs2`, `solver_rel2`, `solver_rhs2`.
- Hoja oculta `__OpenSolver__` con parámetros de configuración para carga nativa en Google Sheets.

### A4. Investigación de OpenSolver para Google Sheets
- **Archivo:** `src/modelStorage.gs`, líneas 3–10 y 88–117 (`insertHiddenSheetData`).
- OpenSolver guarda la configuración del modelo escribiendo entradas `="key=value"` en la hoja oculta `__OpenSolver__`.
- Claves principales: `ModelSheet`, `solver_opt`, `solver_typ`, `solver_adj`, `solver_neg`, `solver_lin`, `solver_eng`, `solver_num`, `solver_lhsN`, `solver_relN`, `solver_rhsN`, `OpenSolver_ChosenSolver`, `OpenSolver_HasLoadedModel`.
- Compatibilidad cruzada:
  - Microsoft Excel: lee los nombres definidos `solver_*`.
  - Google Sheets: lee la hoja oculta `__OpenSolver__` precargada en el libro.
  - Interfaz visual: recuadro superior en fila 8 de la hoja Modelo con los 4 campos exactos a seleccionar.

### A5. Test de re-resolución independiente (`tests/test_spec45.py`)
- La función `_solve_highs_from_workbook_eval` carga el archivo `.xlsx`, evalúa todas sus fórmulas con `formulas.ExcelModel`, extrae las matrices de la hoja Modelo y resuelve con `scipy.optimize.linprog(method='highs')` **sin invocar a `dora.engine`**.
- **Casos sin editar:**
  - `pampas_core_2000`: HiGHS NPV 660,186.29 USD == DORA 660,186.29 USD (diff 0.0000 USD). Decisiones idénticas ($\Delta x \le 10^{-5}$).
  - `se_ba_500`: HiGHS NPV 114,842.15 USD == DORA 114,842.15 USD (diff 0.0000 USD).
  - `rented_300`: HiGHS NPV == DORA (diff 0.0000 USD).
  - `se_ba_rent_out`: HiGHS NPV == DORA (diff 0.0000 USD).
  - `livestock_500`: HiGHS NPV == DORA (diff 0.0000 USD).
- **Casos con supuestos editados en la hoja:**
  - Edición 1 (Precio de soja +20 %): HiGHS 735,014.28 USD == DORA 735,014.28 USD (diff 0.0000 USD).
  - Edición 2 (Capital propio inicial $\times 2$): HiGHS 715,190.72 USD == DORA 715,190.72 USD (diff 0.0000 USD).
  - Edición 3 (Rendimiento de maíz $-15$ %): HiGHS 642,881.04 USD == DORA 642,881.04 USD (diff 0.0000 USD).

### A6. Aviso de plan de DORA vs. recalculado fuera de DORA
- Se agregaron comprobaciones con fórmulas dinámicas en la hoja **Verificación** (celda B5) y en **Resumen** (celda A1):
  - Si las celdas de decisión de `dora_vars` coinciden con los valores originales de DORA guardados en la columna de referencia y todas las fórmulas de coeficientes se conservan: muestra *"Plan de DORA, verificado"*.
  - Si el usuario o OpenSolver modificaron una o más celdas de decisión: la fórmula conmuta dinámicamente a *"Plan recalculado fuera de DORA (OpenSolver / Solver). Este plan no fue generado por DORA."*
  - Si un usuario sobreescribe una fórmula de la hoja Modelo con una constante: conmuta a *"Cambiaste el modelo: el resultado ya no es comparable con el de DORA."*
  - Al restaurar los valores originales, la fórmula vuelve instantáneamente a *"Plan de DORA, verificado"*.

### A7. Lectura de una planilla re-resuelta (`read_plan_xlsx`)
- Se implementó la función completa de inspección y comparación en `dora/spreadsheet.py`:
  - Extrae el vector $x$ desde la fila 3 (`dora_vars`).
  - Inspecciona la matriz de coeficientes y RHS para verificar integridad estructural contra las fórmulas esperadas de Supuestos.
  - Resuelve el modelo con HiGHS y compara el valor objetivo del libro contra el óptimo matemático.
  - Distingue las razones de discrepancia: `same_plan: True` con status verificado, o `same_plan: False` con `reason`: `"model edited"`, `"worse"`, o `"value_only_input"`.

### A8. Hoja de estrategia de venta (`Estrategia de venta`)
- Nueva hoja agregada en la posición correspondiente (`sheet_names["sales"] = "Estrategia de venta"`):
  - **Tabla 1:** Ventas por cultivo y quincena, desglosadas por canal/destino (directo a puerto, acopio local, silo propio), vinculadas por fórmula a las variables de decisión `sell[crop,p,route]` de la hoja Modelo.
  - **Tabla 2:** Evolución de stock en silo y capacidad disponible por quincena, vinculadas reactivamente a `stock[crop,p,silo]` y `put_in[crop,p,silo]`.
  - Totales e ingresos proyectados por fórmula sobre precios netos.

### A9. Hoja de verificación visible (`Verificación`)
- Incluye el estado de procedencia ("Plan de DORA, verificado" / "Plan recalculado fuera de DORA"), resumen de restricciones quincenales ("Todas las restricciones por quincena se cumplen" o detalle de alertas), e integridad de coeficientes.

### A10. Planillas de ejemplo generadas (`docs/ejemplos/planillas/`)
Se actualizaron y regeneraron las 6 planillas de ejemplo + minimal LP:
1. `pampas-core-2000ha.xlsx` (131.4 KB) - Caso demo principal de Guillermo para el INTA.
2. `se-ba-500ha.xlsx` (125.5 KB) - Sudeste de Bs. As. 500 ha propias, capital activo.
3. `rented-300ha.xlsx` (128.4 KB) - 300 ha 100% arrendadas con crédito.
4. `se-ba-rent-out.xlsx` (124.0 KB) - Sudeste de Bs. As. con cesión en alquiler (`allow_rent_out`).
5. `livestock-500ha.xlsx` (45.4 KB) - Cría bovina Cuenca del Salado (SPEC-30).
6. `iowa-400ha.xlsx` (107.8 KB) - Corn Belt Iowa 400 ha (rotación corn/soybean con costos ISU).
7. `lp-minimo.xlsx` (6.0 KB) - Modelo lineal mínimo de diagnóstico (3 variables, 2 restricciones $\le$, obj 10.5).
8. `README.md` - Guía paso a paso en español para abrir en Google Sheets, cargar OpenSolver y resolver.

### A11. Reactividad total del libro ante re-optimización
- En **Caja por quincena**, todos los componentes de flujos son fórmulas vivas que siguen a `dora_vars` de la hoja Modelo:
  - Hectáreas asignadas a cada cultivo.
  - Ventas por quincena de cada cultivo.
  - Crédito tomado (`L`) y cancelado (`M`).
  - Dinero en el banco ($S[p]$) y deuda acumulada ($D[p]$).
  - Costos de almacenamiento mensual y llenado de silo vinculados reactivamente a `effective_storage_options()`.
- **Test:** Se evaluó el libro con un escenario modificado (precio de soja +20 %) en `formulas.ExcelModel`: el saldo de caja evaluado quincena por quincena coincide con el `cash_ledger` de DORA dentro de **0,0016 USD** ($< 0,01$ USD) a lo largo de las 30 quincenas.

### A12. Chequeos económicos visibles por quincena
- En **Caja por quincena**, se agregaron columnas de control con fórmulas booleanas y formato condicional verde/rojo:
  - Saldo en banco $\ge 0$.
  - Deuda acumulada $\le$ línea de crédito.
  - Stock en silo entre $0$ y la capacidad máxima.
  - Toneladas vendidas acumuladas $\le$ cosecha más stock inicial.
- En la hoja **Verificación**, una fórmula resume: *"Todas las restricciones por quincena se cumplen"* o lista las quincenas observadas.
- Con el plan óptimo de DORA todo permanece verde; al forzar una violación en una celda de decisión (por ejemplo, deuda mayor a la línea de crédito), la quincena correspondiente se resalta en rojo y Verificación reporta la alerta.

### A13. Precios sombra en la planilla
- En la hoja **Modelo**:
  - Columna "Precio sombra (DORA)" junto a cada fila de restricción con el valor dual exacto (capital quincenal, tierra, capacidad de silo, línea de crédito, cuotas de rotación).
  - Fila 7 con el costo reducido de cada variable de decisión.
- En la hoja **Resumen**:
  - Bloque explicativo en lenguaje natural: valor marginal de 1 dólar adicional en quincenas críticas, valor de 1 tonelada adicional de capacidad de silo, valor de 1 hectárea adicional.
  - Nota explicativa: *"Estos precios sombra son del plan de DORA; para los del plan nuevo, pedíselos a DORA"*.
- **Informe de sensibilidad en OpenSolver:**
  - Se analizó la arquitectura de OpenSolver para Google Sheets: OpenSolver en Google Sheets delega la resolución a solvers basados en JavaScript o servicios remotos (COIN-OR CBC vía REST), pero **no** implementa la generación de hojas ni celdas con el Sensitivity Report (a diferencia de Excel Solver para escritorio).
  - Por esta razón, la planilla incluye en el bloque de Resumen y en la hoja Modelo la aclaración correspondiente, indicando que los duales provienen del motor de DORA.

---

## 2. Resultados de la Suite de Pruebas

### Tests específicos de la SPEC-45 (`tests/test_spec45.py`):
```
tests/test_spec45.py::test_1_labels PASSED                               [  7%]
tests/test_spec45.py::test_2_model_sheet_layout PASSED                   [ 15%]
tests/test_spec45.py::test_3_solver_names PASSED                         [ 23%]
tests/test_spec45.py::test_4_independent_resolve_unedited PASSED         [ 30%]
tests/test_spec45.py::test_5_independent_resolve_after_edits PASSED      [ 38%]
tests/test_spec45.py::test_10_examples PASSED                            [ 46%]
tests/test_spec45.py::test_6_outside_dora_flag PASSED                    [ 53%]
tests/test_spec45.py::test_7_read_back PASSED                            [ 61%]
tests/test_spec45.py::test_8_sales_strategy PASSED                       [ 69%]
tests/test_spec45.py::test_9_verification_text PASSED                    [ 76%]
tests/test_spec45.py::test_11_whole_workbook_follows_plan PASSED         [ 84%]
tests/test_spec45.py::test_12_visible_checks PASSED                      [ 92%]
tests/test_spec45.py::test_13_shadow_prices PASSED                       [100%]
======================= 13 passed in 183.93s (0:03:03) ========================
```

### Tests de compatibilidad con SPEC-42 (`tests/test_spec42.py`):
```
======================= 14 passed in 134.16s (0:02:14) ========================
```

### Suite completa (`python -m pytest -q`):
```
541 passed, 1 skipped, 4 warnings in 423.53s (0:07:03)
```

### Verificación de limpieza del repositorio:
```
$ git status --porcelain dora/data observatory
(salida vacía, 100% limpio, sin restaurar nada a mano)
```

---

## 3. Registro de Commits

1. **Commit 1 (`d1e49a0`):** `SPEC-45 implementation (phase A, part 1): model sheet, independent re-solve test, example sheets`
2. **Commit 2 (`22fb470`):** `SPEC-45 implementation (phase A, part 2): OpenSolver storage research and Excel solver defined names`
3. **Commit 3 (actual):** `SPEC-45 implementation (phase A, part 3): sales strategy, visible checks, full workbook reactivity, shadow prices, read back`

Sin merge ni push. Ninguna clave ni token en comandos ni logs.
