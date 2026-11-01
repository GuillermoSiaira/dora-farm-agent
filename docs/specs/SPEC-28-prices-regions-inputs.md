# SPEC-28: Prices that say where they come from, one regional picture, and inputs that keep the farm's size

**Status:** draft (31/10), to implement on branch `spec-28-prices-regions`, created from `main` **after SPEC-27 is merged** (both touch `dora/tools.py` and `dora/verifier.py`). Do not merge into `main`; it gets reviewed first. It fixes errors found by E2, E4 and E3 (sheets on branches `claude/e2-e4-6e57f5` and `claude/e3-multimodal-1f5142`, `docs/experimentos/2026-10-31-e{2,3,4}-*.md`). The engine's equations do not change. Results change only where a fix changes the input data (item 1: prices in `same_budget` with the Argentine curve; item 9: field size in the photo tool).

**No number is typed by hand.** Every number below comes from those sheets or from a tool run on `main`. Tests compute their expected values from the tools, except where a value is stated as fixed.

## Why
E2, E4 and E3 ran the tools the way a farmer would, and found errors no test saw. Most are silent: nothing breaks, the answer looks right and is verified, but a price is from the wrong country, a failed source is hidden, or a default of 500 ha replaces the real farm. The verifier controls where each number comes from, not whether the input was the right one, so all of these passed it.

## Prices (E4, E2)

### 1. `same_budget` gives Argentine prices to Iowa and Mato Grosso
`compare_regions` (`dora/tools.py`, ~l. 1370) swaps `price_curve_source: "argentina_latest"` for `"cbot_latest"` outside Argentina only in `same_farm`. In `same_budget` it does not. With the curve of the day, Iowa and Mato Grosso were labeled "MAGyP official spot prices …, as of 2026-10-30", and Iowa went from producing (NPV 538,214 USD) to not producing (500,000).
- Apply the same swap in `same_budget`. Put it in one helper used by both modes, so they cannot drift again.
- **Test:** `compare_regions(mode="same_budget", scenario={…, "price_curve_source": "argentina_latest"})` with a fixture curve: every non-Argentine region reports a CBOT source; Iowa's result equals the one with `cbot_latest` passed directly.

### 2. "Fresh" is measured by the file date, not the price date
`refresh()` (`dora/feeds.py`, ~l. 330) uses the file's `st_mtime`. In a fresh clone, a worktree or a new deploy, the copy dated 27/10 has today's file date and nothing is downloaded for 24 hours. This hits the deployed app first.
- Measure freshness from the snapshot's own `as_of` (and the time it was fetched, stored as `fetched_at` in the file from now on). If neither can be read, treat the file as stale.
- **Test:** a snapshot with `as_of` three days ago and a file touched now → `refresh()` tries to fetch (mock feed called once).

### 3. A failed source never reaches the farmer
`refresh()` returns `kept_last`, but the tools call it and drop the result (`_validate`, ~l. 389). The agent only sees `as_of`, so it cannot say "the source did not answer, this is the last saved price".
- Each price origin the tools return (`price_source` / `price_curve_source` block) gets `"stale": true|false` and `"stale_reason"` ("CBOT no respondió; último dato guardado del 30/10"). The modeling guide tells the agent to say it whenever `stale` is true.
- **Test:** mock feed raising → `evaluate_season` with `price_curve_source: "cbot_latest"` returns `stale: true` and a reason naming the source and the saved date.

### 4. MAGyP or BCRA fail and `refresh()` still says `updated`
The block that rebuilds the Argentine curve ends in `except: pass` (~l. 405). CBOT is updated, the Argentine curve stays old, and the status says `updated`.
- Return a status per source: `{"cbot": "updated", "magyp": "kept_last", "bcra": "kept_last", …}`, and mark the Argentine curve `stale` (item 3) when it was not rebuilt. Log the exception text; never swallow it silently.
- **Test:** CBOT mock ok, MAGyP mock raising → status `magyp: kept_last`, Argentine curve flagged stale.

### 5. Wrong source label for Pergamino
`SOURCE_MAGYP` (`dora/tools.py`, l. 23) says "… Southeast Buenos Aires" for every Argentine region. The agent quoted it for Pergamino in 2 of 6 E4 replies, though the numbers are the core region's (`magyp_nucleo_2026-06.json`).
- Take the label from the region's data file (its `source` field), not from a constant.
- **Test:** `evaluate_season` for `pampas_core` → source mentions the core region and not "Southeast".

