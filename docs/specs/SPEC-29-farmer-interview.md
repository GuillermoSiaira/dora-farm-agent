# SPEC-29: The farmer interview — one question at a time, the one that changes the decision most

**Status:** draft (31/10), to implement on branch `spec-29-interview`, created from `main` **after SPEC-27 and SPEC-28 are merged**. It uses SPEC-27's answer format (section 0 of the modeling guide), its scenario check and its `jargon()` style check, and SPEC-28's per-region scenario helper in `compare_regions` (item 1). Do not merge into `main`; it gets reviewed first. The engine's equations do not change. Most of the work is a new file, `dora/interview.py`, so it conflicts little with 27 and 28.

**No number is typed by hand.** Every number below was read from a tool run on `main` at `dd95fb0` (31/10). The tests compute their expected values from the tools, except the design constants in section 2, which are fixed on purpose and stated as such.

## Why
Guillermo asked DORA in `chat.py` (31/10): "¿te conviene pedirme más información para armar el plan óptimo de Pergamino y Balcarce? Preguntame lo que necesites". DORA said well what it had assumed and where each number came from, and then asked **ten questions at once**. The question that mattered most ("¿mismo campo o misma plata?") was the last one. Other problems in that reply: yields with no crop name ("4,5 / 9,5 / 3,8 / 2,4"), variable names (`pampas_core`), and 54 s and about 100,000 tokens for one answer.

Ten questions at once tell the farmer that DORA does not know which one matters. DORA does know, or can find out: the engine can measure how much each unknown is worth.

### What the engine says, on two farms
Two cases, run on `main`. The second one is close to Guillermo's (the numbers from that chat were not saved).

