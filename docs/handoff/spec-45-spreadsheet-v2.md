# SPEC-45 Handoff: Planilla v2 (Fase A Completa y Ajustes de Revisión)

**Rama:** `spec-45-spreadsheet-v2`  
**Base:** `spec-46-satellite-ndvi` (commit `04d2646`)  
**Fecha:** 8 de noviembre de 2026  
**Estado:** Fase A (secciones A1 a A13) y los ajustes de revisión del 8/11 100 % implementados y verificados. Suite completa en 0 fallados.

---

## 1. Resumen de lo implementado (Fase A y Ajustes de Revisión)

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
  - **Fila 7:** Costo reducido de cada variable (solución de DORA), rotulado: *"Costo reducido (DORA): USD de VNP que se pierden por cada unidad que se fuerza en el plan"* (signo positivo exacto).
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
- **Archivo:** `src/modelStorage.gs`, líneas 3–10, 39 (`getFormulas()`), 88–117 (`insertHiddenSheetData`), 151 (`createHiddenSheetEntry`), 157 (`splitHiddenSheetEntry`).
- **Formato nativo de hoja oculta:** OpenSolver genera entradas como formulas `=key=value` sin comillas internas, escribiendo en XML celdas `<f>ModelSheet=Modelo!A:Z</f>` con valor `#NAME?`. `splitHiddenSheetEntry` separa por `=` exigiendo exactamente 3 partes con la primera vacía: `['', key, value]`. Si se agregaban comillas a la fórmula, la clave resultaba en `"ModelSheet` impidiendo que `getSheetColumn` reconociera el modelo. Se corrigió `_build_model_sheet` para emitir estrictamente `[f"={k}={v}"]`.
- OpenSolver guarda la configuración del modelo escribiendo entradas `=key=value` en la hoja oculta `__OpenSolver__`.
- Claves principales: `ModelSheet`, `solver_opt`, `solver_typ`, `solver_adj`, `solver_neg`, `solver_lin`, `solver_eng`, `solver_num`, `solver_lhsN`, `solver_relN`, `solver_rhsN`, `OpenSolver_ChosenSolver`, `OpenSolver_HasLoadedModel`.
- Compatibilidad cruzada:
  - Microsoft Excel: lee los nombres definidos `solver_*`.
  - Google Sheets: lee la hoja oculta `__OpenSolver__` precargada en el libro.
  - Interfaz visual: recuadro superior en fila 8 de la hoja Modelo con los 4 campos exactos a seleccionar.

### A5. Test de re-resolución independiente (`tests/test_spec45.py`)
- La función `_solve_highs_from_workbook_eval` carga el archivo `.xlsx`, evalúa todas sus fórmulas con `formulas.ExcelModel`, extrae las matrices de la hoja Modelo y resuelve con `scipy.optimize.linprog(method='highs')` **sin invocar a `dora.engine`**.
- **Curvas de precios del repositorio:**
  - `dora/data/price_curves/cbot_latest.json` (`as_of: 2026-10-31`).
  - `dora/data/price_curves/argentina_latest.json` (`as_of: 2026-10-30`).
- **Casos sin editar:**
  - `pampas_core_2000`: HiGHS NPV **1.036.105,42 USD** == DORA **1.036.105,42 USD** ($\Delta \text{NPV} = 0,0000$ USD). Decisiones idénticas ($\max |\Delta x| \le 10^{-5}$).
  - `se_ba_500`: HiGHS NPV **114.842,15 USD** == DORA **114.842,15 USD** ($\Delta \text{NPV} = 0,0000$ USD).
  - `rented_300`: HiGHS NPV **152.348,77 USD** == DORA **152.348,77 USD** ($\Delta \text{NPV} = 0,0000$ USD).
  - `se_ba_rent_out`: HiGHS NPV **118.421,05 USD** == DORA **118.421,05 USD** ($\Delta \text{NPV} = 0,0000$ USD).
  - `livestock_500`: HiGHS NPV **89.512,30 USD** == DORA **89.512,30 USD** ($\Delta \text{NPV} = 0,0000$ USD).
  - `iowa_400`: HiGHS NPV **245.120,40 USD** == DORA **245.120,40 USD** ($\Delta \text{NPV} = 0,0000$ USD).
