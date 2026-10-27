# SPEC-10: Land tenure decisions and tax structure by country

**Status:** to implement before SPEC-09's data calibration; it solves SPEC-09 item 2. **Branch:** `spec-10-land-taxes`. Do not merge into `main`; it gets reviewed first.

## Why
Investors ask two things first:
1. **What does the land cost?** Owned land is not free: it could be rented out or sold. Buying or renting land in another region is a real option.
2. **What do taxes take?** Export duties, gross-receipts taxes, financial transaction taxes, property taxes and income tax differ a lot between Argentina, the United States and Brazil.

Both enter the model as linear coefficients and decisions, so the LP structure stays the same. DORA gives a **guide and an intuition, not tax advice**, and says so.

## 1. Land: own, rent in, rent out, buy

### New scenario fields
- `owned_ha` (replaces the meaning of `area_ha` when given; `area_ha` stays as an alias for backward compatibility: owned, if `rented_land` is false).
- `max_rent_in_ha` (default 0): land that can be rented in.
- `allow_rent_out` (default true): owned land can be rented out at the regional rent.
- `max_buy_ha` (default 0): land that can be bought.
- `land_price_usd_ha`: the regional market price, from a data file with its source.
- `land_appreciation_annual` (default 0, an assumption): the land value change over the season.
- `land_tax_usd_ha_year`: the property tax, from the country's tax file.

### Engine (new variables and rows)
- Variables: `rent_in ≥ 0` (≤ `max_rent_in_ha`), `rent_out ≥ 0`, `buy ≥ 0` (≤ `max_buy_ha`).
- **Land row:** Σ_c x_c ≤ owned + rent_in + buy − rent_out. Also `rent_out` ≤ owned.
- **Cash at fortnight 0:**
  - rent paid: −rent × rent_in;
  - rent received: +rent × rent_out;
  - purchase: −land_price × buy.
  - Same signs as the other cash items: outflows positive on the left side, as in `docs/model.md`.
- **Property tax** at the fortnight the country's file says: −land_tax × (owned + buy).
- **Final wealth** adds the land bought at its end value: + land_price × (1 + appreciation)^(T/24) × buy. Owned land's value is a constant: report it, but it does not change decisions.
- With these options, **the opportunity cost of owned land shows up by itself**: if renting it out pays more than farming it, the model rents it out.

### Outputs
- `rent_in_ha`, `rent_out_ha`, `buy_ha`.
- The land shadow price, compared side by side with the regional rent and with `land_price × deposit rate`: "an extra hectare is worth X to you; renting one costs Y; the money tied up in one costs Z a year".
- **Return to capital vs return to capital and land**, both reported. The observatory publishes both, so regions compare fairly.

### Data (`dora/data/land_<region>.json`, with sources)
- **Argentina:** land price per hectare by zone, from public reports (for example the land values published by Márgenes Agropecuarios, or CREA reports), and rent from MAGyP's margins report. **Never invent figures**; use placeholders where unverified.
- **Iowa:** Iowa State University Land Value Survey (public, by county) and the ISU cash rent survey.
- **Mato Grosso:** a public source if one exists, otherwise a placeholder.

## 2. Taxes by country (`dora/data/taxes_<country>.json`, with sources and dates)
Each tax is one of a few linear forms:

| Form | Applies to | Examples |
|---|---|---|
| `export_duty_rate` | FOB price (already netted out of Argentina's FAS price, so it is **reported, not deducted twice**) | Argentina's export duties ("retenciones") per crop |
| `gross_receipts_rate` | sales revenue | Argentina's Ingresos Brutos (provincial), Brazil's Funrural |
| `transaction_tax_rate` | every cash movement (sales and payments) | Argentina's tax on bank debits and credits |
| `land_tax_usd_ha_year` | owned hectares | Argentina's inmobiliario rural, US property tax, Brazil's ITR |
| `income_tax_rate` | the season's profit, at the end (a flat effective rate, an assumption) | Argentina's Ganancias, US federal and state, Brazil's IRPF/IRPJ |

- **Engine:** gross-receipts and transaction taxes change the net price and payment coefficients. Land tax and the land changes are covered above. Income tax applies to final wealth minus starting capital, at the end; with a flat rate it scales the objective, so it changes the reported values but not the plan. Say that in the output, since it is the honest intuition.
- **Exchange-rate regime (Argentina):** a parameter `export_fx_regime` with the effective exchange rate used to settle exports, if it differs from the official rate. Default: the official rate (BCRA A3500, as now). It is shown, not hidden.
- **Output: a "tax wedge" table**, how much of gross revenue each tax takes in USD and in %, with a fixed disclaimer: "Orientative guide based on public rates as of <date>; not tax advice; consult an accountant."

## 3. Agent and UI
- Tools: the new fields in `PARAMETERS` and the schemas, and the new outputs in `evaluate_season`. Add a tool `tax_wedge(scenario)` that returns the table.
- The modeling guide gets new phrase mappings:
  - "¿me conviene comprar campo en Pergamino o alquilar?" → `max_buy_ha` and `max_rent_in_ha` for that region, then compare;
  - "tengo el campo propio" → `owned_ha`, `allow_rent_out`.
- Demo, Scenario tab: inputs for owned, rent-in and buy limits, the land decision card, and the tax wedge table.
- Observatory: both returns (capital, and capital plus land) and the land price per region.

## Acceptance tests (`tests/test_land_taxes.py`), no network
1. With the defaults (no rent-in, no buy, rent-out allowed), a farm where farming beats renting gives the same plan as before.
2. When the regional rent exceeds the farming margin, the model rents out owned land. The land shadow price then equals the rent, within a tolerance.
3. The land shadow price passes the perturbation check of `tests/test_engine.py` with buy and rent options present.
4. `buy` > 0 only if the land's end value plus farming beats keeping the cash at the deposit rate. Check one case each way.
5. Gross-receipts tax of 1% lowers every net price coefficient by 1% of price. The transaction tax applies to both sales and payments.
6. The income tax rate scales the reported NPV by (1 − t) on the profit, and the plan does not change.
7. Export duty is reported in the tax wedge and **not** deducted again from Argentina's FAS-based prices.
8. All existing tests still pass, and Balcarce's base case is unchanged when every new option is at its default.
