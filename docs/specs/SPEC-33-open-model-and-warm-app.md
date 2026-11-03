# SPEC-33: Muse Spark Open selectable in the chat, and the app kept awake while the judges look

**Status:** ready (2/11), to implement on branch `spec-33-open-model`, created from `main` at the commit that adds this spec. Do not commit and do not merge: write the handoff and Claude reviews. Touch only `app.py`, `dora/agent.py` (only `default_client` / the constructor, see 2), `infra/modal/serve_app.py`, `.env.example` and tests. No engine, verifier, tool or prompt changes.

**Why.** E6 showed that DORA with Muse Spark Open (served on Baseten) gets 93 % right, all verified, with no impossible plan. Today that only lives in an experiment card. A judge should be able to pick the open model in the chat and see the same verified answers. Separately, the app is hosted on Modal and scales to zero: the first visit waits about a minute while the container starts, and a judge may leave before that.

## 1. Model selector in the chat
In the Chat tab, above the message box, a `gr.Radio` with two options, `elem_id="model_choice"`:
- "Muse Spark 1.3 (Meta API)": the default, the current behaviour.
- "Muse Spark Open (Baseten)": shown only if `BASETEN_API_KEY` is set (`BASETEN_API_BASE` and `BASETEN_MODEL` are optional and default to the values in `eval/run_eval.py` `PROVIDERS["baseten"]`: `https://inference.baseten.co/v1` and `meta-models/muse-spark-open-1026`; the hackathon key only opens that model, `meta-models/muse-spark-open` answers 403). If the key is missing, the Radio is not shown at all and everything works as today.

Labels in the selected language: es "Modelo", en "Model". One small line under it: es "Las dos versiones usan el mismo motor y el mismo verificador." / en "Both use the same engine and the same checker."

Changing the option starts a new conversation with that model: the history is cleared and the agent state is reset to `None`, so `respond` builds a new `Agent`. Show it in the chat as a system-style line: es "Ahora conversás con Muse Spark Open." / en "You are now talking to Muse Spark Open." (and the same for 1.3).

## 2. How the agent gets the model
- Add an optional `provider: str = "meta"` argument to `respond` (module level, after `screen_scenario`), passed from the Radio. When it builds a new `Agent` it calls `Agent(client=make_client(provider), model=model_for(provider))`.
- `make_client` and `model_for` are small functions in `app.py`:
  - `"meta"` uses the current `default_client()` and `DORA_MODEL`;
  - `"baseten"` uses `OpenAI(base_url=BASETEN_API_BASE, api_key=BASETEN_API_KEY, max_retries=6)` and `BASETEN_MODEL`.
- **Do not change** `default_client` or the env variables the eval uses. Take the defaults from `eval/run_eval.py` `PROVIDERS["baseten"]` (import it or move it to a small shared module, without changing what the eval does).
- **Voice and images stay on Meta's tools.** Transcription (`dora/media.py`) and SAM (`dora/field_image.py`) read `DORA_API_BASE` and keep doing so; they are tools, not the chat model.
- **Images sent to the chat model:** before the live check, find out whether the Baseten model accepts `image_url` content (one call with the sample invoice). If it does not, then when `provider == "baseten"` and the message has images, reply without calling the model: es "Muse Spark Open no lee fotos en esta versión; elegí Muse Spark 1.3 para mandar facturas." / en "Muse Spark Open does not read photos in this version; choose Muse Spark 1.3 to send invoices." Say in the handoff which case it was, with the error text.
- The daily message cap and the API-failure message from SPEC-31 apply to both providers unchanged. Each reply already says "verificada" or "sin verificar"; keep it.

## 3. Start here cards
The cards keep using the default (Meta). Do not add the selector to the Start here tab.

## 4. Keep the app awake (Modal)
In `infra/modal/serve_app.py`, make the number of warm containers come from an env variable read at deploy time:
```python
WARM = int(os.environ.get("DORA_WARM", "0"))
@app.function(..., max_containers=1, min_containers=WARM)
```
Keep `max_containers=1`, `scaledown_window` and the rest as they are. Comment in the file docstring: `DORA_WARM=1 modal deploy infra/modal/serve_app.py` keeps one container always on (for the judging weeks); a plain `modal deploy` goes back to scaling to zero. Do not deploy: Claude deploys.

## 5. Modal secret
The deployed app needs `BASETEN_API_KEY` in the `dora-app` secret. Do not touch secrets: write in the handoff that Guillermo or Claude adds them (from `.env`, never pasted in the chat). Also add the three names, with empty values, to `.env.example` (key empty; base and model with their defaults).

## Acceptance tests (`tests/test_spec33.py`, no network)
1. With `BASETEN_API_KEY` unset, the Blocks have no component with `elem_id="model_choice"`. With it set (monkeypatch), it exists and its default is the Meta option.
2. `respond(..., provider="baseten")` with no agent yet builds the `Agent` with the Baseten model name and a client whose `base_url` is the Baseten one. Patch `Agent` or the client factory; no network.
3. `respond(..., provider="meta")` builds it as today (`DORA_MODEL`).
4. Changing the Radio returns an empty history plus the "Ahora conversás con…" line, and `None` for the agent state, in the selected language.
5. If photos are not supported (see 2): with `provider="baseten"` and a file attached, the reply is the fixed message and the fake client is never called.
6. `serve_app.py` with `DORA_WARM=1` builds the function with `min_containers=1`; without it, `0`. Import the module with monkeypatched env; if Modal's decorator makes this hard, test a helper `warm_containers()` that returns the int instead.

Full suite: `DORA_API_BASE=http://127.0.0.1:9/v1 DORA_API_KEY=test DORA_MODEL=test python -m pytest -q` (365 passed before this spec; the `BASETEN_*` variables must not be set by the shell when running it). Before handing off, restore the price files the app rewrites:
```
git checkout -- dora/data/basis_argentina.json dora/data/price_curves/argentina_latest.json dora/data/price_curves/cbot_latest.json
```

## Live check (keys in `.env`; cents)
Run `python app.py` locally.
1. Choose Muse Spark Open, send `Tengo 500 ha en Balcarce y 50.000 USD de capital. ¿Qué me conviene sembrar?`, and paste the first reply as it came out and whether it says verified.
2. Same question with Muse Spark 1.3. Say whether the plan (the main number, the NPV) is the same; it should be, because the engine decides.
3. With Open, attach `assets/examples/factura-ejemplo.png` and paste what happened.
4. Switch to English and repeat step 1 once.
Screenshot of the chat with the selector: `docs/screenshots/model-choice.png`. Say what you saw, not "OK".

## Handoff (`docs/handoff/spec-33-open-model.md`)
What changed (files), the tests, the live replies pasted as they came out, whether Open reads images (with the error if not), the screenshot, and anything you could not do. Do not mark a check as passed unless its output proves it.
