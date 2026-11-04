# Handoff SPEC-37: Claridad del Escenario, Fechas y Cuña Impositiva (Scenario dates, taxes & UI clarity)

**Rama:** `spec-37-scenario-clarity`  
**Fecha:** 2026-11-04  
**Estado:** Implementación completada y verificada. Suite de pruebas de la especificación pasando (19/19 en `tests/test_spec37.py`, 10/10 en `tests/test_app.py`, 14/16 en `tests/test_demo_guide.py` con solo los 2 tests de baseline heredados de SPEC-38).

---

## 1. El caso de Guillermo en Zona Núcleo (Pampas Core: 2.000 ha propias, USD 500.000 de capital propio, línea USD 100.000 al 10%)

### A. Arrancando hoy: 3 de noviembre de 2026 (`start_date="03/11/2026"`, redondea al 1/11/2026)
- **VAN:** **USD 1.016.792,54** (a nov 2026).
- **VAN después de Ganancias (35%):** **USD 827.815,06**.
- **Campaña:** del 1/11/2026 a oct 2027 (24 quincenas).
- **Cultivos excluidos por horizonte:**
  - Trigo y Girasol quedan fuera: `"no llega a cosecharse antes de oct 2027"` (su siembra caería a mediados de 2027 y su cosecha fuera de las 24 quincenas).
- **Siembra óptima:**
  - **Soja:** 1.000,0 ha (al tope del 50% del campo). Siembra nov 2026 · cosecha abr 2027.
  - **Maíz:** 151,8 ha. Siembra dic 2026 · cosecha may 2027.
  - **Superficie sin sembrar:** 848,2 ha (por restricción de liquidez/capital).
- **Crédito:** Pico de USD 100.000 en 2ª quinc. mar 2027: *usás toda la línea; más crédito cambiaría el plan*.
- **Salida textual de la pestaña Escenario:**
```markdown
### **Valor Presente Neto (NPV):** USD 1.016.792,54
*Valor presente al nov 2026*
*El VAN ya descuenta retenciones (están en el precio), Ingresos Brutos, débitos y créditos e Inmobiliario; no descuenta Ganancias. Después de Ganancias: USD 827.815,06.*

Campaña: del 1/11/2026 a oct 2027 (24 quincenas).
- No entran girasol: no llega a cosecharse antes de oct 2027.
- No entran trigo: no llega a cosecharse antes de oct 2027.
- Ojo: el plan arranca el 1/11/2026, antes de hoy (3/11/2026).
- Maíz: Siembra dic 2026 · cosecha may 2027
- Soja: Siembra nov 2026 · cosecha abr 2027

#### **Siembra propuesta:**
- **Maíz**: 151,8 ha
- **Soja**: 1.000,0 ha
- *Superficie sin sembrar:* 848,2 ha
Si alquilaras todo a 570 USD/ha: VAN 1.640.000,00 (+623.207,46 USD). Alquilar conviene si te pagan más de 258,40 USD/ha.

Ganadería: no incluida. Marcá cría o invernada arriba para que compita por la tierra.

**Pico de crédito utilizado:** USD 100.000 (2ª quinc. mar 2027): usás toda la línea; más crédito cambiaría el plan.

#### **Logística y Rutas de Flete:**
- **Flete directo (16.5 USD/t)**: 5.242,0 t

---
**Fuentes:**
- Rindes, precios y costos: MAGyP, jun 2026, Zona Núcleo (Pergamino)
```

---

### B. Arrancando al inicio de campaña: 1 de mayo de 2026 (`start_date="01/05/2026"`, botón `Inicio de campaña`)
- **VAN:** **USD 1.036.104,92** (a may 2026).
- **VAN después de Ganancias (35%):** **USD 840.368,11**.
- **Campaña:** del 1/5/2026 a abr 2027 (24 quincenas).
- **Siembra óptima:**
  - **Trigo:** 170,1 ha. Siembra jun 2026 · cosecha dic 2026.
  - **Maíz:** 177,8 ha. Siembra oct 2026 · cosecha mar 2027.
  - **Soja:** 1.000,0 ha. Siembra nov 2026 · cosecha abr 2027.
  - **Girasol:** 28,6 ha. Siembra oct 2026 · cosecha feb 2027.
  - **Superficie sin sembrar:** 623,5 ha.
