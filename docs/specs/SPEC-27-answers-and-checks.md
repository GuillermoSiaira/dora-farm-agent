# SPEC-27: Checks that measure the right thing, and answers a farmer reads first time

**Status:** draft (31/10), to implement on branch `spec-27-answers`, created from `main`. Do not merge into `main`; it gets reviewed first. It changes the agent (prompt, verifier) and the E1 counter, not the engine: plan, NPV and every shadow price stay as they are. After the merge, regenerate `eval/answers.jsonl` (only q33 changes) and tag the version.

**No number is typed by hand.** Every number in this spec was read from a tool run on `main` at `641e43e` or from the E1 result files in `D:\projects\dora-e1\eval\results\` (Standard: `muse-spark-1_3_*_20261030_15*.json`; Contributor: `muse-spark-1_3-contributor_*_20261031_*.json`). The tests compute their expected values from the tools, except where this spec says a value is fixed.

## Why
E1 left four questions with failures: q33, q17, q13, q30. Reading every failing reply shows that two of them are the counter's fault, one is a real agent error the verifier cannot see, and one is half and half:

| Question | What E1 counted (C, Standard / Contributor) | What actually happened |
|---|---|---|
| q33 Pergamino or Iowa | 1/5 and 0/5 correct | All 10 C replies say Iowa wins, which is right. The check looks for `profit_per_sown_ha` of Pergamino (372.18), a number the question does not ask for. |
| q17 invoice without hectares | 4/5 and 3/5 | All 10 C replies ask for the hectares and none solves a season. The 3 "failures" ask with words the counter does not know ("necesito que me digas", "¿para cuántas hectáreas…?"). What is wrong is the style: they list "500 ha, campo propio, 50.000 USD" as model assumptions before asking, so it reads as if DORA had assumed a farm. |
| q13 soybean yield ×3 | 4/5 and 4/5 | Real error. In the failing run the agent called `evaluate_season` with `crops: ["soybean"]`, which the farmer never said (he gave a soybean **yield**, not a crop restriction). The engine returns NPV 374,995.25 for that scenario (reproduced on `main`) instead of 383,129.74 (wheat 121.7 ha + soybean 250 ha). The number came from a tool, so the verifier passed it, and the reply even lists "solo soja" under "Tuyo". |
| q30 −50 ha in Iowa | 5/5 and 4/5 | Worse than counted. In 2 of 5 Standard runs and 2 of 5 Contributor runs the agent turned −50 into 50 on its own ("I read -50 hectares as 50 ha"), solved the season and gave an NPV of 86,079 USD. These count as correct because the reply contains "negativ" or "invalid". The one Contributor "failure" is a good refusal ("which isn't possible… Did you mean 50 ha?") that the English marker list misses. Real score: 3/5 in both. |

Two more things the E1 counter gets wrong:
- **"No plan given" counts as an infeasible plan.** q06 (rented land, 50 lucas) has the optimal plan "sow nothing" (`hectares: {}`, NPV 50,000), and `if not hectares` treats the empty dict as no plan, in all 20 B and C runs. q09, q10 and q20 sometimes use only `shadow_prices`, which returns no hectares, and q23 uses `sensitivity`, whose hectares are inside `results[]`. All of these lower `feasible_rate` (C Standard: 15 of 165 plan records), though no plan was infeasible.
- **The plan taken is the last season solved,** not the one the question asked. When the agent solves the asked scenario and then a variant (rented, other capital), the variant is the one checked.

And the answers are hard to read (Guillermo, reading q33): the decision comes after "Lo que entendí" and the assumptions; the return block puts "353,6 % sobre capital" next to "2,5 % sobre capital y tierra" and "depósito 4 %" without explaining why they differ; Condition B replies write field names (`owned_ha`, `npv_usd`, `rent_out_ha`); almost every reply ends with "te conviene verlo con un especialista en investigación operativa", because the system prompt asks for it.

The "¿qué podés hacer?" reply with a cut sentence in point 4 is reproducible (`python chat.py`, 31/10): the first draft says "el modelo termina en julio (quincena 29)" and "90 días con recargo". Neither number comes from a tool or the farmer: "fortnight 29" is written in the system prompt and "90 días" is an example in the modeling guide. The verifier flags them, and the rewrite deletes the number and leaves the sentence broken. The same line also contradicts SPEC-26: the system prompt still says DORA cannot evaluate holding grain past July.

## 1. q33: the check measures the decision
**Decision:** keep the question, change the check. "¿Dónde me conviene más sembrar?" is what a farmer asks, and its answer is a region, not a margin. Rewriting it as "¿cuánto más gano en Iowa?" would test a number we already test elsewhere (q34, q36 ask for numbers on purpose and stay as they are).

- `compare_regions` adds, at the top level, `best_region` (= `ranking[0]`) and `npv_gap_to_next_usd` (NPV of the first minus NPV of the second, rounded to 2 decimals), and in each region entry `npv_gap_vs_best_usd`. The agent needs these to say "te conviene Iowa: 56.794 USD más" without calculating (the verifier would reject a difference made by the model). For q33 on `main`: Iowa 432,584.01, Pampas Core 375,790.00, gap 56,794.01.
- `sensitivity` adds to each row `npv_change_vs_first_usd` (this row's NPV minus the first row's), for "¿cuánto cambia si…?".
- A new check kind in `eval/questions.jsonl`: `"check": {"tool": "compare_regions", "payload": {…as today…}, "field": "best_region", "kind": "decision"}`. `eval/build_answers.py` writes `"expected_value": "iowa"` for q33 (from the tool, not typed).
- `eval/run_eval.py`, for `kind == "decision"`, uses `decision_named(reply, expected, regions)` instead of `text_contains_expected_value`:
  1. Split the reply into lines and sentences (on `\n`, `.`, `!`, `:`).
  2. Take the first piece that has a verdict word (es: `conviene`, `gana`, `mejor`, `rinde más`, `queda primero`; en: `better`, `best`, `wins`, `ahead`) **and** names at least one of the compared regions. If the piece starts with `entre … ,` / `between … ,` / `comparando … ,` / `comparing … ,`, drop that leading clause first.
  3. Hit if, in that piece, the expected region is named and is named before any other compared region.
  - Region names live in one dict in `run_eval.py`: `pampas_core`: Pergamino, Pampas Core, zona núcleo, núcleo, nucleo; `southeast_buenos_aires`: Sudeste, Southeast; `iowa`: Iowa; `mato_grosso`: Mato Grosso. Lower-case, accent-insensitive match.
  - A ranked list without a verdict ("1. Iowa… 2. Pergamino…") is a miss: the farmer asked where it pays, and the answer has to say it.
- Condition A skips compare_regions questions today; it keeps skipping them.

## 2. q17: ask without reciting assumptions
- **Modeling guide, section 3:** add: "When you ask instead of computing, write only what you understood from the farmer and the question. Do not list MAGyP data or model assumptions (area, capital, credit, prices): you did not use them, and listing them reads as if you had assumed a farm. One or two questions, the ones that block the calculation."
- **`build_scenario`:** when the farmer gave no `area_ha` (nor `owned_ha`), report `"area_ha": {"value": null, "unit": "ha", "origin": "missing", "note": "ask the farmer"}` instead of 500 as `default`. The `Scenario` dataclass keeps its default of 500 for the engine and the tests; only the report changes. (The 500 the replies recited came from here.)
- The refusal counter changes (section 5), so a good question counts whatever words it uses.

## 3. q13 and q30: the scenario must be the one the farmer described
A new deterministic check in `dora/verifier.py`, `check_scenario(tool, args, user_texts, tool_results) -> list[ScenarioProblem]`, run in `Agent._answer` **before** a tool runs, only when `use_verifier` is on (so condition B of E1 keeps measuring the agent without it). It applies to the tools that solve a season: `evaluate_season`, `shadow_prices`, `sensitivity`, `compare_regions`, `climate_scenarios`, `assess_field_image`.

If it finds problems, the tool does not run. The model gets, as that tool's result, `{"error": "scenario_mismatch", "problems": [...], "hint": "Use only what the farmer said. Remove the parameter, or ask the farmer."}`. Each problem names the parameter, the value set and why. The call is logged in `calls` with `"rejected": true`, and `Reply` gets `scenario_rejections` (the list of problems), stored in the E1 record.

Rules (keep them this narrow; widen only with a failing case in hand):
1. **Farm size.** `area_ha` or `owned_ha` must be a number the farmer wrote (or in the screen scenario, which `Agent.ask` already appends to `user_texts`). If the farmer wrote no area, the problem is "area_ha missing: ask the farmer". Exception: `compare_regions` with `mode="same_budget"`, which needs no area.
2. **Numbers the agent set.** Every number in the scenario (top-level values, one level of dicts such as `yields` and `prices`, and the numeric fields of `constraints` and `payment_options`) must match, within 1 %, either a number the farmer wrote or a number some earlier tool returned in this conversation (`support()` over `tool_results`: that covers `build_scenario`'s defaults and `record_document`). Readings of the farmer's numbers:
   - **with their sign**: "-50" is −50 (today `_PATTERN` drops the minus sign; the scenario check must not);
   - `%` as a share: "10%" ↔ 0.10;
   - thousands: "50 lucas", "50 mil", "50k" ↔ 50,000; and when the message says "lucas" or "mil" anywhere, every number in it may also be read ×1000 ("tengo 50 lucas y el banco me da hasta 100" ↔ 100,000);
   - days as fortnights: "60 días" ↔ 4;
   - acres as hectares: "200 acres" ↔ 80.94 (× 0.404686).
3. **Narrowing the farm without the farmer's words.**
   - `crops` with fewer crops than the region allows needs every listed crop named by the farmer (es/en: trigo/wheat, maíz/corn, soja/soybean, girasol/sunflower) **and** a restriction: `solo`, `sólo`, `únicamente`, `nada más`, `only`, `just`, or a sowing verb (`sembrar`, `siembro`, `hacer`, `plantar`, `plant`, `grow`) within 5 words before the crop. "La soja le rinde 7,32" names soybean with no restriction: problem.
   - `rented_land: true` needs `alquil`, `arrend`, `rent` or `lease` in the farmer's words.

q30 is caught by rule 2 (50 is not −50) and q13 by rule 3. The agent is also told, in the system prompt: "Never change a value the farmer gave, even an impossible one (a negative area): say why it cannot be used and ask. A yield or price for one crop is not a restriction to that crop."

The check does not judge whether a scenario is sensible, only whether it is the farmer's. Its limits go in `docs/model.md`'s verifier section: it reads the farmer's words, not their intent; a value the farmer said in other words ("la mitad del campo") is rejected and the model has to ask.

## 4. q30: what is wrong, in one line
The agent "fixes" an impossible input and answers for a farm the farmer did not describe, and the E1 counter rewards it because the reply contains "negative". Section 3 stops the first; section 5 stops the second.

## 5. The E1 counter (`eval/run_eval.py`)
1. **Refusals.** For `expect == "refuse"`, a hit needs both:
   - **no plan**: for B and C, no successful result of a season-solving tool in the conversation (rejected calls in section 3 do not count as results); for A, no hectares in the model's JSON;
   - **a question or a refusal**: the reply contains `?` or one of the markers. Add to the markers: `necesito`, `cuántas hectáreas`, `no puedo`, `no se puede`, `how many`, `can't`, `cannot`, `isn't possible`, `not possible`, `has to be`.
2. **No plan is not an infeasible plan.** `_plan_fields` uses `hectares is None` for "no plan": then `plan_feasible` and `plan_violations` are `None` and a new field `plan_given` is `False`. An empty dict is a plan (sow nothing) and goes to `evaluate_plan` like any other. Add `plan_given_rate` to the run metrics and `no_plan_runs` to `per_question`. `feasible_rate` stays over plans given.
3. **The plan of the scenario asked.** `_agent_plan_and_value` takes the hectares, and the checked field, from the **last** call whose scenario matches the question's (`match_scenario`, with `region` dropped for `compare_regions`, as tool accuracy already does). For `sensitivity`, the row whose `parameter` value equals the question's value for that parameter, with the scenario `{**call_scenario, parameter: row_value}`. If seasons were solved but none matches, `plan_given` is `False` and `plan_scenario_mismatch` is `True`.
4. **Keep what is needed to rescore.** Each B and C record stores `tool_calls` (tool, arguments, error, rejected), as `Reply.tool_calls` already has them.
5. **`eval/rescore.py RESULTS.json [--out PATH]`:** recomputes, from a stored result file, what the stored fields allow: the refusal rule (stored `plan_hectares` stands for "a season was solved"), the decision rule for q33, `plan_given` and `plan_feasible` for `{}` plans (calling `evaluate_plan`, no network). Older files have no tool results, so a `sensitivity` plan cannot be recovered there; say so in the output. It never overwrites the input. It prints, per question, correct runs before and after.

## 6. Answers a farmer reads first time
### System prompt (`dora/agent.py`)
- Remove "For a tailored analysis of a specific farm, suggest contacting an operations-research specialist."
- Replace the "holding grain past the end of the season… fortnight 29… cannot evaluate it" line with: "If the farmer asks about holding grain past July, follow the modeling guide (carry-over needs a quote for that month)." No fortnight number in the prompt.
- Replace "First call build_scenario… and show back what you understood…" with: "Call build_scenario with only the parameters the farmer gave. Then answer in the format of the modeling guide, section 0."
- Add the rule of section 3 (never change the farmer's value; a yield is not a crop restriction).

### Modeling guide, new section 0 "How to answer"
1. **First line: the answer to what was asked, with its USD figure from a tool.** A comparison: the winner and the gap ("Te conviene Iowa: 56.794 USD más de valor actual que Pergamino"), from `best_region` and `npv_gap_to_next_usd`. A what-if: the change (`npv_change_vs_first_usd`). A plan: what to sow and the NPV.
2. **Then the plan**: hectares per crop, what is rented out ("das en alquiler 202,3 ha"; do not also call those hectares unsown), when to sell.
3. **Then what limits the farmer**: at most three bullets, in plain words.
4. **Last, "Lo que entendí"** in at most three lines: what is the farmer's, what comes from regional data, what is a model assumption (owned land, with the offer to recompute if rented).
5. **Return on capital only if the farmer asks** about returns, rates or "cuánto rinde la plata". When asked, quote return on capital and on capital and land with one sentence on why they differ (the second counts the land as capital) and the deposit rate next to the annualized figure.
6. **Never write parameter or field names** (`area_ha`, `npv_usd`, `rent_out_ha`) or JSON; say what they mean ("valor actual", "hectáreas que das en alquiler").
7. **No closing referral.** End with the next step the farmer can take with DORA, if any ("si es alquilado, decime y lo recalculo").
8. **"¿Qué podés hacer?" / "What can you do?"**: answer with the list below, **with no numbers at all** (any number there has no tool behind it), and end with what you need to start. Six short points: plan of sowing and sales; what limits you (money, land, storage) and what an extra dollar, hectare or tonne is worth; supplier terms and contracts; freight and storage, including keeping grain into next season with a quote; comparing regions; invoices, photos and the DORA screen. Then: "Para arrancar decime cuántas hectáreas tenés, dónde y con cuánta plata contás."

Replace the example in section 4.2 ("cada dólar extra te rinde 19,5 % en esos 9 meses") only if it conflicts with these rules; it does not need to change.

### Verifier (`dora/verifier.py`)
- `jargon(text) -> list[str]`: snake_case words (`\b[a-z]+(?:_[a-z0-9]+)+\b`) and back-ticked identifiers. They join the correction round with their own line in the message ("write these in plain words: …"). They do not change `verified`, which stays about numbers; `Reply.style_problems` lists what is left after the rounds, and E1 records store it.
- `correction_message` adds: "If you remove a number, rewrite the whole sentence so it still reads well; never leave an empty parenthesis or a sentence cut in the middle."

## Acceptance tests (`tests/test_spec27.py`, no network)
**q33 and the decision check**
1. `compare_regions` with the q33 payload returns `best_region == "iowa"`, `npv_gap_to_next_usd == 56794.01`, `regions.pampas_core.npv_gap_vs_best_usd == 56794.01`, `regions.iowa.npv_gap_vs_best_usd == 0`; every other field equals `main` (compare the full dict minus the new keys).
2. `sensitivity` rows have `npv_change_vs_first_usd`, 0 in the first row, and equal to the NPV differences.
3. `decision_named` with expected `iowa` among `["pampas_core", "iowa"]`: hit for "**Resultado: te conviene más Iowa.**", "Resultado - gana Iowa:", "Te conviene más Iowa que Pergamino", "Entre Pergamino e Iowa, te conviene Iowa"; miss for "1. **Iowa:** valor presente 432.584 USD\n2. **Pampas Core (Pergamino):** …" (no verdict), "Te conviene Pergamino", and a reply that names no region.
4. `eval/build_answers.py` gives `"expected_value": "iowa"` for q33; the other 38 answers are unchanged.

**The scenario check**
5. q13 text with `{"area_ha": 500, "own_capital_usd": 50000, "yields": {"soybean": 7.32}, "crops": ["soybean"]}` → one problem, on `crops`. Without `crops` → none.
6. q30 text with `{"area_ha": 50, "own_capital_usd": 50000, "region": "iowa"}` → a problem on `area_ha` (farmer wrote −50).
7. q17 text, `evaluate_season` with any scenario → "area_ha missing". `compare_regions` with `mode="same_budget"` and `{"own_capital_usd": 2000000}` for "Si tuviera 2 millones de dólares, ¿dónde compro campo?" → none.
8. No problems for: "Quiero sembrar solo soja y maíz en 300 ha" with `crops: ["soybean", "corn"]`, `area_ha: 300`; "Tengo 500 ha y 50 lucas, el banco me da hasta 100 al 10%" with `own_capital_usd: 50000`, `credit_line_usd: 100000`, `credit_rate_annual: 0.10`; "el proveedor me da 60 días" with `input_payment_delay_fortnights: 4`; "200 acres in Iowa" with `area_ha: 80.94`; a scenario whose numbers are only in the screen scenario.
9. **No false alarms on the eval set:** for every question in `eval/questions*.jsonl` with `expect != "refuse"`, `check_scenario` of its own `scenario` with its own text, and `build_scenario({})` as the only earlier tool result, gives no problems. If some question fails, do not loosen a rule to make it pass: list it in the handoff with the reason, and I decide.
10. Agent with a fake client: the model first calls `evaluate_season` with `crops: ["soybean"]` for q13, gets the `scenario_mismatch` error (and the engine is not called for it: patch `run_tool` and count calls), then calls without `crops` and answers. `Reply.scenario_rejections` has one item. With `use_verifier=False` the first call runs.

**The counter**
11. Refusal rule on stored replies (copy the texts into the test; runs counted from 1): the Standard C run 2 q30 reply ("I read `-50 hectares` as **50 ha**…", with `plan_hectares` `{"corn": 25.0, "soybean": 25.0}`) → miss; the Contributor C run 5 q30 reply ("I can't run that yet — you put **-50 hectares**, which isn't possible…") with no plan → hit; the Contributor C run 1 q17 reply ("Para seguir necesito que me digas: …?") with no plan → hit.
12. q06 with `hectares == {}` → `plan_given` True, `plan_feasible` True, `plan_gap_usd` 0. A q09 record with only `shadow_prices` → `plan_given` False, `plan_feasible` None, and not in `feasible_rate`.
13. q23 with a `sensitivity` call on `own_capital_usd` with values `[50000, 100000]` → plan `{"soybean": 235.6}` (the 100,000 row). An agent that solves the q06 scenario and then the same farm with `rented_land: false` → the plan of the first.
14. `eval/rescore.py` on the four B/C E1 files, run in the test only if they exist (skip otherwise), gives these correct runs (fixed numbers, read from the stored replies on 31/10):

   | | q33 | q17 | q30 |
   |---|---|---|---|
   | Standard B | 3 | 5 | 4 |
   | Standard C | 5 | 5 | 3 |
   | Contributor B | 5 | 5 | 4 |
   | Contributor C | 5 | 5 | 3 |

   and in every file `feasible_rate` counts no "no plan given" record as infeasible (q06's 5 runs become feasible plans).

**Answers**
15. `SYSTEM_PROMPT` contains neither "operations-research" nor "fortnight 29"; `modeling_guide.md` has section 0 with the eight rules; section 3 has the "ask without reciting assumptions" rule.
16. `build_scenario({})["scenario"]["area_ha"]["origin"] == "missing"`; `build_scenario({"area_ha": 300})` reports 300 from the farmer.
17. `jargon("Tuyo: `owned_ha` 500 ha, npv_usd 432584")` finds `owned_ha` and `npv_usd`; `jargon("432.584 USD, 2ª quincena de nov, USD/ha")` finds nothing. A fake-client answer with `area_ha` gets one correction round and `style_problems` is empty after it.
18. `correction_message` has the whole-sentence instruction.

The existing tests must pass unchanged, except where a test asserts the old `build_scenario` area report or the old refusal markers: change those and list them in the handoff.

## Live check (with the Meta key; costs cents, run once)
- `python chat.py`, ask "¿qué podés hacer?" three times (new session each): no numbers, no cut sentence, ends asking for hectares, place and money. Paste the three replies in the handoff.
- `python eval/run_eval.py --ids q01,q13,q17,q23,q30,q33 --runs 2`: paste the q33 and q01 replies in the handoff. q33 has to start with the decision and the gap; none of them has a field name, a return on capital, or the specialist referral. Report the correct runs per question.

## Handoff (`docs/handoff/spec-27-answers.md`)
What was done, with file and line; the `eval/rescore.py` table for the E1 files; the questions from test 9 that failed, if any; the live replies; and anything in this spec that turned out to be wrong.
