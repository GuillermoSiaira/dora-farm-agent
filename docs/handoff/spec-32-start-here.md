# Handoff Report: SPEC-32 "Empezá acá" First Screen

**Branch:** `spec-32-start-here`  
**Status:** Completed and verified (365 passed, 1 skipped)  
**Date:** 2026-11-02  
**Commit status:** Uncommitted (per spec instructions: "Do not commit and do not merge: write the handoff and Claude reviews. Only app.py, a sample file and tests: no engine, agent, verifier or data changes.").

---

## 1. Summary of Changes

### A. `app.py`
1. **CSS Styling for Start Here Tab (`CUSTOM_CSS`):**
   - Added `#start_tab_container` styling with max-width containment and responsive padding.
   - Added `#start_title_md` typography with bold title and explanatory subline.
   - Added `#start_cards_row` and `.start-card` card styling:
     - Rounded corners (`12px`), borders (`1px solid var(--border-color-primary, #e5e7eb)`), and card backgrounds (`var(--background-fill-secondary, #f9fafb)`).
     - Full dark-theme compatibility using Gradio CSS variables (`--block-label-text-color`, `--body-text-color`, `--background-fill-secondary`, `--border-color-primary`).
     - Equal heights and responsive stacking on mobile viewports (`min_width=260`).
   - Added `.start-card-thumb` for the sample invoice image thumbnail (compact height 110px).
   - Added `.start-card-btn` for action buttons (primary green `#16a34a` for Cards 1 & 2, secondary for Card 3).
   - Added `#start_scenario_link_row` and `.start-link-btn` for the subtle secondary link button.
   - Added `.start-steps` container styling for the 4-step sequence guide.

2. **Module-level Constants and Handlers:**
   - `CARD1_PROMPT_ES`: `"Tengo 500 ha en Balcarce y 50.000 USD de capital. ¿Qué me conviene sembrar? Preguntame lo que necesites."`
   - `CARD1_PROMPT_EN`: `"I have 500 ha in Balcarce and 50,000 USD of capital. What should I sow? Ask me whatever you need."`
   - `CARD2_PROMPT_ES`: `"Tengo 500 ha en Balcarce y 50.000 USD. ¿Cómo cambia el plan con estos costos?"`
   - `CARD2_PROMPT_EN`: `"I have 500 ha in Balcarce and 50,000 USD. How does the plan change with these costs?"`
   - `SAMPLE_INVOICE_PATH`: `"assets/examples/factura-ejemplo.png"`
   - `on_switch_to_chat()`: Returns `gr.update(selected="tab_chat")`.
   - `on_start_card1()`: Delegates to `respond()` passing the Card 1 prompt for the current language.
   - `on_start_card2()`: Delegates to `respond()` passing the Card 2 prompt and `SAMPLE_INVOICE_PATH`.
   - `on_start_card3()`: Returns `gr.update(selected="tab_regions")`.
   - `on_start_scenario_link()`: Returns `gr.update(selected="tab_scenario")`.

3. **Tab Layout & Reordering:**
   - Tabs initialized with `selected="tab_start"`.
   - New tab order when `has_chat=True`:
     1. `🚀 Empezá acá / Start here` (`id="tab_start"`)
     2. `💬 Chat con DORA / Chat` (`id="tab_chat"`)
     3. `📊 Escenario / Scenario` (`id="tab_scenario"`)
     4. `🌍 Regiones / Regional Observatory` (`id="tab_regions"`)
     5. `⚖️ Comparar / Compare` (`id="tab_compare"`)
   - New tab order when `has_chat=False`:
     1. `🚀 Empezá acá / Start here` (`id="tab_start"`)
     2. `📊 Escenario / Scenario` (`id="tab_scenario"`)
     3. `🌍 Regiones / Regional Observatory` (`id="tab_regions"`)
     4. `⚖️ Comparar / Compare` (`id="tab_compare"`)

