# SPEC-45 Handoff: Planilla v2 (Fase A, Parte 1)

**Rama:** `spec-45-spreadsheet-v2`  
**Base:** `spec-46-satellite-ndvi` (commit `04d2646`)  
**Fecha:** 8 de noviembre de 2026  
**Estado:** Fase A Parte 1 implementada y verificada. Suite completa en 0 fallados.

---

## 1. Resumen de lo implementado (Fase A, Parte 1: A1, A2, A3, A5, A10)

### A1. Nombres de variables y filas (`dora/engine.py`)
- Se implementó `@dataclass class LPModel` con matrices completas (`c`, `A_ub`, `b_ub`, `A_eq`, `b_eq`, `bounds`, `var_labels`, `row_labels`, `x`, `obj_constant`).
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
- Todo coeficiente que no es fórmula exacta queda como valor estático gris con la nota "valor del motor".

### A3. Hoja Modelo (`dora/spreadsheet.py`)
- Estructura en bloque:
  - Fila 1: Descripciones de variables (`Descripción` / `Description`).
  - Fila 2: Claves de variables (`Clave` / `Key`).
  - **Fila 3:** Celdas de decisión amarillas con la solución de DORA (`dora_vars`).
  - Fila 4: Cotas inferiores (`0.0`).
  - Fila 5: Cotas superiores (vacías salvo límites finitos).
  - Fila 6: Coeficientes de la función objetivo ($-c_j$ para maximización con SUMPRODUCT).
  - Fila 8: Celda objetivo $B8$ con `=SUMPRODUCT(C6:<col_end>6, dora_vars)` (`dora_objective`).
  - Fila 8 (D8): Recuadro de instrucciones para OpenSolver en Google Sheets y Excel.
  - Fila 10: Encabezados de restricciones.
  - Filas 11+: **Igualdades primero, luego desigualdades $\le$**, garantizando rangos contiguos para los solvers.
  - LHS: `=SUMPRODUCT(C{r}:<col_end>{r}, dora_vars)`.
  - Sentido: `=` o `<=`.
  - RHS: Valor o fórmula atada a Supuestos.
- Nombres de libro creados:
  - `dora_vars`, `dora_objective`, `dora_eq_lhs`, `dora_eq_rhs`, `dora_le_lhs`, `dora_le_rhs`.
  - Nombres del Solver de Excel: `solver_opt`, `solver_typ`, `solver_adj`, `solver_neg`, `solver_lin`, `solver_eng`, `solver_num`, `solver_lhs1`, `solver_rel1`, `solver_rhs1`, `solver_lhs2`, `solver_rel2`, `solver_rhs2`.
- Hoja oculta `__OpenSolver__` con parámetros de configuración para carga nativa en Google Sheets.

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

### A10. Planillas de ejemplo generadas (`docs/ejemplos/planillas/`)
Se creó el script generador `scripts/make_example_sheets.py` (con `DORA_OFFLINE=1` para aislar datos locales), generando:
1. `pampas-core-2000ha.xlsx` (123.1 KB, < 1 MB) - Caso demo Guillermo (Pampas core 2000 ha propias, 500k USD capital).
2. `se-ba-500ha.xlsx` (117.9 KB, < 1 MB) - Sudeste de Bs. As. 500 ha propias, 50k USD capital.
3. `rented-300ha.xlsx` (121.5 KB, < 1 MB) - 300 ha 100% alquiladas, crédito 200k USD.
4. `se-ba-rent-out.xlsx` (117.0 KB, < 1 MB) - Sudeste de Bs. As. con cesión en alquiler (`allow_rent_out`).
5. `livestock-500ha.xlsx` (42.6 KB, < 1 MB) - Cría bovina Cuenca del Salado (SPEC-30, 500 ha ganaderas).
6. `iowa-400ha.xlsx` (100.6 KB, < 1 MB) - Iowa 400 ha (rotación corn/soybean con costos ISU).
7. `lp-minimo.xlsx` (6.0 KB, < 1 MB) - Modelo lineal mínimo de 3 variables y 2 restricciones ($\le$), óptimo conocido $x=(2.5, 1.5, 0)$, obj $10.5$.
8. `README.md` - Guía detallada en español explicando cómo abrir en Google Sheets, instalar OpenSolver, resolver y comparar con DORA.

---

## 2. Investigación OpenSolver para Google Sheets (A4 / Commit 2)

Se inspeccionó el repositorio de código abierto `OpenSolver/OpenSolverGoogle`:
- **Archivo:** `src/modelStorage.gs`, líneas 3–10:
  ```javascript
  var HIDDEN_SHEET_NAME = "__OpenSolver__";
  ```
- **Archivo:** `src/modelStorage.gs`, líneas 88–117 (`insertHiddenSheetData`):
  OpenSolver guarda la configuración del modelo escribiendo una lista de celdas con fórmulas de cadena `="key=value"` en la hoja oculta `__OpenSolver__`.
  Claves principales: `ModelSheet`, `solver_opt`, `solver_typ`, `solver_adj`, `solver_neg`, `solver_lin`, `solver_eng`, `solver_num`, `solver_lhsN`, `solver_relN`, `solver_rhsN`, `OpenSolver_ChosenSolver`, `OpenSolver_HasLoadedModel`.
- **Archivo:** `src/model.gs`, líneas 1–60:
  El constructor `Model` inicializa los rangos directamente leyendo estas entradas de `__OpenSolver__`.
- **Compatibilidad cruzada:**
  - En Microsoft Excel: lee los nombres definidos `solver_*`.
  - En Google Sheets: además de los nombres definidos, lee la hoja oculta `__OpenSolver__` precargada en el libro.
  - Para la interfaz visual humana: el recuadro superior en la fila 8 de la hoja Modelo detalla los 4 campos exactos a seleccionar si el usuario prefiere configurarlo manualmente en 1 minuto.

---

## 3. Pruebas y Suite Completa

### Tests específicos de la SPEC-45 (`tests/test_spec45.py`):
```
tests/test_spec45.py::test_1_labels PASSED
tests/test_spec45.py::test_2_model_sheet_layout PASSED
tests/test_spec45.py::test_3_solver_names PASSED
tests/test_spec45.py::test_4_independent_resolve_unedited PASSED
tests/test_spec45.py::test_5_independent_resolve_after_edits PASSED
tests/test_spec45.py::test_10_examples PASSED
======================== 6 passed in 71.56s ========================
```

### Tests de compatibilidad con SPEC-42 (`tests/test_spec42.py`):
```
======================== 14 passed in 94.94s ========================
```

### Suite completa (`python -m pytest -q`):
```
534 passed, 1 skipped, 9 warnings in 347.56s (0:05:47)
```

### Verificación de limpieza del repositorio:
```
$ git status --porcelain dora/data observatory
(salida vacía, 100% limpio, sin restaurar nada a mano)
```

---

## 4. Estado de commits

- **Commit 1 (Fase A, Parte 1):** `SPEC-45 implementation (phase A, part 1): model sheet, independent re-solve test, example sheets`
- Próximo paso: Commit 2 (A4) y Commit 3 (A6-A9, A11-A13).
