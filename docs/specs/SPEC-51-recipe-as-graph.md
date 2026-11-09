# SPEC-51: the recipe as a graph (graph vs text, first right answers, then cheaper ones)

**Status:** written 9/11/2026. Implementation waits for SPEC-50 to be reviewed and merged. Branch `spec-51-graph-recipe`, cut from `spec-50-sheet-bench` once SPEC-50's three commits are reviewed.

**Depends on:** SPEC-50 (`eval/sheets/`: grader, the 12 problems, `run_sheets.py`, audit page, `runner: "sheets"` in the daily runner).

## Why
SPEC-50 gives the model the modelling recipe as **text**: up to 1,600 words of Tow (and later Dorfman, Samuelson and Solow) in the prompt. Two questions follow:

1. **Does a graph work better than a text?** Tow's and DSS's own method already thinks of a linear program as a graph:
   - activities and items are the nodes;
   - each input-output coefficient is an edge between an activity and an item.

   If the model first writes that graph, many formulation errors become **structural checks** that need no known answer. Examples: an intermediate item nobody produces, a profit with no limited resource behind it, a number on an edge that is not in the statement.
2. **Is it cheaper?** A graph is shorter than a sheet. A model that only writes the graph, while code compiles the LP and the sheet, could spend far fewer tokens. **We do not know this.** The structured output, the repair turn or the step-by-step mode could cost more. It is measured, not assumed.

**The order is fixed: first right answers, then cheaper ones.** An arm that is cheaper but solves fewer problems does not win.

**The models that matter most** are the small ones, and above all the ones **on the threshold**: they solve some problems and fail others. A model that already solves everything has little to gain, and one that solves nothing does not show what helps. The strong models come after, to see whether the graph lets them do the same job with fewer tokens.

## 1. Two ideas of "graph"

**A. The recipe as a graph of steps** (procedure). Each step of Tow's method is a node with its own short prompt and its own check:
1. time unit and scope;
2. items, with their kind and unit;
3. activities, with their unit;
4. coefficients (edges);
5. external flows (right-hand sides);
6. objective.

The model goes through one node per turn. It advances only when the node's check passes, with at most one retry per node. Each turn carries only the part of the recipe for that step, plus the graph built so far, so the context is shorter. There are more turns, though, and the arm may still end up costing more.

**B. The problem as a graph** (activity × item). The model returns one JSON graph:

```json
{
  "time_unit": "campaña",
  "items": [
    {"id": "tierra", "kind": "fixed", "unit": "ha", "external": {"op": "<=", "value": 500}},
    {"id": "maiz_grano", "kind": "intermediate", "unit": "t", "external": {"op": "=", "value": 0}},
    {"id": "dinero", "kind": "money", "unit": "USD"}
  ],
  "activities": [
    {"id": "sembrar_maiz", "unit": "ha", "objective": -650},
    {"id": "vender_maiz", "unit": "t", "objective": 180}
  ],
  "edges": [
    {"activity": "sembrar_maiz", "item": "tierra", "coef": -1},
    {"activity": "sembrar_maiz", "item": "maiz_grano", "coef": 8.5},
    {"activity": "vender_maiz", "item": "maiz_grano", "coef": -1}
  ],
  "sense": "max",
  "assumptions": [],
  "questions_to_user": []
}
```

- **Sign convention:** DSS's (book p. 145, the chemical plant): **a negative coefficient means the activity consumes the item, a positive one that it produces it.** Each item row reads `sum(coef · x) (op) external.value`. A capacity limit is written by the compiler as "consumption ≤ capacity"; the graph stays in DSS signs. The same convention goes into the recipe text (SPEC-50 merge) and into `eval/sheets/graph.py`.
- `kind` is one of `fixed`, `bought`, `intermediate`, `final`, `money`.
- Activities are non-negative by construction. A free variable is declared with `"free": true`, which is rare and must be justified in `assumptions`.
- **The graph compiler** (`eval/sheets/graph.py`, our code, no model) turns the graph into `(c, A, b, row types, sense)`. It then writes the SPEC-50 sheet JSON from it, so the SPEC-50 grader, renderer and audit page are reused unchanged.
- **The dual is the same graph read the other way:**
  - each item gets a price;
  - each activity gets a dual row;
  - the signs come from the item's `op`.

  The compiler builds it. The model does not write a second sheet in this arm.