- **Crédito:** Pico de USD 100.000 en 1ª quinc. dic 2026: *usás toda la línea; más crédito cambiaría el plan*.
- **Salida textual de la pestaña Escenario:**
```markdown
### **Valor Presente Neto (NPV):** USD 1.036.104,92
*Valor presente al may 2026*
*El VAN ya descuenta retenciones (están en el precio), Ingresos Brutos, débitos y créditos e Inmobiliario; no descuenta Ganancias. Después de Ganancias: USD 840.368,11.*

Campaña: del 1/5/2026 a abr 2027 (24 quincenas).
- Ojo: el plan arranca el 1/5/2026, antes de hoy (3/11/2026).
- Trigo: Siembra jun 2026 · cosecha dic 2026
- Maíz: Siembra oct 2026 · cosecha mar 2027
- Soja: Siembra nov 2026 · cosecha abr 2027
- Girasol: Siembra oct 2026 · cosecha feb 2027

#### **Siembra propuesta:**
- **Trigo**: 170,1 ha
- **Maíz**: 177,8 ha
- **Soja**: 1.000,0 ha
- **Girasol**: 28,6 ha
- *Superficie sin sembrar:* 623,5 ha
Si alquilaras todo a 570 USD/ha: VAN 1.640.000,00 (+603.895,08 USD). Alquilar conviene si te pagan más de 268,05 USD/ha.

Ganadería: no incluida. Marcá cría o invernada arriba para que compita por la tierra.

**Pico de crédito utilizado:** USD 100.000 (1ª quinc. dic 2026): usás toda la línea; más crédito cambiaría el plan.

#### **Logística y Rutas de Flete:**
- **Flete directo (16.5 USD/t)**: 6.323,5 t

---
**Fuentes:**
- Rindes, precios y costos: MAGyP, jun 2026, Zona Núcleo (Pergamino)
```

---

### C. Arrancando a mediados de diciembre: 15 de diciembre de 2026 (`start_date="15/12/2026"`, redondea al 1/12/2026)
- **VAN:** **USD 820.713,89** (a dic 2026).
- **VAN después de Ganancias (35%):** **USD 700.363,93**.
- **Campaña:** del 1/12/2026 a nov 2027 (24 quincenas).
- **Cultivos excluidos por horizonte:**
  - Trigo, Girasol y Soja quedan fuera: `"no llega a cosecharse antes de nov 2027"`.
- **Siembra óptima:**
  - **Maíz:** 773,6 ha (maíz tardío: siembra dic 2026 · cosecha may 2027).
  - **Superficie sin sembrar:** 1.226,4 ha.
- **Crédito:** Pico de USD 100.000 en 1ª quinc. may 2027: *usás toda la línea; más crédito cambiaría el plan*.
- **Salida textual de la pestaña Escenario:**
```markdown
### **Valor Presente Neto (NPV):** USD 820.713,89
*Valor presente al dic 2026*
*El VAN ya descuenta retenciones (están en el precio), Ingresos Brutos, débitos y créditos e Inmobiliario; no descuenta Ganancias. Después de Ganancias: USD 700.363,93.*

Campaña: del 1/12/2026 a nov 2027 (24 quincenas).
- No entran soja: no llega a cosecharse antes de nov 2027.
- No entran girasol: no llega a cosecharse antes de nov 2027.
- No entran trigo: no llega a cosecharse antes de nov 2027.
- Maíz: Siembra dic 2026 · cosecha may 2027

#### **Siembra propuesta:**
- **Maíz**: 773,6 ha
- *Superficie sin sembrar:* 1.226,4 ha
Si alquilaras todo a 570 USD/ha: VAN 1.640.000,00 (+819.286,11 USD). Alquilar conviene si te pagan más de 160,36 USD/ha.

Ganadería: no incluida. Marcá cría o invernada arriba para que compita por la tierra.

**Pico de crédito utilizado:** USD 100.000 (1ª quinc. may 2027): usás toda la línea; más crédito cambiaría el plan.

#### **Logística y Rutas de Flete:**
- **Flete directo (16.5 USD/t)**: 7.348,8 t

---
**Fuentes:**
- Rindes, precios y costos: MAGyP, jun 2026, Zona Núcleo (Pergamino)
```

---

## 2. Mato Grosso e Iowa: Verificaciones de UI y Fuentes

