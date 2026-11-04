# SPEC-37: the Scenario tab says when the season runs, what the NPV includes, and what is left after taxes

**Status:** ready (3/11). Implement **after SPEC-36, SPEC-38 and SPEC-39 are merged** (all touch `app.py`; SPEC-38 changes the engine answers this one shows), on branch `spec-37-scenario-clarity`, created from `main` at that point. Do not commit and do not merge: write the handoff and Claude reviews. Touch only `app.py` (Scenario tab output, charts, tax table, "¿Cómo empiezo?"), `dora/scenario.py` (the `fortnight_label` helper and `start_date`, see 1.1), `dora/tools.py` (the `start_date` parameter and `tax_wedge` output fields), `dora/modeling_guide.md` (one line, see 1.1), `dora/data/taxes_argentina.json` (export duties, only with evidence, see 5), a new test file and the handoff. No optimisation-model, agent or verifier changes: `start_date` only re-indexes the inputs before the model is built. **Do 1.1 first and paste test 5b before the rest.**

**Why.** Guillermo tested the deployed app on 3/11 (voice note, summarised): Scenario tab, Pampas core (Pergamino), 2,000 ha, 500,000 USD own capital, advanced options untouched. The app said: NPV 1,036,104 USD; wheat 170 ha, corn 177.8, soybean 1,000, sunflower 28.6; peak credit 100,000 USD; direct freight 16.5 USD/t; taxes total about 945,000 USD. Claude reproduced it locally (`evaluate_season` + `tax_wedge`, same inputs; local prices differ slightly from the deployed ones): NPV 1,157,835; peak credit 100,000 = the whole line; taxes 1,060,395, of which export duties 746,141 and income tax 249,910. His points:
1. **No dates.** The page never says when the season starts or ends, how many fortnights it has, or in what year each fortnight falls. The engine's season starts in May 2026 (`season_start: "2026-05"` for Pampas core) and today is 3/11/2026, so the plan starts six months in the past and the wheat sowing window has already closed; the engine's own note says "NPV … in USD of today (May)". He expects the plan to start from today's date and say until when it runs.
2. **Chart axes have no year** ("1ª quincena de dic", and "(año 2)" for the second year).
3. **NPV vs taxes is unclear.** NPV 1.04 M and "Total de impuestos" 945 k side by side: is the NPV before or after taxes, and how much is left? In fact the NPV is **after** export duties (MAGyP prices are FAS, already net of them), gross receipts, the bank transaction tax and the land tax, and **before** income tax. The table adds the export duties into the total even though they were never in the NPV to begin with, so the total looks like it should be subtracted from the NPV.
4. **Export duties "alícuotas a verificar (placeholder)".** `taxes_argentina.json` still has soybean 33 %, corn 12 %, wheat 12 %, sunflower 7 %, marked `placeholder: true` with the note "Export duty rates were lowered during 2025 and must be checked against the decree in force". In the US and Brazil there are no export duties, but the row shows the same "to be verified" note.
5. **Livestock is not visible.** It is inside the closed "Opciones avanzadas" and nothing in the result says it was left out.
6. **Peak credit 100,000 USD** does not say that it is the whole credit line, i.e. that credit binds. The capital chart prints the two per-dollar values with four decimals (0.4622, 0.4243).

## 1. Dates on the Scenario tab
### 1.1 The farmer picks the start date (addendum 3/11, Guillermo: "puede empezar desde ahora, puede empezar desde donde yo quiera")
**What the engine does today, and why it is not enough.** `start: "today"` (SPEC-28, `scenario.py:409-459`) does **not** move the start: it removes the crops whose sowing window closed before `today` and, if none is left, shifts the whole season 12 months. The money still starts at `season_start` (May 2026 for Pampas core), the NPV is still "USD of May", and a farmer who plans on 3/11 gets cash flows that began six months ago. A start date has to move the plan's first fortnight.

