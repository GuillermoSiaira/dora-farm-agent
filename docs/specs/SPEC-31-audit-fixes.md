# SPEC-31: Fixes from the pre-submission audit

**Status:** ready (2/11), to implement on branch `spec-31-audit-fixes`, created from `main` at the commit that adds this spec. Do not commit and do not merge: write the handoff and Claude reviews. Small, local changes only: no engine equations, no new tools, no data except `observatory/`.

**Why.** An audit of `main` (2/11) found six problems a judge or the demo video would hit. Each item below says the file, what is wrong, how to see it, and the change. The diffs are the intended change; adapt line numbers, not behavior.

**Before starting and before handing off:** running the app or the tests rewrites today's prices inside the repo. Restore them so they are not part of the change:
```
git checkout -- dora/data/basis_argentina.json dora/data/price_curves/argentina_latest.json dora/data/price_curves/cbot_latest.json
```

## 1. Scenario tab: drawing a field in Pergamino or Mato Grosso breaks it (`app.py`)
`region_input` (around line 1975) only offers Balcarce and Iowa. `field_from_map` can return `pampas_core` or `mato_grosso`; `on_apply_polygon` sets that value and Gradio raises "Value: pampas_core is not in the list of choices". Outside every region `reg` is `None`, the message says "Desconocida" and the engine silently runs Balcarce.

