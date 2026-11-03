# SPEC-34: invoices with real prices, photographed, and a farmer–DORA dialogue

**Status:** ready (2/11). Implement **after handing off SPEC-33**, on branch `spec-34-real-price-invoices`, which Claude creates from `main` once SPEC-33 is reviewed. Do not commit and do not merge: write the handoff and Claude reviews. Touch only `eval/e3/` (new files), `eval/run_e3.py` (a new option, see 4), a new experiment card and tests. No app, engine, agent or verifier changes.

**Why.** E3 tested invoices drawn by a script with invented prices: DORA read them 6 of 6 times. Real farm invoices are private and none could be found online (searched 2/11: only Colombian and Ecuadorian ones). The next best thing, said plainly: invoices in the real format, with **today's real prices taken from public sources, each one cited**, printed and photographed with a phone. They test three things E3 did not: real formats, a real photo, and whether the input costs inside DORA's model match current market prices.

## 1. Real prices, each with its source (`eval/e3/real_prices.json`)
For each input below, find a current public price (published in October or November 2026). Each entry: `item`, `unit`, `price`, `currency`, `vat_included` (true/false), `source_name`, `url`, `published_on`, `read_on`, and `quote`: the exact words or table row from the page where the price appears.

Argentina (USD or ARS, as published):
- urea granulada (per t), fosfato monoamónico (per t), glifosato (per litre), semilla de trigo (per bolsa or kg), semilla de soja (per kg), atrazina or another maize herbicide (per litre).
- Candidate sources: the monthly input price table of Márgenes Agropecuarios, Agrofy News price notes, La Nación Campo price notes, the Bolsa de Cereales de Buenos Aires or the BCR (Bolsa de Comercio de Rosario) cost reports. Prefer a table to a news sentence.

Iowa (USD):
- anhydrous ammonia (per ton), seed corn (per unit/bag of 80,000 kernels), glyphosate (per gallon) or another herbicide in the same report.
- Source: USDA AMS "Iowa Production Cost Report" (bi-weekly), the latest issue.

**Rules.** Never write a price you did not read on the page. If a price cannot be found with a date in Oct–Nov 2026, leave it out and say so in the handoff; do not use an older one silently (an older one is allowed only marked `"stale": true` with its date). Exchange rate for ARS: the BNA (Banco Nación) seller rate on the invoice date, with its source in the same file.

## 2. Doses: how many units cover how many hectares (`eval/e3/real_doses.json`)
An invoice must cover a stated area, so the quantities need a dose per hectare. Take each dose from the same budgets DORA uses, citing the file and the line:
- Argentina: `dora/data/magyp_southeast_2026-06.json` (Balcarce) and `dora/data/magyp_nucleo_2026-06.json` (Pergamino). If a dose is not in those files, use the MAGyP report they cite, with page.
- Iowa: `dora/data/iowa_2026.json` (ISU budget, FM 1712) and its PDF, with page.
If the budget gives only USD/ha and no dose, say so and use a published agronomic dose with its source.

## 3. Five invoices (`eval/e3/real_cases.json` + images in `eval/e3/media/real_invoices/`)
Each case: `id`, `region`, `crop`, `item` (the DORA cost item it loads: `fertilizer`, `seed`, `crop_protection`, …), `covers_ha`, `currency`, the lines (concept, quantity, unit, unit price = the real price, line amount), net, VAT, total, and `prices_from` (the ids of the entries in `real_prices.json`).

| id | Region | What | Format |
|---|---|---|---|
| r1 | Southeast Buenos Aires (Balcarce) | wheat fertilizer: urea + MAP, 100 ha | Argentine "Factura A" electronic invoice, USD |
| r2 | Pampas core (Pergamino) | soybean seed + glyphosate, 80 ha | Factura A, **in pesos (ARS)** |
| r3 | Pampas core (Pergamino) | maize herbicide, 120 ha | Factura A, USD |
| r4 | Iowa | anhydrous ammonia + seed corn, 160 acres (state the hectares too) | US farm co-op invoice, USD, no VAT (sales tax exempt for farm inputs: write "Ag exempt") |
| r5 | Iowa | soybean herbicide, 160 acres | US co-op invoice, USD |

Seller names, tax ids and addresses are **invented and visibly fake** (for example "Agroinsumos Ejemplo SRL", CUIT 30-00000000-0; "Example Farmers Co-op"). Write at the bottom of each image, small: "Factura de prueba — precios reales, ver fuentes" / "Test invoice — real prices, see sources". Draw them with the existing `eval/e3/make_media.py` code (add the two layouts: Factura A with CAE and IVA 10.5 % / 21 % as each input has it; US co-op with ticket number and "Ag exempt").

