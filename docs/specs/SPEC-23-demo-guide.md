# SPEC-23: A demo that explains itself, and DORA as a guide

**Status:** draft (29/10), to implement on branch `spec-23-demo-guide`, created from `main`. It touches `app.py`, `dora/agent.py`, `dora/modeling_guide.md` and tests. **It must not change the engine or the tools' numbers** (the model is frozen: tag `model-frozen-2026-10-29`).

## Why
- **The page opens empty.** `app.py` computes nothing on load: every chart is a dark box with an icon until the user finds "Calcular Plan Óptimo" at the bottom of the left column. Reloading the page (for example, coming back from the "Usar vía API" page) empties it again. The farmer, and the jury, read this as "the charts are broken". This happened several times during development.
- **A first-time user does not know what to do.** The form is long (map, land, livestock, constraints), the examples are hidden at the bottom, and the charts speak of "shadow prices".
- **The chat could be the guide,** and that is also Meta's model at work (Muse Spark), with voice input (Muse Voice Transcribe) that already exists.
- Small things the review of 29/10 found on screen (section 4).

## 1. The page is never empty
- On load (`demo.load`), compute the default scenario (Balcarce, 500 ha, the form's defaults) with the same function as the "Calcular Plan Óptimo" button, and fill the plan, the cards and every chart of the Scenario tab.
- The Regions tab fills itself on load from the last saved observatory snapshot (it must not call the network on every page load; if there is no snapshot, it says so).
- Any chart that is still empty shows a sentence instead of the icon: "Apretá **Calcular Plan Óptimo** para ver este gráfico" / "Press **Calculate Optimal Plan** to see this chart". Same for the Compare tab before the first comparison.
- If the computation fails, the error is shown in words on the page, not as an empty chart.

## 2. "¿Cómo empiezo?" (How do I start?)
- At the top of the Scenario tab, a short panel that can be closed (and stays closed during the session): three steps in one line each:
  1. Choose an example or draw your field on the map.
  2. Press **Calcular Plan Óptimo**.
  3. Look at what is short and what is left over: the charts say what one more dollar, hectare or tonne of storage is worth to you.
- The three example buttons ("Capital restringido", "Insumos a 90 días", "Contrato de maíz") move up into this panel, as large buttons, each with one sentence saying what it shows. Pressing an example **loads it and computes it** (today it only fills the form).
- A link "Preguntale a DORA" that opens the Chat tab (when the chat is available).

## 3. Layout
- The result (plan, cards) and the first chart must be visible without scrolling on a 1366×768 screen.
- The rarely used parts of the form (livestock, constraints, supplier terms, map) go into "Opciones avanzadas" / "Advanced options", closed by default. The map stays reachable with one click.
- The "Calcular Plan Óptimo" button sits right under the basic fields (area, capital, credit, region), not at the bottom of the column.
- Nothing is removed: every field that exists today is still there.

## 4. Small fixes found on screen (29/10)
- **Mixed languages.** In Spanish, the land comparison appears in English ("an extra hectare is worth 37.73 to you; renting one costs 0.0…"), and the tax names in the tax wedge table are in English. Every text on screen follows the language switch. The tools' text fields used for the screen (`land_comparison`, tax names) get a Spanish version, chosen by `lang`; their numbers do not change.
- **Land card with unsown land.** When there are unsown hectares and the land shadow price is positive, the card adds: "aunque quedan X ha sin sembrar: el valor viene de la rotación (con una hectárea más podés sembrar más del cultivo que está en su tope)". X comes from the tool. In English too.
- **Returns with their period.** The return on capital and the return on capital and land show "en la campaña (14,5 meses)" and next to it the annual figure and the deposit rate (fields that exist since SPEC-21: `return_on_capital_annual_pct`, `deposit_rate_annual_pct`). When the land has no price (single field), show only the return on capital, and say why the other one is missing.
- **Export duties in the tax wedge.** The rates in `taxes_argentina.json` are old (marked placeholder). Until the decree in force is read, the export duty row says "alícuotas a verificar (placeholder)" next to the amount, and the table states that MAGyP prices are already net of duties (so the row is informative). Do not change the rates in this spec.

## 5. DORA as a guide (Muse Spark)
- The agent can answer questions about the page: "¿qué hago acá?", "¿qué significa este gráfico?", "¿qué es un precio sombra?", "¿por qué me dice que la tierra vale X si me sobran hectáreas?".
- How: add to the system prompt (or to `modeling_guide.md`) a short section "Using the DORA screen": what each tab is for, what each chart and card means, the three steps, and the example scenarios. Plain language, short answers, offer the next step. It must not invent numbers: for any number it calls the tools, as always, and the verifier still checks every answer.
- **Context of the screen:** when the user asks from the Chat tab, the agent receives the last scenario computed on the Scenario tab (its parameters, not its results), so "¿qué significa este gráfico?" is answered about the farmer's own run. The agent recomputes with the tools if it needs numbers.
- **First message in the chat** (shown, not sent to the model): a short greeting that says what DORA can do and invites to write or send a voice note: "Contame tu campaña: hectáreas, cultivos, plata y crédito. Podés escribir o mandar un audio."
- It is not intrusive: nothing pops up on its own.

## 6. Voice output (only if Meta offers it)
- Check the documentation of the Meta API we use (base `https://api.meta.ai/v1`) for a text-to-speech endpoint. Write in the handoff what you found and where (the page and its date).
- **If it exists:** a "🔊 Escuchar" button under each chat answer that reads it aloud with that endpoint. Audio is generated only when the button is pressed.
- **If it does not exist:** do nothing in this spec. Do not use the browser's speech or another provider presented as Meta.

## Acceptance tests (`tests/test_demo_guide.py`, no network)
1. Building the app and running the load event fills the Scenario outputs (plan markdown not empty, every chart a figure with data).
2. Each example button loads and computes: the plan differs between "Capital restringido" and "Contrato de maíz", and the maize contract plan has at least 150 ha of maize.
3. Language: with `lang="es"`, no output of the Scenario tab contains the English sentence "an extra hectare is worth"; with `lang="en"`, no Spanish label of section 4 appears.
4. Land card: in the default Balcarce scenario (unsown hectares, land shadow price > 0), the card contains the rotation sentence with the unsown hectares from the tool.
5. Returns: the card shows the season figure, the annual figure and the deposit rate, all equal to the tool's fields.
6. The tools' numbers do not change: `evaluate_season` and `shadow_prices` for the default scenario give the same values as `main` (to 1e-9).
7. Guide: the system prompt contains the "Using the DORA screen" section; a scripted agent call (no network, with a fake client) passes the last scenario to the model.
8. If voice output is implemented: the button exists only in the chat, and no audio request is made until it is pressed.

The existing tests must pass unchanged. If one breaks because a label moved, stop and write it in the handoff.

## Check in the browser
Open the page fresh, reload it, go to "Usar vía API" and come back: the charts are never empty. Then press each example. Then ask the chat "¿qué significa el gráfico de la quincena?" in Spanish and in English. Claude repeats these checks before merging.
