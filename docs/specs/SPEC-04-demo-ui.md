# SPEC-04: Demo web app with shadow-price charts

**Status:** to implement. **Branch:** `spec-04-demo-ui`. Do not merge into `main`; it gets reviewed first.

## Why
The demo is 25% of the score. The judges must see, in under a minute:
1. a farmer describing the season;
2. the plan DORA proposes;
3. **when capital is scarce and what each resource is worth**, as charts;
4. every number traced to its source.

The app must work **without the language model**: a "Scenario" tab drives the engine directly. When an API key is present, a "Chat" tab adds the agent.

## Stack
- **Gradio** (add `gradio>=4.40` to `requirements.txt`) and **Plotly** for charts (`plotly>=5.20`).
- Entry point: `app.py` at the repository root, so it runs on a Hugging Face Space (`python app.py`).
- No other new dependencies.

## Tab 1: Scenario (no model needed)
Inputs:
- Area (ha) and crops (checkboxes).
- Own capital (USD), credit line (USD) and credit rate (%).
- Supplier payment term (fortnights: 0, 2, 4 or 6) and its surcharge (%).
- Storage capacity (t).
- Price source: MAGyP default, or any snapshot from `available_curves()`.
- Constraints: a small table with one row per constraint (type, crop, value, month, price).
- A **Run** button.

Each input sends exactly the parameter names of `tools.PARAMETERS` through `run_tool("evaluate_season", ...)` and `run_tool("shadow_prices", ...)`. The UI never computes results itself.

Outputs:
1. **Plan card:** hectares per crop, unsown hectares, NPV (USD of today), peak credit and its fortnight. Each number shows its origin; build that from `build_scenario`.
2. **Chart A, "When is capital scarce?":** a line of `internal_rate_annual` by fortnight, with a horizontal line at the market rate. Shade the fortnights where the internal rate is above the market rate.
3. **Chart B, "What each resource is worth":** horizontal bars for the capital, land, storage and credit line shadow prices, each with its unit in the label.
4. **Chart C, "Cash and credit":** an area chart with cash surplus and debt by fortnight. This needs `cash` and `debt` from the engine; add them to the `evaluate_season` output as two lists rounded to 0 decimals.
5. **Constraints table:** each constraint with binding (yes/no), its opportunity cost and its unit, from SPEC-02's output.
6. **Sales by month:** a stacked bar chart from `sales_t_by_month`.

Example scenarios, as buttons that fill the inputs:
- "Capital-rationed farm": 500 ha, 50,000 USD capital, 100,000 USD credit.
- "Same farm, 90-day supplier term".
- "Corn contract": a `min_area` of 150 ha of corn.

## Tab 2: Chat (needs a model)
- Hidden unless the `DORA_API_KEY` environment variable is set.
- A chat box backed by `dora.agent.Agent`.
- Each reply shows a badge: **"verified: every number comes from the engine"**, or **"not verified"** with the unsupported numbers listed.
- A collapsible "Tool calls" panel lists each call and its arguments.
- A daily cap of 200 questions (counter in memory is enough), with a polite message when it is reached.

## Look
- Clean and agricultural, not flashy. Use Gradio's `Soft` theme with a green primary color.
- Every chart has axis labels with units, its title as a question, and a one-line caption explaining how to read it.
- Spanish UI text by default, with an English toggle (two dictionaries of strings). The judges read English, Argentine farmers read Spanish.

## Acceptance tests (`tests/test_app.py`)
1. Building the Gradio app does not raise (call the builder function, do not launch).
2. The function behind Run, called with the "Capital-rationed farm" example, returns a dict with the plan, three Plotly figures and the constraints table, and the NPV equals `evaluate_season`'s.
3. `evaluate_season` now includes `cash` and `debt`, with 30 values each, and the existing tests still pass.
4. Without `DORA_API_KEY`, the Chat tab is not built.
5. All existing tests still pass.

## Rules
- English code in the existing style.
- No network calls in tests.
- Do not change `engine.py` except to expose what the charts need.