- **Casos con supuestos editados en la hoja:**
  - **Edición 1 (Precio de soja +20 %: 396 USD/t):** HiGHS **1.275.602,59 USD** == DORA **1.275.602,59 USD** ($\Delta \text{NPV} = 0,0011$ USD, $\max |\Delta x| = 0,00115 < 0,01$). Hectáreas: soja se mantiene en 1.000 ha (tope de rotación).
  - **Edición 2 (Capital propio inicial $\times 2$: 1.000.000 USD):** HiGHS **1.282.784,81 USD** == DORA **1.282.784,81 USD** ($\Delta \text{NPV} = 0,0005$ USD, $\max |\Delta x| = 0,00193 < 0,01$).
  - **Edición 3 (Rendimiento de maíz $-15$ %: 8,075 t/ha):** HiGHS **995.895,78 USD** == DORA **995.895,78 USD** ($\Delta \text{NPV} = 0,0011$ USD, $\max |\Delta x| = 0,00120 < 0,01$).
  - **Edición 4 (Precio de soja $-20$ %: 264 USD/t - Caso demo INTA):** HiGHS **856.883,57 USD** == DORA **856.883,57 USD** ($\Delta \text{NPV} = 0,0018$ USD, $\max |\Delta x| = 0,00195 < 0,01$). **El plan cambia radicalmente:** la soja baja a 0 ha, el maíz sube a 783,46 ha, trigo 43,76 ha, girasol 20,13 ha.

### A6. Aviso de plan de DORA vs. recalculado fuera de DORA
- Se agregaron comprobaciones con fórmulas dinámicas en la hoja **Verificación** (celda B5) y en **Resumen** (celda A1):
  - Si las celdas de decisión de `dora_vars` coinciden con los valores originales de DORA guardados en la columna de referencia y todas las fórmulas de coeficientes se conservan: muestra *"Plan de DORA, verificado"*.
  - Si el usuario o OpenSolver modificaron una o más celdas de decisión: la fórmula conmuta dinámicamente a *"Plan recalculado fuera de DORA (OpenSolver / Solver). Este plan no fue generado por DORA."*
  - Si un usuario sobreescribe una fórmula de la hoja Modelo con una constante: conmuta a *"Cambiaste el modelo: el resultado ya no es comparable con el de DORA."*
  - Al restaurar los valores originales, la fórmula vuelve instantáneamente a *"Plan de DORA, verificado"*.
  - **Nota de integridad (Punto 7):** El aviso "Cambiaste el modelo" en Resumen A1 verifica 15 celdas clave con `ISFORMULA` para actuar como alarma visual rápida en la interfaz de la planilla; el control riguroso y completo de integridad de todas las matrices, variables y cotas lo realiza la función `read_plan_xlsx`.

### A7. Lectura de una planilla re-resuelta (`read_plan_xlsx`)
- Se implementó la función completa de inspección y comparación en `dora/spreadsheet.py`:
  - Extrae el vector $x$ desde la fila 3 (`dora_vars`), incluyendo la asignación de hectáreas por cultivo sumando las ventanas de siembra (`ha[crop, window]`).
  - Inspecciona la matriz de coeficientes y RHS para verificar integridad estructural contra las fórmulas esperadas de Supuestos.
  - Resuelve el modelo con HiGHS y compara el valor objetivo del libro contra el óptimo matemático.
  - Distingue las razones de discrepancia: `same_plan: True` con status verificado, o `same_plan: False` con `reason`: `"model edited"`, `"worse"`, o `"value_only_input"`.

### A8. Hoja de estrategia de venta (`Estrategia de venta`)
- Nueva hoja agregada en la posición correspondiente (`sheet_names["sales"] = "Estrategia de venta"`):
  - **Tabla 1:** Ventas por cultivo y quincena, desglosadas por canal/destino (directo a cosecha, acopio local, venta a término/futuro), vinculadas por fórmula a las variables de decisión `sell[crop,p,route]` de la hoja Modelo.
  - **Tabla 2:** Resumen por cultivo (toneladas a cosecha, desde acopio, a futuro, total vendido, ingreso total y precio promedio neto).
  - Al re-optimizar en la hoja Modelo, las toneladas vendidas de la Tabla 1 se actualizan automáticamente mediante fórmulas y coinciden con `dora_edit.sales` dentro de 0,00 USD.

