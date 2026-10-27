# SPEC-15: Agent answers a farmer can read

**Status:** to implement. **Branch:** `spec-15-agent-polish`. Do not merge into `main`; it gets reviewed first.

## Why
The first live runs with Muse Spark 1.3 (2026-10-27, `eval/REPORT.md`) answer correctly, but some answers read like engine output:
- Fortnight names come out in English inside Spanish answers ("early Dec", "late Jul"), because the tools return `fortnight_name(p)` in English.
- The worst fortnight is reported as an annualized rate, "1336% anual". It is correct (the fortnightly rate compounded 24 times) but it scares and confuses. SPEC-04b already changed the chart to show the rate of the stretch.
- Some answers print raw shares ("0.10 anual", "retorno 0.8493") instead of percentages.

## 1. Fortnight names in the farmer's language
- `fortnight_name(p, lang="en")` in `scenario.py`: `lang="es"` returns "1ª quincena de dic", "2ª quincena de jul", "(año 2)". The demo already has a Spanish formatter; reuse one function for both.
- Tools take an optional `lang` argument (`"es"` default when the farmer writes in Spanish). `evaluate_season`, `shadow_prices`, `sensitivity`, `compare_regions` return fortnight names in that language. Add `lang` to the schemas.
- The agent passes the language of the farmer's message. Modeling guide: "pass `lang` = the language the farmer writes in".

## 2. The cost of money in a scarce stretch, without scary annualized figures
- Tools report, for each stretch where capital is scarce, `rate_for_stretch_pct`: the rate over the stretch itself (λ_start / λ_end − 1), with its start and end fortnight names and its length in days. Keep `internal_rate_annual` for the charts and the verifier, but the guide tells the agent to explain with the stretch rate: "entre fines de julio y principios de diciembre, cada dólar extra te rinde 12% en esos 4 meses".
- Also report `usd_today_per_extra_dollar` for the worst fortnight (already exists for capital: reuse it).

## 3. Percentages as percentages
- Every share in tool outputs that the agent is likely to quote (`return_on_capital`, `return_on_capital_and_land`, rates, `max_crop_share`, tax rates) also comes as `*_pct` with one decimal. The verifier already accepts both readings; check it with a test.
- Modeling guide: "quote percentages from the `_pct` fields; money in USD without decimals unless under 10; hectares with one decimal".

## 4. Evaluation
- Add 6 questions to `eval/questions.jsonl` with answers built by `eval/build_answers.py`:
  - 2 in Spanish asking when money is short (check the stretch rate);
  - 2 comparing regions (`compare_regions`, `same_farm`: "¿dónde me conviene más sembrar, en Pergamino o en Iowa?"), checking the season margin per hectare of one region;
  - 2 about logistics (routes): "¿cuánto me come el flete?" checking the inland freight share.
- Do not run the live evaluation (it spends credits); Claude runs it after review.

## Acceptance tests (`tests/test_agent_polish.py`), no network
1. `fortnight_name(21, "es")` returns a Spanish name; `fortnight_name(21)` is unchanged.
2. `evaluate_season({... "lang": "es"})` has no English month abbreviations in any fortnight field.
3. For the base Balcarce scenario, the stretch rate equals λ_start / λ_end − 1 computed from `cash_value`.
4. `return_on_capital_pct` = round(100 × `return_on_capital`, 1).
5. The verifier accepts "12,3%" when a tool returned 12.3 (pct field) and when it returned 0.123 (share).
6. The new eval questions have answers in `answers.jsonl`.
7. All existing tests still pass.