## 2. The graph checks (`eval/sheets/graph_checks.py`)
They run on the graph alone, **without the expected answer**. That makes them usable later in DORA's runtime verifier, not only in the bench. Each check returns a list of findings in plain language, in Spanish and English, for the repair turn and the audit page.

1. **Orphan intermediate:** an `intermediate` item with no producing edge, or with no consuming edge.
2. **Unbounded profit:** an activity with a positive objective that, following the edges, consumes no item with a finite limit (`fixed`, or `bought` with a cap). This is a structural warning; HiGHS gives the final verdict.
3. **Invented numbers:** every `coef`, `external.value` and `objective` belongs to the problem's allowed set. The SPEC-50 function is reused, with its fixes after review (explicit `statement_numbers`, no blanket ×1000 or ×100).
4. **Units:** `unit(coef) = unit(item) / unit(activity)`, when the model gives `coef_unit`, which is optional. Otherwise the check only verifies that every item and activity has a unit.
5. **Fixed item without a limit:** a `fixed` item with no `external` is a missing datum. It must be asked about or declared.
6. **Dangling references:** an edge to an item or activity that does not exist; duplicate ids.
7. **Disconnected parts:** an item or activity with no edges.

## 3. The arms (`eval/run_sheets.py --arms ...`)
All arms run on the same 12 SPEC-50 problems, with the same grader and the same final score (`solved`, `handled` for incomplete problems).

| Arm | What the model writes | Recipe in the prompt | Turns |
|---|---|---|---|
| `recipe` (SPEC-50, the baseline) | the sheet JSON | text, ≤ 1,600 words | 1 |
| `graph_only` | the graph JSON; code compiles LP and sheet | graph recipe, ≤ 600 words | 1 |
| `graph_repair` | the graph; if a check fails, the findings go back once | graph recipe | 1–2 |
| `graph_then_sheet` | first the graph (checked, one repair), then the sheet from its own graph | graph recipe + sheet format | 2–3 |
| `steps` | one node of idea A per turn, gated by its check | one step's slice per turn | 6–12 |

- **The graph recipe** (`eval/sheets/data/recipe_graph.es.md`, `.en.md`) is **written by us**, at most 600 words. It covers the graph format, the sign convention, Tow's five steps expressed as "nodes and edges", and the seven checks. It cites pages of Tow and DSS. Nothing is copied.
- **Problems with `asks_dual`:** in the graph arms the dual is compiled, so `dual_ok` is not measured there. These arms are compared on the primal only, which is what SPEC-50's `solved` measures.
- **Problems with `asks_reading`:** the reading turn is the same as in SPEC-50, run on the compiled sheet.
- **One repair turn at most** in any arm, so cost stays bounded and comparable.

## 4. What is measured (`<out>/<model>_summary.json`, per arm)
**First, being right:**
- `solved_rate`, `handled_incomplete_rate`, `invented_numbers_mean`, `missing_nonneg_rate` (cannot happen in graph arms; reported as `n/a`);
- `graph_check_fail_rate`, per check, before and after the repair turn;
- `reading_ok_rate`, where asked.

**Then, cost:**
- input and output tokens per problem and per arm, and the number of turns;
- **`usd_per_solved` = cost of the arm / problems solved.** This is the headline cost number: a cheap arm that solves nothing has an infinite cost per solved problem;
- the cost in USD from `--usd-per-m`, or from the Kaggle proxy quota delta.

**Variance:** every arm runs at least 3 times per model (`--runs 3`). Arms are compared **paired by problem**. The handoff reports the per-problem table, the mean and the spread. One run decides nothing.

**The decision rule, written before any result:**
- A graph arm **beats** `recipe` for a model if its `solved_rate` is at least as high (within the spread of the 3 runs), and its `usd_per_solved` is lower.
- If it solves more but costs more, that is reported as "more right, more expensive", and Guillermo decides.
- If it is cheaper but solves less, it loses.

## 5. Which models
**Threshold models first.** They are picked from SPEC-50's first runs: models whose `solved_rate` on the `recipe` arm falls between 0.3 and 0.8. Candidates, by what E11 and E14 showed on the tool:
- GPT-5.4 nano;
- gpt-oss-120b;
- Granite 4.0 H Small;
- Gemini 3.1 Flash Lite;
- Gemini 3 Flash.

If a candidate solves everything or nothing on `recipe`, it leaves the threshold group and is run once, for the record.