4. **Card & Step Contents:**
   - **Card 1 (Planificá tu campaña / Plan your season):** Description and action button chaining `on_switch_to_chat` then `on_start_card1`.
   - **Card 2 (Mandale una factura / Send an invoice):** Description, `gr.Image` thumbnail (110px) showing `assets/examples/factura-ejemplo.png`, and action button chaining `on_switch_to_chat` then `on_start_card2`.
   - **Card 3 (Compará regiones / Compare regions):** Description and button switching to `tab_regions`.
   - Fallback when `has_chat=False`: Cards 1 and 2 show `"*El chat necesita la clave del modelo.*"` / `"*The chat needs the model key.*"` instead of active buttons. Card 3 remains fully functional.
   - **Scenario link:** `"¿Querés tocar los números vos? Abrí la pestaña Escenario."` / `"Want to set the numbers yourself? Open the Scenario tab."` switching to `tab_scenario`.
   - **Four-step sequence guide:** Numbered 1 to 4 detailing how DORA works.

5. **Bilingual Language Switching:**
   - Integrated `start_title_md`, `card1_title_md`, `card1_desc_md`, `card2_title_md`, `card2_desc_md`, `card3_title_md`, `card3_desc_md`, `card1_btn`, `card2_btn`, `card3_btn`, `scenario_link_btn`, `no_chat_msg1`, `no_chat_msg2`, and `start_steps_md` into `ui_texts` for immediate dynamic translation between Spanish and English.

6. **Component References on `app`:**
   - Attached `app.tab_start`, `app.start_title_md`, `app.card1_title_md`, `app.card2_title_md`, `app.card3_title_md`, `app.card1_btn`, `app.card2_btn`, `app.card3_btn`, `app.scenario_link_btn`, `app.tabs`, `app.has_chat` for clean testing.

### B. Sample Invoice (`assets/examples/factura-ejemplo.png`)
- Copied from `eval/e3/media/invoices/f1.png` (96,135 bytes).
- Real invoice featuring line items for Urea granulada 46-0-0 ($13,000 USD) and Fosfato monoamónico 11-52-0 ($8,000 USD).

### C. Acceptance Tests (`tests/test_spec32.py`)
- Created 5 offline unit tests verifying all acceptance criteria:
  - `test_1_tab_order_and_initial_selection`: Verifies `selected="tab_start"` and tab order both with `has_chat=True` and `has_chat=False`.
  - `test_2_language_switching`: Verifies that switching between Spanish and English updates the title, card titles, descriptions, buttons, link button, and step guide.
  - `test_3_card1_handler`: Verifies `on_start_card1` with a mock agent populates the Balcarce prompt into the conversation history and records the model response in ES and EN.
  - `test_4_card2_handler_with_invoice`: Verifies `on_start_card2` sends `assets/examples/factura-ejemplo.png` with the invoice query prompt into history.
  - `test_5_card3_and_scenario_link_handlers`: Verifies `on_start_card3` returns `selected="tab_regions"` and `on_start_scenario_link` returns `selected="tab_scenario"`.

---

## 2. Test Suite Results

### Acceptance Tests (`tests/test_spec32.py`):
```
python -m pytest tests/test_spec32.py -q
.....                                                                    [100%]
5 passed in 9.20s
```

### Full Test Suite:
```
$env:DORA_API_BASE='http://127.0.0.1:9/v1'; $env:DORA_API_KEY='test'; $env:DORA_MODEL='test'; python -m pytest -q
............................................................................................ [ 24%]
............................................................................................ [ 48%]
............................................................................................ [ 73%]
......................................................................................s..... [ 97%]
..........                                                                                   [100%]
365 passed, 1 skipped in 236.23s (0:03:56)
```

### Existing Tests Impact:
- **0 existing tests were broken, modified, or deleted.**
- All 360 existing test cases passed unmodified alongside the 5 new SPEC-32 tests.

---

## 3. Live Check Results