**Photos.** For each invoice, two images:
- `rN.png`: the clean render.
- `rN_photo.jpg`: **a real phone photo** of the invoice printed on paper (or, if there is no printer, shown on a screen), on a table, slightly tilted, as a farmer would take it. Guillermo takes these; Antigravity writes in the handoff which ones are missing. The run works with whatever photos exist.

## 4. Running it
Add `--cases <file>` and `--media-dir <dir>` to `eval/run_e3.py` so `--only invoices` can run `real_cases.json` (defaults keep today's behaviour). For each case and each image (`png` and, if present, `_photo.jpg`): the same measures as E3 (lines read exactly, sum read, cost per ha loaded vs expected, NPV vs the engine's NPV with the right cost). Add one field per case:
- `model_usd_ha`: the cost per ha DORA's data uses for that region, crop and item;
- `invoice_usd_ha`: the invoice net / `covers_ha` (converted at the BNA rate for ARS);
- `diff_pct`: `(invoice_usd_ha - model_usd_ha) / model_usd_ha`.
Note that an invoice can cover only part of an item (for example the herbicide but not the insecticide); say so per case instead of forcing the comparison.

Command, Muse Spark 1.3, one run:
```
python eval/run_e3.py --only invoices --cases eval/e3/real_cases.json --media-dir eval/e3/media/real_invoices --output eval/results/e3_real_prices.json
```
Pilot first with `r1` only and paste its result; then the rest.

## 5. The dialogue (`eval/e3/dialogues/rN.json`, at least r1, r2 and r4)
Three turns with the real agent, saved as they came out:
1. Farmer sends the photo with: es "Te mando la factura del fertilizante del trigo. Cubre 100 ha. Tengo 500 ha en Balcarce y 50.000 USD. ¿Cómo cambia el plan?" (adapt to each case; r4 in English).
2. Farmer: es "¿Ese precio está caro o barato comparado con lo que usás vos?" / en "Is that price high or low compared to what you use?"
3. Farmer: es "Si consigo la urea un 10 % más barata, ¿cuánto gano?" / en "If I get it 10 % cheaper, how much do I gain?"
Save each reply, whether it was verified, and the tools called. Do not fix or retry a bad reply: it goes in the card as it is.

## 6. Card (`docs/experimentos/2026-11-03-e3-real-prices.md`)
Same structure as the other cards: question, setup (commit, command, model), a table per invoice (read ok, cost/ha loaded, model vs invoice cost/ha with `diff_pct`, NPV ok, clean vs photo), the dialogues summarised with links to the raw files, cost in USD, and "Qué aprendimos". State plainly: "These are not real farm invoices; they are test invoices with real public prices."

## Acceptance tests (`tests/test_spec34.py`, no network)
1. Every price in `real_prices.json` has `url`, `published_on`, `read_on` and a non-empty `quote`; every case's `prices_from` ids exist there.
2. For each case: line amounts = quantity × unit price; net = sum of lines; total = net + VAT (0 for Iowa); all to the cent.
3. `invoice_usd_ha` and `diff_pct` are computed as in 4 (unit test on a hand-made case, including an ARS one).
4. `run_e3.py` without `--cases` behaves as before (same case ids loaded).
5. The images listed in `real_cases.json` exist (`rN.png`); photos are optional.

Full suite as in SPEC-33. Restore the price files before handing off.

## Handoff (`docs/handoff/spec-34-real-price-invoices.md`)
Each price with its source and the quote; prices not found; doses and where they came from; the pilot result; the full run table; the three dialogues pasted as they came out; missing photos; cost. Do not mark anything as passed unless its output proves it.

## Claude's review (3/11): rejected, redo the prices with saved evidence
The pipeline (`run_e3.py` options, renderer, `real_cases.json` structure, tests) is fine; keep it. **The prices are not.** Claude opened every `url` in `real_prices.json` on 3/11:
- 404: bichosdecampo `mercado-de-fertilizantes-octubre-2026`, camposimple `glifosato-54`, camposimple `soja-grupo-iv-fiscalizada`, campoargento `atrazina-90-wg`, agrired `s-metolacloro-96`, cooperativalehmann `semillas-trigo-2026`, agchemicalsolutions `glyphosate-4-plus`.
- BNA `HistoricoCotizaciones` redirects to `Error/ErrorPage`; mymarketnews `viewReport/2863` did not resolve; the ISU PDF answered 403; only agchemicalsolutions `fomesafen-2sl` exists (redirects to `fomesafen-2sl-by-solera/`), and its price was not checked.
So the quotes were not read from those pages. A quote must never be written from memory or from a search snippet that was not opened. Redo:

1. **Evidence on disk.** Write `eval/e3/fetch_sources.py`: for each price, download the page (or PDF) and save it as `eval/e3/sources/<id>.html|.pdf|.txt`, plus `eval/e3/sources/index.json` with `id`, `url`, final URL after redirects, HTTP status and fetch time. Only a status 200 page that is not an error page counts.
2. **The quote must be in the file.** `quote` is copied from the saved text, verbatim. New test in `tests/test_spec34.py`: for every entry of `real_prices.json`, the saved source exists and contains `quote` (after collapsing whitespace; for a PDF, compare against its extracted text). The test is offline: it reads the saved files.
3. **If a current price cannot be fetched, do not invent one.** Options, in order: another public page that loads (search, then open it); a price already in DORA's data files with its own source (`dora/data/budgets/magyp_*`, `iowa_2026.json`, labelled `"source_name": "DORA data file: <file>"`, `published_on` from that file); or leave the input out and say so in the handoff. Fewer invoices with real evidence beat five with invented ones. Exchange rate: use what DORA's FX feed (`BcraFxFeed`) returns today, with its date, and say so.
4. **Regenerate** the invoices, `truth.json` entries r1–r5, `eval/results/e3_real_prices.json`, the three dialogues and the card from the new prices. In the card and the handoff, say exactly which prices come from a fetched page, which from DORA's data files, and which inputs were dropped. Remove the sentence "precios reales de mercado … relevados de fuentes públicas oficiales" unless every price meets point 2.
5. Add to the handoff a section "Corrección (3/11)" with the fetch index table (id, URL, status) and the test output.

## Claude's review, second pass (3/11): evidence approved, the card overstates the results
The prices now have real evidence (Claude re-opened two Campo Simple pages live: urea 615 USD/t and DM 46E25 990 USD/bigbag match). Keep `real_prices.json`, `eval/e3/sources/`, `fetch_sources.py`, the invoices and the tests. **Do not re-run the model** unless point 2 needs it (cents only). What is wrong is the card and the handoff, which contradict `eval/results/e3_real_prices.json`:

1. **"5 de 5 importes leídos al centavo" is false.** r5: `read_sum` 185.3, `read_lines_exact` false (it read the per-ha figure, not the invoice amount). The right count is 4 of 5 read exactly; say what r5 read.
2. **NPV.** `npv_photo_eq_expected` is false for r1, r2, r3 and r4, and the table shows them as if fine. Check r1 first: its answer text says "86710 USD" (= expected 86,709.57) but `npv_photo` is 88,186.6, which is the "sin factura" NPV the answer also quotes. If `run_e3.py` takes the wrong number from the reply (or from the wrong tool call), fix the extraction, add a test with r1's saved answer, and re-score from the saved results without calling the model. Report the true per-case outcome after that.
3. **Per case, say plainly what happened** (one line each, no ✅ unless the field is true):
   - r2: the photo loaded only the seed (74.25 USD/ha) and set the glyphosate apart; the expected 94.9 mixes seed and herbicide in one item. Say whether DORA's split is better than the expected value; if so, the expected value is the problem, write that, do not count it as a DORA miss or a pass.
   - r3: the photo loaded nothing and asked for confirmation (pre-emergence herbicides are a part of crop protection, not all of it). Say it is a reasonable answer that the metric counts as a miss.
   - r4: the photo loaded 418.7 USD/ha (fertilizer only) instead of 699.7 (fertilizer + seed); NPV off.
   - The `diff_pct` column for r2 and r4 compares a two-item invoice with one model item; compare like with like (per item) or drop the column for those rows.
4. **Iowa prices are circular.** r4 and r5 were built from `dora/data/iowa_2026.json`, so "matches the model, 0 % difference" is true by construction and says nothing about market prices. Say this in the card's header and in "Qué aprendimos"; the market-price comparison only exists for Argentina (r1–r3).
5. **"Qué aprendimos"**: replace point 1 (it is about our process, not about DORA) and point 3 (it repeats the table) with what the run shows: reading is exact for clean Argentine invoices; mixed invoices (two items for one crop) are where DORA loads the wrong item or stops to ask; Argentine market prices vs DORA's zone data: urea+MAP for wheat +5 %, soybean seed +20 %; Iowa not measured against the market.
6. **Costs table.** Take tokens and cost from the result files (`llm_cost_usd`, the dialogues' usage), not round numbers. If a figure is estimated, say so.
7. Add "Corrección 2 (3/11)" to the handoff with what changed.
