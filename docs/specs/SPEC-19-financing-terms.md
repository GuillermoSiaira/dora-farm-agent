# SPEC-19: Supplier terms as a decision, and payment caps by date

**Status:** implemented by Claude on 28/10 (branch `spec-19-financing`), tested live with Muse Spark 1.3.

## Why
A farmer short of money finances the season three ways: own capital, the bank, and the input suppliers ("a cosecha", "a 90 días con 3%", "en cuotas"). A supplier's term is a loan whose rate nobody states. Until now the farmer had to pick the term and DORA evaluated it; now the engine chooses, crop by crop, by comparing each term with what money is worth in each fortnight. And the farmer can state limits like "I cannot pay out more than 60 thousand until February", which get a shadow price.

## 1. Supplier terms (`payment_options`)
- Each option: `id`, `delay_fortnights` (from each purchase to the first payment), `surcharge` (negative for a cash discount), `installments`, `every_fortnights`. It applies to seed, fertilizer and crop protection; field operations and overhead are paid on their dates.
- The base term is always available: cash, or the farmer's imposed term (`input_payment_delay_fortnights`, `input_delay_surcharge`).
- Engine: variables `z[c, term]`, hectares of crop `c` whose inputs are paid under that term, with `Σ_term z[c, term] = x_c`. The cash equation takes the fixed payments on `x_c` and each term's payments on `z[c, term]` (`Scenario.fixed_payments_per_ha`, `Scenario.input_payments_per_ha`).
- Report (`evaluate_season.financing`): hectares per term and crop, and each term's implied annual rate, `(1 + surcharge)^(24 / average delay) − 1` (approximate for installments), next to the bank's rate. The choice itself does not use that rate: it uses the shadow prices of cash in each fortnight.

## 2. Payment caps by date (`max_payments_by`)
- Constraint `{"type": "max_payments_by", "month": "YYYY-MM", "usd": X}`: payments for inputs, field operations and overhead from fortnight 0 to the end of that month ≤ X, under whatever terms the engine chose.
- Its dual is reported as the opportunity cost: USD of today per extra dollar of room until that month.

## Acceptance tests (`tests/test_financing.py`)
Option equal to the base changes nothing; cheap terms used and dear ones not (3%, 8%, 15% surcharge at 90 days on the Balcarce base); hectares split adds up; installments keep the total with surcharge; the base term reproduces the old payments; cap shadow price within the left and right derivatives (±100 USD); a loose cap has dual 0; more terms never lower the value, with or without a cap; report fields; validation errors; `compare_regions` keeps crop-less constraints.

## Live test (28/10, Muse Spark 1.3), all answers verified
1. "90 días con 3% o 3 cuotas con 5%": engine chose 90 days for soybean and sunflower, none in installments; the agent explained 12.6% vs 34.0% a year against the bank's 10% (used to the top) and the 16.7% the stretch pays.
2. "No más de 60 lucas hasta septiembre": plan changes (less wheat, sunflower added); each extra dollar of room is worth 0.07 USD today.
3. "¿Cómo me financio?" with no offer: the agent suggested asking the supplier for terms and offered to compute them; it did not invent an offer.