Executed with live Meta model (`muse-spark-1.3` via `https://api.meta.ai/v1`) loaded from `.env`.

### A. Card 1 — Planificá tu campaña (Spanish)
- **Farmer message:**
  ```
  Tengo 500 ha en Balcarce y 50.000 USD de capital. ¿Qué me conviene sembrar? Preguntame lo que necesites.
  ```
- **Verification badge:** `✅ verificado: cada número sale del motor` (`verified: true`)
- **DORA Reply (exact verbatim output):**
  ```markdown
  ✅ **verificado: cada número sale del motor**

  Entendí que tenés 500 ha en Balcarce y 50.000 USD de capital propio.

  ¿Hasta cuánto te presta el banco para la campaña? Si no sabés, lo calculo con 100.000 USD que es un supuesto del modelo.

  <details><summary>Detalle de llamadas a herramientas (2)</summary>

  - **build_scenario**: `{"lang":"es","scenario":{"own_capital_usd":50000.0,"owned_ha":500.0,"region":"southeast_buenos_aires"}}`
  - **next_question**: `{"lang": "es", "scenario": {"own_capital_usd": 50000.0, "owned_ha": 500.0, "region": "southeast_buenos_aires"}, "asked": [], "previous": null}`
  </details>
  ```

### B. Card 2 — Mandale una factura (Spanish, with invoice image)
- **Farmer message:**
  ```
  Tengo 500 ha en Balcarce y 50.000 USD. ¿Cómo cambia el plan con estos costos?

  📷 *[factura-ejemplo.png](assets/examples/factura-ejemplo.png)*
  ```
- **Verification badge:** `✅ verificado: cada número sale del motor` (`verified: true`)
- **DORA Reply (exact verbatim output):**
  ```markdown
  ✅ **verificado: cada número sale del motor**

  Entendí que tenés 500 ha en Balcarce con 50.000 USD, y me pasaste la factura contado de urea y de fosfato monoamónico.

  Para poder usarla en el plan no puedo repartirla sin saber la cobertura: ¿para cuántas hectáreas y para qué cultivo es ese fertilizante?

  ### 📑 Conciliación de Documento del Productor:
  | Cultivo | Concepto | Costo Propuesto | Ref. Regional | Desviación |
  |---|---|---|---|---|
  | wheat | fertilizer | USD 26.0/ha | USD 214.2/ha | 87.9% ⚠️ (>50%) |
  | wheat | fertilizer | USD 16.0/ha | USD 214.2/ha | 92.5% ⚠️ (>50%) |

  <details><summary>Detalle de llamadas a herramientas (2)</summary>

  - **build_scenario**: `{"lang":"es","scenario":{"area_ha":500.0,"own_capital_usd":50000.0,"region":"southeast_buenos_aires"}}`
  - **record_document**: `{"items":[{"amount":13000.0,"concept":"Urea granulada 46-0-0 20 t","currency":"USD","unit":"total"},{"amount":8000.0,"concept":"Fosfato monoamónico 11-52-0 10 t","currency":"USD","unit":"total"}],"kind":"invoice","scenario":{"area_ha":500.0,"own_capital_usd":50000.0,"region":"southeast_buenos_aires"}}`
  </details>
  ```

### C. Card 1 — Plan your season (English, repeated after language switch)
- **Farmer message:**
  ```
  I have 500 ha in Balcarce and 50,000 USD of capital. What should I sow? Ask me whatever you need.
  ```
- **Verification badge:** `✅ verified: every number comes from the engine` (`verified: true`)
- **DORA Reply (exact verbatim output):**
  ```markdown
  ✅ **verified: every number comes from the engine**

  Got it — 500 ha in Balcarce with 50,000 USD of capital.

  Is that land owned or rented? If you don't know, I'll keep it as owned land as a model assumption.

  <details><summary>Tool calls details (2)</summary>

  - **build_scenario**: `{"lang":"en","scenario":{"area_ha":500,"own_capital_usd":50000,"region":"southeast_buenos_aires"}}`
  - **next_question**: `{"lang": "en", "scenario": {"area_ha": 500, "own_capital_usd": 50000, "region": "southeast_buenos_aires"}, "asked": [], "previous": null}`
  </details>
  ```

