# SPEC-30: Livestock in heads — how the cattle business works in each region

**Status:** draft (1/11), to implement on branch `spec-30-livestock`, created from `main` after SPEC-29 (merged). Do not merge into `main`; it gets reviewed first. It changes the engine (new variables and constraints for cattle) and the livestock data, so it gets a new model tag after E1 final.

**Where the numbers come from.** A Gemini Deep Research report, saved in the repo as `docs/research/ganaderia-gemini-2026-11-01.md` (five zones, every figure with source, link and date, 56 items marked "SIN FUENTE"). Claude checked a sample: the Cuenca del Salado cow-calf gross margin (317.750 ARS/ha) **is** on page 68 of SAGyP's Boletín Nº 59 (Sept 2026); the diesel price it attributes to the same bulletin is **not** there; Rosgan's index page and Iowa State's budget could not be opened by the fetch tool. About a third of the Argentine technical coefficients come from SAGyP's Boletín Nº 10 of **June 2014**. Eight citations are Google search links instead of the document. So: **the business structure (activities, stages, months, weights) is solid; every number goes in with its source and date, flagged when old or unchecked, and can be corrected later without touching the code.** That is Guillermo's call (1/11): put the prices and coefficients we have, say where they come from, and refine.

## Why
Today cattle are three blocks per hectare (cow-calf, cow-calf with herd purchase, steer fattening), with one income and one cost per hectare from SAGyP's June models, marked provisional, only in Balcarce and Pergamino. There are no animals, no stocking rate, no backgrounding, no feedlot, no seasons of grass, and cow-calf is treated as a one-season activity. A farmer or consultant who asks "¿cuántas vacas aguanta mi campo en invierno?" or "¿recrío o vendo el ternero al destete?" gets nothing, and the cattle-versus-crops comparison rests on a single margin per hectare.

## 1. What the model gets
Activities in **heads**, per region, each with its months, weights and cash flows by fortnight:

| Activity | In | Out | Land | Typical months (from the report) |
|---|---|---|---|---|
| `cow_calf` (cría) | cows (own herd) + replacement heifers + bulls | weaned steer and heifer calves, cull cows, cull bulls | grass all year | AR: service Oct–Dec, calving Jul–Sep, weaning Mar. US: calving Mar–Apr, weaning Oct–Nov. MT: rainy season Oct–Apr |
| `backgrounding` (recría) | weaned calf | backgrounded steer/heifer | grass, or pen in winter (US) | AR Salado: Mar → Jun/Jul, 175 → 250 kg. US: 150 days |
| `finishing_pasture` (invernada a pasto) | calf or backgrounded steer | finished steer | grass (+ supplement) | AR núcleo: 180 → 404 kg in 11.5 months |
| `finishing_feedlot` (engorde a corral) | backgrounded steer | finished steer | no grass (pen) | AR núcleo: 300 → 400 kg in 100 days. US: 340 → 612 kg in 195 days. MT: 70–120 days |

Which activities exist in each region follows the report: the Cuenca del Salado is a cow-calf region (SAGyP models no pure fattening there); the core region models fattening and feedlot but no cow-calf; Mato Grosso and Iowa have all four. A region without data for an activity does not offer it (a `ScenarioError` that names the region and the activity, as today for cattle in Iowa).

### Engine (`dora/engine.py`)
- **Heads per activity** are the decision variables (continuous; rounding to heads is for the reply). Cash flows per head by fortnight: purchase of the animal that enters, direct costs (health, supplement, feed, labour, marketing as a share of sales), sale of what leaves, at the price for that category and month.
- **Grass balance by season** (four seasons, or months where the source gives them): Σ heads × EV per head of that category ≤ receptivity (EV/ha for that season) × hectares given to grass + EV bought as supplement or hay. This constraint's dual is the **shadow price of grass**: what one more hectare of pasture is worth in winter. It is reported like land and storage today (`shadow_prices.grass_by_season`).
- **Feedlot**: capacity in heads (default: no limit; the farmer may give one), feed per kg of gain × cost per kg of ration, days in pen. No grass.
- **Cow herd as capital**: own cows at the start are valued at the market price of a cow (opportunity cost, as land is), and the herd at the end of the season is valued the same way, as SPEC-26 values carried-over grain. Replacement and culling keep the herd's size unless the farmer says it grows or shrinks.
- **Land is shared with crops** through the existing land constraint; cattle-only land (`livestock_only_ha`, lowlands) stays as today.
- **Health** (SENASA calendar in Argentina: foot-and-mouth campaigns, brucellosis in heifer calves) enters as a cost per head in the month it is paid.