**Then the strong ones**, to see whether the graph saves tokens: Claude Sonnet 5 (the ceiling) and DeepSeek R1. Here the interesting number is `usd_per_solved`, since `solved_rate` should already be high.

**Where they run:**
- **Kaggle model proxy:** the daily queue, 3 USD a day cap, free quota.
- **Meta API (Muse Spark), the model of the Meta hackathon.** It is already wired:
  - the key is `DORA_API_KEY` and the base is `DORA_API_BASE` (`https://api.meta.ai`), both in `D:\projects\dora-hackathon\.env`;
  - the model is `muse-spark-1.3`;
  - E1, E6 and E8 ran it: 36–38 % alone, 93–100 % with DORA.

  Hackathon credit: 150 USD, of which 133.52 USD were left on 30/10. Later spend was not checked, so Guillermo checks the balance before the first run.

  Use it as `--base` from `DORA_API_BASE` and `--key-var DORA_API_KEY`. The key never goes in a log, a command line or a document.

  Muse Spark is not a small model. It enters with the strong ones, for `usd_per_solved`. It also shows Meta that the graph harness makes its model cheaper per correct answer.
- **Local open models** (Qwen 14B on Modal, as in E12) come after, with their own cost approval.

## 6. The daily runner
- Queue entries carry `runner: "sheets"`, `arms`, `runs` and an optional `provider` (`kaggle`, the default, or `meta`).
- With `meta`, the runner skips the Kaggle quota check and token refresh, and applies its own cap of **2 USD a day** from a new constant `META_DAILY_CAP`, counting tokens × price from the summary.
- Nothing else in the runner changes.
- **Claude adds the entries** after review. The implementation adds only the code and the test.

## 7. Teaching and audit
- `render.py` draws the graph as an SVG next to the sheet in `audit.html`: activities as boxes and items as circles, with edges coloured by produce or consume and labelled by their coefficient. The graph-check findings are marked on the drawing.
- The same SVG is the course material: "what consumes what and what produces what" is understood before a matrix.

## 8. Tests (`tests/test_spec51.py`, offline, no model)
1. **Compiler round trip:** for each of the 12 problems, a hand-built correct graph (`tests/fixtures/spec51/`) compiles to an LP whose optimum equals `reference_lp` within 1e-6. Its compiled sheet grades `solved` with the SPEC-50 grader.
2. **The compiled dual** equals SPEC-50's canonical dual of the same LP, and strong duality holds within 1e-6.
3. **Each graph check, in both directions:** a correct graph passes all seven checks, and a graph broken on purpose for each check is caught by that check only:
   - an orphan intermediate;
   - a selling activity with nothing limited behind it;
   - a rent changed to 180,000;
   - a fixed item with no limit;
   - a dangling edge;
   - a duplicate id;
   - a disconnected item.
4. **Sign convention:** the same problem written with capacities as "consumption ≤ capacity" (positive coefficients) and in DSS signs compiles to the same LP.
5. **Incomplete problem 11:** a graph that puts a capital of 260,000 silently is `handled = false`; the same graph with the question is `handled = true`.
6. **The `steps` arm's gate logic:** a node whose check fails is retried once, then the arm stops and records the failure. Monkeypatch the model; no network.
7. `run_daily.py` with `provider: "meta"` builds the right command and applies `META_DAILY_CAP`, without reading any key. Monkeypatch `subprocess.run`.
8. `render.py` writes the SVG, and `audit.html` embeds it.

## 9. Handoff
- The per-problem table of the 12 graphs: items, activities, edges and the compiled optimum.
- The output of `pytest tests/test_spec51.py` and of the full suite.
- An `audit.html` built from the fixtures, with the drawn graphs.
- The sign convention, written once, as used by `graph.py`, the recipe and the checks.

## Not in this spec
- Running models (Claude queues them after review).
- Plugging the graph checks into DORA's runtime verifier in `dora-main`. That gets its own spec once the bench shows which checks catch real errors.
- Training. If graphs turn out to be cheaper and as accurate, verified graphs become the training data for a small specialist (LoRA), under SPEC-48's split and its own cost approval.

## What we learn
- Whether a small model on the threshold **solves more problems** when it formulates a graph instead of a sheet, or when it goes one step at a time.
- Whether the graph is **cheaper per solved problem**. It may be, or it may not; the bench answers it.
- Which structural checks catch real errors without knowing the answer. They are the candidates for DORA's runtime verifier, the part that makes a formulation trustworthy in a company.