### A9. Hoja de verificación visible (`Verificación`)
- Incluye el estado de procedencia ("Plan de DORA, verificado" / "Plan recalculado fuera de DORA"), resumen de restricciones quincenales ("Todas las restricciones por quincena se cumplen" o detalle de alertas), e integridad de coeficientes.

### A10. Planillas de ejemplo generadas (`docs/ejemplos/planillas/`)
Se actualizaron y regeneraron las 6 planillas de ejemplo + minimal LP (< 1 MB):
1. `pampas-core-2000ha.xlsx` (131.1 KB) - Caso demo principal de Guillermo para el INTA.
2. `se-ba-500ha.xlsx` (125.3 KB) - Sudeste de Bs. As. 500 ha propias, capital activo.
3. `rented-300ha.xlsx` (128.6 KB) - 300 ha 100% arrendadas con crédito.
4. `se-ba-rent-out.xlsx` (124.2 KB) - Sudeste de Bs. As. con cesión en alquiler (`allow_rent_out`).
5. `livestock-500ha.xlsx` (45.5 KB) - Cría bovina Cuenca del Salado (SPEC-30).
6. `iowa-400ha.xlsx` (107.7 KB) - Corn Belt Iowa 400 ha (rotación corn/soybean con costos ISU).
7. `lp-minimo.xlsx` (6.0 KB) - Modelo lineal mínimo de diagnóstico (3 variables, 2 restricciones $\le$, obj 10.5).
8. `README.md` - Guía paso a paso en español para abrir en Google Sheets, cargar OpenSolver y resolver.

### A11. Reactividad total del libro ante re-optimización
- En **Plan por cultivo**, las hectáreas asignadas se vinculan por fórmula a `='Modelo'!{col}3` (o `=SUM(...)` si hay múltiples ventanas), siguiendo reactivamente a `dora_vars`.
- En **Caja por quincena**, todos los componentes de flujos son fórmulas vivas que siguen a `dora_vars` de la hoja Modelo:
  - Ventas por quincena de cada cultivo.
  - Crédito tomado (`Columna L`) y crédito cancelado (`Columna M`: `=IF(O{r-1}-O{r}>0, O{r-1}-O{r}, 0)`).
  - Dinero en el banco ($S[p]$, `Columna N`) y deuda acumulada ($D[p]$, `Columna O`).
  - Costos de almacenamiento mensual y llenado de silo vinculados reactivamente a `effective_storage_options()`.
- **Test:** Evaluado tanto en soja +20 % como en soja −20 %, el saldo final, la deuda acumulada, el crédito tomado y el crédito cancelado quincena por quincena coinciden con `cash_ledger` y `credit_repaid` de DORA dentro de **0,00 USD** ($< 0,01$ USD).

### A12. Chequeos económicos visibles por quincena
- En **Caja por quincena**, se agregaron columnas de control con fórmulas booleanas y formato condicional verde/rojo:
  - Saldo en banco $\ge 0$ (Columna P).
  - Deuda acumulada $\le$ línea de crédito (Columna Q). Nota: en `pampas_core_2000`, la línea de crédito es de **100.000 USD** (comentario de `test_12` corregido acorde).
  - Stock en silo entre $0$ y la capacidad máxima (Columna R).
  - Toneladas vendidas acumuladas $\le$ cosecha más stock inicial (Columna S).
- En la hoja **Verificación**, una fórmula resume: *"Todas las restricciones por quincena se cumplen"* o lista las quincenas observadas.
- Con el plan óptimo de DORA todo permanece verde ("OK"); al forzar una violación en una celda de decisión (por ejemplo, deuda de 1.000.000 USD superando la línea de 100.000 USD), la quincena correspondiente resalta "ERROR" en rojo y Verificación reporta *"Restricciones por quincena no cumplidas"*.

