# Handoff Report: SPEC-35 "La Gruesa" and "La Fina" Set Crops in Code, and Fewer Rounds per Answer

**Branch:** `spec-35-gruesa`  
**Status:** Completed and verified  
**Date:** 2026-11-03  
**Commit status:** Uncommitted (per spec: *"Do not commit and do not merge: write the handoff and Claude reviews. Touch only dora/agent.py, dora/verifier.py, dora/modeling_guide.md and tests. No engine, tool or app changes."*)

---

## 1. Reproduction of Suspected Cause (Empirical Confirmation)

Before changing any code, we reproduced the exact query on `main` (`1c67dd7`) locally with the live Meta API:
`planifiquemos la proxima campaña gruesa en campo propio de la zona del sudeste bonaerense, son 400 ha y tengo 60.000 USD`

### Empirical Evidence:
```
--- REJECTION LOG ---
ScenarioProblem(parameter='crops', value=['corn', 'soybean', 'sunflower'], reason='crop corn restricted without farmer instruction')

--- CALLS LOG ---
{'tool': 'build_scenario', 'arguments': '{"lang":"es","scenario":{"allow_rent_out":true,"crops":["corn","soybean","sunflower"],"own_capital_usd":60000,"owned_ha":400,"region":"southeast_buenos_aires"}}', 'error': False, 'rejected': False}
{'tool': 'evaluate_season', 'arguments': '{"lang":"es","scenario":{"allow_rent_out":true,"crops":["corn","soybean","sunflower"],"own_capital_usd":60000,"owned_ha":400,"region":"southeast_buenos_aires"}}', 'error': True, 'rejected': True}
{'tool': 'evaluate_season', 'arguments': '{"lang":"es","scenario":{"allow_rent_out":true,"own_capital_usd":60000,"owned_ha":400,"region":"southeast_buenos_aires"}}', 'error': False, 'rejected': False}

--- BOT REPLY ---
Te da un valor actual de 120.625 USD: sembrás 200,0 ha de soja, 136,5 ha de girasol y 44,8 ha de trigo.
...
Supuesto: crédito de 100.000 USD y silo de 1.000 t; si querés solo gruesa sin trigo, decime y lo recalculo.
```

### Analysis of the Cause:
1. The model followed the guide table entry for "La gruesa" and called `build_scenario` with `crops: ["corn", "soybean", "sunflower"]`.
2. Next, the model called `evaluate_season` with `crops: ["corn", "soybean", "sunflower"]`.
3. Because `evaluate_season` is checked by `check_scenario`, Rule 3 (narrowing crops) evaluated whether the farmer explicitly said "corn", "soybean", "sunflower" using crop restriction regexes. Because the farmer said `"campaña gruesa"` but did not write the literal crop names `"maíz"`, `"soja"`, `"girasol"`, `check_scenario` rejected `crops` with `ScenarioProblem(parameter='crops', value=['corn', 'soybean', 'sunflower'], reason='crop corn restricted without farmer instruction')`.
4. In the following round, the model complied with the verifier error message (*"Use only what the farmer said. Remove the parameter, or ask the farmer"*), removed `crops`, and called `evaluate_season` without the `crops` parameter.
5. `evaluate_season` defaulted to all crops in Southeast Buenos Aires, including wheat (44.8 ha). The model was forced to present a plan containing wheat and add an apology line (*"si querés solo gruesa sin trigo, decime y lo recalculo"*), paying 7 rounds and 109.5 seconds.
6. **Verdict:** This was 100% the cause.

---

## 2. Summary of Changes

### A. Verifier: `season_crops` and `check_scenario` (`dora/verifier.py`)
1. **Helper `season_crops(text: str | list[str]) -> list[str] | None`:**
   - Detects summer phrases: `\b(gruesa|cosecha\s+gruesa|cultivos?\s+de\s+verano|summer\s+crops?)\b` (case- and accent-insensitive) -> `["corn", "soybean", "sunflower"]`.
   - Detects winter phrases: `\b(fina|cosecha\s+fina|cultivos?\s+de\s+invierno|winter\s+crops?)\b` -> `["wheat"]`.
   - Returns `None` if both match (e.g. "gruesa y fina") or neither.
   - Whole-word matching prevents false positives ("finanzas", "afinar el plan", "la final" return `None`).
   - Supports multi-turn `user_texts` checking in reverse chronological order.
2. **Contradiction & Explicit Crop Rules:**
   - If a message contains a crop that contradicts the season word (e.g. "la gruesa, pero sumale trigo", where wheat contradicts summer crops), `season_crops` returns `None`, allowing explicit user crop specifications to take precedence.
   - If a message restricts explicitly to a single crop (e.g. "solo soja"), explicit crops win.
   - For compatible crops (e.g. "Para la fina: 300 ha en Pergamino, 50.000 USD. ¿Cuánto trigo siembro?"), wheat does not contradict "fina", so `season_crops` confirms `["wheat"]`.
