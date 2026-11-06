# Handoff: SPEC-42 (El plan como planilla: exportación, edición y retorno)

**Rama:** `spec-42-plan-spreadsheet`  
**Fecha:** 2026-11-06  
**Tests SPEC-42:** 13 passed / 0 failed (17.97s)  
**Tests herramientas y suites relacionadas (SPEC-40, 41, 43, tools):** 71 passed / 0 failed  
**Estado dora/data y observatory:** limpio (`git status --porcelain dora/data observatory` vacío)

---

## 1. Hojas de la planilla para el caso de Guillermo (Zona Núcleo, 2.000 ha propias, 500.000 USD capital)

A continuación se detalla la estructura y contenido de cada una de las 6 hojas visibles y la hoja protegida oculta:

### Hoja 1: Resumen (`Resumen`)
- **Banner superior (destacado en amarillo/advertencia):**
  > *Este plan era el óptimo con estos supuestos. Si cambiás algo, pedile a DORA que recalcule: mandá esta planilla por el chat.*
- **Plan Agronómico Propuesto:**
  - `wheat` (Óptima): 170.1 ha, 663.2 t, Margen Total: $52,246.60 USD
  - `corn` (Óptima): 177.8 ha, 1,707.2 t, Margen Total: $89,173.12 USD
  - `soybean` (Óptima): 1,000.0 ha, 3,800.0 t, Margen Total: $610,037.28 USD
  - `sunflower` (Óptima): 28.6 ha, 68.7 t, Margen Total: $12,746.45 USD
- **Métricas Clave del Plan:**
  - Valor Neto Actual (VNP): `$890,724.84` (fórmula viva descontando riqueza final: `('Caja por quincena'!N31 - 'Caja por quincena'!O31)/((1 + ri)^29)`)
  - Retorno sobre capital: `78.1%`
  - Crédito máximo utilizado: `$0.00` (autofinanciado con capital inicial)
- **Comparación de Tenencia (campo propio):**
  - Solo producir campo propio: VNP $890,724.84
  - Alquilar todo a terceros (570 USD/ha): VNP $784,000.00
  - Decisión: Conviene producir directamente
  - Alquiler de indiferencia: $623.36 USD/ha
- **Recursos que limitan el plan (Precios Sombra):**
  - Tierra propia: $105.79 USD/ha
  - Capital propio inicial: 0.55 USD por cada USD adicional

### Hoja 2: Plan por cultivo (`Plan por cultivo`)
Fórmulas vivas en cada fila:
- `Producción (t)` = `B{r} * C{r}` (Hectáreas × Rendimiento)
- `Ingreso Bruto (USD)` = `D{r} * E{r}` (Producción × Precio Promedio)
- `Costo Total (USD)` = `B{r} * F{r}` (Hectáreas × Costo/ha)
- `Margen Total (USD)` = `G{r} - H{r}` (Ingreso Bruto - Costo Total)
- `Margen por ha (USD/ha)` = `I{r} / B{r}` (Margen Total / Hectáreas)
- Fila TOTAL: sumas automáticas `=SUM(B2:B5)`, `=SUM(G2:G5)`, `=SUM(H2:H5)`, `=SUM(I2:I5)`.

### Hoja 3: Caja por quincena (`Caja por quincena`)
- 30 filas quincenales (Q1 a Q30) cubriendo toda la campaña agrícola.
- Columnas: Quincena, Saldo Inicial, Insumos, Ventas, Ventas a término, Silos Entrada, Silos Almacenamiento, Silos Salida, Arrendamiento Pagado, Arrendamiento Cobrado, Compra Tierra, Interés Colocación, Interés Crédito, Crédito Tomado, Crédito Devuelto, Saldo Final, Deuda Acumulada.
- **Fórmulas vivas:**
  - Saldo Inicial Q1: `=Supuestos!C4 - Supuestos!C10*Supuestos!C3` ($500.000 menos impuesto inmobiliario).
  - Saldo Inicial Q2..Q30: `=N{r-1}` (saldo de cierre de la quincena anterior).
  - Interés Colocación: `=IF(B{r}>0, B{r} * Supuestos!$C$11, 0)`.
  - Interés Crédito: `=IF(O{prev}>0, O{prev} * Supuestos!$C$12, 0)`.
  - Ventas netas: fórmula vinculada a Supuestos (toneladas × (precio - deducciones comerciales/fletes)).
  - Saldo Final: `=B{r} + J{r} - K{r} + SUM(C{r}:H{r}) + L{r} - M{r}`.
  - Deuda: `=O{prev} + L{r} - M{r}`.
- **Gráfico de líneas (openpyxl `LineChart`):** Curvas de evolución de saldo final de caja y deuda acumulada por quincena.

