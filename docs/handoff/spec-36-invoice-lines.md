# Handoff Report: SPEC-36 Invoice Lines to Crop and Cost Item, Re-planned Before & After

**Branch:** `spec-36-invoice-lines`  
**Date:** 2026-11-04  
**Status:** Completed and verified (15 unit tests passed, full suite clean: 406 passed, 1 skipped, E3 live evaluation completed with Claude's 3/11 review)  
**Commit status:** Ready to commit on `spec-36-invoice-lines`.

---

## 1. Summary of Changes & Diff per File

```
 app.py                   | 131 +++++++++++++++++--
 dora/modeling_guide.md   |   5 +-
 dora/schemas.py          |  14 ++-
 dora/tools.py            | 318 ++++++++++++++++++++++++++++++++++++-----------
 eval/e3/real_cases.json  | 121 +++++++++++++++---
 eval/run_e3.py           | 168 +++++++++++++++++++++++--
 tests/test_multimodal.py |   5 +-
 tests/test_spec36.py     | 358 ++++++++++++++++++++++++++++++++++++++++++++++++++++++
 8 files changed, 1007 insertions(+), 113 deletions(-)
```

### Detailed breakdown:
1. **`dora/schemas.py` (`record_document`):**
   - Added `cost_item` enum to item properties: `["seed", "fertilizer", "crop_protection", "field_operations", "rent", "tax", "other"]`.
   - Added `covers_whole_item` boolean property to denote whether the farmer confirmed the invoice represents the whole cost item for that crop (or all crop protection: herbicides, insecticides and fungicides).
   - Updated `concept` description to enforce: *"The line's text as written on the invoice. One item per invoice line: never merge or drop lines."*
   - Added top-level property `"lang": _LANG`.

2. **`dora/tools.py` (`record_document` and helpers):**
   - Relocated `CROP_TRANSLATION_TO_ES` to module level and re-imported in `app.py`.
   - Refactored `_plan_view(res, sc, lang)` from `assess_field_image` into a shared module-level helper (`npv_usd`, `profit_usd`, `hectares`, `max_credit_usd`, `debt_left_at_end_usd`, `capital_stretches`).
   - Extended `_normalize_concept` to classify active ingredients (glyphosate, atrazine, S-metolachlor, 2,4-D, dicamba, etc.) and fertilizers (ammonia, UAN, NPK, etc.), enforcing word boundaries (`\bmap\b|\bdap\b`) so "Mapa de rindes" is not misidentified.
   - Handled line precedence: `cost_item` explicit from model $\to$ `_normalize_concept`.
   - Lines classified as `"tax"` (VAT/IVA, percepciones) are assigned `cost_item="tax"`, `excluded="tax"`, and contribute $0 to operating costs.
   - If crop is unspecified: defaults to scenario's crop if singular; otherwise sets `crop=None` and adds `"missing: crop"` to `missing` (removing the legacy `else: crop_name = "wheat"` fallback).
   - Groups non-excluded lines by `(crop, cost_item)`, summing USD/ha into `group_usd_ha`.
   - Calculates **signed** `deviation_pct` ($100 \times \frac{\text{proposed} - \text{default}}{\text{default}}$) against regional default or earlier document overrides.
   - Detects partial protection: `partial = (cost_item == "crop_protection" and not any(line.get("covers_whole_item")))`.
   - **Claude's 3/11 Review Rule:** When every line of a group has `covers_whole_item: true`, the farmer's confirmation wins over the 50 % rule: `apply = True`, with `reason = "confirmed by the farmer"`, preserving `deviation_pct` for UI reporting.
   - Formulates localized `to_confirm` prompts for unconfirmed partial purchases, >50% deviations, or missing crops.
   - Integrated immediate re-planning: if valid scenario and applied groups exist, executes LP solver for `sc_before` and `sc_after`, returning `plan_before`, `plan_after`, `npv_change_usd`, `hectares_change`, and `scenario_after`. Traps `ScenarioError` safely into `plan_after_error`.

3. **`dora/modeling_guide.md` (Section 2):**
   - Updated Rule 1 (pass every line as written, with `crop` and `cost_item`, never merge or drop).
   - Added Rule 5 (quote tool before and after, quoting `proposals`, `plan_before`, `plan_after`, and `npv_change_usd` without redundant `evaluate_season` calls).
   - Added Rule 6 (ask `to_confirm` questions together; re-invoke `record_document` with `covers_whole_item: true` upon user confirmation).
   - Added Rule 7 (carry forward `scenario_after.costs_override` in subsequent turns).

4. **`app.py` (Reconciliation presentation):**
   - Iterates `reversed(agent_instance.tool_results)` to take the last `record_document` call result.
   - Replaced monolithic table with three structured blocks in the user's language:
     1. **Renglones / Lines:** Concept, crop, cost item, USD/ha (or exclusion explanation).
     2. **Comparación con la zona / Compared with the zone:** Invoice USD/ha, zone USD/ha, signed difference %, and usage status ("sí" / `sí, confirmado por vos ({deviation_pct:+.0f} % contra la zona)` / "no: <motivo>").
     3. **Antes y después / Before and after:** Side-by-side comparison of NPV, hectares per crop, maximum credit line, and `Diferencia de VAN: {npv_change_usd:+,.0f} USD`.
   - Preserves BCRA exchange rate note for ARS invoices and fallback message when crop/coverage is missing.

5. **`tests/test_multimodal.py`:**
   - Explicitly specified `"crop": "wheat"` in `test_record_document_hectares_and_deviation` and `test_record_document_ars_conversion`, adapting to the elimination of the silent wheat assumption.

6. **`eval/e3/real_cases.json` & `eval/run_e3.py`:**
   - Added `expected_groups` to all real invoice cases and `confirm_text` for cases with crop protection.
   - Enhanced `run_agent` in `eval/run_e3.py` with multi-turn support (`confirm`).
   - Implemented `eval_groups_and_npv` evaluating `groups_ok`, `lines_all_passed`, `npv_after`, and `npv_after_ok`.
   - Implemented turn 2 evaluation (`after_confirm`) comparing post-confirmation plan metrics against engine ground truth.

---

## 2. Test Suite Execution

### A. SPEC-36 Suite (`tests/test_spec36.py`):
All 15 unit tests pass cleanly offline:

```
tests/test_spec36.py::test_1_two_lines_one_item PASSED                   [  6%]
tests/test_spec36.py::test_2_two_items_one_invoice PASSED                [ 13%]
tests/test_spec36.py::test_3_active_ingredients_without_cost_item PASSED [ 20%]
tests/test_spec36.py::test_4_cost_item_from_model_wins PASSED            [ 26%]
tests/test_spec36.py::test_5_vat_line PASSED                             [ 33%]
tests/test_spec36.py::test_6_no_crop_several_crops PASSED                [ 40%]
tests/test_spec36.py::test_7_partial_crop_protection PASSED              [ 46%]
tests/test_spec36.py::test_8_signed_deviation PASSED                     [ 53%]
tests/test_spec36.py::test_9_before_and_after PASSED                     [ 60%]
tests/test_spec36.py::test_10_earlier_override_kept PASSED               [ 66%]
tests/test_spec36.py::test_11_infeasible_after PASSED                    [ 73%]
tests/test_spec36.py::test_12_app_reconciliation_markdown PASSED         [ 80%]
tests/test_spec36.py::test_13_assess_field_image_unchanged PASSED        [ 86%]
tests/test_spec36.py::test_14_real_cases_math PASSED                     [ 93%]
tests/test_spec36.py::test_15_farmer_confirmation_wins_over_50pct_rule PASSED [100%]

============================= 15 passed in 4.96s ==============================
```

### B. Full Test Suite (`python -m pytest -q`):
```
406 passed, 1 skipped, 2 warnings in 317.34s (0:05:17)
```
*(The single skipped test is `test_6_warm_containers` which requires modal cloud credentials in environment).*

---

## 3. Pilot Run: Case r1

**Execution command:**
```bash
python eval/run_e3.py --only invoices --cases eval/e3/real_cases.json --media-dir eval/e3/media/real_invoices --output eval/results/e3_pilot_r1.json
```

**Output from `e3_pilot_r1.json`:**
```
id: r1 | groups_ok: True | lines_all_passed: True | npv_after: 86709.57 | npv_after_ok: True
```

**Verbatim Farmer-facing Reply (Turn 1):**
```markdown
Con tu factura el plan queda en 86.710 USD de valor actual: 1.477 USD menos que antes.

**Plan después:** trigo 119,3 ha y soja 250,0 ha. Antes era trigo 121,7 ha y soja 250,0 ha, o sea 2,4 ha menos de trigo.

**Tu factura:**
- Urea 20 t a 12.300 USD + MAP 10 t a 10.200 USD van a fertilizante de trigo: 225 USD/ha para esas 100 ha, contra 214 USD/ha de la zona. Desvío de 5%, se usa.
- El IVA de la factura por 2.363 USD no se usa como costo: es impuesto.

Lo demás sigue con costos de la zona: semilla, fitosanitarios, labores de trigo y todo maíz, soja y girasol; eso es parte tuya y el resto regional. Guardo ese fertilizante de trigo para lo que sigamos calculando.

**Lo que te limita:**
- La plata: de la 2ª quincena de jul a la 2ª quincena de abr cada dólar te rinde 17,2% en esos 9 meses, con lo peor en la 1ª quincena de dic.
- Usás el crédito al tope de 100.000 USD y terminás sin deuda al cierre.

**Lo que entendí**
Tuyo: 500 ha en Balcarce, 50.000 USD propios y fertilizante de trigo para 100 ha.
De la zona: rindes, precios y resto de costos del sudeste bonaerense.
Supuesto: lo calculé como campo propio; si es alquilado, decime y lo recalculo.
```

---

## 4. Full Evaluation Table: E3 Invoices (`eval/results/e3_invoice_lines.json`)

| ID | Región / Cultivo / Insumos | Renglones Leídos | Líneas OK | Grupos Identificados | `groups_ok` | VAN Post (T1) | `npv_after_ok` (T1) | Con Confirmación (T2) | `groups_ok` (T2) | VAN Post (T2) | `npv_after_ok` (T2) |
|:---:|---|:---:|:---:|---|:---:|:---:|:---:|---|:---:|:---:|:---:|
| **r1** | Balcarce Trigo: Urea + MAP + IVA | 2 + IVA | Sí | `wheat.fertilizer = 225.0 USD/ha` (dev +5.0%) | **True** | 86.709,57 USD | **True** | *N/A (aplicó directo)* | - | - | - |
| **r2** | Pergamino Soja: Semilla + Glifosato (ARS) | 2 + 2 IVA | Sí | `soybean.seed = 74.01` (dev +19.8%, apply=T)<br>`soybean.crop_protection = 20.58` (dev -71.6%, partial) | **True** | 197.421,39 USD | **True** | **Aplica glifosato confirmado** | **True** | 210.629,79 USD | **True** |
| **r3** | Pergamino Maíz: Atrazina + Dual Gold | 2 + IVA | Sí | `corn.crop_protection = 28.99` (dev -68.2%, partial) | **True** | *None (frenado)* | False (*) | **Aplica herbicidas confirmados** | **True** | 190.399,61 USD | **True** |
| **r4** | Iowa Corn: Anhydrous Ammonia + Seed Corn | 2 insumos | Sí | `corn.fertilizer = 418.7` (dev 0.0%, apply=T)<br>`corn.seed = 281.0` (dev 0.0%, apply=T) | **True** | 295.124,70 USD | **True** | *N/A (ambos aplicaron)* | - | - | - |
| **r5** | Iowa Soybean: Herbicida postemergente | 1 insumo | Sí | `soybean.crop_protection = 185.16` (dev -0.1%, partial) | **True** | *None (frenado)* | False (*) | **Aplica herbicida confirmado** | **True** | 295.141,16 USD | **True** |

> **(*) Nota sobre T1 en r3 y r5:** En el turno 1, `npv_after` es `None` porque al tratarse de compras parciales no confirmadas aún ningún rubro se aplica al plan, preservando la línea base.

---

## 5. Verbatim Dialogues: r2, r3, and r5 (Before and After Confirmation)

### Caso r2 (Pergamino — Soja: Semilla DM 46E25 + Glifosato en ARS)

#### Turno 1 (Antes de confirmación)
- **Mensaje del productor:**
  ```
  Te mando la factura en pesos de la semilla de soja y el glifosato para 80 ha en Pergamino. Tengo 400 ha y 70.000 USD. ¿Cómo queda el plan?
  ```
- **Respuesta de DORA:**
  ```markdown
  Con tu semilla, el plan queda en 197.421 USD de valor actual, 3.694 USD menos que con el costo zonal (201.115 USD).

  Plan con tu factura:
  * soja 200,0 ha, maíz 93,2 ha, trigo 39,0 ha, girasol 8,0 ha
  * semilla de soja: 74,01 USD/ha tuya contra 61,8 USD/ha de la zona (+19,8%), se usa en el plan
  * glifosato: 20,58 USD/ha contra 72,4 USD/ha de la zona (-71,6%), no se usa todavía porque parece una compra parcial. El IVA no entra como costo.
  * por tu semilla más cara, el maíz cae 3,1 ha y el trigo 0,2 ha.

  Lo que te limita:
  * la plata: usás el crédito al tope de 100.000 USD, entre la 1ª quincena de oct y la 2ª de mar cada dólar te rinde 57,8% en esos 5,5 meses
  * la soja está al tope que deja la rotación

  ¿Esa factura de glifosato es todo tu gasto en agroquímicos del soja o solo una parte?

  Lo que entendí:
  Tuyo: 400 ha en Pergamino, 70.000 USD propios y factura para 80 ha de soja a tipo de cambio 1.549,72 del 03-11-2026.
  Zona: resto de costos, rindes y precios del Núcleo.
  Supuesto: lo calculé como campo propio; si es alquilado decime y lo recalculo.
  ```

#### Turno 2 (Después de confirmación)
- **Mensaje de confirmación del productor:**
  ```
  Sí, es todo lo que gasto en agroquímicos para ese cultivo.
  ```
- **Respuesta de DORA:**
  ```markdown
  Con tu costo confirmado, el plan queda en 210.630 USD de valor actual, 9.515 USD más que con el costo zonal de 201.115 USD.

  Plan con tu factura:
  * soja 200,0 ha, maíz 104,5 ha, trigo 24,2 ha, girasol 8,3 ha
  * semilla de soja a tu factura: 74,01 USD/ha contra 61,8 USD/ha de la zona (+19,8%)
  * glifosato a tu factura: 20,58 USD/ha contra 72,4 USD/ha de la zona (-71,6%), lo uso porque me confirmaste que es todo el gasto en agroquímicos del soja. El IVA no entra como costo.
  * por tu costo más barato en soja, el maíz sube 8,1 ha, el girasol 0,2 ha y el trigo baja 15,0 ha. Tipo de cambio usado 1.549,72 del 03-11-2026.

  Lo que te limita:
  * la plata: usás el crédito al tope de 100.000 USD
  * entre la 1ª quincena de oct y la 2ª de mar, cada dólar extra en el campo te rinde 57,8% en esos 5,5 meses
  * la soja queda al tope que deja la rotación

  Lo que entendí:
  Tuyo: 400 ha en Pergamino, 70.000 USD propios, semilla y glifosato del soja para 80 ha.
  Zona: resto de costos, rindes y precios del Núcleo. Lo calculé como campo propio.
  Si traés la factura del fertilizante del soja la sumo al mismo plan.
  ```

---

### Caso r3 (Pergamino — Maíz: Atrazina + Dual Gold)

#### Turno 1 (Antes de confirmación)
- **Mensaje del productor:**
  ```
  Te mando la factura de herbicidas de presiembra de maíz para 120 ha en Pergamino. Tengo 350 ha y 60.000 USD. ¿Cómo impacta en el margen?
  ```
- **Respuesta de DORA:**
  ```markdown
  Entendí que tenés 350 ha en Pergamino con 60.000 USD y me pasaste la factura de presiembra de maíz para 120 ha.

  La cargué así:
  - Atrazina + Dual Gold van al maíz como herbicidas: 13,00 + 15,99 = 28,99 USD/ha para esas 120 ha.
  - Contra el dato de la zona para todos los agroquímicos del maíz, 91,2 USD/ha, te da 68,2% por debajo.
  - Por eso todavía no lo apliqué al margen: figura como compra parcial y con desvío grande. El IVA de 730,55 USD no se cuenta como costo.

  ¿Esta factura de 28,99 USD/ha es todo lo que gastás en agroquímicos del maíz, o es solo la presiembra y te falta el resto?
  ```

#### Turno 2 (Después de confirmación)
- **Mensaje de confirmación del productor:**
  ```
  Sí, es todo lo que gasto en agroquímicos para ese cultivo.
  ```
- **Respuesta de DORA:**
  ```markdown
  Con tu costo confirmado el valor actual pasa a 190.400 USD: 10.098 USD más que con el dato de la zona.

  La factura quedó así:
  - Atrazina a maíz como herbicida: 13,00 USD/ha.
  - Dual Gold a maíz como herbicida: 15,99 USD/ha.
  - Total maíz herbicidas: 28,99 USD/ha contra 91,2 USD/ha de la zona. Se usó porque me confirmaste que es todo el gasto. El IVA no se cuenta como costo.
  - Plan antes: 180.301 USD de valor actual con trigo 35,3 ha, maíz 98,3 ha, soja 175,0 ha, girasol 7,6 ha.
  - Plan después: 190.400 USD de valor actual con trigo 35,8 ha, maíz 106,9 ha, soja 175,0 ha, girasol 7,8 ha. Sumás 8,6 ha de maíz, 0,5 ha de trigo y 0,2 ha de girasol.

  Lo que te limita:
  - La plata entre la 1ª quincena de oct y la 2ª quincena de mar: cada dólar extra te rinde 71,6% en esos 5,5 meses.
  - El pico está en la 1ª quincena de mar y usás el crédito al tope.

  Lo que entendí: tuyo el campo de 350 ha, 60.000 USD y los 28,99 USD/ha de agroquímicos del maíz; resto de costos rindes y precios de la zona; lo calculé como campo propio, si es alquilado decime y lo recalculo.
  ```

---

### Caso r5 (Iowa — Soybean: Herbicida postemergente)

#### Turno 1 (Antes de confirmación)
- **Farmer message:**
  ```
  Here is the invoice for soybean herbicide treatment covering 160 acres. I have 500 acres in Iowa and $150,000 capital. How does the plan change?
  ```
- **DORA Reply:**
  ```markdown
  It doesn't change the plan yet — your base plan is worth 295,127 USD in present value.

  Plan: sow 101.2 ha of corn and 101.2 ha of soybean, rent out 0.0 ha.
  Sell corn in November, soybean 149.9 t in November and 264.9 t in July next year.

  Your invoice:
  * 1 line to soybean herbicide: 11,998 USD over 64.8 ha = 185.16 USD/ha
  * Zone cost for soybean crop protection: 185.30 USD/ha, so -0.1% difference
  * Not applied yet because the tool marks it as partial: is this invoice all your crop protection for soybean, or only part of it?

  What limits you:
  * Cash is tight from late Jun to late Nov, you use up to 53,068 USD of credit.
  * Rotation caps you at about half corn / half soybean.
  * One more hectare is worth 700.52 USD to you; extra storage and extra credit are worth nothing.

  What I understood:
  Yours: 500 acres (202.3 ha) in Iowa with 150,000 USD capital, plus that soybean herbicide invoice.
  Regional data: yields, prices and costs are Iowa defaults, no cost from your invoice applied yet.
  Assumption: I calculated it as owned land with 100,000 USD credit line and 1,000 t storage — if rented, tell me and I recalculate.
  ```

#### Turno 2 (Después de confirmación)
- **Farmer confirmation:**
  ```
  Yes, that is all my crop protection for that crop.
  ```
- **DORA Reply:**
  ```markdown
  Applied — present value goes from 295,127 USD to 295,141 USD, +14 USD.

  Plan after: 101.2 ha of corn and 101.2 ha of soybean, no land rented out. Sales timing unchanged from the base run — corn in November, soybean split November and July next year.

  Your invoice:
  * Soybean post-emergence herbicide to soybean protection: 11,998 USD over 64.8 ha = 185.16 USD/ha
  * Zone cost: 185.30 USD/ha, -0.1% difference, so used directly
  * Only your soybean protection cost is yours now; corn seed, fertilizer, protection, field work and overhead, and soybean seed, fertilizer, field work and overhead are still zone defaults.

  What limits you:
  * Cash is tight from late Jun to late Nov — each extra dollar in that 5.0-month stretch earns 3.9%.
  * You use up to 53,053 USD of credit, with the peak in late Oct.
  * Rotation caps you at about half corn / half soybean, so hectares don't move.

  What I understood:
  Yours: 500 acres in Iowa with 150,000 USD capital, plus that invoice now confirmed as all soybean protection.
  Regional data: yields, prices and all other costs are Iowa defaults.
  Assumption: I calculated it as owned land — if rented, tell me and I recalculate with rent.
  ```

---

## 6. App Screenshot: Case r4 (`docs/screenshots/r4-invoice-lines.png`)

- **Archivo:** `docs/screenshots/r4-invoice-lines.png` ($1366 \times 1100$, 99.741 bytes).
- **Contenido capturado:**
  - Pestaña de chat con el mensaje del productor en Iowa y la miniatura del comprobante comercial de insumos `r4.png`.
  - La respuesta verificada de DORA (`verified: true`).
  - **Bloque 1 — Lines:**
    - `Bulk Nitrogen Fertilizer - Anhydrous ammonia (N equivalent)` $\to$ corn / fertilizer $\to$ `418.70 USD/ha`.
    - `Commercial Seed Corn (80,000 kernels/unit)` $\to$ corn / seed $\to$ `281.00 USD/ha`.
  - **Bloque 2 — Compared with the zone:**
    - `corn` / `fertilizer` $\to$ Invoice: `418.7 USD/ha` | Zone: `418.7 USD/ha` | Difference: `+0.0 %` | Used: `yes`.
    - `corn` / `seed` $\to$ Invoice: `281.0 USD/ha` | Zone: `281.0 USD/ha` | Difference: `+0.0 %` | Used: `yes`.
  - **Bloque 3 — Before and after:**
    - `NPV (USD)`: 295,125 USD (Before) vs. 295,125 USD (After).
    - `Hectares corn`: 101.2 ha vs. 101.2 ha.
    - `Hectares soybean`: 101.2 ha vs. 101.2 ha.
    - `Max credit (USD)`: 53,065 USD vs. 53,065 USD.
    - `NPV difference: +0 USD`.

---

## 7. Costos del Experimento

Cifras extraídas del resultado de ejecución del harness (`eval/results/e3_invoice_lines.json`):

| Concepto | Cantidad |
|---|:---:|
| Total requests de inferencia | 35 |
| Total tool calls ejecutadas | 24 |
| **Costo total de ejecución (LLM)** | **0,8728 USD** |

---

## 8. Verificación de Integridad de Precios

Se ejecutó la restauración requerida de los archivos de precios:
```bash
git checkout -- dora/data/price_curves/ dora/data/basis_*.json
```
`git status` confirma que los archivos `dora/data/price_curves/argentina_latest.json`, `dora/data/price_curves/cbot_latest.json` y `dora/data/basis_argentina.json` permanecen limpios e intactos.