3. **Acceptance in `check_scenario`:**
   - If `season_crops(user_texts)` returns a crop list, and `set(scenario["crops"]) == set(sc_crops)` (any order), the crops parameter is accepted as instructed by the farmer.
   - Unstated crops (e.g. `["barley"]`) continue to be rejected as before.

### B. Agent: Auto-populating Omitted `crops` and Turn Caching (`dora/agent.py`)
1. **Season Crop Inference:**
   - Before running a season-solving tool (`fn_name in SEASON_SOLVING_TOOLS`):
     - If `season_crops(self.user_texts)` is not `None` and the model passed no `crops` parameter, `crops` is set to that list in the arguments.
     - Logged in `calls` as `"crops_from_season_word": True`.
     - If the model passed a different list, it is left untouched for `check_scenario` to validate.
2. **`build_scenario` In-Turn Caching:**
   - Maintained `turn_build_cache: dict[str, str]` during each `_answer` invocation.
   - If `build_scenario` is called with the exact same scenario parameters as an earlier call within the same turn, returns the cached result without re-executing `run_tool`.

### C. Modeling Guide (`dora/modeling_guide.md`)
- Added under `## 4. Analysis after the first run`:
  > "Call `build_scenario` once per scenario; `evaluate_season` takes the same object directly. Do not rebuild a scenario you already built unless the farmer changed something."

---

## 3. Test Suite Results

### A. Acceptance Tests (`tests/test_spec35.py`):
```
tests/test_spec35.py::test_1_season_crops PASSED                         [ 20%]
tests/test_spec35.py::test_2_check_scenario PASSED                       [ 40%]
tests/test_spec35.py::test_3_agent_sets_season_crops_when_omitted PASSED [ 60%]
tests/test_spec35.py::test_4_agent_explicit_crop_contradiction_not_overwritten PASSED [ 80%]
tests/test_spec35.py::test_5_build_scenario_caching PASSED               [100%]
============================== 5 passed in 0.14s ==============================
```

### B. Full Test Suite:
Run with dummy variables:
```bash
$env:DORA_API_BASE='http://127.0.0.1:9/v1'; $env:DORA_API_KEY='test'; $env:DORA_MODEL='test'; Remove-Item Env:\BASETEN_API_KEY -ErrorAction SilentlyContinue; Remove-Item Env:\BASETEN_API_BASE -ErrorAction SilentlyContinue; Remove-Item Env:\BASETEN_MODEL -ErrorAction SilentlyContinue; python -m pytest -q
```
**Result:** `383 passed, 1 skipped, 2 warnings in 312.45s`

---

## 4. Live Check Results (Meta API; cents)

All four messages were executed sequentially against the local application using the live Meta API credentials from `.env`:

### Message 1: Coarse Season Plan (Gruesa)
- **Prompt:** `planifiquemos la proxima campaña gruesa en campo propio de la zona del sudeste bonaerense, son 400 ha y tengo 60.000 USD`
- **Log line:**
  ```
  [chat] provider=meta model=muse-spark-1.3 seconds=21.9 rounds=3 tools=build_scenario,evaluate_season verified=True images=0 audio=False
  ```
- **Tool calls and crops:**
  - `build_scenario`: `crops=['corn', 'soybean', 'sunflower']`
    `arguments: {"lang":"es","scenario":{"allow_rent_out":true,"crops":["corn","soybean","sunflower"],"own_capital_usd":60000,"owned_ha":400,"region":"southeast_buenos_aires"}}`
  - `evaluate_season`: `crops=['corn', 'soybean', 'sunflower']`
    `arguments: {"lang":"es","scenario":{"allow_rent_out":true,"crops":["corn","soybean","sunflower"],"own_capital_usd":60000,"owned_ha":400,"region":"southeast_buenos_aires"}}`