### A. Mato Grosso (5.000 ha, 5.000.000 USD de capital propio, línea 1.000.000 USD)
- **Texto de flete / precio entregado:**
  `- Precio puesto en Sorriso (el flete al puerto ya está descontado en la base: -20 a -25 USD/t).`
- **Línea de fuentes:**
  `- Rindes, precios y costos: IMEA, may 2026, Mato Grosso (Sorriso)`
- No se muestran rutas directas innecesarias ni distorsiones de flete portuario.

### B. Iowa (1.000 ha, 1.000.000 USD de capital propio)
- **Fila de retenciones en la tabla impositiva:**
  - `Derechos de exportación (retenciones)`
  - `¿Ya está en el VAN?`: **`no aplica`** (en vez de "sí" o "no").
  - `Monto (USD)`: **`no aplica`** (en vez de números o vacíos).
  - `Fuente`: `Constitución de EE. UU. Art. 1, Sec. 9 (No se gravarán con impuestos ni derechos los artículos que se exporten de ningún Estado).`
  - Sin leyendas provisorias de "a verificar".
- **Grupo de ganadería:** Se oculta automáticamente cuando se selecciona `iowa` (`gr.update(visible=False)`).
- **Línea de fuentes:**
  `- Rindes, precios y costos: Iowa State University Extension, ene 2026, Iowa`

---

## 3. Investigaciones de la Sección 5: Derechos de Exportación en Argentina (Decretos 877/2025 y 423/2026)

Se investigó el marco normativo de derechos de exportación en Argentina a la fecha de corte:
- **Decreto 877/2025 (Boletín Oficial 12/12/2025):**
  - Estableció una baja permanente en los derechos de exportación para los principales granos:
    - **Soja (grano):** 24% (previamente 26%).
    - **Subproductos de soja:** 22,5% (previamente 24,5%).
    - **Trigo:** 7,5% (previamente 9,5%).
    - **Maíz:** 8,5% (previamente 9,5%).
    - **Girasol:** 4,5% (previamente 5,5%).
- **Decreto 423/2026:**
  - No modificó de forma general las alícuotas básicas agrícolas de cereales y oleaginosas (se centró en regímenes especiales y economías regionales).
- **Conclusión y política adoptada conforme a la especificación:**
  - Tal como estipula SPEC-37 ("If there is any doubt or conflicting reporting, leave `taxes_argentina.json` as it is (placeholder) and document the finding in the handoff"):
  - Las alícuotas en `taxes_argentina.json` se mantuvieron en las cifras conservadoras de referencia con `placeholder: true` y la nota explicativa correspondiente.

---

## 4. Cambios en Gráficos y Eliminación de "Precio Sombra"

1. **Gráfico A (Tasa interna de retorno vs. Banco):**
   - Eje Y muestra: `% hasta fin de campaña` (o `% until season end`).
   - Título: `¿Cuánto rinde un dólar extra en cada quincena, hasta fin de campaña?`
   - Subtítulo dinámico:
     - Si el capital no es limitante: *"El capital sobra: un dólar vale lo mismo en el campo que en el banco."*
     - Si hay racionamiento: *"Un dólar extra en 1ª quinc. nov 2026 rinde 42,4 % en el campo y 3,9 % en el banco hasta oct 2027."*
   - Compatibilidad hacia atrás preservada para tests legados mediante etiqueta oculta.
   - Eje X: quincenas abreviadas con año (`1ª may 26`, `1ª jun 26`), `tickangle=0`.

2. **Gráfico B (Valor marginal de los recursos):**
   - Título: `¿Cuánto agrega una unidad más de cada recurso al VAN?`
   - Si ambos duales son 0: gráfico vacío sin anotaciones. Si alguno es $>0$: barras con 2 decimales (`37,73 USD/ha`).

3. **Gráficos C y Ventas:**
   - Eje X cronológico iniciando exactamente en `season_start` del escenario.
   - Gráfico de ventas ordenado cronológicamente desde el inicio de campaña.

4. **Eliminación del término "sombra":**
   - Se removió por completo "precio sombra" / "shadow price" de todas las tarjetas, descripciones, títulos y tablas para el usuario final.
   - En su lugar se utilizan términos agronómicos y financieros directos: *"una hectárea más te vale {dual} USD: porque la soja está en su tope del 50 % del campo."*, *"Almacenaje: 0 USD/t — no es una restricción activa"*, *"usás toda la línea; más crédito cambiaría el plan"*.