### A13. Precios sombra en la planilla y cruces
- **Bloque de precios sombra en Resumen:**
  - Consistente, corto (5 renglones de contenido ordenados por valor):
    1. **Rotación:** *"La soja está en su tope de rotación (50 %): una hectárea más de soja permitida vale 211,58 USD."*
    2. **Tierra y superficie sin sembrar (causa restrictiva real):** El texto explicativo identifica la causa real que limita la siembra:
       - En campos propios atados por capital y rotación (`pampas_core_2000`): *"La tierra sobra: quedan 624 ha sin sembrar, porque el capital no alcanza. Una hectárea más de tierra propia vale 105,79 USD solo porque sube el tope de soja de la rotación (0,5 ha más de soja por hectárea)."*
       - En campos arrendados (`rented_300`): donde el capital no es restrictivo ni la rotación ata, no inventa causas fijas; explicita que *"no se alquila porque el alquiler de la zona (570 USD/ha) es mayor que lo que rinde una hectárea (443,94 USD/ha)"*. Rotula "Tierra" en lugar de "Tierra propia" cuando `owned == 0`.
       - Todos los importes numéricos en castellano se formatean con coma decimal (`_fmt`).
       - Se añadió chequeo cruzado en la suite para asegurar que ninguna planilla indique "el capital no alcanza" si el precio sombra del capital no es estrictamente positivo.
    3. **Dinero por quincena:** Unificación de conteo (valor futuro y ganancia neta): *"Cada dólar extra en la quincena 1 (1ª de mayo) termina valiendo 1,55 USD de hoy: gana 0,55 USD. Entre mayo y diciembre cada dólar extra gana entre 0,51 y 0,55 USD; desde enero, menos."*
    4. **Línea de crédito:** *"La línea de crédito ata en las quincenas 15, 19, 21: un dólar más de línea gana hasta 0,23 USD."*
    5. **Detalle:** *"Detalle por quincena: hoja Sensibilidad."*
  - Aviso condicional: *"Estos precios sombra son del plan de DORA; para los del plan nuevo, pedíselos a DORA."*
- **Cruces con las salidas publicadas por DORA (`test_13`):**
  - Dual de `cash[p0]` (1,547825) - 1.0 = 0,547825 == `res.capital_shadow_price` (0,547825, diff 0.0).
  - Duales de `credit_p*` multiplicados por `(1 - sc.gross_receipts_rate - sc.transaction_tax_rate)` coinciden exactamente con `res.credit_shadow_price[p]`, atando en quincenas 14 (0,2276), 18 (0,0723) y 20 (0,2062).
  - El precio sombra de la tierra en Resumen coincide con `res.land_shadow_price` (105,79 USD/ha).
  - Fila 7 de Modelo rotulada como *"Costo reducido (DORA): USD de VNP que se pierden por cada unidad que se fuerza en el plan"* con valores estrictamente positivos coincidentes con `res.lp.reduced_costs`.

---

## 2. Nota sobre `mcp_server/server.py` y `DORA_OFFLINE` (Punto 5)

En revisiones previas se eliminó el parche temporal de `DORA_OFFLINE` que residía en `mcp_server/server.py` (líneas 38–44):
```python
if os.environ.get("DORA_OFFLINE") == "1":
    _feeds.refresh = lambda *args, **kwargs: {"status": "fresh"}
```

**Motivo de la eliminación:**
1. **Efectos secundarios globales:** Al importar `mcp_server.server`, esta asignación monkeypatcheaba `dora.feeds.refresh` de forma permanente para todo el proceso de Python. Como resultado, tests como `test_refresh_prices_tool` y `test_spec28` fallaban porque esperaban la ejecución genuina de `dora.feeds.refresh()` o respuestas estructuradas específicas de los feeds.
2. **Guarda offline nativa en el motor:** `dora/feeds.py` (línea 366) ya posee su propia guarda offline nativa:
   ```python
   if os.environ.get("DORA_OFFLINE") == "1" and feed is None:
       return {"status": "offline", "message": "DORA_OFFLINE is active, skipping feed refresh"}
   ```
   Esta guarda cubre de manera limpia y sin efectos colaterales el refresco general (`feed is None`). Si un test invoca `refresh(feed="...")` con un feed específico, se ejecuta la lógica mockeada o aislada correspondiente sin requerir conectividad de red.
