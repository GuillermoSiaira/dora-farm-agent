# Handoff Report: SPEC-31 Pre-submission Audit Fixes

**Branch:** `spec-31-audit-fixes`  
**Status:** Completed and verified (360 passed, 1 skipped)  
**Date:** 2026-11-02  
**Commit status:** Uncommitted (per spec instructions: "Do not commit and do not merge: write the handoff and Claude reviews").

---

## 1. Summary of Changes (by Item and File)

### Item 1: Scenario Tab: drawing a field in Pergamino or Mato Grosso breaks it
- **Files:** `app.py`, `dora/geo.py`
- **What was changed:**
  - `app.py`: Added `("Zona núcleo (Pergamino)", "pampas_core")` and `("Mato Grosso", "mato_grosso")` to `region_input` choices.
  - `app.py`: Extracted `on_apply_polygon` and `on_region_change` to module level. Both dynamically resolve crop choices from `REGIONS[reg]["crops"]` translated using `CROP_TRANSLATION_TO_ES` / `CROP_TRANSLATION_TO_EN` according to `lang_state`.
  - `app.py`: If `reg is None` or outside known regions, returns `gr.update()` without changing field values and emits warning message: `"⚠️ El campo queda fuera de las regiones que DORA conoce (Balcarce, Pergamino, Iowa, Mato Grosso)."` (or English equivalent).
  - `app.py`: Rewired `region_input.change` with `inputs=[region_input, lang_state]`.
  - `app.py`: Updated `on_lang_change` to accept `current_crops` and `current_region` as inputs so that changing language preserves the currently checked crops in that region instead of resetting to all 4 default crops.
  - `dora/geo.py`: Updated docstrings in lines 47 and 138 to document the 4 supported regions (Southeast Buenos Aires, Pampas Core, Iowa, Mato Grosso).
- **Test:** `tests/test_spec31.py::test_1_region_dropdown_and_polygon_apply`.

### Item 2: Chat: clear message when model API fails
- **Files:** `app.py`
- **What was changed:**
  - `app.py`: Added module-level date tracking `_daily_chat_date = datetime.date.today().isoformat()`. In `respond`, resets `_daily_chat_counter = 0` whenever the calendar date changes so the 200 daily quota resets per day.
  - `app.py`: Extracted `respond` to module level and wrapped `agent_instance.ask` in `try...except Exception:`. On API failure, decrements `_daily_chat_counter -= 1` and appends a friendly message to the chat history:
    - Spanish: `"⚠️ No pude hablar con el modelo ahora. Probá de nuevo en un minuto; la pestaña Escenario funciona sin él."`
    - English: `"⚠️ Could not reach the model right now. Try again in a minute; the Scenario tab works without it."`
  - `app.py`: Fixed Spanish unverified badge string at line 123 from `"⚠️ **not verified**"` to `"⚠️ **sin verificar**"`.
- **Test:** `tests/test_spec31.py::test_2_respond_api_failure_handling`.

### Item 3: Observatory: regenerate snapshot and drop local link
- **Files:** `app.py`, `observatory/latest.json`, `observatory/2026-11-02.json`, `docs/observatory-format.md`
- **What was changed:**
  - `app.py`: Defined `is_es = (lang == "es")` at the beginning of `get_observatory_ui_data()` so that missing snapshot fallback messages do not raise `UnboundLocalError`.
  - `app.py`: Removed `file:///` local filesystem links from the Observatory banner headers in both Spanish and English, displaying only the snapshot date: `"**Fecha de la foto:** `{date_str}`"` / `"**Snapshot date:** `{date_str}`"`.
  - `observatory/`: Generated new dated snapshot `observatory/2026-11-02.json` and updated `observatory/latest.json` with today's price curves and verified commentary via `run_observatory(save=True)`.
  - `docs/observatory-format.md`: Documented the `provisional` regional array field (`string[]`) in the specification table.
- **Tests:** `tests/test_spec31.py::test_6_observatory_header_no_file_protocol` and `tests/test_calibration.py::test_observatory_format_docs_completeness`.

