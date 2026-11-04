# SPEC-38: owned land can be rented out at the zone's rent, and DORA says when that beats farming it

**Status:** ready (3/11). Implement **after SPEC-36 is merged and before SPEC-37** (this one changes the engine's answers; SPEC-37 then shows them), on branch `spec-38-rent-out`, created from `main` at that point. Do not commit and do not merge: write the handoff and Claude reviews. Touch only `dora/scenario.py`, `dora/engine.py` (one bound, see 2), `dora/tools.py` (`evaluate_season` output and the parameter table), `dora/modeling_guide.md` (one paragraph), `app.py` (the advanced options and the plan text, see 5), `eval/answers_spec38.jsonl` (new), a new test file and the handoff. Do not edit `eval/answers.jsonl`, the README or the examples' numbers: Claude does that after review.

**Why.** Claude reviewed the Scenario tab on 3/11 with Guillermo's case (Pampas core, 2,000 ha owned, 500,000 USD own capital): the plan leaves **623.5 ha unsown** (31 % of the farm). The checkbox "Permitir alquilar hacia afuera" is ticked, but it does nothing: the rent an owner would receive (`regional_rent_usd_ha`) is loaded only when the farm itself is rented (`scenario.py:478`, `if self.rented_land and self.regional_rent_usd_ha <= 0`). For an owner it stays 0, so the `rent_out` variable (`engine.py:507`, income at fortnight 0) pays nothing and the land sits idle. With the zone's rent passed by hand, on `main` (live prices, 3/11):

| Case | Farming (today's answer) | With the zone's rent |
|---|---|---|
| Pampas core, 2,000 ha, 500,000 USD, rent 570 USD/ha (`land_pampas_core.json`, verified) | NPV 1,157,834.52; 623.5 ha idle | NPV 1,640,000.00; all 2,000 ha rented out |
| Southeast Buenos Aires, 500 ha, 50,000 USD, rent 350 USD/ha (`land_southeast_buenos_aires.json`, placeholder) | NPV 113,432.02; 123.1 ha idle | NPV 225,000.00; all 500 ha rented out |

The comment at `scenario.py:315` already says it: "with June-2026 margins, no crop pays the rent". An owner's land has a price even when the owner farms it: what someone else would pay to farm it. Leaving it out makes every owner's plan look better than it is, the "return on capital" of 117 % ignores the land, and the plan keeps land idle when it could be rented. Guillermo decided (3/11) to fix the engine, not just to show a comparison.

## 1. The owner's rent (`dora/scenario.py`)
In `__post_init__`, where `regional_rent_usd_ha` is set today (line ~478), change the condition so the rent is loaded **whenever there is land to rent in or out**:
```python
needs_rent = self.rented_land or self.max_rent_in_ha > 0 or (self.allow_rent_out and self.owned > 0)
if needs_rent and self.regional_rent_usd_ha <= 0:
    ... same order as today: land file if not placeholder; else the source's rent (max over crops); else land file placeholder
```
Record where it came from in a new field `regional_rent_source: str` (`"farmer"` when the scenario passes `regional_rent_usd_ha`, `"land file: <source>"`, `"<budget file> rent"`) and `regional_rent_placeholder: bool` (True when it came from a placeholder land file). Keep `regional_rent_usd_ha` as a scenario parameter the farmer can set ("me pagan 12 quintales" → the model converts with the soybean price and passes it).

Note for Southeast Buenos Aires: the land file is a placeholder (350), so the order above takes the MAGyP budget's rent (425.1). Say in the handoff which rent each region ends up with.

## 2. Engine (`dora/engine.py`)
- `_optimize_stochastic` (line ~1897) bounds `rent_out` with `sc.owned` without checking `allow_rent_out`; use the same bound as `optimize` (line 915): `(0, sc.owned if sc.allow_rent_out else 0.0)`.
- **Part farmed, part rented out (Guillermo, 3/11: "puede hacer una parte sembrada y la otra alquilarla").** The `rent_out` variable is already continuous between 0 and the owned hectares, so the plan can mix. Add one scenario parameter `max_rent_out_ha` (float, optional; default = no limit beyond the owned land) for a farmer who wants to keep farming at least part: bound `rent_out` with `(0, min(sc.owned, max_rent_out_ha) if sc.allow_rent_out else 0.0)` in both `optimize` and `_optimize_stochastic`. In the app, a field `Alquilar como máximo (ha)` next to the rent field (empty = no limit). Guide: "quiero sembrar al menos 300 ha" → `max_rent_out_ha = owned − 300`. Test: Pampas core 2,000 ha with `max_rent_out_ha: 1000` rents out at most 1,000 ha and farms or leaves idle the rest, and its NPV lies between the farm-only and the free plan.
- Nothing else. The rent is received at fortnight 0 net of the transaction tax (`engine.py:507`); the owner still pays the land tax (`engine.py:525`). Write in the handoff that this is the model (rent paid in advance, the usual Argentine contract) and leave it.

## 3. `evaluate_season` output (`dora/tools.py`)
Add:
- `regional_rent_usd_ha`, `regional_rent_source`, `regional_rent_placeholder`;
- `rent_out_income_usd` = `rent_out_ha * regional_rent_usd_ha` (gross);
- `tenure_comparison`, only when `owned > 0` and `regional_rent_usd_ha > 0`, computed with two extra solves of the same scenario:
  - `farm_only_npv_usd`: `allow_rent_out = False` (what today's code answers);
  - `rent_all_npv_usd`: every crop and livestock activity capped at 0 ha (`max_area` 0 for each crop; no livestock), `allow_rent_out = True`;
  - `best`: `"farm"`, `"rent_out"` or `"mix"` from the main plan (`rent_out_ha` 0, = owned, or in between);
  - `gain_vs_farm_only_usd` = main NPV − `farm_only_npv_usd`.
  If either extra solve fails, leave that key out and add `tenure_comparison_error`. Pass `tenure_comparison: false` in the scenario to skip it (the eval scripts and `compare_regions` skip it to save time; the app and the chat keep it on).
- The `return_on_capital_and_land` figures (already in `Result.summary`) must use the rent as the land's yearly cost when `land_price_usd_ha` is 0 and the rent is known: say in the handoff which formula you used and show it for Guillermo's case. If this needs an engine change beyond a formula in `summary`, stop and ask in the handoff instead.

## 4. Guide (`dora/modeling_guide.md`)
One paragraph in the section about land and tenure:
```
**Owned land has a rent.** An owner can farm the land or rent it out at the zone's rent (`regional_rent_usd_ha`, from the land file or the margins report). The plan chooses. When `rent_out_ha` > 0, say it first: how many hectares to rent out, at what rent, and `tenure_comparison` (farming only gives `farm_only_npv_usd`, renting everything gives `rent_all_npv_usd`). If the rent is a placeholder (`regional_rent_placeholder`), say it is an estimate and ask what they would get. If the farmer says they do not want to rent out, pass `allow_rent_out: false`. If they say what they would be paid, pass `regional_rent_usd_ha`.
```

## 5. App (`app.py`)
- Advanced options: next to "Permitir alquilar hacia afuera", a number field `Alquiler que te pagarían (USD/ha)`, empty by default, with the placeholder text showing the zone's value and source (`Zona: 570 USD/ha (Márgenes Agropecuarios, 2025/26)`). Empty = the zone's rent; a number = `regional_rent_usd_ha`.
- Plan text, right under the hectares: when `rent_out_ha` > 0, `- **Dado en alquiler:** {ha} ha a {rent} USD/ha ({income} USD)`; and when `tenure_comparison` is there, one line: `Sembrando todo lo que alcanza: VAN {farm_only}. Alquilando todo: VAN {rent_all}. El plan elige {lo mejor}.` (es; en analogous). If the rent is a placeholder, add `(alquiler estimado: cargá el tuyo en Opciones avanzadas)`.
- The three "¿Cómo empiezo?" examples and the "Empezá acá" cards: run them after the change and paste what they give in the handoff. **Do not change them**; Claude and Guillermo decide (they may become "si lo sembrás vos" examples with `allow_rent_out: false`).

## 6. What changes in E1 (offline, no model calls)
Regenerate the expected answers into a new file, without touching `eval/answers.jsonl`:
```
python eval/build_answers.py --output eval/answers_spec38.jsonl
```
(add `--output` if the script does not have it; default unchanged). Then a table in the handoff: question id, field, old expected value, new expected value, and whether the plan now rents land out. Also run the SPEC-20/25/26/30 question files the same way if `build_answers.py` takes `--questions` (it reads `questions.jsonl` by default). **Do not re-run any model.** Claude decides what to re-run from that table.

## Tests (`tests/test_spec38.py`, no network: use `price_curve_source: "magyp_june"` or the fixture the other engine tests use)
1. Owned 500 ha Southeast Buenos Aires, 50,000 USD: `regional_rent_usd_ha > 0`, `regional_rent_source` names the budget file, `regional_rent_placeholder` as decided in 1.
2. Same with `allow_rent_out: false`: NPV, hectares and sales **equal to the current `main`** (store the values from `main` in the test before changing code). This is the regression guard: the old answer is still available.
3. Same with `regional_rent_usd_ha: 0.01`: no land rented out (rent too low), plan equal to test 2.
4. Same with `regional_rent_usd_ha: 2000`: all 500 ha rented out, `best == "rent_out"`, NPV = own capital + 500 × 2000 × (1 − transaction tax rate) − land tax × 500, to the cent (rent and land tax fall in fortnight 0, so nothing is discounted; with the default scenario both taxes are 0: on `main` on 3/11, 500 ha at 350 gave exactly 225,000 = 50,000 + 500 × 350). Write the formula in the test.
5. `tenure_comparison.farm_only_npv_usd` equals test 2's NPV; `rent_all_npv_usd` equals the NPV of the scenario with every crop capped at 0.
6. Pampas core 2,000 ha, 500,000 USD: `rent_out_ha + sum(hectares) + unsown_ha == 2000` (± 0.1), and the NPV is ≥ test-2-style farm-only NPV (renting is an option, never a loss).
7. A rented farm (`rented_land: true`, no owned land): output unchanged from `main` (store values) and no `tenure_comparison`.
8. `_optimize_stochastic` with `allow_rent_out: false` rents nothing.
9. App: with a hand-made `evaluate_season` result (rent_out 623.5 ha, rent 570, comparison present) the plan text has `Dado en alquiler: 623,5 ha a 570 USD/ha` and the comparison line; with `regional_rent_placeholder: true` it has `alquiler estimado`.

Full suite as in SPEC-35. Some existing tests will fail because they expect today's owner plans: **do not edit them to pass**. List each failing test with its old and new value in the handoff, and pass `allow_rent_out: false` in that test's scenario only if the test is about something else (capital, contracts, storage) and say so per test. Restore the price files before handing off:
```
git checkout -- dora/data/price_curves/ dora/data/basis_*.json
```

## Handoff (`docs/handoff/spec-38-rent-out.md`)
The rent each region ends up with and its source; Guillermo's case before and after (hectares, rented out, NPV, the comparison line, returns); the examples' results; the E1 table from 6; the list of existing tests that changed and why; test output. Do not mark anything as passed unless its output proves it.

## Claude's review (4/11 00:45)
Engine part approved: the 9 tests pass (re-run by Claude in a clean worktree of 3ffd526), and test 2 reproduces `main` exactly (NPV 88,186.60 = old q04). Fix these on `spec-38-rent-out` before going on with SPEC-39 (then rebase or merge `spec-38-rent-out` into `spec-39-break-even-prices`):
1. **The 79 failing tests.** The spec asked for each one by name, with old and new value, and for `allow_rent_out: false` in the tests that are about something else. Do that now: storage, duals and taxes, sowing windows and climate, carryover, livestock and contracts are about something else, so add `allow_rent_out: False` to those tests' scenarios (only that key; no expected value edited). For `test_demo_guide.py` and any test whose subject is the plan itself, do not edit it: list it in the handoff with old and new value. Target: the full suite passes except that list. Paste the real suite output.
2. **"Pico de crédito utilizado: USD 0 (None)".** When the peak credit is 0, write `Pico de crédito utilizado: USD 0` without the fortnight (es and en).
3. **Return on capital and land.** Do not capitalize the rent at the deposit rate (570/0.04 = 14,250 USD/ha is not a land price). When `land_price_usd_ha` is 0 and the rent is known, report instead `return_over_land_rent_pct` = (NPV − own capital − owned_ha × rent × (1 − transaction tax)) / own capital: what farming adds over renting the land out. It is 0 when the plan rents everything. Show it for Guillermo's case in the handoff.
4. Do not change the examples or `eval/answers.jsonl`: Guillermo decides tomorrow (almost every E1 answer changes, see the table).
Log the fix in `noche-3-11.md` with the new suite numbers.

## Claude's review (4/11 07:50): Guillermo's decision, replaces point 1 and 4 of the 00:45 review
Guillermo (4/11): many owners do rent the land out, but DORA is for the farmer who sows; the plan must say what is best **if he farms it** (crops or livestock), and tell him what renting would give. Renting is a comparison and an option he asks for, not the default.
1. **Default `allow_rent_out = False`** in `Scenario` (and in the app's checkbox, unticked). With it, every existing test, the E1 answers and the examples give the same as `main`: the 79 failures should go away without editing them. The `allow_rent_out=False` you added to tests can stay (harmless). Do not run `build_answers.py` over `eval/answers.jsonl`: restore it (`git checkout -- eval/answers.jsonl`); `eval/answers_spec38.jsonl` stays as the record of the rent-out case.
2. **The rent is loaded whenever `owned > 0`** (and in the cases already in the spec), so the comparison can be computed with the default.
3. **`tenure_comparison` is computed with the default too** (owned > 0, rent > 0), with one extra solve (`rent_all_npv_usd`; `farm_only_npv_usd` is the main plan's NPV when `allow_rent_out` is false). Add:
   - `break_even_rent_usd_ha` = (farm_only_npv_usd − rent_all_npv_usd) / (owned_ha × (1 − transaction_tax_rate)) + regional_rent_usd_ha: the rent above which renting everything beats farming;
   - `renting_pays_more` = rent_all_npv_usd > farm_only_npv_usd.
   Test: with that rent passed as `regional_rent_usd_ha` and `allow_rent_out: True`, the plan's NPV equals farm_only within 1 USD.
4. **Plan text (app):** when the plan farms and `tenure_comparison` is there: `Si alquilaras todo a {rent} USD/ha: VAN {rent_all} ({diff:+} USD). Alquilar conviene si te pagan más de {break_even} USD/ha.` If the rent is a placeholder, add `(alquiler estimado: cargá el que te ofrecen en Opciones avanzadas)`. When the farmer ticks "Permitir alquilar hacia afuera", the plan may rent out and the lines of 5 apply as written.
5. **Guide paragraph:** replace the one in the spec with: "**Farm or rent out.** By default the plan farms the owner's land (crops or livestock). Always quote `tenure_comparison`: what renting everything would give and `break_even_rent_usd_ha`. If the farmer asks whether to farm or rent, or says he would rent part, call `evaluate_season` again with `allow_rent_out: true` (and `max_rent_out_ha` if he wants to keep part) and say what the plan chooses. The rent is what they agree with the tenant: if `regional_rent_placeholder` is true or the farmer has an offer, ask for it and pass `regional_rent_usd_ha`."
6. Points 2 and 3 of the 00:45 review still apply (credit label; `return_over_land_rent_pct` instead of capitalizing the rent).
7. Re-run the 3 examples and Guillermo's case and paste them: they must equal `main`, plus the new comparison line. Full suite must pass (paste it). Then commit on `spec-38-rent-out`, log it in `noche-3-11.md`, and carry it into `spec-39-break-even-prices` before SPEC-39 (SPEC-39 test 6 uses `allow_rent_out: true` explicitly).