## 2. Data (`dora/data/livestock/<region>.json`)
One file per region: `southeast_buenos_aires` (Cuenca del Salado and Sudeste: Balcarce, Azul), `pampas_core`, `mato_grosso`, `iowa`. Every number is an object:
```json
{"value": 0.3, "unit": "EV/ha", "source": "UNICEN / Tablas CREA-INTA, p. 48", "url": "https://...", "date": "2019-10",
 "status": "checked | unchecked | old | sin_fuente"}
```
- `old`: data dated before 2024. `unchecked`: copied from the report and not yet opened by a person or by Claude. `checked`: opened and confirmed. `sin_fuente`: the report had none; the value is the closest one with a source from another zone or the current model, and `note` says which.
- Copy the values from `docs/research/ganaderia-gemini-2026-11-01.md` exactly, with its source and date. Replace every `google.com/search?q=` link with the document link it wraps. Do not round or "improve" a value.
- **Currency**: local prices stay in local currency with their date; the conversion to USD uses the exchange rate the tools already fetch (BCRA for ARS; for BRL, the PTAX value and date the report gives, until a feed exists), and says which.
- Every result that uses a value not `checked` carries the provisional mark (SPEC-28 item 7) listing which data and why ("receptividad del Salado: dato de 2019, sin verificar").

## 3. The farmer's words and the interview
- **Modeling guide, new section 8 "Cattle"**: how the business works in each region, in plain words, taken from the report's section A (cite it): the Salado breeds and sells calves in autumn; the core region fattens on alfalfa and finishes in pens; Mato Grosso lives by the rainy and dry seasons; Iowa breeds on pasture and corn stalks and finishes on corn and distillers' grains. What to ask when the farmer mentions cattle: which activities (cría, recría, invernada, corral), how many cows, how many hectares of grass and of what kind, whether they buy or keep the calves.
- **Phrases to parameters** (section 1 of the guide): "tengo 300 vacas" → own herd; "hago cría" → `cow_calf`; "recrío los terneros" → `backgrounding`; "termino a corral" → `finishing_feedlot`; "aguanta 0,5 vacas por hectárea en invierno" → receptivity for winter.
- **`next_question` (SPEC-29)**: when the scenario has cattle, add candidates: `herd_size` (¿cuántas vacas tenés?), `activities` (¿hacés cría, recría o engorde, y a pasto o a corral?), `winter_receptivity` (¿cuántas vacas por hectárea te aguanta el campo en invierno?), `calf_fate` (¿vendés el ternero al destete o lo recriás?). Same rule as the others: ranked by what the farmer loses if DORA answers without asking.
- **Scenario check (SPEC-27)**: an activity the farmer did not mention needs their words, like crops.

## 4. Questions for E1 final
Add to `eval/questions_spec30.jsonl`, with answers generated from the tools (`eval/build_answers.py`):
- "Tengo 500 ha en la Cuenca del Salado, 300 vacas y hago cría. ¿Cuál es el valor actual de la campaña?"
- "En Balcarce, 500 ha y 100 lucas: ¿me conviene vender el ternero al destete o recriarlo?"
- "Con 400 ha en Pergamino, ¿qué rinde más: invernada a pasto o terminar a corral?"
- "I have 200 cows in Iowa on pasture and corn stalks. What's the present value of the year?"
- "¿Cuántas vacas me aguanta el campo en invierno en el Salado con 500 ha de campo natural?" (the check is the grass shadow price or the herd the engine chooses, whichever the question asks).

## Acceptance tests (`tests/test_spec30.py`, no network)
1. Every number in `dora/data/livestock/*.json` has `value`, `unit`, `source`, `date` and `status`; no `url` contains `google.com/search`; every `old` value is dated before 2024.
2. Salado, 500 ha of natural grass, `cow_calf` only, with the report's monthly receptivity: the herd the engine chooses is limited by winter (the grass dual is positive in winter and zero in spring); halving winter receptivity lowers the herd.
3. Feedlot uses no grass: adding `finishing_feedlot` with no capacity limit does not change the grass dual.
4. The cow herd's end value: with the same herd at start and end and no price change, the herd adds no profit by itself (only the calves and culls sold do).
5. Iowa `cow_calf` runs (no `ScenarioError`); Pampas Core `cow_calf` raises a `ScenarioError` naming the region and the activity (SAGyP models no cow-calf there).
6. A result that uses an `unchecked` or `old` value carries the provisional mark naming it.
7. `next_question` with cattle in the scenario can return `herd_size` or `activities`; with no cattle it never does.
8. The SPEC-28 cattle-only case (Balcarce, 500 ha, 100,000 USD, cría e invernada) still runs; its numbers change (new data), and the handoff shows before and after.
9. The existing suite passes; tests that assert the old per-hectare cattle numbers are updated and listed in the handoff.

## Live check (Meta key; cents, run once)
- "Tengo 500 ha en la Cuenca del Salado y 300 vacas, hago cría. ¿Cuántas vacas me aguanta el campo y qué me conviene hacer con los terneros?" The reply names the winter as what limits, gives the herd and the value from the tools, and says which data are provisional and why.
- The analyst in English: "Compare a cow-calf operation of 300 cows in Iowa and in the Salado: when does each one sell calves and how does each one come out?" The reply says the calendars are crossed (calves sold in autumn in each hemisphere) and gives both values.
If the agent asks for a missing value, answer it and run again: the check has to reach the answer.

## Handoff (`docs/handoff/spec-30-livestock.md`)
What was done, file and line; the data table per region with each value's status; which report values were left out and why; before and after for the SPEC-28 cattle-only case; the live replies; and anything in this spec that turned out wrong.