**Engine: `start_date` (new scenario parameter, `dora/scenario.py` and the parameter table in `dora/tools.py`).**
- `start_date: "YYYY-MM-DD"`, optional. Rounded **down** to the start of its fortnight (day 1 or 16). It replaces the region's `season_start` as the first fortnight of the plan; the horizon stays `FORTNIGHTS` (24) fortnights from there.
- Let `k` = number of fortnights from the region's base `season_start` to the rounded `start_date` (may be negative or over 24; reduce it modulo 24 and keep the year in the new `season_start`).
- Every **fortnight index** that is defined relative to the base season start is shifted by `-k`: the crop calendar (`sowing`, `harvest`), the sowing windows from `sowing_<region>.json` (`sowing`, `harvest` of each window), and any other fortnight-indexed field of crops, livestock, storage, contracts or carryover. **Before coding, list every such field** (grep `["sowing"]`, `["harvest"]`, `fortnight`, `p ==` in `scenario.py`, `engine.py`, `livestock*`) and paste the list in the handoff. Prices need no shift: they are read by calendar month through `fortnight_month(season_start, p)`.
- A window whose shifted sowing index is below 0 is moved one year later (`+24`). If its harvest then falls at or beyond fortnight 24, the window is dropped. A crop with no window left is removed from the plan, as `start: "today"` does now, and listed in `calendar.crops_removed` with the reason `"harvest beyond the horizon"` or `"sowing window closed"`.
- Livestock: if a livestock activity cannot be shifted cleanly (for example its cycle is longer than the horizon), drop it with a reason in `calendar.livestock_removed`; do not leave it on the old calendar.
- Money already spent before `start_date` is not modelled: say so in the season line (1.2) as `No incluye lo gastado antes de {fecha}.`
- `start: "today"` becomes `start_date = today` (keep accepting `start: "today"` and `today` for the chat and old tests). `start: "season"` and no `start_date` = today's behaviour, unchanged.
- The `note` "NPV and shadow prices in USD of today (May)" uses the real start month and year: `"... in USD of {mon yyyy}"`.

**Scenario tab.** Above "Calcular Plan Óptimo": a date field `start_date_input` (`gr.DateTime` with `include_time=False`, or a text field `dd/mm/aaaa` if that component misbehaves on the deployed Gradio), labelled `Arranca el` / `Starts on`, **default: today**, with a small button `Inicio de campaña ({1/5/2026})` that fills the region's base season start. The three example buttons of "¿Cómo empiezo?" and the "Empezá acá" cards pass the base season start explicitly, so their numbers do not change (they are quoted in the README and E1). Translate the labels with the other UI texts (the `ui_texts` list).

**Chat.** Add one line to `modeling_guide.md` section 4 (this guide change is allowed): `If the farmer says when the plan starts ("arranco en diciembre", "desde el 15 de marzo", "desde hoy"), pass start_date (first day of that fortnight; "desde hoy" = today's date). If they do not say it and the region's season start has passed, plan from today and say so in "Lo que entendí".` The verifier needs no change: dates are not numbers it checks.

### 1.2 A season line at the top of the result
Right under the NPV heading, one line built from `eval_res["calendar"]` (the `calendar` block `evaluate_season` already returns), es:
`Campaña: del {d/m/aaaa inicio} a {mes año fin} ({n} quincenas).`
plus, when they apply:
- `crops_removed` non-empty: `No entran {cultivos}: {motivo}` (motivo es: "su ventana de siembra ya cerró" / "no llega a cosecharse antes de {mes año fin}").
- `start_date` after the base season start: `No incluye lo gastado antes del {d/m/aaaa}.`
- the start is before today: `Ojo: el plan arranca el {d/m/aaaa}, antes de hoy ({d/m/aaaa}).`
- `price_stale`: the existing `price_stale_reason`.
Then, per sown crop, `Siembra {mes año} · cosecha {mes año}` from `calendar.crops`. English analogous. Month names: the Spanish short names already used (`ene`, `feb`, …) plus the year: `nov 2026`.

### 1.3 Years on the chart axes
New helper in `dora/scenario.py`:
```python
def fortnight_label(season_start: str, p: int, lang: str = "en") -> str:
    """'1ª quinc. dic 2026' / 'early Dec 2026': the fortnight with its calendar year."""
```
using `fortnight_month(season_start, p)` for the year and month. Use it **only in `app.py` charts** (capital value chart, cash and debt chart, sales chart, and the "Pico de crédito" line). Do not change `fortnight_name`: tool outputs and the verifier match on it.
The engine's note "NPV and shadow prices in USD of today (May)" is shown nowhere in the app as is; under the NPV heading write instead `Valor presente al {mes año de inicio}` (es) / `Present value as of {month year}` (en).

## 2. What the NPV includes, and what is left after income tax
### 2.1 `tax_wedge` (`dora/tools.py`), new fields only
- In each entry of `taxes`, add `"in_npv": True | False | None`:
  - `export_duties`: `True` when the region's prices are FAS (Argentina, MAGyP: already net of duties), and the row is informative; `None` when the rate is 0 (US, Brazil).
  - `gross_receipts`, `transaction`, `land`: `True` (the engine charges them, `engine.py:466-525`).
  - `income`: `False`.
