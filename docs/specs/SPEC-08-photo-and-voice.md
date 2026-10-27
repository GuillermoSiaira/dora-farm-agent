# SPEC-08: Photo and voice input (plumbing ready before the model)

**Status:** to implement after SPEC-07, or before it if time is short. **Branch:** `spec-08-multimodal`. Do not merge into `main`; it gets reviewed first.

## Why
Multimodal input weighs on "use of Meta's tools" (25%). Muse Spark reads images and audio. All the plumbing can be built and tested now with a scripted model, so on the day the API key arrives only the endpoint changes.

## Flow
1. The farmer uploads **one or more** photos (invoices, cost sheets, a supplier quote) and/or a voice note in the Chat tab.
2. **Images** go to the model as OpenAI-compatible image content parts (`{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}`) in the user message, together with the text.
3. **Audio** is transcribed first, and the transcript enters the conversation as the farmer's text:
   - The transcription function is `transcribe(path) -> str` in `dora/media.py`, with a pluggable backend: an OpenAI-compatible `/audio/transcriptions` endpoint (Meta's or the provider's), chosen with `DORA_TRANSCRIBE_MODEL`.
   - Without a backend configured, return a clear message ("voice notes need a transcription model") instead of failing.
4. The model **extracts** what it can into a new tool `record_document(kind, items)`:
   - `kind`: `"invoice"`, `"cost_sheet"`, `"quote"` or `"other"`.
   - `items`: a list of `{concept, amount, currency, unit, date, payment_terms, crop}`.
   - The tool does not compute the plan. It returns a **reconciliation** against the regional defaults, following the coherence rules of SPEC-05's modeling guide:
     - which scenario coefficients this document can replace (for example, a fertilizer invoice can replace the fertilizer cost and its payment term);
     - what is missing to replace them (for example, the hectares, to turn a total into USD/ha);
     - deviations above 50% from the regional default, flagged for confirmation;
     - the completeness of the scenario: which coefficients are now the farmer's and which are still defaults.
   - Amounts in ARS are converted with the same BCRA rate as SPEC-03, and the rate and date are shown.
5. The agent asks what is missing. Only after the farmer confirms does it call `build_scenario` with the replaced coefficients.

## Engine change needed
`Scenario` gets an optional `costs_override: dict[str, dict[str, float]]`: crop → {item: USD/ha}, for the items `seed`, `fertilizer`, `crop_protection`, `field_operations`, `overhead_owned` and `overhead_rented`. `payments_per_ha` uses the override when it is present. Coefficients only; `engine.py` does not change. Add it to `PARAMETERS` and the schema, with origin `"farmer document"`.

## UI (Chat tab of SPEC-04)
- A file upload that accepts images (jpg, png, pdf first page rendered to an image is out of scope) and an audio upload or recording.
- Show the uploaded images as thumbnails in the conversation, and the reconciliation table after `record_document`.

## Acceptance tests (`tests/test_multimodal.py`), with the scripted model and no network
1. Building a user message with two images produces two `image_url` parts with valid base64 data URLs and the text part.
2. `record_document` with a fertilizer invoice of 21,000 USD and no hectares returns "missing: hectares" and replaces nothing.
3. The same invoice with `area_ha: 100` in the scenario proposes `fertilizer = 210 USD/ha`. If the regional default is 214.2, there is no deviation flag. With 642,600 USD (3×), the deviation is flagged.
4. An ARS invoice is converted with a mocked BCRA rate, and the rate and date appear in the output.
5. `costs_override` changes `payments_per_ha` only for the overridden items, and NPV moves in the expected direction (a higher cost gives a lower NPV).
6. `transcribe` without a backend returns the clear message. With a mocked backend, the transcript reaches the agent as user text.
7. All existing tests still pass.