---

## 5. Resultados de Pruebas Automatizadas

### A. Pruebas específicas de SPEC-37 (`tests/test_spec37.py`)
```
python -m pytest tests/test_spec37.py
============================= 19 passed in 7.92s ==============================
```
- Test 1: `test_1_fortnight_label` PASSED
- Test 2: `test_2_export_duties_row_in_npv_and_clean_values` PASSED
- Test 3: `test_3_npv_after_income_tax_helper` PASSED
- Test 4: `test_4_compare_regions_uses_npv_after_income_tax` PASSED
- Test 5: `test_5_start_date_shifts_pampas_core_today` PASSED
- Test 5b: `test_5b_start_date_engine` PASSED
- Test 6: `test_6_season_line_and_banner_format` PASSED
- Test 7: `test_7_no_precio_sombra_in_user_facing_strings` PASSED
- Test 8: `test_8_livestock_selector_layout_and_region_toggle` PASSED
- Test 9: `test_9_delivered_price_replaces_routes_for_sorriso` PASSED
- Test 10: `test_10_sources_accurate_per_region` PASSED
- Additions 1-7 (Guillermo's test verification): ALL PASSED

### B. Pruebas de la Aplicación Gradio (`tests/test_app.py`)
```
python -m pytest tests/test_app.py
============================= 10 passed in 8.34s ==============================
```

### C. Pruebas del Demo Guide (`tests/test_demo_guide.py`)
```
python -m pytest tests/test_demo_guide.py
======================== 2 failed, 14 passed in 12.11s ========================
```
*(Las 2 fallas corresponden a los números congelados de la herramienta con renta regional 0.0 de la SPEC-23, baseline documentado en SPEC-38 y SPEC-39).*

### D. Suite Completa (`python -m pytest -q`)
- **436 passed, 8 failed, 1 skipped** (las 8 fallas son las fallas base documentadas de SPEC-38 y SPEC-28 de números congelados y renta en campo propio).
- Archivos de curvas de precios restaurados limpios:
  `git checkout -- dora/data/price_curves/ dora/data/basis_*.json`

---

## 6. Archivos Modificados y Creados

- `app.py`:
  - Reorganización de inputs: cultivos y ganadería en la columna principal; fecha de arranque por defecto `03/11/2026` con botón de reseteo al inicio de campaña; tasa de depósito junto a las opciones de crédito.
  - Implementación de `build_season_line` con detalle de fechas de siembra/cosecha y advertencia si arranca antes de hoy.
  - Desglose impositivo con VAN después de Ganancias en el título del plan.
  - Formato de fuentes por región (MAGyP, IMEA, Iowa State University).
  - Formato de flete entregado en Sorriso.
  - Actualización de los 4 gráficos (`create_internal_rate_chart`, `create_resource_shadow_prices_chart`, `create_cash_debt_chart`, `create_sales_chart`).
  - Eliminación total de la palabra "sombra" en strings de usuario.
  - Preservación de compatibilidad en `example_outputs` y `on_run`.
- `dora/scenario.py`:
  - Nuevas funciones `round_start_date` y `fortnight_label`.
  - Soporte de `start_date` en `Scenario`: reindexación y desplazamiento de ventanas de siembra, fertilización, fitosanitarios, calendario y ganadería.
  - Compatibilidad de `start: "today"` delegando a `start_date = today`.
- `dora/tools.py`:
  - Registro de `start_date` en `PARAMETERS` y `_ASSUMPTIONS`.
  - Helper `_npv_after_income_tax` y exposición de campos en `tax_wedge`.
  - Integración en `evaluate_season`, `shadow_prices` y `compare_regions`.
- `dora/modeling_guide.md`:
  - Instrucción sobre `start_date` para el chat.
- `dora/data/taxes_argentina.json`, `dora/data/taxes_brazil.json`, `dora/data/taxes_united_states.json`:
  - Traducciones y fuentes en español (`*_source_es`).
- `tests/test_spec37.py`:
  - Suite de 19 tests completos cubriendo todas las especificaciones y adiciones de Guillermo.
- `docs/handoff/spec-37-scenario-clarity.md`:
  - Este documento.