- Add `"npv_usd"` (the plan's NPV), `"income_tax_npv_usd"` (income tax discounted to the season start exactly as `compare_regions` computes `npv_after_income_tax_usd`, `tools.py:1873`: move that formula to a helper `_npv_after_income_tax(res, sc, rate)` and call it from both places) and `"npv_after_income_tax_usd"`.
- Keep `total_taxes_usd` and the `total` row for compatibility, and add `"taxes_not_in_npv_usd"` (only income tax today) and `"taxes_in_npv_usd"` (gross receipts + transaction + land + export duties when `in_npv`).

### 2.2 App
- Under the NPV heading, one line (es): `El VAN ya descuenta retenciones (están en el precio), Ingresos Brutos, débitos y créditos e Inmobiliario; no descuenta Ganancias. Después de Ganancias: USD {npv_after_income_tax_usd}.` English analogous. For US/Brazil, drop "retenciones" and use the names `tax_wedge` gives.
- Tax table: add a column `¿Ya está en el VAN?` with "sí" / "no" / "no aplica"; replace the single "Total de impuestos" row with two rows: `Ya descontados en el VAN` and `A descontar: Ganancias`, and a last row `VAN después de Ganancias`. Keep the "% Ingreso Bruto" column.
- Remove the sentence "por lo que la fila de retenciones es informativa" (now said by the column) but keep "los precios de MAGyP son FAS (ya netos de derechos de exportación)".
- "Alícuotas a verificar (placeholder)": show it only when the country's export duties are not all 0 **and** `taxes_argentina.json` still has `placeholder: true` after section 5. For US and Brazil show "no aplica" in the duty row.
- Income tax: the source already says it is the 35 % company rate and that individuals pay progressive rates; show that sentence under the table (es: `Ganancias al 35 % de sociedades; una persona humana paga escala progresiva.`).

## 3. Credit
- If `max_credit_usd >= credit_line_usd - 1`: the line reads `Pico de crédito utilizado: USD {x} ({quincena año}): usás toda la línea; más crédito cambiaría el plan.` Otherwise as today plus the year.
- Capital chart: values with two decimals and the label `0,46 USD por cada dólar extra` (es) / `0.46 USD per extra dollar` (en). Same for the credit line bar.

## 4. Livestock visible
- Move the livestock group (`md_livestock_head`, `livestock_input`, `livestock_only_input`) out of "Opciones avanzadas" to right under the crops selector, still optional and unchecked by default, only for regions that have a `livestock_<region>.json` (Pampas core and Southeast Buenos Aires today; hide it for Iowa and Mato Grosso).
- In the result, when no livestock activity was selected and the region has livestock data: one line `Ganadería: no incluida. Marcá cría o invernada arriba para que compita por la tierra.` (es) / en analogous.
- In "¿Cómo empiezo?" add to step 1: `Si tenés hacienda, marcá cría o invernada.`

## 5. Export duty rates, with evidence
Same rules as SPEC-34: a rate counts only if it is read on a page saved to disk.
- Find the decree in force on 3/11/2026 for soybean, corn, wheat and sunflower export duties (Boletín Oficial, or the MAGyP/ARCA page that cites the decree number). Save it as `dora/data/sources/export_duties_ar_<date>.html|pdf` and record in `taxes_argentina.json`: the new rates, `export_duties_source` with the decree number and URL, `export_duties_read_on`, and `export_duties_quote` (the exact sentence from the saved file). Then set `placeholder: false` **for the export duties only** (add `"export_duties_placeholder": false` and keep the file-level `placeholder` for the land tax estimate, which is still an estimate).
- Hint, to be checked and not to be copied: duties were cut several times in 2025 (a temporary cut in January, a permanent one in July, a further cut announced in December). Only the saved decree decides.
- If no page with the decree can be saved, change nothing in the file and say so in the handoff; the "a verificar" note stays.
- If the rates change, DORA's NPV does not (prices are FAS); only the informative duty row and the gross revenue at FOB change. Say this in the handoff with the before/after duty row for Guillermo's scenario.

## 6. Smaller errors found in Claude's review of the same screen (3/11)
Reproduced with `app.run_scenario(area_ha=2000, own_capital_usd=500000, region="pampas_core", lang="es")` on `main`: NPV 1,036,104.92, as on the deployed app.
1. **"Fuentes" names the wrong region.** `STRINGS["source_magyp"]` (`app.py:137` and `:190`) is fixed text "… sudeste de Buenos Aires" and is shown for Pampas core too. Build it from the region's data file (`regional_source_label(region)` and the file's `date`): es `Rindes, precios y costos: {fuente}, {mes año}, {nombre de la región}`.
2. **Sales chart months in alphabetical order** (`abr, dic, feb …`, `app.py:454`, `sorted(all_months_set)`). Order them by calendar from the season start, with the year (`dic 2026, … abr 2027`).
3. **Capital chart: four decimals and "p".** Two decimals (also in 3); the y axis of the first chart says `Valor hoy de $1 en p (USD)`: write `Valor hoy de 1 USD cobrado en esa quincena` (en `Today's value of 1 USD received in that fortnight`).
4. **English text in the Spanish tax table.** The `Fuente` column shows the data files' English sentences (transaction tax, income tax). Add `*_source_es` keys to `taxes_argentina.json` with the Spanish wording and use them when `lang == "es"`.
5. **"Retorno … en la campaña (14,5 meses)"** while the plan's horizon is 24 fortnights (12 months): `season_months = (T - 1) / 2` with the default `T` (`engine.py:1014`). Say in the handoff what `T` is in that formula and why it differs from 24; then show the months that match the season line of 1.2, or explain the difference in one sentence on screen.
6. **Land shadow price sentence.** `Tierra: 105,79 USD/ha … (aunque quedan 623,5 ha sin sembrar: el valor viene de la rotación (con una hectárea más podés sembrar más del cultivo que está en su tope))` is unreadable, and after SPEC-38 the idle land should mostly be rented out. Rewrite, es: `Una hectárea más te vale {x} USD: {motivo}`, with motivo from the result: rotation (`porque la soja está en su tope del {share} % del campo`), capital (`no: falta plata para sembrarla`) or rent (`lo que te pagan por alquilarla`). Remove the repeated "Comparación: una hectárea más te vale …" line in the land card.
7. **Return on capital ignores the land.** After SPEC-38, show `Retorno sobre capital y tierra` using the rent as the land's cost (SPEC-38, 3) instead of "no se calcula porque la tierra no tiene precio asignado".