- **Reply text (verbatim):**
  ```markdown
  ✅ **verificado: cada número sale del motor**

  Te da un valor actual de 89.785 USD con este plan de gruesa en campo propio.

  **El plan:** 200,0 ha de soja y 133,3 ha de girasol, nada de maíz. Te quedan 166,7 ha sin sembrar por falta de caja. Vendés el girasol en febrero (unas 268 t) y la soja en abril (488 t).

  **Lo que te limita:**
  * La plata de octubre a abril: entre la 2ª quincena de oct y la 2ª quincena de abr cada dólar extra te rinde 12,2% en esos 6 meses. Un dólar propio más hoy te suma 0,10 USD de valor actual por encima de dejarlo depositado.
  * Usás el crédito al tope (llegás a los 100.000 USD en febrero): más cupo también te sumaría.
  * El galpón no te limita: una tonelada más de almacenaje vale cero.

  **Lo que entendí:**
  Tuyo: 400 ha propias en sudeste, gruesa (maíz, soja, girasol) y 60.000 USD propios.
  De la zona: rindes y precios MAGyP junio-2026 y flete a Quequén.
  Supuesto del modelo: crédito disponible de 100.000 USD al 10% y depósito al 4%; si no tenés ese crédito avisame y lo recalculo.

  <details><summary>Detalle de llamadas a herramientas (2)</summary>

  - **build_scenario**: `{"lang":"es","scenario":{"allow_rent_out":true,"crops":["corn","soybean","sunflower"],"own_capital_usd":60000,"owned_ha":400,"region":"southeast_buenos_aires"}}`
  - **evaluate_season**: `{"lang":"es","scenario":{"allow_rent_out":true,"crops":["corn","soybean","sunflower"],"own_capital_usd":60000,"owned_ha":400,"region":"southeast_buenos_aires"}}`
  </details>
  ```
- **Proof:** The plan has **zero wheat** (200 ha soybean, 133.3 ha sunflower, 0 ha corn, 0 ha wheat).

---

### Message 2: Fine Season Plan (Fina)
- **Prompt:** `Para la fina: 300 ha en Pergamino, 50.000 USD. ¿Cuánto trigo siembro?`
- **Log line:**
  ```
  [chat] provider=meta model=muse-spark-1.3 seconds=19.0 rounds=3 tools=build_scenario,evaluate_season verified=True images=0 audio=False
  ```
- **Tool calls and crops:**
  - `build_scenario`: `crops=['wheat']`
    `arguments: {"lang":"es","scenario":{"area_ha":300,"crops":["wheat"],"own_capital_usd":50000,"region":"pampas_core"}}`
  - `evaluate_season`: `crops=['wheat']`
    `arguments: {"lang":"es","scenario":{"area_ha":300,"crops":["wheat"],"own_capital_usd":50000,"region":"pampas_core"}}`
- **Reply text (verbatim):**
  ```markdown
  ✅ **verificado: cada número sale del motor**

  Te conviene sembrar 150,0 ha de trigo, con un valor actual de 64.963 USD.

  Plan:
  * sembrás 150,0 ha de trigo y te quedan 150,0 ha sin sembrar en la fina.
  * vendés 675 t en diciembre.

  Lo que te limita:
  * el tope de rotación del trigo te frena en 150,0 ha, aunque tenés tierra libre.
  * entre la 2ª quincena de jul y la 2ª quincena de dic la plata va justa: cada dólar extra en ese tramo de 5,0 meses te rinde 4,1%, usás hasta 34.044 USD de crédito.
  * el galpón no te limita: una tonelada más de almacenaje no te suma nada.

  Lo que entendí: 300 ha en Pergamino y 50.000 USD son datos tuyos; trigo 4,5 t/ha a 208,5 USD/t son datos MAGyP Jun-2026 Zona Núcleo; lo calculé como campo propio — si es alquilado, decime y lo recalculo.

  <details><summary>Detalle de llamadas a herramientas (2)</summary>

  - **build_scenario**: `{"lang":"es","scenario":{"area_ha":300,"crops":["wheat"],"own_capital_usd":50000,"region":"pampas_core"}}`
  - **evaluate_season**: `{"lang":"es","scenario":{"area_ha":300,"crops":["wheat"],"own_capital_usd":50000,"region":"pampas_core"}}`
  </details>
  ```
- **Proof:** Evaluated with **only wheat** (`crops: ["wheat"]`). Result: 150.0 ha wheat, NPV 64,963 USD.

---

### Message 3: Baseline Balcarce Prompt (Unchanged)
- **Prompt:** `Tengo 500 ha en Balcarce y 50.000 USD de capital. ¿Qué me conviene sembrar?`
- **Log line:**
  ```
  [chat] provider=meta model=muse-spark-1.3 seconds=25.6 rounds=3 tools=build_scenario,evaluate_season verified=True images=0 audio=False
  ```
- **Tool calls and crops:**
  - `build_scenario`: `crops=None`
    `arguments: {"lang":"es","scenario":{"area_ha":500,"own_capital_usd":50000,"region":"southeast_buenos_aires"}}`
  - `evaluate_season`: `crops=None`
    `arguments: {"lang":"es","scenario":{"area_ha":500,"own_capital_usd":50000,"region":"southeast_buenos_aires"}}`