### 6. Default prices: today's (decided by Guillermo, 31/10)
Today, if the farmer does not ask for the curve of the day, DORA uses June's MAGyP margins report and says so. "Prices come in by themselves" is true only in the observatory and when the model picks the curve.
- **Default: the curve of the day** (CBOT + Argentine basis), with its date. If a source fails, the latest saved data with its date and `stale` (item 3); June's report only if nothing newer exists.
- One constant `DEFAULT_PRICE_SOURCE` in `dora/tools.py`, set to `"latest"`; `"magyp_june"` keeps today's behavior.
- The eval (`eval/answers*.jsonl`, `run_eval.py`, the tests) pins `"magyp_june"` explicitly, because the curve of the day changes every day and the answers would stop matching. The app, `chat.py` and WhatsApp use the default.

## One regional picture (E2)

### 7. The provisional mark differs between tools
`compare_regions` reads `placeholder` from the `REGIONS` dict, which does not have it for the core region, so it marks `region_data: false`; the observatory reads `magyp_nucleo_2026-06.json`, which says `placeholder: true` (freight inside marketing costs). Mato Grosso is provisional in both, yet in E2 the agent never named it.
- Both tools read the flag from the data files. `compare_regions` lists, per region, **which** data are provisional (`provisional: ["costos y rindes", "flete", …]`), and the modeling guide asks the agent to name the provisional data of each region it compares, not only taxes and freight in general.
- **Test:** `compare_regions` for the four regions → `pampas_core` and `mato_grosso` have non-empty `provisional`; the observatory agrees for every region.

### 8. The observatory and `compare_regions` give two pictures of the same farm
They differ in land rent (the observatory does not charge it: core sows, 738,989 USD; `compare_regions` rents the land out, 775,790), Iowa freight (12 USD/t truck to the river vs 40 USD/t the whole route) and season length (the observatory annualizes with 15 months, `FORTNIGHTS / 24`, l. 115; the rest of the model uses 14.5).
- The observatory computes each region by calling the same code as `compare_regions(mode="same_farm")`, so land, freight and season are the same. Season length comes from one shared constant.
- **Test:** for the same scenario, the observatory's NPV per region equals `compare_regions`' within 0.01 USD.

### 9. Observatory commentary from the command line calls a model named "default"
`_generate_commentary` (`dora/observatory.py`, l. 210) defaults to `model="default"`; the call fails and the error is dropped, so the commentary is empty. When it works, it comes out in English with numbers without units ("return on capital at 59.98") and no word about provisional data.
- Default to `DORA_MODEL` from the environment; if the call fails, write the reason in the report instead of nothing. The commentary is in the report's language, every number has its unit, and it names the provisional data (item 7).
- **Test (no network):** with a fake client, the commentary request uses `DORA_MODEL`; with a failing client, the report has `commentary_error`.

## Inputs that keep the farm's size (E3)

### 10. Invoices: hectares per line
`record_document` (`dora/tools.py`, ~l. 994) divides each cost by the whole farm when the invoice covers fewer hectares. Typed in, the model passed the hectares as one more invoice line; the tool did not understand it and gave 42 USD/ha instead of 210 (2 of 6 right; from the photo, 6 of 6). Those replies were verified, because 42 came from a tool.
- The schema gets an explicit `area_ha` per item (it already reads `it.get("area_ha")`, l. 1098, but the schema does not offer it), and a line with `unit: "ha"` and no amount is read as the hectares of the invoice, not as a cost.
- When the tool divides by the farm's area because no hectares were given, it says so in its result (`per_ha_basis: "superficie del campo (no venía en la factura)"`), so the agent can ask.
- "agroquímicos" with an accent must map to crop protection: normalize accents before matching (today it looks for "agroquim", l. 1042).
- **Tests:** the E3 typed cases (`eval/e3/`, branch `claude/e3-multimodal-1f5142`) give the right cost per hectare in 6 of 6; "Agroquímicos" → crop protection.