### Item 4: Agent must not invent "no credit"
- **Files:** `dora/modeling_guide.md`, `dora/verifier.py`
- **What was changed:**
  - `dora/modeling_guide.md`: Added rule in Section 1 below the "50 lucas propias" entry:
    `| "Tengo 50.000 USD de capital." / "$50,000 capital" (nothing said about the bank) | own_capital_usd: 50000 only. Do not pass credit_line_usd: the model's credit line stays and is named as an assumption. Pass credit_line_usd: 0 only if the farmer says nobody lends ("sin crédito", "nadie me presta", "no credit"). |`
  - `dora/verifier.py`: Defined module-level regex dictionary:
    `ZERO_NEEDS_FARMER = {"credit_line_usd": r"sin\s+cr[eé]dito|nadie\s+me\s+presta|no\s+me\s+prest|no\s+(?:tengo|hay)\s+cr[eé]dito|no\s+credit|without\s+credit|no\s+(?:bank\s+)?loan|can'?t\s+borrow"}`
  - `dora/verifier.py`: In Rule 2 of `check_scenario`, flagged `credit_line_usd: 0` unless the user text matches `ZERO_NEEDS_FARMER`: `"the farmer did not say 0: leave it out (model default) or ask"`.
  - `dora/verifier.py`: Added `"build_scenario"` to `SEASON_SOLVING_TOOLS` so that `check_scenario` validates scenario parameters when the model calls `build_scenario`.
- **Test:** `tests/test_spec31.py::test_3_verifier_zero_needs_farmer`.

### Item 5: Stretch duration_months rounded to 0
- **Files:** `dora/engine.py`, `dora/modeling_guide.md`
- **What was changed:**
  - `dora/engine.py:120`: Changed `"duration_months": round((e - s) / 2, 1)`, ensuring a 1-fortnight stretch gives `0.5` months rather than `0`.
  - `dora/modeling_guide.md:120`: Added instruction: "If `duration_days` is under 30, say the days ('en esos 15 días' / 'in those 15 days'), not months."
- **Test:** `tests/test_spec31.py::test_4_capital_stretches_half_month`.

### Item 6: "Lo que entendí" inside English answers
- **Files:** `dora/verifier.py`, `dora/agent.py`
- **What was changed:**
  - `dora/verifier.py`: Added `wrong_language_label(text: str, user_text: str) -> list[str]` which detects English queries with Spanish label `"Lo que entend"` and returns `["The answer is in English: write 'What I understood', not 'Lo que entendí'."]`. Added handler to `correction_message`.
  - `dora/agent.py`: Imported `wrong_language_label` and called it in `_get_styles(ans, actual_text)`.
- **Test:** `tests/test_spec31.py::test_5_wrong_language_label`.

---

## 2. Test Suite Results

Offline test suite:
```
DORA_API_BASE=http://127.0.0.1:9/v1 DORA_API_KEY=test DORA_MODEL=test python -m pytest -q
360 passed, 1 skipped in 316.19s
```
Specific tests for SPEC-31 (`tests/test_spec31.py`):
```
python -m pytest tests/test_spec31.py -q
6 passed in 10.25s
```

All 6 acceptance tests passed without network access.

---

## 3. Live Check Results

### A. Live Evaluation: `python eval/run_eval.py --ids q22,q26 --runs 3`
Saved to `eval/results/live_check_spec31.json`.
- **Condition:** `with_verifier` (Condition C)
- **Model:** `muse-spark-1.3` (via Meta API)
- **Runs:** 3 runs × 2 questions = 6 evaluations
- **Results:**
  - **Answer Correctness:** 100.0% (6 of 6)
  - **Tool Accuracy:** 100.0% (6 of 6)
  - **Verified Rate:** 100.0% (6 of 6)
  - **Feasible plans:** 100.0%
  - **Mean gap:** 0.0%

#### Tool calls and verifier enforcement in live check:

**Run 0, q22:**
```json
{
  "tool": "build_scenario",
  "arguments": "{\"lang\":\"en\",\"scenario\":{\"area_ha\":500.0,\"input_delay_surcharge\":0.02,\"input_payment_delay_fortnights\":4,\"own_capital_usd\":50000.0,\"region\":\"iowa\"}}"
}
```
*(Agent did not pass `credit_line_usd: 0`; Iowa default credit was used. Expected NPV: 163,865.99 USD).*

