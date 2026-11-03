# SPEC-33b: the chat shows your message at once, says it is working, and logs how long each answer took

**Status:** ready (3/11). Same branch `spec-33-open-model`, on top of the uncommitted SPEC-33 work (Claude reviewed it: approved). Do not commit. Add a section "SPEC-33b" at the end of `docs/handoff/spec-33-open-model.md`. Touch only `app.py`, `dora/verifier.py` (`correction_message` only), `dora/agent.py` (the two lines that call it) and tests.

**Why.** On the deployed app (3/11) Guillermo typed a message and saw nothing for two minutes: his own message did not appear, only Gradio's "processing 86.0s". The Modal log shows that answer took 122 s (most take 16–19 s). Two problems: the chat gives no feedback while it works, and we cannot tell from the logs why one answer was slow.

## 1. Show the message at once
Today `respond` adds the user message and the reply to the history together, at the end. Chain two steps on the send button, on Enter and on the Start here cards 1 and 2:
1. `show_pending(user_text, files, audio, history, lang)`: returns the history plus the user message (same display as today: text, photo thumbnails, "🎤 nota de voz" if audio) and an assistant line es "⏳ DORA está armando el escenario y calculando…" / en "⏳ DORA is building the scenario and computing…". It runs without the queue (`queue=False`) so it shows instantly. If there is nothing to send, return the history unchanged.
2. Then (`.then`) the existing `respond`. At its start, if the last two history items are that pending pair, remove them; everything else in `respond` stays as it is (it appends the user message and the reply as today). This keeps `respond`'s signature and return value, so existing tests keep passing.

The input box is cleared in step 1 (so the user sees the text moved to the chat). Pass the original text, files and audio to step 2 through a `gr.State` or by keeping the inputs until step 2 clears them; pick one and say which.

## 2. One log line per answer
At the end of `respond` (and in its exception branch), `print` one line to stdout (it shows in `modal app logs`):
```
[chat] provider=meta model=muse-spark-1.3 seconds=18.4 rounds=3 tools=build_scenario,evaluate_season verified=True images=0 audio=False
```
`rounds` is the number of model requests in this turn (`agent.usage["requests"]` difference). No user text, no keys in the log.

## 3. Invoice table: no rows that say nothing
In the live check of SPEC-33 the reconciliation table showed `| unknown | fertilizante | USD 26.0/ha | USD None/ha | 0.0% ✅ |`. When a row's crop is unknown or its regional reference is `None`, do not show it as a row with a ✅. If no row has both, show the table title and one line instead: es "Falta saber para qué cultivo y cuántas hectáreas cubre la factura para compararla con la zona." / en "To compare it with the zone I need the crop and the hectares the invoice covers."

## 4. Find out why one answer took 122 s
Locally, with the Meta key, send these five messages in a fresh chat each, and paste the `[chat]` line of each:
1. `Tengo 500 ha en Balcarce y 50.000 USD de capital. ¿Qué me conviene sembrar? Preguntame lo que necesites.`
2. `hola`
3. `Tengo 300 ha alquiladas en Pergamino a 12 qq de soja, 80.000 USD y el banco me presta 100.000 al 9 %. ¿Qué siembro?`
4. Card 2 (the sample invoice).
5. `¿Y si llueve poco?` as the second message after message 1.
If any takes more than 60 s, say how many rounds and which tools; do not change the agent to fix it (Claude decides).

## 5. The answer switched to English after a correction (bug seen on 3/11)
Guillermo wrote, in Spanish: `planifiquemos la proxima campaña gruesa en campo propio de la zona del sudeste bonaerense`. The verified answer came in **English** and started with "Same plan worth 113,539 USD in present value, here with the crop on every number:". Cause: the style check `unnamed_series` sent the correction `say which crop each number is` alone, in English, without "in the same language", so the model rewrote in English and talked about the correction. (The same thing happened with q28 in SPEC-31.) Every correction round also adds time, which may explain the 122 s.

Fix:
- `correction_message(problems, style_problems, lang)` gets a new argument `lang` ("es" or "en") and always ends with one closing line:
  - es: "Reescribí la respuesta completa para el productor, en castellano, como si fuera la primera: no menciones esta corrección ni digas 'mismo plan'."
  - en: "Rewrite the whole answer for the farmer, in English, as if it were the first one: do not mention this correction or say 'same plan'."
- In `dora/agent.py`, compute `lang` once per turn from the farmer's text with the same rule `fix_label_language` uses (English only if no Spanish characters and English words; otherwise Spanish) and pass it. Move that rule to a small helper `farmer_lang(text)` in `verifier.py` and use it in both places.
- Do not change which problems are detected, nor `MAX_CORRECTIONS`.

Tests (add to `tests/test_spec33b.py`):
6. `correction_message([], ["say which crop each number is"], "es")` ends with the Spanish closing line; with "en", the English one.
7. `farmer_lang("planifiquemos la proxima campaña gruesa en campo propio")` is "es"; `farmer_lang("What should I sow with my 500 ha?")` is "en"; `farmer_lang("hola")` is "es".
8. Agent with a fake client whose first answer triggers `unnamed_series` (three decimal numbers separated by " / ") and whose second answer is fine: the correction message the fake client receives contains the Spanish closing line when the farmer wrote in Spanish.

Live check: send exactly Guillermo's message above on the local app and paste the reply: it must be in Spanish and must not mention the correction. Add its `[chat]` line (seconds and rounds).

## Tests (`tests/test_spec33b.py`, no network)
1. `show_pending` with text returns the history plus the user message and the pending line, in each language; with nothing to send, the history unchanged.
2. `respond` called with a history ending in the pending pair removes it and ends with exactly one user message and one reply (fake agent).
3. The log line is printed with `provider`, `seconds`, `rounds` and `verified` (capture stdout, fake agent).
4. The reconciliation table with an `unknown` crop or `None` reference shows no ✅ row and shows the "Falta saber…" line.
5. Full suite passes. Restore the price files before handing off.

## Live check
Run the app locally, send message 1 and say: did your message appear at once, did the pending line appear, and did it get replaced by the answer. Screenshot while it is working: `docs/screenshots/chat-pending.png`.