Change:
- Add `("Zona núcleo (Pergamino)", "pampas_core")` and `("Mato Grosso", "mato_grosso")` to the dropdown choices.
- In `on_apply_polygon` and `on_region_change`, take the crops from `REGIONS[reg]["crops"]` (`dora/scenario.py`) instead of the hard-coded lists, shown in the current language (Spanish names when `lang == "es"`, using the app's existing crop translation dict). `on_region_change` must receive `lang_state` as an input.
- If `reg` is `None`: return `gr.update()` for area, crops and region, and a message: "⚠️ El campo queda fuera de las regiones que DORA conoce (Balcarce, Pergamino, Iowa, Mato Grosso)." / "⚠️ The field is outside the regions DORA knows (...)".
- `dora/geo.py:138`: update the docstring that says "(Southeast Buenos Aires and Iowa)".
- `on_lang_change` (around line 2834): keep the crops the user had ticked and the region's own crop list; do not re-tick all four.

## 2. Chat: a clear message when the model's API fails (`app.py`, `respond`, around line 2589)
Today `agent_instance.ask(...)` has no `try`. With the API unreachable it retries ~35 s, raises, Gradio shows a generic "Error", the message is lost and the daily counter still went up.
```diff
-                        reply = agent_instance.ask(clean_text, images=image_paths, audio=audio_path, screen_scenario=screen_scenario)
+                        try:
+                            reply = agent_instance.ask(clean_text, images=image_paths, audio=audio_path, screen_scenario=screen_scenario)
+                        except Exception:
+                            _daily_chat_counter -= 1
+                            msg = ("⚠️ No pude hablar con el modelo ahora. Probá de nuevo en un minuto; la pestaña Escenario funciona sin él."
+                                   if lang == "es" else "⚠️ Could not reach the model right now. Try again in a minute; the Scenario tab works without it.")
+                            history += [{"role": "user", "content": clean_text}, {"role": "assistant", "content": msg}]
+                            return "", None, None, history, agent_instance
```
Match the function's real return values (check how the other early returns look). Also:
- `_daily_chat_counter` (line 39) never resets: store the date with it and reset it when the date changes, so it is really per day.
- Line 123: the Spanish badge says "⚠️ **not verified**"; make it "⚠️ **sin verificar**".

## 3. Observatory: regenerate the snapshot and drop the local link (`observatory/`, `app.py`)
`observatory/latest.json` is from 27/10, before SPEC-28. With today's code all three Argentine regions come out as "don't sow, rent the land out", with other values, so the map and the table disagree with Compare and the chat.
- Regenerate it with the current code: `python -c "from dora.observatory import run_observatory; run_observatory(save=True)"` (uses today's prices; the commentary may call the model, which costs cents). Keep the new dated file and `latest.json`.
- `app.py` lines 1870 and 1875 link to `file:///d:/projects/dora-hackathon/observatory/latest.json`, which does not open in the public app. Show only the date: "**Fecha de la foto:** `{date_str}`" / "**Snapshot date:** `{date_str}`".
- `get_observatory_ui_data` uses `is_es` before defining it (around line 1757, only when `latest.json` is missing): define it at the top of the function.
- In the handoff, paste the new per-region values and plans (what the map labels now say).

## 4. The agent must not invent "no credit" (`dora/modeling_guide.md`, `dora/verifier.py`)
In E1 final the two wrong answers (q22 and q26, Iowa, "$50,000 capital") passed `credit_line_usd: 0` although the question says nothing about the bank. The engine then plans ~59 ha of soybean instead of ~175. The scenario check let it through because `_matches_any` (verifier.py:316) accepts any 0 if any tool result contains a 0, and `build_scenario` results always do.

Guide, in the table of section 1, below the "50 lucas propias" row:
```diff
+| "Tengo 50.000 USD de capital." / "$50,000 capital" (nothing said about the bank) | `own_capital_usd: 50000` only. Do not pass `credit_line_usd`: the model's credit line stays and is named as an assumption. Pass `credit_line_usd: 0` only if the farmer says nobody lends ("sin crédito", "nadie me presta", "no credit"). |
```
Verifier, rule 2 of `check_scenario` (around line 363), before the generic number check:
```diff
+ZERO_NEEDS_FARMER = {"credit_line_usd": r"sin\s+cr[eé]dito|nadie\s+me\s+presta|no\s+me\s+prest|no\s+(?:tengo|hay)\s+cr[eé]dito|no\s+credit|without\s+credit|no\s+(?:bank\s+)?loan|can'?t\s+borrow"}
         if isinstance(v, (int, float)):
             if k in flagged_params:
                 continue
+            if k in ZERO_NEEDS_FARMER and float(v) == 0.0:
+                if not any(re.search(ZERO_NEEDS_FARMER[k], t, re.I) for t in user_texts):
+                    problems.append(ScenarioProblem(k, v, "the farmer did not say 0: leave it out (model default) or ask"))
+                continue
```
Put `ZERO_NEEDS_FARMER` at module level. E5 question `e5_08` ("nadie me presta") must still pass.

## 5. "earns 79.7% in those 0 months" (`dora/engine.py:120`, `dora/modeling_guide.md:120`)
`round((e - s) / 2)` gives 0 for a one-fortnight stretch (and Python rounds 5 fortnights to 2 months).
```diff
-                "duration_months": round((e - s) / 2),     # so the agent can say "en esos N meses" without computing
+                "duration_months": round((e - s) / 2, 1),  # 1 fortnight = 0.5, never 0
```
Guide line 120, add: "If `duration_days` is under 30, say the days ('en esos 15 días' / 'in those 15 days'), not months." `tests/data/spec23` must still give 9.0.

## 6. "Lo que entendí" inside English answers (`dora/verifier.py`, `dora/agent.py`)
The guide was already fixed in `bf7cb6a`; add a style check so it cannot come back. It feeds the existing correction round, like the other style problems.
```diff
# dora/verifier.py
+def wrong_language_label(text: str, user_text: str) -> list[str]:
+    english = not re.search(r"[áéíóúñ¿¡]", user_text) and re.search(r"\b(the|what|how|with|my|is)\b", user_text, re.I)
+    return ["The answer is in English: write 'What I understood', not 'Lo que entendí'."] if english and "Lo que entend" in text else []
# dora/agent.py, inside _get_styles
+            st.extend(wrong_language_label(ans, actual_text))
```

## Acceptance tests (`tests/test_spec31.py`, no network)
1. The region dropdown choices include the four region keys; `on_apply_polygon` with a polygon in Pergamino returns `pampas_core` and that region's crops; with a polygon in the ocean it returns no region change and the "fuera de las regiones" message. (If the handlers are nested inside the Blocks, extract them to module-level functions so they can be tested.)
2. `respond` with an agent whose `ask` raises returns the warning message in the history and does not increase `_daily_chat_counter`.
3. `check_scenario("build_scenario", {"credit_line_usd": 0, ...}, ["On 500 ha with $50,000 capital in Iowa ..."], [<a build_scenario result>])` reports `credit_line_usd`; with user text "nadie me presta" it does not.
4. `capital_stretches` for a one-fortnight stretch gives `duration_months == 0.5`.
5. `wrong_language_label` flags an English question whose answer contains "Lo que entendí" and does not flag a Spanish one.
6. The Observatory header has no `file:///`.

Full suite: `DORA_API_BASE=http://127.0.0.1:9/v1 DORA_API_KEY=test DORA_MODEL=test python -m pytest -q` (354 passed, 1 skipped before this spec).

## Live check (Meta key in `.env`; cents)
- `python eval/run_eval.py --ids q22,q26 --runs 3` (condition C). Expect 6 of 6 correct and no `credit_line_usd: 0` in the tool calls. Save the output under `eval/results/live_check_spec31.json`.
- Open the app (`python app.py`), draw a field in Pergamino on the Scenario tab and run it; open the Regional Observatory tab and check the labels match the new snapshot. Say what you saw, not "OK".

## Handoff (`docs/handoff/spec-31-audit-fixes.md`)
Per item: what changed (files), the test that covers it, and the output of the live check pasted as it came out (tool calls of q22/q26, the new Observatory values). List anything you could not do. Do not mark a check as passed unless its output proves it.
