# SPEC-30 — Claude's review (2026-11-01)

Status: **not accepted yet.** Tests pass (354 passed, 1 skipped), but the points below must be fixed before commit. Do not delete or edit this file; answer each point in `spec-30-livestock.md` under a new section "Answers to review".

## 1. The herd's value is counted as if it were profit (blocker)

`npv_usd` is the present value of final wealth, and final wealth now includes `cows_end × cow_end_value`, while the cows the farmer already owns at the start count for nothing. So the NPV grows with the price of a cow, not with what the operation earns.

Measured (500 ha, 300 own cows, cow_calf only, defaults):

| Region | npv_usd | herd end value | cash at end − own capital |
|---|---|---|---|
| Salado | 344,371 | 145,758 | 165,327 |
| Iowa | 866,693 | 676,471 | 182,285 |

Live check 2 told the analyst "Iowa comes out ahead: 866,693 vs 344,371". Most of that gap is the price of a cow (2,300 vs 826 USD), not the business. The cash result is about the same in both places.

Fix:
- The objective and `npv` must count the starting herd: subtract `discount^0 × cow_start_price × cows_start` (own herd) in the same way end value is added, so an owned herd kept from start to end adds nothing by itself. Test 4 checks a sum outside the LP; it must check `npv` itself.
- If the farmer owns more cows than the land carries (300 owned, 176.5 fit), the extra cows must be **sold** (at cull price, in the first fortnight) and that income must appear in the cash flow and in the answer ("you'd have to sell about 123 cows"). Right now they vanish.
- Explain where Salado's 165,327 USD of cash comes from for 176.5 cows (≈ 937 USD per cow, against a gross margin of 211.8 USD per head in the data). If it includes selling the extra cows, say so; if not, find the error.
- `profit` for income tax must use the same start herd as the objective.

## 2. The "checked" data

`checked` means a person or Claude opened the source and saw the number. Six values are marked `checked`:
- The 4 `exchange_rate` values. Iowa's 1.0 (USD) can stay. The ARS 1,560 and BRL 5.3744 come from the Gemini report, not from someone who opened the source: make them `unchecked`.
- `southeast_buenos_aires.activities.cow_calf.direct_costs_usd_head_year = 148.5` ("Boletín 59, p. 67"): this number is not in the research report, and the report says the Boletín 59 tables are images. Make it `sin_fuente` unless you can show where it comes from.
- `...gross_margin_usd_head = 211.8` ("317,750 ARS/ha @ 0.667 EV/ha"): 317,750 / 1,560 = 203.69 USD/ha, as in the report; divided by 0.667 EV/ha that is about 305 USD per EV, not 211.8. 211.8 is 317,750 / 1,500. Fix the arithmetic, write the formula in `note`, and make it `unchecked` (it is derived, not read).

## 3. The handoff's data table does not match the JSON

Section 3 of the handoff lists about 15 `checked` values, an exchange rate of 1,050 ARS/USD and an 80 % weaning rate for the Salado. The JSON has 6 checked, uses 1,560 and has a 72 % weaning rate. Rewrite the table from the JSON files (generate it with a script and paste it in, don't type it by hand).

## 4. Live checks

After fixing point 1, run both live checks again and paste the new answers. Check 1 must say how many cows to sell. Check 2 must compare the businesses by what they earn, not by what the cows are worth.
