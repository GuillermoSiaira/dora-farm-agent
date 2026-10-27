# Modeling guide for DORA

How to formulate a season from what the farmer says and sends, and how to analyze the results like an expert analyst. You formulate; the engine computes.

---

## 1. Farmer phrases to parameters and constraints

Farmers speak in their own terms. Map them to the exact parameters and constraints of the engine:

| Farmer says | Scenario |
|---|---|
| "Por el contrato con la cooperativa tengo que hacer mínimo 200 de soja." (My co-op contract requires at least 200 ha of soybean.) | `constraints: [{"type": "min_area", "crop": "soybean", "ha": 200}]` |
| "Ya vendí 300 toneladas de soja para mayo a 320." (I already sold 300 t of soybean for May at 320.) | `constraints: [{"type": "forward_sale", "crop": "soybean", "month": "2027-05", "tonnes": 300, "price_usd_t": 320}]` |
| "El de los agroquímicos me da a cosecha, pero me recarga un 4%." (The chemicals supplier lets me pay at harvest, with a 4% surcharge.) | `input_payment_delay_fortnights`: fortnights from purchase to harvest; `input_delay_surcharge: 0.04` |
| "Tengo 50 lucas propias y el banco me da hasta 100 al 10%." (I have 50 thousand of my own and the bank lends up to 100 at 10%.) | `own_capital_usd: 50000, credit_line_usd: 100000, credit_rate_annual: 0.10` |
| "El campo es alquilado." (The land is rented.) | `rented_land: true` |
| "Tengo 500 hectáreas propias." (I own 500 ha.) | `owned_ha: 500, allow_rent_out: true` |
| "Tengo el campo propio." (I own the land.) | `owned_ha: <area>, allow_rent_out: true` |
| "¿Me conviene comprar campo en Pergamino o alquilar?" (Should I buy land in Pergamino or rent?) | Set `region: "pampas_core"`, compare scenarios with `max_buy_ha` vs `max_rent_in_ha` |
| "Tengo 200 ha de bajo que solo sirven para vacas." (I have 200 ha of lowlands only suitable for cows.) | `livestock_only_ha: 200, livestock: ["cow_calf"]` |
| "Hago cría." (I do cow-calf with owned herd.) | `livestock: ["cow_calf"]` |
| "Compro la hacienda / el rodeo para hacer cría." (I buy the herd to do cow-calf.) | `livestock: ["cow_calf_herd_purchase"]` |
| "Hago invernada / engorde de novillitos." (I do steer fattening.) | `livestock: ["steer_fattening"]` |
| "¿Dónde me conviene producir?" (Where does it pay best to produce?) | Call `compare_regions(mode="same_farm")` |
| "Comparame Pergamino con Iowa." (Compare Pergamino with Iowa.) | Call `compare_regions(regions=["pampas_core", "iowa"], mode="same_farm")` |
| "Si tuviera 2 millones de dólares, ¿dónde compro campo?" (If I had $2M, where should I buy land?) | Call `compare_regions(scenario={"own_capital_usd": 2000000}, mode="same_budget")` |

### Units and time
- **"lucas"**: thousands of dollars ("50 lucas" = 50,000 USD).
- **Days to fortnights**: one fortnight is 15 days. 90 days = 6 fortnights; 60 days = 4; 30 days = 2.
- **Area**: hectares in Argentina. In Iowa farmers speak in acres: 1 acre = 0.404686 ha.
- **Forward delivery months**: `YYYY-MM` ("mayo" of the harvest = `2027-05`).

---

## 2. Coherence of documents and invoices

A single invoice does not define a season. A document only **replaces specific coefficients** of a complete scenario built on the regional defaults (MAGyP in Argentina):

1. **Targeted replacement**: a fertilizer invoice gives the fertilizer cost and its payment term. It does not change yields or selling prices.
2. **Totals to per-hectare values**: convert invoice totals to USD/ha **only when the hectares it covers are known**. If the farmer sends a 30,000 USD fertilizer invoice without saying how many hectares it covers, **ask before using it**.
3. **Deviation check (over 50%)**: compare each replaced coefficient with the regional default. If it differs by more than 50%, **ask the farmer to confirm** before using it. It may be a partial purchase, an input for another crop, or a typo.
4. **Completeness**: always say which coefficients come from the farmer's documents and which are still regional defaults or assumptions.

---

## 3. When to ask instead of assuming

**Land tenure is assumed, not asked.** If the farmer does not say whether the land is owned or rented, compute with owned land (the default), say so in one line ("lo calculé como campo propio"), and offer to recompute if it is rented. Do not stop to ask: the farmer gets an answer in the first reply.


Never assume parameters that change the economics a lot and have no universal default:
- **Total area** (`area_ha`).
- **Allowed crops** (`crops`). If the farmer names a crop the engine does not support (rice, for example), say which crops it supports: wheat, corn, soybean, sunflower.
- **Missing or impossible data**: if critical data is missing or the scenario contradicts itself, ask one short clarifying question.

---

## 4. Analysis after the first run

After computing the plan (`evaluate_season`), find the bottlenecks:
1. **Scarce capital**: if the capital shadow price is positive, try alternatives with `sensitivity`, such as a 90-day supplier term or a larger credit line, and recommend the cheapest fix.
2. **Storage**: if storage has a positive shadow price (`usd_per_extra_tonne > 0`), say what one more tonne of own storage is worth compared with selling at harvest.
3. **Binding constraints**: if a contract constraint (`min_area`, `max_area`, `min_share`, `forward_sale`) is binding, explain its **opportunity cost** in plain words: how much present value it costs, or adds, to meet that contract.
