# SPEC-09: Data calibration and polish (from the review of SPEC-06 to 08)

**Status:** to do. Data items need sources checked by hand or with web access.

## 1. Replace placeholder data with verified figures
All three new data files are marked `"placeholder": true`, and the figures look rounded and estimated:
- `dora/data/iowa_2026.json`: check each value against Iowa State University's "Estimated Costs of Crop Production in Iowa – 2026" (Ag Decision Maker A1-20), converted per acre × 2.4711.
- `dora/data/magyp_nucleo_2026-06.json`: take the Zona Núcleo table from the same MAGyP margins report as the Southeast file.
- `dora/data/mato_grosso_2026.json`: IMEA cost of production for Sorriso, with the exchange rate and its date.
- `dora/data/basis_iowa.json`: a cited source for the Iowa basis.

Set `placeholder: false` only for a value checked against its publication.

## 2. Make the regional comparison fair
The observatory reports returns on capital of 94% to 362% a year, which is not credible. The likely causes:
- **Land enters free** (`rented_land: false`), so land's opportunity cost is missing. Compare regions with land valued at its rent (`rented_land: true`), or report "return to capital and land" separately.
- **The standard farm has very little capital per hectare.** Set capital and credit per hectare from each region's cost per hectare, for example 50% of direct costs as own capital.
- **Iowa's capital shadow price is about 1.0 to 1.3**, driven by the placeholder margins. Recheck after the real data.

This is an analytical decision for Guillermo: what "return on capital" means in the published reference.

## 3. Observatory UI
- The map shows no region markers at the default zoom. Fit the bounds to the four regions on load.
- Show "provisional data" next to any region whose data file is a placeholder.
- Use crop names in Spanish in Spanish mode, as in the Scenario tab.
- Leave the model commentary empty until the API key exists, which is the current behavior; it is fine.

## 4. Before the demo
- Regenerate `observatory/latest.json` after steps 1 and 2.
- Regenerate `eval/answers.jsonl` for Iowa after step 1.