- **Reply text (verbatim):**
  ```markdown
  ✅ **verificado: cada número sale del motor**

  Te conviene sembrar soja y trigo, con un valor actual de 88.187 USD.

  Plan: 250,0 ha de soja y 121,7 ha de trigo, dejás 128,3 ha sin sembrar. Vendés todo a cosecha: el trigo en diciembre y la soja en abril.

  Lo que te limita:
  * La plata: entre la 2ª quincena de julio y la 2ª de abril cada dólar extra te rinde 19,5% en esos 9 meses. Un dólar más de capital propio hoy vale 0,16 USD más que dejarlo en el banco, y un dólar más de crédito 0,11 USD más.
  * La rotación de soja está al tope: una hectárea más de cupo de soja te vale 75,47 USD.
  * Una hectárea más de campo te vale 37,73 USD; una tonelada más de almacenaje no te vale nada: el galpón no es tu cuello de botella.

  Lo que entendí:
  Tuyo: 500 ha en Balcarce y 50.000 USD de capital.
  Zona: rindes y precios MAGyP de Sudeste y flete a Quequén.
  Lo calculé como campo propio con crédito supuesto; si es alquilado, decime y lo recalculo.

  <details><summary>Detalle de llamadas a herramientas (2)</summary>

  - **build_scenario**: `{"lang":"es","scenario":{"area_ha":500,"own_capital_usd":50000,"region":"southeast_buenos_aires"}}`
  - **evaluate_season**: `{"lang":"es","scenario":{"area_ha":500,"own_capital_usd":50000,"region":"southeast_buenos_aires"}}`
  </details>
  ```
- **Proof:** Unchanged from today (all crops; NPV **88.187 USD**, 250 ha soybean, 121.7 ha wheat).

---

### Message 4: Repeat Message 1 Comparison
- **Prompt:** `planifiquemos la proxima campaña gruesa en campo propio de la zona del sudeste bonaerense, son 400 ha y tengo 60.000 USD`
- **Log line:**
  ```
  [chat] provider=meta model=muse-spark-1.3 seconds=22.5 rounds=3 tools=build_scenario,evaluate_season verified=True images=0 audio=False
  ```
- **Tool calls and crops:**
  - `build_scenario`: `crops=['corn', 'soybean', 'sunflower']`
  - `evaluate_season`: `crops=['corn', 'soybean', 'sunflower']`
- **Reply text (verbatim):**
  ```markdown
  ✅ **verificado: cada número sale del motor**

  Te conviene sembrar gruesa con un valor actual de 89.785 USD: 200 ha de soja y 133,3 ha de girasol, sin maíz.

  El plan: sembrás 200 ha de soja que vendés en abril y 133,3 ha de girasol que vendés en febrero, todo a cosecha. No das campo en alquiler.

  Lo que te limita:
  * La plata: de la 2ª quincena de oct a la 2ª quincena de abr cada dólar extra te rinde 12,2% en esos 6 meses. Un dólar más de capital propio hoy te vale 10 centavos más que dejarlo en plazo fijo.
  * El tope de rotación de soja: no podés pasar las 200 ha, cada hectárea extra de soja que pudieras agregar te valdría 84 USD.
  * El silo no te limita: una tonelada más de almacenaje te vale nada, conviene vender a cosecha.

  Lo que entendí: tuyos son las 400 ha propias y los 60.000 USD; rindes y precios son del Sudeste de MAGyP jun-2026; el crédito de 100.000 USD al 10% y el silo de 1.000 t son supuestos del modelo.
  Si tenés silo propio, embolsado o plazo del proveedor, decime y lo recalculo.

  <details><summary>Detalle de llamadas a herramientas (2)</summary>

  - **build_scenario**: `{"lang":"es","scenario":{"allow_rent_out":true,"crops":["corn","soybean","sunflower"],"own_capital_usd":60000,"owned_ha":400,"region":"southeast_buenos_aires"}}`
  - **evaluate_season**: `{"lang":"es","scenario":{"allow_rent_out":true,"crops":["corn","soybean","sunflower"],"own_capital_usd":60000,"owned_ha":400,"region":"southeast_buenos_aires"}}`
  </details>
  ```
- **Comparison with the 109.5 s / 7 rounds before SPEC-35:**
  - **Rounds:** reduced from **7 rounds** to **3 rounds** (fewer than half).
  - **Seconds:** reduced from **109.5 s** to **22.5 s** (**4.8x faster**).
  - **Plan accuracy:** Correct coarse season (summer crops only: soybean + sunflower, 0 wheat).


## Claude's review (3/11)
Approved. One fix added: "la gruesa" in Iowa gave `sunflower`, which Iowa has no data for, so the engine returned an error. Now the season crops are filtered by the region's crops, both in the agent's fill-in and in `check_scenario`. New test `test_6_gruesa_in_iowa_drops_sunflower`. Full suite: 383 passed, 2 skipped.
