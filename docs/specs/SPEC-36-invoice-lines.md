# SPEC-36: each invoice line to its crop and cost item, compared with the zone, replaced, re-planned, shown before and after

**Status:** ready (3/11), to implement on branch `spec-36-invoice-lines`, created from `main` at the commit that adds this spec. Do not commit and do not merge: write the handoff and Claude reviews. Touch only `dora/tools.py` (`record_document` and one helper), `dora/schemas.py` (the `record_document` schema), `dora/modeling_guide.md` (section 2), `app.py` (the reconciliation block after a `record_document` call), `eval/run_e3.py`, `eval/e3/real_cases.json` (new fields only), two existing tests named below, a new test file, a new card and the handoff. No engine, verifier or agent-loop changes.

**Why.** SPEC-34 showed that DORA reads real invoices well (4 of 5 amounts exact) but loses lines when one invoice has two items: r2 (soybean seed + glyphosate) loaded only the seed, r4 (anhydrous ammonia + seed corn) loaded only the fertilizer, r3 (two maize herbicides) loaded nothing and asked. Reading `record_document` (`dora/tools.py:1311`) explains most of it in code, not in the model:
1. **Lines of the same item are not added up.** Urea and MAP each become a separate `wheat.fertilizer` proposal with its own USD/ha; `replaces` gets two entries for the same coefficient and whichever one the model copies wins.
2. **Active ingredients are not recognised.** `_normalize_concept` maps "herbicid…" but not "Glifosato", "Atrazina" or "Dual Gold (S-metolacloro)": those lines get `cost_item = None` and are dropped silently. The schema has no `cost_item` field, so the model cannot say it either (tests already pass `cost_item`, and the code ignores it).
3. **A line with no crop becomes wheat** when the plan has several crops (`else: crop_name = "wheat"`): a silent guess.
4. **Herbicides are only part of crop protection.** The zone value (`crop_protection`) covers herbicides, insecticides and fungicides; replacing it with a herbicide-only invoice lowers the cost without saying so.
5. **Nothing is re-planned.** The tool returns proposals; the model must then copy them into `costs_override` and call `evaluate_season` again, which it did inconsistently (SPEC-34 NPV misses), and which costs rounds (SPEC-35).

The goal: the farmer sends an invoice and gets, in one tool call, a table with each line, its crop and its cost item, the zone value next to the invoice value, which ones were used and why, and the plan before and after with the difference in NPV. Every number comes from the tool.

## 1. Schema (`dora/schemas.py`, `record_document`)
Add to each item's `properties`:
```python
"cost_item": {"type": "string",
              "enum": ["seed", "fertilizer", "crop_protection", "field_operations", "rent", "tax", "other"],
              "description": "Cost item this line belongs to. 'tax' for VAT (IVA), perceptions or sales tax lines; "
                             "'other' if it is not a farm input cost."},
"covers_whole_item": {"type": "boolean",
                      "description": "Only for crop_protection: true when the farmer confirmed this invoice is all the "
                                     "crop protection for that crop (herbicides, insecticides and fungicides)."},
```
Change the `concept` description to: `"The line's text as written on the invoice. One item per invoice line: never merge or drop lines."`. Add `"lang": _LANG` to the top-level properties. Do not make the new fields required.

## 2. `record_document` (`dora/tools.py`)

### 2.1 Cost item of a line
Order of precedence:
1. `it["cost_item"]` if it is one of the enum values (`"other"` → `None`, `"tax"` → excluded, see below).
2. Otherwise `_normalize_concept(concept)`, extended. Checks in this order (accent- and case-insensitive, as today):
   - **tax:** whole word `iva` or `vat`, or `percepci`, `sales tax`, `impuesto` → `"tax"`.
   - **crop_protection** (before fertilizer, so "Glifosato" is not caught by anything else): today's words plus `glifosat`, `glyphosat`, `atrazin`, `metolaclor`, `metolachlor`, `dual gold`, `2,4-d`, `2,4 d`, `dicamba`, `paraquat`, `cletodim`, `clethodim`, `haloxifop`, `haloxyfop`, `imazet`, `fomesaf`, `sulfentraz`, `diclosulam`, `flumioxazin`, `cipermetrin`, `cypermethrin`, `clorpirif`, `lambdacialot`, `azoxistrob`, `azoxystrob`, `tebuconaz`, `post-emergence`, `pre-emergence`, `preemergent`, `postemergent`.
   - **fertilizer:** today's words plus `amoniaco`, `ammonia`, `nitrog`, `uan`, `potas`, `kcl`, `sulfato de amonio`, `superfosfato`, `npk`, `nitrato`. Keep `map` and `dap` as **whole words** only (today `"map"` is a substring test: change it to `re.search(r"\bmap\b|\bdap\b", c_clean)`).
   - seed, field_operations, overhead, rent: as today.