**Run 1, q22 (Demonstration of Verifier enforcement):**
In Run 1, the model initially attempted:
```json
{
  "tool": "build_scenario",
  "arguments": "{\"lang\":\"en\",\"scenario\":{\"area_ha\":500,\"credit_line_usd\":0,\"input_delay_surcharge\":0.02,\"input_payment_delay_fortnights\":4,\"own_capital_usd\":50000,\"region\":\"iowa\"}}"
}
```
The Verifier intercepted and rejected it:
```json
{
  "parameter": "credit_line_usd",
  "value": 0,
  "reason": "the farmer did not say 0: leave it out (model default) or ask"
}
```
The agent corrected itself in the next round, omitting `credit_line_usd`:
```json
{
  "tool": "build_scenario",
  "arguments": "{\"lang\":\"en\",\"scenario\":{\"area_ha\":500,\"input_delay_surcharge\":0.02,\"input_payment_delay_fortnights\":4,\"own_capital_usd\":50000,\"region\":\"iowa\"}}"
}
```
The plan succeeded and answered with NPV 163,866 USD (100% correct).

**Run 2, q26:**
```json
{
  "tool": "build_scenario",
  "arguments": "{\"lang\":\"en\",\"scenario\":{\"area_ha\":500.0,\"constraints\":[{\"crop\":\"soybean\",\"month\":\"2027-05\",\"price_usd_t\":330.0,\"tonnes\":200.0,\"type\":\"forward_sale\"}],\"own_capital_usd\":50000.0,\"region\":\"iowa\"}}"
}
```
*(No `credit_line_usd: 0` passed; tool completed cleanly with NPV: 146,019.65 USD).*

---

### B. Interactive UI Simulation: Scenario Tab (Pergamino) & Regional Observatory Tab

Observed by executing the UI workflows directly:

#### 1. Scenario Tab (Delimiting polygon in Pergamino):
- **Coordinates passed:** `[[[-60.57, -33.89], [-60.55, -33.89], [-60.55, -33.87], [-60.57, -33.87], [-60.57, -33.89]]]`
- **Detected area:** `410.6 ha`
- **Detected region:** `pampas_core`
- **Region dropdown selection:** `"Zona núcleo (Pergamino)"`
- **Crop choices & selection:** `['trigo', 'maíz', 'soja', 'girasol']` (dynamically loaded from `REGIONS['pampas_core']['crops']` in Spanish)
- **Status message:** `✅ **Campo delimitado:** 410.6 ha en **Zona núcleo (Pergamino)** (-33.88, -60.56).`
- **Execution via `app.run_scenario`:**
  - Net Present Value (NPV): `USD 198.124,96`
  - Proposed sowing: Trigo: 40,7 ha, Maíz: 65,7 ha, Soja: 205,3 ha, Girasol: 6,6 ha, Unsown: 92,3 ha.
  - Peak credit used: USD 100.000 (1ª quincena de dic).
  - Land decision card: Tierra propia 410,6 ha, Tomada 0,0 ha, Dada en alquiler 0,0 ha, Comprada 0,0 ha, Retorno sobre el capital: 315,5% en la campaña.

#### 2. Regional Observatory Tab:
- **Banner Header:**
  ```markdown
  ### 🌐 Referencia Publicada del Observatorio
  **Fecha de la foto:** `2026-11-02`
  ```
  *(No local `file:///` URLs).*
- **Market Commentary:**
  > Pampas Core (Pergamino) lidera en retorno con 175.6%, seguido por Iowa con 139.7%, Mato Grosso con 131.3% y Southeast Buenos Aires con 68.7%. En valor por hectárea, Iowa alcanza 1107.14 USD/ha, sobre Pampas Core con 767.66 USD/ha, Mato Grosso con 678.25 USD/ha y Southeast Buenos Aires con 535.65 USD/ha. Solo Iowa tiene restricción de capital con 0.0683 USD, mientras las demás registran -0.0 USD. El flete es menor en Pampas Core con 16.5 USD/t a Up-River Rosario y Southeast Buenos Aires con 18.0 USD/t a Quequén, frente a Iowa con 40.0 USD/t a Mississippi River terminals y Mato Grosso con 75.0 USD/t a Santos / Paranaguá. Provisorios: flete en Southeast Buenos Aires; costos, rindes y flete en Pampas Core; costos y rindes en Mato Grosso; ninguno en Iowa.

