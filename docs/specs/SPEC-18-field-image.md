# SPEC-18: Aerial photo of the field, measured with SAM 3.1

**Status:** implemented by Claude on 28/10 (branch `spec-18-field-image`), tested live with Muse Spark 1.3.

## Why
A farmer after a storm wants to know two things: how much of the field is lost, and what that does to the season's cash. A language model looking at a photo would guess a percentage; DORA's verifier would rightly reject it. SAM 3.1 (Meta's segmentation model, on the same Meta Model API) **measures** the damaged area instead, and the engine re-plans the season with that measurement.

## What it does
1. The farmer sends a vertical photo of the field (drone straight down, or satellite) in the chat.
2. The agent calls `assess_field_image` with the photo's position in the message. The model never sees or passes the image bytes: the agent hands the photos of the latest message to the tool (`run_tool(..., images=...)`, `IMAGE_TOOLS` in `tools.py`).
3. `field_image.measure_damage` asks SAM 3.1 for each concept of the damage (`flooding`: "flood water" and "puddle"; the same water reads differently in a flooded plain and in a field with ponding) and joins the masks, counting overlaps once.
4. Affected share = pixels covered ÷ pixels of the photo. Affected hectares = share × `area_ha`.
5. The engine re-plans with the **hectares already sown** (fixed by `min_area`/`max_area` at ±0.01 ha) and the affected crops' yield lowered by `share × loss_share`. Inputs are committed, so:
   - the debt may stay open at the end of the season (`final_debt_allowed`, an internal scenario field the model cannot set), reported as `debt_left_at_end_usd`;
   - if even the farmer's credit line cannot carry the season, the smallest extra credit that does is found by bisection (to 50 USD) and reported as `extra_credit_needed_usd`.
6. The tool returns before and after (present value, profit, hectares, peak credit, cash stretches), the change in present value, and a PNG of the photo with the damaged area in red, which the app shows in the chat.

## Decoding SAM's output
The Responses endpoint answers with `<0f>` and one record per object: a box and a mask. With `metadata.mask_encoding = "one_bit"`, the mask is a context-modelled binary range code in a base85 variant, over the object's box. `dora/sam_mask.py` is a Python port of Meta's `@meta-sam/parser` 0.1.0 decoder (SAM License, copied in `docs/licenses/SAM_LICENSE`). It was checked against the overlays drawn from real API answers (tests/fixtures/sam).

## Limits, said to the farmer
- **Only vertical photos.** In an oblique photo, the share of the picture is not the share of the land. The guide tells the agent to say so and ask for a vertical one (live test: it does).
- The photo must show the whole field and nothing else; otherwise the share applies to whatever the photo shows.
- One damage type for now: standing water. Hail or lodging do not read as a single visual concept.
- Farmers' photos sent through Meta's free credits may be used by Meta: no private farm data in tests.

## Acceptance tests (`tests/test_field_image.py`), no network
Decoder against the recorded outputs (shares 0.7518 and 0.0296; 16 ponds in the Wisconsin photo; each mask inside its box); empty output and bad payloads; union of concepts; re-plan keeps sown hectares and scales yields; no damage changes nothing; a larger loss costs more and needs extra credit; errors the agent can act on; the agent passes the farmer's photo to the tool.

## Live test (28/10, Muse Spark 1.3)
- Vertical orthophoto crop with two flooded patches: `build_scenario` → `assess_field_image`; 8.9% of the field, 44.4 ha, present value −19,753 USD, no extra credit; every number verified.
- Oblique photo from a plane: the agent refused to turn it into hectares and asked for a vertical photo.