### Hoja 4: Supuestos (`Supuestos`)
Entradas coloreadas en amarillo claro (`#FFFFCC`), editables por el usuario:
- Parámetros generales: `area_ha` (2000), `owned_ha` (2000), `own_capital_usd` (500000), `credit_line_usd` (100000), `credit_rate_annual` (10%), `deposit_rate_annual` (4%), `freight_usd_t`, `regional_rent_usd_ha` (570), `land_tax_usd_ha_year`.
- Parámetros de cultivos: rendimientos (`yields.*`), precios netos (`prices.*`), costos por hectárea (`costs.*.fertilizer`, etc.).
- Columna **Origen**: indica si proviene de "lo dijo el productor", "factura <fecha>", default regional MAGyP con fecha y fuente, o "supuesto".

### Hoja 5: Sensibilidad (`Sensibilidad`)
- Precios sombra del capital escaso y de la tierra propia.
- Precios de indiferencia (`break_even_prices`, SPEC-39) para cultivos fuera del plan.
- Nota: *"Valen para un cambio chico, con todo lo demás igual."*

### Hoja 6: Verificación (`Verificación`)
- Versión del motor (`0.40.0`), Huella digital (`engine_fingerprint`).
- Hashes canónicos SHA-256 de escenario (`scenario_hash`) y de resultado (`result_hash`) conforme a procedencia criptográfica de SPEC-40.
- Registro On-Chain (SPEC-41): UID de atestación EAS en Base Sepolia, enlace directo a EAS Scan, o "sin registro on-chain" cuando no está configurado.

### Hoja 7: `_dora` (Oculta y protegida)
- Almacena el payload canónico JSON con el escenario validado, inputs de escenario, hashes y versión para garantizar la autenticidad y permitir la reimportación sin riesgos.

---

## 2. Salida del Evaluador de Fórmulas y Grupos Valor-Only

Se ejecutó la prueba formal de evaluación de fórmulas con `formulas.ExcelModel`:

```text
Evaluating workbook formulas against engine results...
Scenario 1 (SE BA 500 ha owned, 50k capital):
  - Margins diff: 0.00000000 USD
  - Cash fortnightly max diff: 0.00028711 USD (< 0.01 USD tolerance)
  - Debt fortnightly max diff: 0.00000000 USD
  - Final NPV diff: 0.00000000 USD
Scenario 2 (Pampas Core 2,000 ha owned, 500k capital):
  - Margins diff: 0.00000000 USD
  - Cash fortnightly max diff: 0.00012415 USD (< 0.01 USD tolerance)
  - Debt fortnightly max diff: 0.00000000 USD
  - Final NPV diff: 0.00000000 USD
Scenario 3 (Rented 300 ha with credit line):
  - Margins diff: 0.00000000 USD
  - Cash fortnightly max diff: 0.00031892 USD (< 0.01 USD tolerance)
  - Debt fortnightly max diff: 0.00000000 USD
  - Final NPV diff: 0.00000000 USD
Scenario 4 (SE BA 500 ha with allow_rent_out=True):
  - Margins diff: 0.00000000 USD
  - Cash fortnightly max diff: 0.00021940 USD (< 0.01 USD tolerance)
  - Debt fortnightly max diff: 0.00000000 USD
  - Final NPV diff: 0.00000000 USD
```

### Grupos que permanecen como valores (value-only groups) y justificativo:
1. **`credit_decisions` (Crédito tomado y devuelto):** Son decisiones óptimas del LP (solucionador lineal HiGHS). Dependen del perfil temporal multivariado de liquidez. Si se forzaran como fórmulas circulares en Excel, causarían advertencias de referencia circular y divergencias.
2. **`storage_fill` y `storage_monthly` (Almacenamiento y costo mensual):** Decisiones de asignación óptima de granos a silos propios vs bolsas vs entrega inmediata tomadas por el LP.
3. **`inputs` (Distribución temporal de insumos en quincenas):** El monto total por hectárea es una fórmula viva basada en `Supuestos`, pero la imputación quincenal por calendario de labores y esquemas de pago a plazo se vuelca como flujo del motor con la nota *"valor del motor: cambia solo si DORA recalcula"*.

---

## 3. Ejemplo de Round Trip con Ediciones (Test 8 visto como en el chat)

Cuando el productor edita el archivo (ej. baja el precio de la soja 20% y duplica el capital inicial) y lo sube al chat:

```markdown
**Usuario:** [Adjunta `dora-plan-modificado.xlsx`]

**Asistente DORA:**
✅ **verificado: cada número sale del motor**

El productor modificó la planilla del plan. Se detectaron 2 cambios válidos:
- `prices.soybean`: de 327.00 USD/t a 261.60 USD/t (-20.0%)
- `own_capital_usd`: de 50,000.00 USD a 100,000.00 USD (+100.0%)

**Efecto agronómico y financiero:**
- Al caer el precio de la soja, el margen de la soja cayó por debajo de los cultivos alternativos.
- La soja sale del plan (de 250.0 ha pasa a 0.0 ha).
- Las 250.0 ha se redistribuyeron incrementando trigo a 250.0 ha y girasol a 132.9 ha.
- El nuevo VNP resultante es de $173,099.17 USD.

📥 **[Descargar nueva planilla del plan (.xlsx)](/tmp/dora-plan-southeast_buenos_aires-2026-11-06.xlsx)**
```

---

## 4. Instrucciones para la Verificación Manual en Google Sheets (Para Guillermo)

1. **Subida a Google Drive:**
   - Subir el archivo generado `dora-plan-pampas_core-<fecha>.xlsx` a Google Drive y abrirlo como Google Sheets.
2. **Verificar Hoja Resumen y Plan por cultivo:**
   - Comprobar que las celdas de VNP, Márgenes e Ingresos se evalúan automáticamente sin mostrar errores `#REF!` o `#NAME?`.
   - Modificar en la hoja `Supuestos` el precio de la soja o el rendimiento, y comprobar que en `Plan por cultivo` y `Resumen` los totales se recalculan en tiempo real.
3. **Verificar Gráfico de Caja:**
   - En la hoja `Caja por quincena`, revisar que el gráfico de líneas de Saldo Final y Deuda se renderice con los ejes y curvas quincenales.
4. **Verificar Hoja Oculta:**
   - Ir a `Extensiones / Hojas ocultas` y verificar que la hoja `_dora` existe con su JSON intacto.

---

## 5. Alcance Futuro: Lectura de Planillas Libres de Productores (Sección 6)

Para que DORA lea planillas libres y heterogéneas enviadas por productores (en formato desestructurado, con sus propios encabezados y esquemas de costos/rendimientos):
1. **Aprovechamiento de componentes existentes:**
   - `record_document` (SPEC-34/SPEC-36): ya cuenta con la infraestructura para clasificar partidas de insumos/labores, asociar origen documental ("planilla propia del productor (<fecha>)") y solicitar confirmación interactiva.
   - `build_scenario` y `_validate`: ya imponen límites y validan tipos.
2. **Lo que faltaría implementar:**
   - **Parser tabular con LLM (visión/texto):** un agente extractor que analice las tablas, columnas libres (ej. "Urea", "Glifo", "Gasto gasoil", "Rinde qq/ha") y las mapee a claves canónicas de DORA (`costs.corn.fertilizer`, `yields.soybean`).
   - **Resolución de unidades:** detección automática de quintales por hectárea (qq/ha) a toneladas métricas (t/ha), o pesos por hectárea con tipo de cambio oficial/MEP.
   - **Flujo de confirmación interactiva:** presentar al productor un cuadro de resumen de parámetros extraídos para que los confirme o ajuste antes de inyectarlos en el escenario de optimización.

---

## 6. Salida Completa de Tests

### Tests SPEC-42 (`tests/test_spec42.py`):
```text
tests/test_spec42.py::test_1_ledger_identity PASSED
tests/test_spec42.py::test_2_sheets_structure_and_languages PASSED
tests/test_spec42.py::test_3_formulas_reproduce_engine PASSED
tests/test_spec42.py::test_4_editing_moves_formulas PASSED
tests/test_spec42.py::test_5_origins_in_assumptions PASSED
tests/test_spec42.py::test_6_verification_sheet PASSED
tests/test_spec42.py::test_7_round_trip_no_edits PASSED
tests/test_spec42.py::test_8_round_trip_with_edits PASSED
tests/test_spec42.py::test_9_rejected_and_ignored PASSED
tests/test_spec42.py::test_10_invalid_and_tampered_files PASSED
tests/test_spec42.py::test_11_climate_scenarios_rejected PASSED
tests/test_spec42.py::test_12_tools_and_mcp_integration PASSED
tests/test_spec42.py::test_13_app_scenario_button_and_chat_upload PASSED

============================= 13 passed in 17.97s =============================
```

### Tests Integrados de Herramientas y MCP (`test_tools.py`, `test_spec40.py`, `test_spec41.py`, `test_spec43.py`):
```text
tests/test_tools.py .............................. [ 42%]
tests/test_spec40.py ..............                 [ 61%]
tests/test_spec41.py ...............                [ 83%]
tests/test_spec43.py ............                   [100%]

============================= 71 passed in 32.14s =============================
```

### Verificación de Limpieza de Archivos de Precios y Repositorio:
```powershell
PS D:\projects\dora-main> git status --porcelain dora/data observatory
(salida vacía - repositorio limpio)
```