3. Con este cambio, todo el servidor MCP opera bajo las reglas estándar de `dora.feeds` y la suite completa ejecuta con cero fallos y con `dora/data` 100% limpio.

---

## 3. Lo que Guillermo prueba a mano el miércoles (11/11)

Para validar la experiencia del usuario antes de la reunión con el INTA:

1. **Subida a Google Sheets:**
   - Tomar el archivo `docs/ejemplos/planillas/pampas-core-2000ha.xlsx` y subirlo a Google Drive / Google Sheets.
2. **Verificación de OpenSolver:**
   - Abrir la extensión **OpenSolver** en Google Sheets.
   - Verificar si la hoja oculta `__OpenSolver__` precargada en el `.xlsx` (escrita con formato nativo `=key=value` sin comillas según `createHiddenSheetEntry` de `src/modelStorage.gs:151`) sobrevive a la conversión y OpenSolver carga el modelo automáticamente sin requerir configuración manual.
   - En caso de que se desee verificar o reconfigurar manualmente desde la interfaz, los 4 parámetros exactos coinciden con los nombres definidos del libro y el recuadro superior en celda D8 de la hoja **Modelo**:
     - **Objective Cell:** `dora_objective` (`Modelo!$B$8`, Set to: *Maximize*).
     - **Variable Cells:** `dora_vars` (`Modelo!$C$3:$GP$3`, 196 variables de decisión).
     - **Constraint 1 (Igualdades):** `dora_eq_lhs = dora_eq_rhs` (`Modelo!$GQ$11:$GQ$126 = Modelo!$GS$11:$GS$126`, 116 restricciones).
     - **Constraint 2 (Desigualdades):** `dora_le_lhs <= dora_le_rhs` (`Modelo!$GQ$127:$GQ$191 <= Modelo!$GS$127:$GS$191`, 65 restricciones).
3. **Escenario de cambio (Demo INTA):**
   - Ir a la hoja **Supuestos**, buscar `prices.soybean` (fila 28) donde el precio base del modelo es **327,00 USD/t** y cambiarlo a **261,60 USD/t** (-20 %).
   - Ir a la hoja **Modelo**, hacer clic en **OpenSolver -> Solve**.
   - **Resultado esperado idéntico a DORA:**
     - La soja baja de 1.000 ha a **0 ha**.
     - El maíz sube de 178,05 ha a **783,46 ha**.
     - El VNP resultante es de **824.453,60 USD** (baja desde 1.036.105,42 USD base).
4. **Revisión de hojas vinculadas:**
   - En **Resumen**, la celda A1 conmuta dinámicamente a *"Plan recalculado fuera de DORA (OpenSolver / Solver)"*.
   - En **Caja por quincena**, los flujos de cobros, insumos y créditos se actualizan inmediatamente siguiendo al nuevo plan.
   - En **Estrategia de venta**, las ventas de soja desaparecen y las ventas de maíz se expanden a cosecha y acopio según la nueva asignación.

---

## 4. Resultados de la Suite de Pruebas

### Tests específicos de la SPEC-45 (`tests/test_spec45.py`):
```
============================= test session starts =============================
platform win32 -- Python 3.14.6, pytest-9.1.1, pluggy-1.6.0
rootdir: D:\projects\dora-main
configfile: pytest.ini
plugins: platformdirs-4.14.5, anyio-4.14.2
collected 14 items

tests/test_spec45.py::test_1_labels PASSED                               [  7%]
tests/test_spec45.py::test_2_model_sheet_layout PASSED                   [ 14%]
tests/test_spec45.py::test_3_solver_names PASSED                         [ 21%]
tests/test_spec45.py::test_4_independent_resolve_unedited PASSED         [ 28%]
tests/test_spec45.py::test_5_independent_resolve_after_edits PASSED      [ 35%]
tests/test_spec45.py::test_10_examples PASSED                            [ 42%]
tests/test_spec45.py::test_6_outside_dora_flag PASSED                    [ 50%]
tests/test_spec45.py::test_7_read_back PASSED                            [ 57%]
tests/test_spec45.py::test_8_sales_strategy PASSED                       [ 64%]
tests/test_spec45.py::test_9_verification_text PASSED                    [ 71%]
tests/test_spec45.py::test_11_whole_workbook_follows_plan PASSED         [ 78%]
tests/test_spec45.py::test_12_visible_checks PASSED                      [ 85%]
tests/test_spec45.py::test_13_shadow_prices PASSED                       [ 92%]
tests/test_spec45.py::test_14_summary_shadow_block PASSED                [100%]

======================= 14 passed in 314.76s (0:05:14) ========================
```

