# SPEC-32: "Empezá acá", a first screen for someone who has never used DORA

**Status:** ready (2/11), to implement on branch `spec-32-start-here`, created from `main` at the commit that adds this spec. Do not commit and do not merge: write the handoff and Claude reviews. Only `app.py`, a sample file and tests: no engine, agent, verifier or data changes.

**Why.** Today the app opens on the Scenario tab: a map, a dozen inputs and charts. A judge or a farmer who arrives for the first time does not know where to start, and the part that shows what DORA is (the conversation) is the fourth tab. The first screen has to say in one line what DORA does and offer three examples that run by themselves with one click.

## 1. A new first tab, open by default
`gr.TabItem("🚀 Empezá acá / Start here", id="tab_start", elem_id="tab_start")`, placed first and selected when the app loads. New tab order: Empezá acá, Chat con DORA, Escenario, Regiones, Comparar. (Move the Chat tab block; keep its `id="tab_chat"`.)

Content, in the selected language (Spanish by default, English with the language selector, like the rest of the app):

**Title and one line.**
- es: "DORA planifica tu campaña agrícola. Vos le contás tu campo; un motor matemático calcula el plan y cada número se verifica antes de mostrártelo."
- en: "DORA plans your crop season. You describe your farm; a math engine computes the plan, and every number is checked before you see it."

**Three cards, each with a title, one line of what you will see, and a button.**
1. **Planificá tu campaña / Plan your season.** "DORA te pregunta de a una cosa por vez, empezando por la que más cambia el plan." / "DORA asks one thing at a time, starting with what changes the plan the most." Button "Probar / Try it": switches to the Chat tab and sends, as the farmer, `Tengo 500 ha en Balcarce y 50.000 USD de capital. ¿Qué me conviene sembrar? Preguntame lo que necesites.` (en: `I have 500 ha in Balcarce and 50,000 USD of capital. What should I sow? Ask me whatever you need.`). The reply appears as if the user had typed it.
2. **Mandale una factura / Send an invoice.** "DORA lee la foto renglón por renglón y recalcula el plan con esos costos." / "DORA reads the photo line by line and recalculates the plan with those costs." Button: switches to Chat and sends the sample invoice image with `Tengo 500 ha en Balcarce y 50.000 USD. ¿Cómo cambia el plan con estos costos?` (en: `I have 500 ha in Balcarce and 50,000 USD. How does the plan change with these costs?`).
3. **Compará regiones / Compare regions.** "Balcarce, Pergamino, Iowa y Mato Grosso en un mapa, con su retorno y su flete al puerto." / "Balcarce, Pergamino, Iowa and Mato Grosso on a map, with their return and freight to port." Button: switches to the Regiones tab.

Under the cards, one smaller line with a link-styled button: "¿Querés tocar los números vos? Abrí la pestaña Escenario." / "Want to set the numbers yourself? Open the Scenario tab." → switches to `tab_scenario`.

**How to use DORA, four short steps** (a plain numbered list, since it is a real sequence):
1. Contale tu campo: hectáreas, región, plata propia, crédito. / Tell it about your farm: hectares, region, own money, credit.
2. Si falta algo que cambia el plan, DORA te pregunta; si no sabés, dice qué va a suponer. / If something that changes the plan is missing, DORA asks; if you don't know, it says what it will assume.
3. Podés escribir, mandar una nota de voz o una foto de una factura. / You can type, send a voice note or a photo of an invoice.
4. Cada respuesta dice si está verificada: todos los números salen del motor. / Every answer says whether it is verified: all its numbers come from the engine.

## 2. How the buttons send a message
Reuse the chat's existing `respond` function (module level since SPEC-31); do not duplicate the agent call. Each example button chains two events: first `gr.update(selected="tab_chat")` on `tabs`, then `.then(...)` calling `respond` with the example text (and, for card 2, `files=[<sample path>]`), writing to the same outputs as the chat's send button (chatbot, agent state, inputs). The daily limit and the API-failure message from SPEC-31 apply unchanged.

If the chat is not available (`has_chat` is false, no API key), cards 1 and 2 show their text and, instead of the button, "El chat necesita la clave del modelo." / "The chat needs the model key."; card 3 still works.

## 3. The sample invoice
Copy `eval/e3/media/invoices/f1.png` to `assets/examples/factura-ejemplo.png` and use that path (relative to the repo root, so it works in the Modal container, which runs from `/app`). Show a small thumbnail of it in card 2 so the user sees what will be sent.

## 4. Style
Use the app's existing theme (same fonts and colors as the other tabs); the cards sit in one row on desktop and stack on a phone (`gr.Row` with `equal_height=True`, each card a `gr.Column(min_width=260)`). No new external libraries. Text must be readable in Gradio's dark theme: set text colors that work on both backgrounds (the Observatory map once had grey labels on white under the dark theme).

## Acceptance tests (`tests/test_spec32.py`, no network)
1. The first `TabItem` in the Blocks is `tab_start`, and `tabs` is created with `selected="tab_start"`; the order of the tab ids is start, chat, scenario, regions, compare. (When `has_chat` is false: start, scenario, regions, compare.)
2. The Start tab's texts switch language: with "English" selected its title and the three card titles are in English; with "Español", in Spanish.
3. The card 1 handler, with a fake agent whose `ask` returns a fixed reply, puts the Balcarce example text as the user message and the fake reply in the history, in the selected language.
4. The card 2 handler sends `assets/examples/factura-ejemplo.png` (the file exists) together with the example text.
5. The card 3 and "Escenario" handlers return `gr.update(selected="tab_regions")` and `gr.update(selected="tab_scenario")`.
6. Existing tests that assume the Scenario tab is first are updated, not deleted; say which ones in the handoff.

Full suite: `DORA_API_BASE=http://127.0.0.1:9/v1 DORA_API_KEY=test DORA_MODEL=test python -m pytest -q` (360 passed, 1 skipped before this spec). Before handing off, restore the price files the app rewrites:
```
git checkout -- dora/data/basis_argentina.json dora/data/price_curves/argentina_latest.json dora/data/price_curves/cbot_latest.json
```

## Live check (Meta key in `.env`; cents)
Run `python app.py`, open it at 1366 × 768 and at phone width (about 400 px), in light and dark:
- The app opens on Empezá acá. Click each of the four buttons and paste, for cards 1 and 2, the first reply DORA wrote (as it came out) and whether it says verified.
- Switch to English and repeat card 1 once.
- Save screenshots in `docs/screenshots/start-here-*.png` (desktop light, desktop dark, phone).
Say what you saw, not "OK".

## Handoff (`docs/handoff/spec-32-start-here.md`)
What changed (files), the tests, the replies from the live check pasted as they came out, the screenshots, and anything you could not do. Do not mark a check as passed unless its output proves it.