8. **The "¿Cuánto vale un dólar en cada quincena?" chart reads as if the bank paid nothing** (Guillermo, 3/11, screenshot: "la línea gris siempre está clavada en uno, no considera la tasa del banco"). It does consider it: the grey line is the discount factor `(1 + rf)^(-p)` at the 4 % deposit rate (`app.py:267`), which only falls from 1 to about 0.96 over the season, so next to the green line (1.55 in May) it looks flat at 1. Both lines are "value today", a concept a farmer does not use. Redraw it as **what 1 USD put in at that fortnight is worth at the end of the season**, in %:
   - farm: `100 × (λ_p / λ_end − 1)`, with `λ_p` = `usd_today_per_dollar` of fortnight p (from `shadow_prices.by_fortnight`) and `λ_end` the last fortnight's;
   - bank: `100 × ((1 + rf)^(p_end − p) − 1)`;
   - when money is not scarce, `λ_p` equals the discount factor and both lines meet, as today.
   Title `¿Cuánto rinde un dólar extra en cada quincena, hasta fin de campaña?`; y axis `% hasta fin de campaña`; legend `En el campo` / `En el banco ({tasa} % anual)`; subtitle with the first fortnight's two numbers, es: `Un dólar extra en {quincena año} rinde {x} % en el campo y {y} % en el banco hasta {mes año fin}.` Hover: both values and the annualised internal rate (already computed). Test: with a hand-made `by_fortnight` where `λ_p` equals the discount factor, the two series are equal; with `λ_0 = 1.55`, `λ_end = 0.955`, the farm value at p=0 is `100 × (1.55/0.955 − 1)` and the bank value `100 × ((1 + rf)^p_end − 1)`, to 0.1.

