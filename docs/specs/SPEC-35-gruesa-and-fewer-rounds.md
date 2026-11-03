# SPEC-35: "la gruesa" and "la fina" set the crops in code, and fewer rounds per answer

**Status:** ready (3/11), to implement on branch `spec-35-gruesa`, created from `main` at the commit that adds this spec. Do not commit and do not merge: write the handoff and Claude reviews. Touch only `dora/agent.py`, `dora/verifier.py`, `dora/modeling_guide.md` and tests. No engine, tool or app changes.

**Why.** On the deployed app (3/11, main `1c67dd7`) Guillermo wrote `planifiquemos la proxima campaña gruesa en campo propio de la zona del sudeste bonaerense, son 400 ha y tengo 60.000 USD`. The answer (verified, in Spanish) led with a plan of **soybean and wheat**. "La gruesa" in Argentina means the summer crops (maize, soybean, sunflower); wheat is "la fina". It mentioned "para la gruesa en sí, lo que conviene es soja sola" only in passing. The Modal log for that turn:
```
[chat] provider=meta model=muse-spark-1.3 seconds=109.5 rounds=7 tools=build_scenario,evaluate_season,build_scenario,evaluate_season,evaluate_season,shadow_prices verified=True
```
A line was added to the guide's phrase table on 3/11 ("La gruesa" → `crops: ["corn", "soybean", "sunflower"]`); it did not fix it.

**Suspected cause, to confirm first.** The scenario check (`check_scenario` in `dora/verifier.py`, SPEC-27/31) rejects parameters the farmer did not say ("Use only what the farmer said"). If the model passed `crops: ["corn","soybean","sunflower"]`, the check may have rejected it because the farmer never wrote those crop names, so the model fell back to the default crops (with wheat) and paid extra rounds. **Before changing anything**, reproduce it locally with the Meta key and paste the tool calls with their arguments and any `scenario_mismatch` result (the `calls` log of the `Reply`). Say whether this is the cause.

## 1. Season words set the crops
- A helper `season_crops(text) -> list[str] | None` in `dora/verifier.py`:
  - "gruesa", "cosecha gruesa", "cultivos de verano", "summer crops" → `["corn", "soybean", "sunflower"]`;
  - "fina", "cosecha fina", "cultivos de invierno", "winter crops" → `["wheat"]`;
  - both or neither → `None`.
  Match whole words only, case- and accent-insensitive ("la fina" must not match "finanzas", "afinar" or "final").
- In `check_scenario`: if the farmer's texts give `season_crops`, then `crops` equal to that list (any order) is accepted as said by the farmer. A different `crops` list is still checked as today.
- In `dora/agent.py`, before running a season-solving tool: if the farmer's texts give `season_crops` and the model passed no `crops`, set `crops` to that list in the arguments (log it in `calls` as `"crops_from_season_word": true`). If the model passed a different list, leave it (the check decides).
- If the farmer later says something that contradicts it (for example "sumale trigo"), the explicit crop wins: `season_crops` applies only when no crop is named in the same message. Write the rule you used in the handoff.

## 2. Fewer rounds
In that turn the model called `build_scenario` twice and `evaluate_season` three times. Two changes:
- **Guide:** one sentence in section 4 of `modeling_guide.md`: "Call `build_scenario` once per scenario; `evaluate_season` takes the same object directly. Do not rebuild a scenario you already built unless the farmer changed something." (es and en are not needed: the guide is for the model.)
- **Code, only if the guide is not enough:** if `build_scenario` is called with exactly the same scenario as an earlier call in the same turn, return the earlier result without running it again (the model still gets an answer, so the round count does not change, but no time is lost on the engine). Do not block or reject the call.
Do not change `MAX_TOOL_ROUNDS`, `MAX_CORRECTIONS` or the verifier rules.

## Tests (`tests/test_spec35.py`, no network)
1. `season_crops`: "la gruesa" and "campaña gruesa" give the summer list; "la fina" gives `["wheat"]`; "finanzas", "afinar el plan", "la final" give `None`; "gruesa y fina" gives `None`; "summer crops" gives the summer list.
2. `check_scenario` accepts `crops: ["soybean","corn","sunflower"]` when the farmer wrote "la gruesa", and still rejects `crops: ["barley"]` (or whatever the current test for an unsaid crop uses).
3. Agent with a fake client that calls `evaluate_season` without `crops` after "planifiquemos la gruesa…": the arguments that reach `run_tool` have the summer list.
4. Agent with a fake client that names wheat after "la gruesa, pero sumale trigo": `crops` is not overwritten.
5. Full suite passes (377 passed, 1 skipped on main). Restore the price files before handing off:
```
git checkout -- dora/data/basis_argentina.json dora/data/price_curves/argentina_latest.json dora/data/price_curves/cbot_latest.json
```

## Live check (Meta key; cents)
Run `python app.py` locally and paste, for each message in a fresh chat: the reply as it came out, the `[chat]` line, and the crops in the tool arguments.
1. `planifiquemos la proxima campaña gruesa en campo propio de la zona del sudeste bonaerense, son 400 ha y tengo 60.000 USD` → the plan has no wheat.
2. `Para la fina: 300 ha en Pergamino, 50.000 USD. ¿Cuánto trigo siembro?` → only wheat.
3. `Tengo 500 ha en Balcarce y 50.000 USD de capital. ¿Qué me conviene sembrar?` → unchanged from today (all crops; NPV 88.187 USD with today's data, or say if prices moved).
4. Repeat message 1 once more and compare seconds and rounds with the 109.5 s / 7 rounds above.

## Handoff (`docs/handoff/spec-35-gruesa.md`)
The cause you found (with the tool calls pasted), what changed, the tests, the live replies and `[chat]` lines as they came out. Do not mark a check as passed unless its output proves it.
