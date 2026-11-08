# SPEC-46 review (Claude, 8/11/2026): changes requested

Reviewed commit `31daac2` on `spec-46-satellite-ndvi` (handoff `docs/handoff/spec-46-satellite-ndvi.md`).

**Verdict: not approved yet.** The core works:
- the live NDVI of the prototype's square is 0.585, the same as the prototype;
- 15/15 SPEC-46 tests and the full suite (526 passed) pass;
- `assess_field_image` is untouched in behaviour;
- nothing was redeployed.

Six items must be fixed before merge. Items 1 to 3 are correctness; 4 to 6 are honesty and hygiene. Work on the same branch, commit as `SPEC-46 review fixes:`, and append the results to the handoff (real output, no paraphrase).

## 1. Verifier: only a measured area counts (security of the check)
`check_scenario` now accepts any top-level numeric `field_ha` or `area_ha` from **any** tool result. Two of those are echoes of what the model said, not measurements:
- `assess_field_image` returns `field_ha = farm_ha`, which the model passes in;
- `field_ndvi` with only `lat`/`lon` builds a square from `scenario.area_ha`, which the model wrote, and returns that as `field_ha`.

So a model can invent an area, call one of these tools, and the verifier then accepts the invented area in `evaluate_season`.

Fix:
- `field_ndvi` returns `area_source`: `"polygon"` (a polygon was passed) or `"approx_square"` (built from coordinates).
- The verifier counts a tool result's area **only** when it comes from `field_ndvi` with `area_source == "polygon"`, or from the map's polygon result (whatever the app passes as screen context for a drawn field).
- Nothing else counts, and `assess_field_image` does not.

Tests:
- (a) `field_ndvi` with `lat`/`lon` and `scenario.area_ha=300`, the farmer said no area, then `evaluate_season` with 300 → `area_ha` flagged;
- (b) `assess_field_image` with `farm_ha=250` and nothing from the farmer → `evaluate_season` with 250 flagged;
- (c) keep test 12, with the polygon result now carrying `area_source: "polygon"`.

## 2. The 90-second budget is not enforced
The spec (section 8) says: total budget 90 s; past it, return what is done with `status: "partial"`. Today each year has a 25 s `fut.result` timeout but there is no overall deadline, and the live cold call took **199.86 s**.

Fix:
- one deadline for the whole call (current scene plus history);
- years not finished by then are listed in `years_missing`, and `normal` is computed only if at least 3 years arrived (otherwise `normal: null` with the reason);
- `status: "partial"`.

Test: a fake reader that sleeps for two of the five years, with the budget monkeypatched to 1 s → `status: "partial"`, `years_missing` has those two, and the call returns in under 3 s.

## 3. "Cached" calls still go to the network; the timing claim is wrong
`field_ndvi` calls `search_fn` (STAC, over the network) every time, for the current window and for each historical year. Only the per-scene reads are cached. So the handoff's "6.70 s, 0 network requests" is not right: the searches ran. The spec asks for a second call for the same field and date in **under 1 s**.

Fix:
- cache the STAC search results by `(poly_hash, start, end)`;
- historical windows never expire; the current window expires after 6 hours.

Test: second call with a counting fake `_search` → called 0 times; measure the cached live call again and paste the real time. If it is still over 1 s, profile it and say where the time goes (imports of rasterio count).

## 4. A meaningless comparison must not produce a yield proposal
The live check shows the problem the spec worried about. On the prototype's square the anomaly was **+143 %**: the normal (5 previous years at the same date) is about 0.24, because in those years the field had no crop in early October. With the `[0.5, 1.1]` clip, that would still propose a yield **10 % above** the base, from a comparison that is meaningless.

Fix:
- When `now / normal` is above 1.5 or below 0.4, do **not** propose a yield. Return `proposal: null` with `reason: "history_mismatch"` and the `history_note` question ("En años anteriores el lote pudo tener otro cultivo: ¿en qué años tuvo trigo?"), in the farmer's language.
- Add the same rule to the guide's section 2c.

Test: medians `[0.24, 0.22, 0.25, 0.23, 0.26]` with now 0.585 → no proposal, the reason and the question.

## 5. Handoff: report what was measured, nothing else
Section 2 says "-16.0 % when compared with wheat-specific reference". The live run did not compute that: −16 % is the synthetic number from test 6.
- Remove it, or run the live check again with `same_crop_years` set to years that really had wheat (if you can tell from the NDVI curve, a winter peak in September and October) and paste that output.
- Also correct the cache sentence (item 3).

## 6. Hygiene
- **`dora/satellite.py` adds `D:/projects/tools/proto-geo` to `sys.path`.** Library code must not depend on a prototype folder on one machine. Remove it. Install `requirements-geo.txt` into the project environment on D: (pip cache already points to `D:\projects\tools\pip-cache`) and keep the `rasterio is None` error message for machines without it.
- **`app.py` `on_apply_polygon` returns 4 or 5 outputs depending on the caller.** Use one signature (5 outputs) and update the tests that call it, instead of branching on who calls.

## Not a blocker, for later
The live check took 200 s cold, mostly reading five years of COGs from the US. For the demo (Telegraph, and a meeting on 12/11), warm the cache the day before, as section 7 of the spec says.