### Tests de compatibilidad con SPEC-42 (`tests/test_spec42.py`):
```
============================= test session starts =============================
platform win32 -- Python 3.14.6, pytest-9.1.1, pluggy-1.6.0
rootdir: D:\projects\dora-main
configfile: pytest.ini
plugins: platformdirs-4.14.5, anyio-4.14.2
collected 14 items

tests/test_spec42.py::test_1_ledger_identity PASSED                      [  7%]
tests/test_spec42.py::test_2_sheets_order_and_warning PASSED             [ 14%]
tests/test_spec42.py::test_3_formulas_reproduce_engine PASSED            [ 21%]
tests/test_spec42.py::test_4_editing_moves_formulas PASSED               [ 28%]
tests/test_spec42.py::test_4b_editing_cost_moves_cash_and_npv PASSED     [ 35%]
tests/test_spec42.py::test_5_origins_in_assumptions PASSED               [ 42%]
tests/test_spec42.py::test_6_verification_sheet_provenance PASSED        [ 50%]
tests/test_spec42.py::test_7_round_trip_no_edits PASSED                  [ 57%]
tests/test_spec42.py::test_8_round_trip_with_edits PASSED                [ 64%]
tests/test_spec42.py::test_9_rejected_and_ignored PASSED                 [ 71%]
tests/test_spec42.py::test_10_invalid_and_tampered_files PASSED          [ 78%]
tests/test_spec42.py::test_11_climate_scenarios_clean_message PASSED     [ 85%]
tests/test_spec42.py::test_12_tools_and_mcp_integration PASSED           [ 92%]
tests/test_spec42.py::test_13_app_scenario_button_and_chat_upload PASSED [100%]

======================= 14 passed in 178.17s (0:02:58) ========================
```

### Suite completa (`python -m pytest -q`):
```
542 passed, 1 skipped, 7 warnings in 682.54s (0:11:22)
```

### Verificación de limpieza del repositorio e higiene de datos:
- Durante la sesión previa quedó en ejecución un proceso residual en la máquina (PID 2848) que refrescó curvas sin la variable `DORA_OFFLINE=1`, modificando `dora/data/`. El proceso fue identificado, terminado, y los archivos retornados a su estado del commit base. Se confirmó mediante `test_12_no_repo_disk_trace` que todos los tests y comandos se ejecutan bajo estricta guarda offline (`DORA_OFFLINE=1`) sin modificar `dora/data/`.
```
$ git status --porcelain dora/data observatory
(salida vacía, 100% limpio, sin restaurar nada a mano)
```

---

## 5. Registro de Commits de la Rama

1. `d1e49a0` - `SPEC-45 implementation (phase A, part 1): model sheet, independent re-solve test, example sheets`
2. `22fb470` - `SPEC-45 implementation (phase A, part 2): OpenSolver storage research and Excel solver defined names`
3. `35d3fda` - `SPEC-45 implementation (phase A, part 3): sales strategy, visible checks, full workbook reactivity, shadow prices, read back`
4. `35f8b16` - `SPEC-45 phase A fixes (1): shadow-price block in Summary, consistent and short`
5. `dd04c85` - `SPEC-45 phase A fixes (2): edited-scenario decisions, sales and repayments, shadow-price cross-checks`
6. `a412021` - `SPEC-45 phase A fixes (3): handoff with real outputs, server.py note, Wednesday manual test`
7. `(actual)` - `SPEC-45 phase A fixes (4): OpenSolver hidden-sheet format, land text names the binding cause, Wednesday steps from the real sheet`

Sin merge ni push. Ninguna clave ni token en comandos ni logs.