### 11. Aerial photo: the field is the farm, not 500 ha
`assess_field_image` (~l. 1583) uses `area_ha`, which defaults to 500, when the scenario gives `owned_ha` and no `area_ha`. In E3 photo a3 (600 ha), DORA said 23.9 ha: 4.8 % of 500, not of 600 (28.7). It matched the true 24 ha by chance.
- Use the farm's area: `area_ha` if given, else `owned_ha` plus rented land. If none is known, do not assume 500: return the share only and ask for the area.
- **Test:** scenario `{"owned_ha": 600}` and a mask covering 4.8 % → `field_ha` 600, `affected_ha` 28.8 (share × 600, rounded as the tool rounds).

### 12. The verifier and numbers said in words
With voice, every number arrives in words. In E3 note v5 the farmer said "noventa" (days) and the verifier rejected "90" in the reply, because it only finds digits in what the farmer said.
- The verifier also reads Spanish and English number words in the farmer's text ("noventa", "ochocientas", "dos mil quinientos", "ninety") as supported numbers. Only in the farmer's own text, never in the model's reply.
- **Test:** user text "tengo ochocientas hectáreas y pago a noventa días" supports 800 and 90.

## Calendars (Guillermo, 31/10)
### 13. Crossed seasons, and seasons that already started
Each region has a fixed `season_start` in `dora/scenario.py`: May 2026 for the three Argentine/Brazilian regions, April 2026 for Iowa. On 31/10/2026 both are in the past, and nothing tells the farmer. Guillermo's case: comparing Iowa with Pergamino or Balcarce as if both seasons started today. The northern and southern seasons are crossed: today Argentina is sowing its summer crops (gruesa) while Iowa's next corn and soybean sowing is in spring 2027; Argentina's wheat (fina) was sown months ago. A farmer has to hear that before any number.
- **Report, do not change the model.** Every season tool (`evaluate_season`, `compare_regions` per region, `shadow_prices`, `sensitivity`) adds a `calendar` block: `season_start`, `season_end`, each crop's sowing and harvest month (from the region's calendar), `today` (the system date; injectable for tests), `crops_sowing_passed` (crops whose last sowing fortnight is before today) and `next_season_start` (the same month one year later when the season start is before today).
- **`compare_regions`** adds at the top level `calendars_differ: true` when the regions' sowing months for the same crop differ by three months or more, and `calendar_note` naming, per region, when its next sowing of each crop is.
- **Modeling guide, section 0:** "In a comparison across hemispheres (Iowa against Argentina or Brazil), say in the first lines that the seasons are crossed and when each one can start; the numbers compare one full season in each region, not seasons that start today. If the farmer wants to start now, say which crops can still be sown this season (`crops_sowing_passed`) and offer to compute without the others." Removing those crops is allowed by SPEC-27's scenario check: add to rule 3 that a crop listed in `crops_sowing_passed` of an earlier tool result may be left out without the farmer's words.
- **Test:** with `today = 2026-10-31`, `compare_regions` for Iowa and Pampas Core reports `calendars_differ: true`, Iowa's `next_season_start` in 2027, and wheat in Pampas Core's `crops_sowing_passed`; with `today = 2026-04-01`, Iowa's `next_season_start` is absent. Every other field is unchanged (compare the dicts minus `calendar`).
- **Live check:** "Quiero arrancar hoy la gruesa: ¿me conviene Iowa o Pergamino?" The reply has to say that in Iowa the corn and soybean sowing comes in spring and that the comparison is of full seasons.