**A. A plan: Balcarce, 500 ha, 50,000 USD own capital** (everything else is a default). The plan is wheat 121.7 ha and soybean 250 ha, NPV 88,186.6 USD. For each thing DORA assumed, the table shows what happens if the truth is different and the farmer follows this plan anyway (`evaluate_plan` with the plan's hectares fixed):

| DORA assumed | If the truth is… | What following the plan costs |
|---|---|---|
| owned land | rented | the plan cannot be carried out |
| credit line 100,000 USD | no credit | the plan cannot be paid: 99,543 USD short |
| — | 200,000 USD | 7,694 USD less than the best plan |
| own capital 50,000 USD (the farmer's) | — | not asked: the farmer said it |
| supplier pays now | 90 days | 5,803.36 USD less than the best plan |
| storage 1,000 t | none, or 2,000 t | nothing (0) |
| land may be rented out | it may not | nothing (0) |

Shadow prices of the same plan: capital 0.1608 USD per extra dollar, land 37.73 USD per extra hectare, credit 0.1128, storage 0. They agree with the table where they can speak (storage is worth 0, and no storage answer changes the plan), but they cannot rank the questions alone: they are marginal (one more dollar, not "no credit at all"), they come in different units, and tenure or supplier terms have no shadow price.

So the order is: tenure, credit, supplier terms. Storage and renting out are never asked. That is the interview Guillermo described, and it comes out of the model, not a fixed list.

**B. A comparison: Pergamino or Balcarce, 500 ha, 100,000 USD own capital, `same_farm`.** Pergamino wins, 375,790 against 266,450 USD (gap 109,340). But in both regions the best plan sows **nothing** and rents out all 500 ha (regional rent 570 and 350 USD/ha). The farmer asked where to sow; DORA answers "where your land is worth more as rent". Then:
- No answer about money, credit, storage or supplier terms changes the winner or the plan: Pergamino's NPV moves only by the capital itself (325,790 with 50,000; 475,790 with 200,000), and the plan stays "rent everything out". Asking about money here is noise.
- If the farmer wants to farm the land (`allow_rent_out: false`), Pergamino still wins and sows 400.6 ha (NPV 237,569.38 against 130,056.03), and following the plan "rent everything out" would leave the land empty: the largest loss in this case (the test computes it with `evaluate_plan`).
- If the land is rented, neither region pays: both end with the 100,000 USD they started with and sow nothing.
- With `same_budget` (the same 100,000 USD to buy or rent land), both regions also end at 100,000.

So in case B the first question is not about money but "¿lo querés trabajar vos, o lo darías en alquiler?", and DORA has to say up front that its answer means renting out. Guillermo's "mismo campo o misma plata" comes before it, because it changes what the comparison means (section 3, rule 2).

## 1. What changes for the farmer
- **One question per reply**, the one whose answer changes the decision most.
- **Every question says what DORA does if the farmer does not know**: "si no sabés, sigo con 100.000 USD de crédito, que es lo típico de la zona".
- **Every answer is recomputed, and the reply says what changed** in one line before the next question: "con el campo alquilado no conviene sembrar en ninguna de las dos: terminás con los 100.000 USD con que arrancaste".
- **The interview stops by itself** when nothing left to ask changes the plan by more than 1 % of its value (section 2), and says so: "lo demás que no sé no te cambia el plan".
- **It is offered, not imposed.** After an answer built on assumptions, the last line offers it ("si querés, te hago unas preguntas, de a una, empezando por la que más cambia el resultado"). It starts when the farmer accepts or asks to be asked ("preguntame lo que necesites", "¿necesitás más datos?", "ask me"). The one exception is a missing farm size (SPEC-27, q17): that question is asked right away, as today.

## 2. The tool: `next_question` (`dora/interview.py`)
`next_question(scenario, asked=[], compare=None, previous=None, lang=None) -> dict`, registered in `TOOLS` and `TOOL_SCHEMAS` like the others.
- `scenario`: the farmer's scenario so far (only what the farmer said, as in `build_scenario`).
- `asked`: ids of questions already asked (answered or "no sé"). The agent fills it (section 4); the model may omit it.
- `compare`: `{"regions": [...], "mode": "same_farm" | "same_budget", "mode_given": bool}` when the farmer compares regions; `null` for a plan.
- `previous`: the scenario of the previous `next_question` call in this conversation. The agent fills it.

### Candidates
A fixed catalog in `interview.py`. Each entry: `id`, the scenario parameter(s) it is about, the alternatives it tests, and the question in es and en (templates with **no numbers**; numbers are filled in from the scenario or the results). A candidate is skipped when the farmer already gave its parameter (`build_scenario` origin `farmer`) or its id is in `asked`.

| id | Asks | Alternatives tested (design constants) |
|---|---|---|
| `area` | ¿Cuántas hectáreas tenés? | none: **blocking**, asked first whenever `area_ha` and `owned_ha` are missing (except `same_budget`) |
| `compare_basis` | ¿Comparás con el mismo campo en los dos lugares, o con la misma plata para comprar o alquilar campo en cada uno? | none: **blocking** in a comparison when `compare.mode_given` is false |
| `tenure` | ¿El campo es tuyo o alquilado? | `rented_land` flipped |
| `rent_out` | ¿Lo querés trabajar vos, o lo darías en alquiler si conviene más? | `allow_rent_out: false`; only when the current plan rents land out |
| `own_capital` | ¿Con cuánta plata propia arrancás la campaña? | half and double of the current value |
| `credit_line` | ¿Hasta cuánto te presta el banco? | 0 and double |
| `supplier_terms` | ¿A cuántos días te deja pagar los insumos tu proveedor? | 6 fortnights (90 days, the example in `PARAMETERS`) |
| `storage` | ¿Cuántas toneladas podés guardar, en silo o silobolsa? | 0 and double |

The alternatives (half, double, zero, 90 days) are design choices, not data: they stand for "the farmer's answer could be quite different". They go in one dict, `ALTERNATIVES`, and the output reports the value tested, so every number the agent quotes comes from the tool. Widen the catalog (yields, prices, sowing capacity) only with a failing case in hand.

### What it measures: what the farmer loses if DORA answers without asking
For each candidate and each alternative `A`:
- **Plan** (`compare` is null): solve the current scenario (the plan DORA would give now), then `evaluate_plan(scenario + A, that plan's hectares)`.
  - not feasible → `infeasible: true`, with `shortfall_usd` = `extra_credit_needed_usd` when the cash is what falls short;
  - feasible → `regret_usd` = `gap_usd` (best plan under `A` minus this plan under `A`).
- **Comparison**: per region, the scenario as `compare_regions` builds it (SPEC-28's helper; do not duplicate it). The current winner `w` and its plan; under `A`, `regret_usd` = best NPV over the regions under `A` minus `evaluate_plan(region w scenario + A, w's plan)` NPV. That counts both a wrong region and a wrong plan in the right region. Also report `winner_under_alternative`, and `infeasible` as above.

`evaluate_plan` fixes only the crops' hectares; the engine still decides sales, credit and renting land out. So `regret_usd` is a floor of the true loss, as `plan_check.py` already says.

The candidate's score is its worst alternative: infeasible beats any regret; among infeasible ones, "cannot be carried out" (no `shortfall_usd`) comes first, then the larger shortfall; then the larger `regret_usd`.

### Order and stop
1. A blocking candidate (`area`, then `compare_basis`), if any.
2. Otherwise the best score. If that score is feasible and `regret_usd` < `STOP_SHARE` × |NPV of the current plan| (in a comparison, of the winner), the interview is done.
3. Also done after `MAX_QUESTIONS` questions in `asked`.

`STOP_SHARE = 0.01` and `MAX_QUESTIONS = 5` are design constants.

### Output (keep it short: it goes into the conversation every turn)
```json
{
  "done": false,
  "next": {
    "id": "credit_line",
    "question": "¿Hasta cuánto te presta el banco?",
    "if_unknown": {"parameter": "credit_line_usd", "value": 100000.0, "origin": "model assumption"},
    "why": {"alternative": {"credit_line_usd": 0.0}, "infeasible": true, "shortfall_usd": 99543.0,
            "shadow_price": {"resource": "credit_line", "usd_per_extra_dollar": 0.1128}}
  },
  "current": {"npv_usd": 88186.6, "hectares": {"wheat": 121.7, "soybean": 250.0},
              "rent_out_ha": 0.0, "winner": null, "gap_usd": null},
  "change": null,
  "ranking": [ {"id": "...", "score": {...}}, "... at most three, after next" ],
  "stop_threshold_usd": "STOP_SHARE × |current NPV|, computed by the tool"
}
```
- `why.shadow_price`: the shadow price of the resource the question is about (capital, credit, land, storage), from `shadow_prices` on the current scenario; omitted for tenure, renting out and terms. The agent uses it to explain the question in plain words ("cada dólar más de crédito hoy te vale 11 centavos").
- `change` (when `previous` is given): `npv_before_usd`, `npv_after_usd`, `npv_change_usd`, `hectares_before`, `hectares_after`, `winner_before`, `winner_after`, `gap_before_usd`, `gap_after_usd`, and `limit_before` / `limit_after`: what limits the farmer, as the first capital stretch (`start_fortnight`, `end_fortnight`, `rate_for_stretch_pct`) when capital's shadow price is above 0, else land, else storage, else `null`. That gives the line "ahora te limita la caja de octubre a marzo".
- When `done`: `next` is null and `done_reason` is `"below_threshold"` (with the largest regret left) or `"max_questions"`.
- Region ids never go out bare: each region carries its `name` from `REGIONS` ("Pampas Core (Pergamino)").

## 3. Rules the agent follows
### Modeling guide, new section 7 "The interview"
1. Call `next_question` and ask **only** `next.question`, in your own words, with what you do if the farmer does not know (`if_unknown`, saying whose value it is: "lo típico de la zona", "un supuesto del modelo").
2. In a comparison, ask first whether it is the same farm or the same money, unless the farmer said it ("tengo 500 ha", "si tuviera 2 millones…"); pass `mode_given` accordingly.
3. With the farmer's answer, put it in the scenario and call `next_question` again. Open the reply with one line from `change` (what changed in USD, in the plan, in what limits the farmer), then the next question.
4. "No sé" keeps the default; go on to the next question.
5. When `done`, give the final answer in the section 0 format (SPEC-27), and say in one line that what is left unknown does not change the plan.
6. Never list several questions. Never ask about something `next_question` did not return.
7. When a comparison's winner rents out all the land, say it in the first line ("en las dos conviene alquilar el campo; en Pergamino el alquiler vale más") and ask `rent_out` before anything else that is not blocking.
8. Every yield, price or cost goes next to its crop's name ("trigo 4,5 t/ha"), never as a bare series.

The system prompt adds one line: "If the farmer asks you to ask, or accepts your offer, interview with next_question (modeling guide, section 7): one question per reply."

### Scenario check (SPEC-27, section 3)
Add `next_question` to the tools it checks, with one exception: a missing farm size is not a problem for `next_question` (the tool answers with the `area` question). The alternatives it tries are the tool's own and are not checked.

## 4. The agent keeps the interview's state (`dora/agent.py`)
The model should not have to remember which questions it asked.
- `Agent.interview = {"asked": [], "previous": None}`.
- Before running `next_question`, the agent sets `asked` to the union of its list and the model's, and `previous` to its stored scenario. After the call, it adds `next.id` to `asked` and stores the call's `scenario`.
- `Reply.interview` = `{"asked": [...], "next_id": ..., "done": ...}` when `next_question` was called in this turn; E7 stores it.

## 5. Checks on the reply (`dora/verifier.py`)
They join SPEC-27's style round (they do not change `verified`, which stays about numbers):
- **One question.** If `next_question` ran in this turn and the reply has more than one `?`, the correction message says: "Ask only the question next_question returned; remove the others." `Reply.style_problems` lists it if it remains.
- **Bare series.** `unnamed_series(text)`: three or more numbers with decimals separated by `/` (`\d+[.,]\d+\s*/\s*\d+[.,]\d+\s*/\s*\d+[.,]\d+`) → "say which crop each number is". Dates have no decimals and do not match.

## 6. E7: the interview with a simulated farmer (`eval/run_e7.py`)
An experiment, with its sheet and page like the others, run once SPEC-29 is merged.
- **Cases** (`eval/e7/farms.jsonl`): case A, case B, and two more written by the implementer from E1 questions (one with credit, one with supplier terms), each with an opening message and a **hidden farm**: the full scenario the farmer knows but did not say (some parameters may be missing on purpose: the farmer answers "no sé").
- **Simulated farmer**: deterministic, no model. It reads the `next.id` that `next_question` returned in that turn (from `Reply.interview`), and answers from a template per id with the hidden value ("es alquilado", "el banco me presta hasta 30 lucas", "no sé"). If the turn called no `next_question`, it answers "seguí".
- **Ground truth**: the decision on the hidden farm, from the tools (winner and plan; the plan's hectares within 1 ha).
- **Measures**, per case and run (3 runs, Muse Spark 1.3 Standard, DORA complete): questions until the plan or winner equals the hidden farm's; replies with more than one question; questions that say what DORA does if the farmer does not know; did it stop by itself; tokens and seconds per turn.
- **Baseline**: the opening message on `main` before SPEC-29, one turn: how many questions in the first reply (Guillermo's chat had ten).
- It costs a few cents with Standard; run the pilot (one case, one run) first and paste it in the handoff.
- The sheet ends with "Qué aprendimos", as all sheets.

## Acceptance tests (`tests/test_spec29.py`, no network)
**The tool**
1. Case A (`{"area_ha": 500, "own_capital_usd": 50000, "region": "southeast_buenos_aires"}`): the order of `next.id` over successive calls (adding each id to `asked`, the scenario unchanged) is `tenure`, `credit_line`, `supplier_terms`, then `done` with `done_reason == "below_threshold"`. `own_capital` is never asked (the farmer gave it); `storage` and `rent_out` never come up. The `credit_line` question reports `infeasible: true` and `shortfall_usd` equal to `evaluate_plan`'s `extra_credit_needed_usd` for the same plan and `credit_line_usd: 0`.
2. Case B (`{"area_ha": 500, "own_capital_usd": 100000, "region": "pampas_core"}`, `compare = {"regions": ["pampas_core", "southeast_buenos_aires"], "mode": "same_farm", "mode_given": false}`): the first `next.id` is `compare_basis`. With `mode_given: true`, it is `rent_out`. `own_capital`, `credit_line`, `storage` and `supplier_terms` have `regret_usd == 0` and no `infeasible`. `current.rent_out_ha` equals the area.
3. No area and no `compare` → `next.id == "area"` and no season is solved (patch `optimize`, count 0 calls).
4. `change`: case A with `previous` = case A and `scenario` = case A + `credit_line_usd: 0` → `npv_change_usd` equals `evaluate_season`'s difference between the two, and `hectares_after` equals the second plan's.
5. Every number in the output is in the tools' results or in the scenario: run `verify()` on `json.dumps(output)` with the tool results as support → no problems. Output has no bare region id outside the `id` fields.
6. `MAX_QUESTIONS`: with five ids in `asked`, `done` with `done_reason == "max_questions"`.
7. Determinism: the same input gives the same output twice (compare the dicts).

**The agent and the checks**
8. Fake client: the model calls `next_question` without `asked`; the agent fills it; on the second call the first id is in `asked` and `previous` is the first scenario. `Reply.interview.asked` has both ids.
9. A reply with two `?` after a `next_question` call gets one correction round; a reply with two `?` without `next_question` does not.
10. `unnamed_series("4,5 / 9,5 / 3,8 / 2,4")` finds one; `unnamed_series("trigo 4,5 t/ha, maíz 9,5 t/ha")` and `"4/11/2026"` find none.
11. The scenario check lets `next_question` through with no area, and still rejects it with `crops: ["soybean"]` on the q13 text (SPEC-27 rule 3).
12. `modeling_guide.md` has section 7 with its eight rules; the system prompt has the interview line.

The existing tests must pass unchanged.

## Live check (with the Meta key; costs cents, run once)
- `python chat.py`: "Tengo 500 ha y 100 lucas. ¿Me conviene más Pergamino o Balcarce? Preguntame lo que necesites." Answer each question as a farmer would, three to five turns. Paste the whole conversation in the handoff. Each reply: one question, with what DORA does if the farmer does not know, and from the second reply on, one line of what changed. No region ids, no bare series.
- Note the seconds and tokens of each turn (`chat.py` shows them) next to Guillermo's 54 s and ~100,000 tokens.
- E7 pilot (section 6).

## Handoff (`docs/handoff/spec-29-interview.md`)
What was done, with file and line; the order of questions for the four E7 cases as the tool gives it; the live conversation; the E7 pilot; and anything in this spec that turned out to be wrong (in particular, whether the "rent everything out" result of case B should change how `compare_regions` is explained, which is a question for Guillermo, not something to fix here).