3. Lines whose cost item is `"tax"` are kept in `lines` with `"excluded": "tax"` and add nothing: costs are net of VAT (an Argentine "Responsable Inscripto" recovers the IVA; US farm inputs are tax-exempt). Lines with no cost item are kept with `"excluded": "unknown item"` and their concept goes into `missing` as `"missing: cost item for '<concept>'"`.

### 2.2 Crop of a line
- `it["crop"]` translated as today.
- If missing: the scenario's crop when the scenario has exactly one crop; otherwise **`None`**, and add `"missing: crop"` to `missing` once. Delete the `else: crop_name = "wheat"` branch.
- A crop that is not in the scenario's crops: keep the line, `"excluded": "crop not in plan"`.

### 2.3 Hectares
As today (per-line `area_ha`, else the invoice's hectares line, else the field area labelled `per_ha_basis = "superficie del campo (no venía en la factura)"`, else `missing: hectares`). Per line, compute `usd_ha` exactly as today.

### 2.4 Group by (crop, cost item) and add up
For every `(crop, cost_item)` with at least one non-excluded line that has a `usd_ha`:
```python
group_usd_ha = round(sum(line["usd_ha"] for line in group_lines), 2)
```
(Each line's USD/ha is already over the hectares it covers, so adding them is right when urea and MAP each cover the same 100 ha.)

One entry in `proposals` per group, in the order the groups first appear:
```python
{
  "crop": crop, "item": cost_item,
  "concepts": [line concepts in the group],
  "proposed_usd_ha": group_usd_ha,          # keep the name: tests and app read it
  "default_usd_ha": zone value or None,    # reg_crops[crop][cost_item], with costs already in the scenario's costs_override taking precedence
  "default_source": "zone" | "earlier document",
  "deviation_pct": signed, 1 decimal: 100 * (proposed - default) / default,
  "deviation_flag": abs(deviation_pct) > 50,
  "partial": True | False,                 # see 2.5
  "apply": True | False,
  "reason": None | "deviation over 50%" | "partial crop protection" | "hectares from field area",
}
```
Note `deviation_pct` becomes **signed** (it was an absolute value): an invoice cheaper than the zone shows a negative number. Update the one test that reads it if it fails (see Tests).

### 2.5 Which groups are applied
- `partial = (cost_item == "crop_protection" and not any(line.get("covers_whole_item") for line in group_lines))`.
- `apply = crop is not None and not deviation_flag and not partial`.
  A group on the field-area basis is still applied (SPEC-28 behaviour, keep it) but carries `reason = "hectares from field area"`.
- `replaces` lists only applied groups: `f"{crop}.{item} = {group_usd_ha} USD/ha"`.
- `to_confirm`: one entry per group not applied, with the question the model should ask, in `lang`:
  - partial, es: `"¿Esta factura es todo lo que gastás en agroquímicos para el {cultivo} (herbicidas, insecticidas y fungicidas) o solo una parte?"`; en: `"Is this invoice all your crop protection for {crop} (herbicides, insecticides and fungicides), or only part of it?"`.
  - deviation, es: `"La factura da {proposed} USD/ha de {rubro} para el {cultivo} y la zona usa {default} USD/ha ({deviation_pct:+.0f} %). ¿Cubre otra superficie, es una compra parcial o es para otro cultivo?"`; en analogous.
  - crop missing, es: `"¿Para qué cultivo es {concept}?"`; en: `"Which crop is {concept} for?"`.
  Use `CROP_TRANSLATION_TO_ES` (move it from `app.py` to `dora/tools.py` if it is only in `app.py`, and import it back in `app.py`) and the `item_es` names already in `app.py` (`fertilizante`, `semilla`, `agroquímicos`, `labores`; add `crop_protection: "agroquímicos"`, `field_operations: "labores"`).

### 2.6 Re-plan before and after
Only if `scenario` is a dict that `_validate` accepts (with `area_ha`) **and** at least one group is applied:
```python
merged = {c: dict(v) for c, v in (scenario.get("costs_override") or {}).items()}
for p in proposals:
    if p["apply"]:
        merged.setdefault(p["crop"], {})[p["item"]] = p["proposed_usd_ha"]
after_scenario = dict(scenario, costs_override=merged)
sc_b, _ = _validate(scenario);       res_b = optimize(sc_b)
sc_a, _ = _validate(after_scenario); res_a = optimize(sc_a)
```
Return:
```python
"plan_before": _plan_view(res_b, sc_b, lang),
"plan_after":  _plan_view(res_a, sc_a, lang),
"npv_change_usd": round(float(res_a.npv - res_b.npv), 2),
"hectares_change": {crop: after_ha - before_ha, rounded to 0.1, only crops where it changed by more than 0.1},
"scenario_after": {"costs_override": merged},
```
`_plan_view` is the `view()` function now nested in `assess_field_image` (`npv_usd`, `profit_usd`, `hectares`, `max_credit_usd`, `debt_left_at_end_usd`, `capital_stretches`): move it to module level as `_plan_view(res, sc, lang)` and call it from both places (no change in `assess_field_image`'s output). If `optimize` raises `ScenarioError` for the after scenario, return `"plan_after_error": str(e)` instead of `plan_after`, and do not raise.
If no group is applied, or there is no valid scenario, return none of these keys.

### 2.7 Output keys
Keep every key there is today (`kind`, `items`, `proposals`, `missing`, `replaces`, `completeness`, `per_ha_basis`, `fx_conversion`, `rate`, `date`, `bcra_rate`, `bcra_date`), with `items` = the processed lines. Add `lines` (same list as `items`, each with `concept`, `crop`, `cost_item`, `amount`, `currency`, `amount_usd`, `area_ha`, `usd_ha`, `excluded`), `to_confirm`, and the 2.6 keys. `completeness.farmer_coefficients` counts only applied groups.

## 3. Guide (`dora/modeling_guide.md`, section 2)
Replace point 1 with, and add after point 4:
```
1. **One item per line.** Pass every line of the invoice to `record_document` as written, each with its `crop` and `cost_item` (glyphosate, atrazine and S-metolachlor are crop_protection; urea, MAP and anhydrous ammonia are fertilizer; VAT/IVA lines are `tax`). Never merge two lines into one, never leave a line out. Pass the scenario you are working on, so the tool re-plans.
5. **Quote the tool, before and after.** The tool adds up the lines of each item, compares them with the zone and re-plans. Say, from its output: which lines went to which crop and item, the invoice USD/ha against the zone USD/ha (`proposals`), which were used and which were not and why, and `plan_before.npv_usd`, `plan_after.npv_usd`, `npv_change_usd` and `hectares_change`. Do not call `evaluate_season` again to get these numbers.
6. **What is not used yet.** For each entry in `to_confirm`, ask its question (one message, all questions together). When the farmer confirms that a crop-protection invoice is all of it, call `record_document` again with `covers_whole_item: true` on those lines.
7. **Carry it forward.** In later tool calls of the conversation, put `scenario_after.costs_override` into the scenario.
```
Leave point 3 (the 50 % rule) as it is: the code now applies it.

## 4. App (`app.py`, the block after `if tc.get("tool") == "record_document":`)
- Read the **last** `record_document` result, not the first (iterate `reversed(agent_instance.tool_results)`): after a confirmation the second call is the one that counts.
- Replace today's table with three short blocks, in the farmer's language:
  1. **Renglones / Lines:** `| Renglón | Cultivo | Rubro | USD/ha |` (excluded lines show the reason instead of USD/ha: "IVA, no es costo", "rubro no reconocido", "cultivo no está en el plan").
  2. **Comparación con la zona / Compared with the zone:** `| Cultivo | Rubro | Factura | Zona | Diferencia | Se usa |` with `Se usa` = "sí" / "no: <reason>" (es reasons: "más de 50 % de diferencia", "es solo parte de los agroquímicos", "falta el cultivo").
  3. **Antes y después / Before and after** (only if `plan_before` is there): `| | Antes | Después |` with rows VAN (USD), hectares per crop, max credit used (USD); then one line: `Diferencia de VAN: {npv_change_usd:+,.0f} USD`.
- Keep the BCRA line for ARS invoices and the "Falta saber para qué cultivo…" line when there are no proposals.
- These blocks are drawn from the tool result after verification, as today; they are not part of the model's text.

## 5. E3 re-run on the SPEC-34 invoices (`eval/run_e3.py`, `eval/e3/real_cases.json`)
- In `real_cases.json` add to each case `expected_groups`: a list of `{"crop", "item", "usd_ha", "apply"}` computed from its lines (ARS at the `bcra_fx_20261102` rate in `real_prices.json`), and `confirm_text` for cases with a crop-protection group. Expected:
  | id | groups | apply |
  |---|---|---|
  | r1 | wheat.fertilizer = (12,300 + 10,200) / 100 = 225.00 | yes |
  | r2 | soybean.seed = 9,175,225.14 / rate / 80; soybean.crop_protection = 2,551,763.20 / rate / 80 | seed yes; crop protection no (partial) |
  | r3 | corn.crop_protection = 3,478.80 / 120 = 28.99 | no (partial) |
  | r4 | corn.fertilizer = 27,110.83 / 64.75 = 418.70; corn.seed = 18,194.75 / 64.75 = 281.00 | both yes |
  | r5 | soybean.crop_protection = 11,998.18 / 64.75 = 185.30 | no (partial) |
  If a deviation over 50 % changes an `apply` above, write what the code gives and say so in the handoff; do not edit the zone data.
  `confirm_text`: es `"Sí, es todo lo que gasto en agroquímicos para ese cultivo."`, en `"Yes, that is all my crop protection for that crop."`.
- In `do_invoices`, per image, from the **last** `record_document` result of the run: `groups_ok` (every expected group present, `proposed_usd_ha` within 1 % and `apply` equal), `lines_all_passed` (the number of non-tax lines passed equals the case's lines), `npv_after` = `plan_after.npv_usd`, and `npv_after_ok` against the engine's NPV with the expected applied groups as `costs_override` (computed in the script, as `expected_npv` today). For cases with `confirm_text`, run a second turn with it in the same conversation and record the same fields as `after_confirm`.
- Keep the SPEC-34 fields; add these. Command (Muse Spark 1.3), pilot with r1 first and paste it, then all:
  ```
  python eval/run_e3.py --only invoices --cases eval/e3/real_cases.json --media-dir eval/e3/media/real_invoices --output eval/results/e3_invoice_lines.json
  ```

## 6. Card (`docs/experimentos/2026-11-04-e3-invoice-lines.md`)
Same structure as `2026-11-03-e3-real-prices.md`. Table per case and image: lines passed / lines on the invoice, groups right, applied right, NPV after right, and the same after confirmation. One row "before SPEC-36" with the SPEC-34 outcome per case, so the change is visible. Say plainly that the Iowa prices come from DORA's own data (circular) and that these are test invoices with real public prices. Cost from the result file. "Qué aprendimos": what moved from the model into code, and what is still the model's job (reading, crop and item of each line).

## Tests (`tests/test_spec36.py`, no network, no model)
1. **Two lines, one item:** urea 12,300 + MAP 10,200, `crop: "wheat"`, `area_ha: 100` each, scenario Balcarce 500 ha → one proposal `wheat.fertilizer` with `proposed_usd_ha == 225.0`, `apply` true, one entry in `replaces`.
2. **Two items, one invoice:** seed 18,194.75 and anhydrous ammonia 27,110.83, `crop: "corn"`, 64.75 ha, Iowa → two proposals, `corn.seed == 281.0` and `corn.fertilizer == 418.7`, both applied.
3. **Active ingredients without `cost_item`:** "Glifosato 66,2 % bidón 20 L", "Atrazina 90 % WG", "Dual Gold (S-metolacloro 96 %)" map to `crop_protection`; "Urea granulada" and "Anhydrous ammonia" to `fertilizer`; "Mapa de rindes" does **not** map to fertilizer.
4. **`cost_item` from the model wins** over the keywords (a line "Producto X" with `cost_item: "seed"` is seed).
5. **VAT line:** a line "IVA 10,5 %" adds nothing, appears in `lines` with `excluded == "tax"`.
6. **No crop, several crops:** a fertilizer line without `crop`, scenario with wheat and soybean → no proposal applied, `"missing: crop"` in `missing`, one `to_confirm` entry; no wheat guess.
7. **Partial crop protection:** herbicide line for corn → `partial` true, `apply` false, `to_confirm` has the es question with "maíz"; the same with `covers_whole_item: true` → applied.
8. **Signed deviation:** an invoice at 100 USD/ha against a zone value of 200 gives `deviation_pct == -50.0` and `deviation_flag` false; at 90 gives -55.0 and flag true, not applied.
9. **Before and after:** with test 1's scenario, `plan_before.npv_usd` equals `evaluate_season(scenario)["npv_usd"]`, `plan_after.npv_usd` equals `evaluate_season(dict(scenario, costs_override={"wheat": {"fertilizer": 225.0}}))["npv_usd"]` (both to the cent), and `npv_change_usd` is their difference.
10. **Earlier override kept:** a scenario that already has `costs_override = {"soybean": {"seed": 70.0}}` keeps it in `scenario_after.costs_override` next to the new wheat fertilizer, and the wheat fertilizer's `default_source` is "zone".
11. **Infeasible after:** monkeypatch `optimize` to raise `ScenarioError` on the second call → `plan_after_error` present, no exception.
12. **App:** with a hand-made tool result (tests 2 and 7 combined), the reconciliation markdown has the three blocks, "no: es solo parte de los agroquímicos" for the herbicide, and the NPV difference line; with two `record_document` results the last one is used.
13. `assess_field_image` output unchanged after moving `_plan_view` (run its existing tests).
14. `real_cases.json`: each `expected_groups.usd_ha` equals the lines' sum / hectares (ARS at the `bcra_fx_20261102` rate) to the cent.

Existing tests to adapt, and only these:
- `tests/test_multimodal.py`: in `test_record_document_hectares_and_deviation` and `test_record_document_ars_conversion` the items have no crop and the scenario has the default four crops; add `"crop": "wheat"` to those items (the old code guessed wheat; the new one asks). No other edit.
- `tests/test_spec28.py`: if the signed `deviation_pct` breaks an assertion, compare its absolute value. No other edit.

Full suite as in SPEC-35 (377 passed, 1 skipped on main before this spec, plus the new tests). Restore the price files before handing off:
```
git checkout -- dora/data/price_curves/ dora/data/basis_*.json
```

## Handoff (`docs/handoff/spec-36-invoice-lines.md`)
The diff summary per file; test output; the r1 pilot pasted; the full table; for r2, r3 and r5 the farmer-facing answer before and after confirmation, pasted as it came out; the app screenshot of r4 (lines, comparison, before and after); cost. Do not mark anything as passed unless its output proves it.

## Claude's review (3/11 night): approved with one change
Checked: the diff stat, the handoff, the pilot r1 (groups right, NPV after 86,709.57 = expected), the full table (r1 and r4 load every line and the NPV after is exact; r2 loads the seed and holds the glyphosate; r3 and r5 ask about crop protection). Keep it. One change before committing:

1. **The farmer's confirmation wins over the 50 % rule.** In r2 and r3, after the farmer says "Sí, es todo lo que gasto en agroquímicos para ese cultivo", the tool still holds the item for "deviation over 50%", so the conversation asks a question it already got an answer to. The deviation question ("¿es una compra parcial…?") and the crop-protection question ask the same thing. Rule: when every line of a group has `covers_whole_item: true`, apply it even if `deviation_flag` is true, with `reason = "confirmed by the farmer"`, and keep the signed `deviation_pct` in the output and in the app's comparison table (`Se usa: sí, confirmado por vos ({deviation_pct:+.0f} % contra la zona)`). Same for a fertilizer or seed group the farmer confirms (add `covers_whole_item` to the schema description as "the farmer confirmed this line is the whole cost item for that crop", not only crop protection). Add a test: a corn crop-protection group at 28.99 USD/ha (zone 91.2) with `covers_whole_item: true` is applied, `reason == "confirmed by the farmer"`, `deviation_pct == -68.2`.
2. Re-run only the second turn of r2 and r3 (`--case r2`, `--case r3`; the first turn's result does not change) and update the table and the card. Paste the replies.
3. The handoff says "full suite clean" without its output: paste the `python -m pytest -q` summary line.
Then commit on `spec-36-invoice-lines` and continue with the night prompt (`docs/handoff/noche-3-11-prompt.md`).