### 14. Starting from today, for the analyst (Guillermo, 31/10)
The second user of the demo is an analyst (a trader or an exporter) asking: "Simulate a 1,000 ha farm in Iowa and one in Pergamino with today's futures: how would each one come out?" With item 13 alone DORA can only say the seasons do not line up. With this item it can answer for **the next season each farm can actually sow**, priced with the curve of the day. On 31/10 the saved curves (`dora/data/price_curves/cbot_latest.json`, `argentina_latest.json`) run from 2026-12 to 2028-03, which covers both cases.
- New scenario field `start`: `"season"` (default, today's behavior) or `"today"`. With `"today"`, per region:
  - crops whose last sowing fortnight is before today are removed (`crops_sowing_passed`, item 13);
  - if no crop is left, `season_start` moves forward 12 months (Iowa on 31/10 → 2027-04) and all crops come back;
  - prices are read from the curve for the season's own months (the existing interpolation already does this from `season_start`). If the curve does not reach a month the season needs, the tool says so in `calendar.price_months_missing` and uses the last month available, marked `stale`.
- `compare_regions` and `evaluate_season` accept it; the `calendar` block says what was removed or moved and why.
- What it is not: a forecast. Yields are the regional defaults (or the farmer's); the guide says so in one line ("rindes normales de la zona; no es un pronóstico").
- Scenario check (SPEC-27): `start: "today"` needs the farmer's words ("hoy", "ahora", "arrancar ya", "today", "now", "next season", "próxima campaña"), like `rented_land` needs "alquil".
- **Tests:** with `today = 2026-10-31`: Iowa with `start: "today"` has `season_start == "2027-04"` and the same crops as with `"season"`; Pampas Core with `start: "today"` has no wheat and keeps `season_start`; with `start: "season"` every result equals today's (compare the dicts minus `calendar`). With a curve that ends before a needed month, `price_months_missing` is not empty.
- **Live check (in English, as an analyst):** "I'm an analyst. Simulate a 1,000 ha farm in Iowa and one in Pergamino starting from today, with today's futures. How would each producer come out, and when does each one sow?" The reply says when each one sows, what is sown in each, the NPV of each from the tools, the price date, and that it is not a yield forecast.
- Looking back (the last season with its real yields and prices) is not in this spec: we have no saved price history per month. It goes in the README as a next step.

### 15. Livestock only (Guillermo, 31/10)
The engine already models cattle in Balcarce and Pergamino (`livestock`: cow_calf, cow_calf_herd_purchase, steer_fattening). On `main`, Balcarce, 500 ha, 100,000 USD, with `livestock: ["cow_calf", "steer_fattening"]`, the optimum is all cattle (cow_calf 199.9 ha, steer_fattening 300.1 ha, NPV 194,911.37), against 145,936.42 with crops only. But a farmer who says "solo hago ganadería" cannot be modeled directly: `crops: []` is rejected ("'crops' must be a list with items from…").
- Accept `crops: []` when `livestock` is not empty (still an error without livestock: nothing to produce).
- Scenario check (SPEC-27, rule 3): `crops: []` needs the farmer's words ("solo ganadería", "solo hacienda", "sin agricultura", "no siembro", "only cattle", "no crops").
- The livestock data files (`dora/data/livestock_*.json`) are marked `placeholder: true`, and they convert at 1,050 ARS/USD. Every result that uses them carries the `provisional` mark of item 7 with that reason, and the guide says it in one line. Comparing cattle against crops is the kind of result a farmer acts on; it cannot go out as if the data were final.
- **Tests:** `evaluate_season` with `crops: []` and `livestock: ["cow_calf"]` gives no crop hectares and a positive cow_calf area; with `crops: []` and no livestock it is still a `ScenarioError`; the result carries the provisional mark.
- **Live check:** "Tengo 500 ha en Balcarce y 100 lucas, solo hago ganadería: cría e invernada. ¿Cómo me conviene repartir el campo?" The reply has no crop, gives the split and the NPV from the tools, and says the cattle data are provisional.


## Acceptance tests (`tests/test_spec28.py`, no network)
The tests named in each item, plus:
- The existing suite passes. The `test_whatsapp.py` tests must not depend on `DORA_API_BASE` being set (they fail today in a worktree without `.env`): set the variables they need inside the test.
- With `DEFAULT_PRICE_SOURCE` pinned to `"magyp_june"`, `eval/answers*.jsonl` regenerated from the tools are unchanged except where item 1 or 11 changes an input (list them in the handoff).

## Live check (Meta key; cents, run once)
- Run the E2 question ("¿cómo viene la campaña en las cuatro regiones?") twice and E4's P2 with MAGyP blocked once. Paste the replies: they must name Mato Grosso's provisional data and say the Argentine price is the last saved one.
- Run one typed E3 invoice and photo a3. Paste the replies.

## Handoff (`docs/handoff/spec-28-prices-regions.md`)
What was done, file and line; which eval answers changed and why; the live replies; anything in this spec that turned out wrong.