9. **The bank rate is set by the user** (Guillermo, 3/11). `deposit_rate_annual` is already a scenario parameter (`tools.py:56`, default 4 %) but the Scenario tab has no field for it. Add `Tasa que te paga el banco por tus dólares (% anual)` / `What the bank pays on your dollars (% a year)`, default 4, next to the credit fields (not in the advanced options), passed as `deposit_rate_annual = value / 100`. The chart of 8 and the return lines use it. Guide line: "If the farmer says what a deposit or a plazo fijo pays them, pass `deposit_rate_annual`." Test: 0 % and 8 % give different bank lines in the chart of 8, and the NPV changes.
10. **No "precio sombra" on screen** (Guillermo: "la gente no sabe lo que es un precio sombra"). Replace it in every visible text: the title `Optimización de campaña y precios sombra` (`app.py:2375`) → `Plan óptimo y costo de oportunidad de los recursos` (en `Optimal plan and the opportunity cost of resources`); the descriptions at `app.py:100`, `:153`, `:3244-3245` the same way; the metric `Precio sombra del capital (USD por USD)` (`app.py:813`) → `Cuánto vale un dólar más de capital (USD)`. Keep "shadow price" in code, tool outputs and the guide (the model needs it); grep the rendered Spanish and English UI texts and the "Empezá acá" cards for "sombra" / "shadow" and list what you changed. Test: the rendered Scenario tab texts (es and en) contain no "sombra" and no "shadow".

Tests for 6, in `tests/test_spec37.py`: Pampas core result has "Pergamino" or "Zona Núcleo" in Fuentes and not "sudeste"; sales chart x values in calendar order; no `en p` in the axis title; the es tax table has no English source sentence (no "rate", "engine", "company"); the land sentence for a rotation-bound case contains "tope".

## Tests (`tests/test_spec37.py`, no network)
1. `fortnight_label("2026-05", 0, "es") == "1ª quinc. may 2026"`, `p=15` gives `"2ª quinc. dic 2026"`, `p=23` gives `"2ª quinc. abr 2027"`; English `"early May 2026"`.
2. `tax_wedge` for Pampas core 2,000 ha, 500,000 USD: `in_npv` is True for export duties, gross receipts, transaction and land, False for income; `npv_usd` equals `evaluate_season(...)["npv_usd"]`; `npv_after_income_tax_usd == npv_usd - income_tax_npv_usd` to the cent; `taxes_in_npv_usd + taxes_not_in_npv_usd == total_taxes_usd` to the cent.
3. Same for Iowa: export duty row `in_npv is None` and usd 0.
4. `compare_regions` `npv_after_income_tax_usd` unchanged after moving the formula to the helper (same value as on `main` for one fixed scenario: store it in the test).
5. App, season line: with a hand-made `calendar` block (start 2026-11-01, `crops_removed: ["wheat"]`, season to 2027-10) the result markdown contains `1/11/2026`, `oct 2027`, `No entran trigo`; with start 2026-05-01 and today 2026-11-03 it contains `Ojo: el plan arranca el 1/5/2026`.
5b. **Start date, engine.** (a) `start_date` equal to the region's base season start gives the same `evaluate_season` NPV, hectares and sales as no `start_date` (to the cent), for Pampas core and Iowa. (b) `start_date: "2027-05-10"` (rounds to 2027-05-01, k = 24) gives the same plan as the base one with every price month a year later; check hectares equal and `calendar.season_start == "2027-05"`. (c) Pampas core, `start_date: "2026-11-03"` (rounds to 2026-11-01): wheat is in `crops_removed` with "harvest beyond the horizon" (its next sowing is mid-2027 and its harvest falls after Oct 2027), corn and soybean are planned, `calendar.season_start == "2026-11"`, and the cash series starts with the own capital in that first fortnight. (d) `start_date: "2026-11-20"` rounds to 2026-11-16. (e) `start: "today", today: "2026-11-03"` gives the same as (c).
6. App, credit: peak = line gives "usás toda la línea"; peak below the line does not.
7. App, taxes: the table for Argentina has the column `¿Ya está en el VAN?` and the rows `Ya descontados en el VAN`, `A descontar: Ganancias`, `VAN después de Ganancias`; for Iowa the duty row says "no aplica" and no "a verificar".
8. App, livestock: for Pampas core with no livestock selected the result has `Ganadería: no incluida`; for Iowa it does not and the livestock inputs are hidden.
9. The three "¿Cómo empiezo?" examples still give the NPVs they give on `main` (store them in the test; run with `start: "season"`).
10. If section 5 changed the file: the saved source exists and contains `export_duties_quote` (whitespace collapsed).

Full suite as in SPEC-35, plus the new tests. Restore the price files before handing off:
```
git checkout -- dora/data/price_curves/ dora/data/basis_*.json
```

## Handoff (`docs/handoff/spec-37-scenario-clarity.md`)
Screenshots of the Scenario tab for Guillermo's case (Pampas core, 2,000 ha, 500,000 USD) starting today (3/11/2026), on 1/5/2026 and on 15/12/2026: the season line, the NPV lines, the credit line, the tax table, the charts with years. The export duty decree found (or not), with its quote. Test output. Do not mark anything as passed unless its output proves it.