### D. Card 3 & Scenario Link Button Checks
- **Card 3 button ("Ver regiones" / "View regions"):** Returns `gr.update(selected="tab_regions")`, switching to the Regional Observatory tab.
- **Scenario link button ("¿Querés tocar los números vos? Abrí la pestaña Escenario."):** Returns `gr.update(selected="tab_scenario")`, switching to the Scenario tab.

---

## 4. UI Screenshots

Captured from live headless Chrome instances at exact target resolutions:

1. **Desktop Light Theme:**
   - File: `docs/screenshots/start-here-desktop-light.png`
   - Resolution: $1366 \times 768$
   - Size: 100,484 bytes
   - What was observed: The app opens directly on "🚀 Empezá acá / Start here" (green active underline). Three cards sit side by side in an equal-height row. Card 2 displays the invoice thumbnail. All text is crisp and legible on light background.

2. **Desktop Dark Theme:**
   - File: `docs/screenshots/start-here-desktop-dark.png`
   - Resolution: $1366 \times 768$ (URL: `?__theme=dark`)
   - Size: 99,298 bytes
   - What was observed: High-contrast dark cards with `--background-fill-secondary` backgrounds and distinct borders. White headings and light gray body text are completely readable with no gray-on-white or low-contrast issues. Buttons retain strong green accent.

3. **Mobile / Phone Viewport:**
   - File: `docs/screenshots/start-here-phone.png`
   - Resolution: $400 \times 800$
   - Size: 51,369 bytes
   - What was observed: The cards gracefully wrap and stack vertically. Card 1 appears first, followed by Card 2 with its invoice thumbnail, ensuring full legibility and touch target accessibility on mobile screens.

---

## 5. Price Curves Verification

Per SPEC-32 instruction:
```
git checkout -- dora/data/basis_argentina.json dora/data/price_curves/argentina_latest.json dora/data/price_curves/cbot_latest.json
```
Price curves were restored to `main` HEAD. `git status` verifies these files are completely clean and unmodified.

---

## 6. Git Status

```
On branch spec-32-start-here
Changes not staged for commit:
  (use "git add <file>..." to update what will be committed)
  (use "git restore <file>..." to discard changes in working directory)
	modified:   app.py

Untracked files:
  (use "git add <file>..." to include in what will be committed)
	assets/examples/factura-ejemplo.png
	docs/handoff/spec-32-start-here.md
	docs/screenshots/start-here-desktop-dark.png
	docs/screenshots/start-here-desktop-light.png
	docs/screenshots/start-here-phone.png
	tests/test_spec32.py
```

No commits made on branch `spec-32-start-here`. Ready for review.


---

## Revisión de Claude (2/11)
- **Tarjeta 2, mensaje cambiado.** Con "¿Cómo cambia el plan con estos costos?" DORA tenía que preguntar para cuántas hectáreas y qué cultivo era la factura (correcto, pero no muestra nada). Ahora la tarjeta usa el mensaje de E3, que lo dice: "Te mando la factura del fertilizante del trigo. Cubre 100 ha de trigo. Tengo 500 ha en Balcarce y 50.000 USD. ¿Cómo cambia el plan con este costo?". Probado con el modelo: lee 210 USD/ha de fertilizante contra 214,2 de la zona, da el plan (116.267 USD de valor actual) y sale verificada.
- **Tabla de la factura en la respuesta.** Estaba siempre en castellano y con "wheat"/"fertilizer" sin traducir; ahora sigue el idioma. Y cuando falta la cobertura no muestra los costos por hectárea, que estaban repartidos sobre un área supuesta y contradecían la pregunta de DORA.
- Suite: 365 pasan, 1 se saltea.