- **Regional Table Values (`observatory/latest.json`):**

| Región | Cultivos | NPV/ha (USD) | Retorno Capital (%) | Retorno Cap. + Tierra (%) | Sombra Tierra (USD/ha) | Sombra Capital | Flete (USD/t) | Puerto |
|---|---|---|---|---|---|---|---|---|
| **Southeast Buenos Aires (Balcarce)** ⚠️ *(Provisorio)* | *(0 ha sembradas, 500 ha en alquiler)* | 535.65 | 68.70% | 3.20% | 332.90 | -0.0000 | 18.0 | Quequén (120 km) |
| **Pampas Core (Pergamino)** ⚠️ *(Provisorio)* | *(0 ha sembradas, 500 ha en alquiler)* | 767.66 | 175.60% | 3.30% | 551.58 | -0.0000 | 16.5 | Up-River Rosario (110 km) |
| **Iowa (central)** | maíz: 212,7 ha, soja: 212,7 ha | 1107.14 | 139.70% | 2.60% | 643.25 | 0.0683 | 40.0 | Mississippi River (180 km) |
| **Mato Grosso (Sorriso)** ⚠️ *(Provisorio)* | *(0 ha sembradas, 500 ha en alquiler)* | 678.25 | 131.30% | 3.80% | 377.00 | -0.0000 | 75.0 | Santos / Paranaguá (1400 km) |

---

## 4. Price Curves Verification & Working Tree Cleanliness

Before handoff, dynamic price curve files touched during test execution were restored:
```bash
git checkout -- dora/data/basis_argentina.json dora/data/price_curves/argentina_latest.json dora/data/price_curves/cbot_latest.json
```

Git status:
- Branch: `spec-31-audit-fixes`
- Uncommitted changes in tracked files:
  - `app.py`
  - `docs/observatory-format.md`
  - `dora/agent.py`
  - `dora/engine.py`
  - `dora/geo.py`
  - `dora/modeling_guide.md`
  - `dora/verifier.py`
  - `observatory/latest.json`
- New untracked files created for spec:
  - `docs/handoff/spec-31-audit-fixes.md`
  - `eval/results/live_check_spec31.json`
  - `observatory/2026-11-02.json`
  - `tests/test_spec31.py`
- Nothing committed and nothing merged, ready for review.


---

## Revisión de Claude (2/11)
- **Sacado:** `build_scenario` en `SEASON_SOLVING_TOOLS`. Lo pedía, sin querer, el test 3 de la spec. Con eso, el control rechazaba cualquier número de `build_scenario` que el productor no hubiera dicho (no hay resultados previos), y en la corrida de las 41 preguntas el agente quedó dando vueltas 8 rondas en una y la evaluación se cortó. `evaluate_season` ya atrapa el `credit_line_usd: 0`. El test 3 ahora usa `evaluate_season`.
- **Cambiado:** el control de "Lo que entendí" ya no le pide al modelo que corrija. En q28 el modelo contestó la corrección ("You're right — in English I'll use What I understood") en vez de contestarle al productor, y perdió la respuesta. Ahora `fix_label_language` (verifier.py) cambia la etiqueta en el código. El test 5 prueba eso.
- **Corridas de control:** las 41 preguntas de E1 final, una vez cada una, con la SPEC-31: 41 de 41 correctas y verificadas (`eval/results/regression_spec31/`, sin commitear; q28 se volvió a correr después del cambio de la etiqueta). Suite: 360 pasan, 1 se saltea.
- **Observatorio nuevo (2/11):** con los precios del día, las tres regiones argentinas dan "no sembrar, dar todo en alquiler" (crop_mix vacío); Iowa siembra maíz y soja. El video y el README tienen que decirlo así.
