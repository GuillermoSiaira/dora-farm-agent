"""E12, the LLM mechanic: which knob fixes which kind of error, at what cost, and the shadow price of the budget.

    python eval/e12_mechanic.py prior            # step 0: E9 errors (fixes64k) by kind, and each knob's ceiling
    python eval/e12_mechanic.py measure          # knobs measured in eval/results/e12: fixed, broken, silent failures
    python eval/e12_mechanic.py lp [--q 1000] [--budget 3]   # choose knobs as a linear program (HiGHS)

No model is called: it reads saved results. The grader here knows the answers (eval/answers.jsonl): it measures
the knobs offline, on the bench. The runtime verifier does not know them; "silent" counts the answers that are
wrong and still pass the verifier, the ones a knob must not increase."""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from eval.e9_page import KINDS, kind  # noqa: E402
from eval.run_eval import DEFAULT_ANSWERS_PATH, DEFAULT_QUESTIONS_PATH, _read_jsonl  # noqa: E402

E9 = ROOT / "eval" / "results" / "e9"
E12 = ROOT / "eval" / "results" / "e12"
SIZES = ["7B", "14B"]
KNOBS = ["grammar", "fewshot", "both"]
# the two example questions shown to the model in the few-shot arm: left out of every comparison
EXAMPLE_IDS = {"q01", "q09"}
# questions whose expected number appears anywhere in the examples' text (inputs included, so it over-counts on
# purpose): `--clean` leaves them out too, the conservative reading of the few-shot knob
LEAKED_IDS = {"q04", "q05", "q06", "q07", "q08", "q10", "q11", "q15", "q16", "q21", "q25", "q31"}
EXCLUDED = set(EXAMPLE_IDS)
CALL_AS_TEXT = re.compile(r"<tool_call>|\{\s*\"name\"\s*:\s*\"(build_scenario|evaluate_season|shadow_prices|"
                          r"sensitivity|climate_outlook|climate_scenarios|next_question)", re.I)


def _qa():
    return ({q["id"]: q for q in _read_jsonl(DEFAULT_QUESTIONS_PATH)},
            {a["id"]: a["expected_value"] for a in _read_jsonl(DEFAULT_ANSWERS_PATH)})


def records(path: Path) -> list[list[dict]]:
    """Per run, the scored answers (skipped ones out), without the few-shot example questions."""
    d = json.loads(path.read_text(encoding="utf-8"))
    return [[r for r in run if not r.get("skipped") and r["id"] not in EXCLUDED] for run in d["detailed_results"]]


def label(q, r, expected) -> str:
    k = kind(q, r, expected, True)
    if k == "no_call" and CALL_AS_TEXT.search(r.get("reply") or ""):
        return "call_as_text"           # wrote the call as text: a grammar can turn it into a real call
    return k


def silent(r: dict) -> bool:
    """Wrong and still verified: the runtime verifier lets it through."""
    return bool(r.get("verified")) and not r.get("correct_verified") and not r.get("failed")


def by_question(path: Path) -> dict[str, list[str]]:
    qs, ans = _qa()
    out: dict[str, list[str]] = {}
    for run in records(path):
        for r in run:
            out.setdefault(r["id"], []).append(label(qs[r["id"]], r, ans.get(r["id"])))
    return out


def base_file(size: str) -> Path:
    return E9 / "fixes64k" / f"Qwen2_5-{size}-Instruct_dora.json"


def knob_file(size: str, knob: str) -> Path:
    return E12 / knob / f"Qwen2_5-{size}-Instruct_dora.json"


# which kinds each knob can reach, a priori (the ceiling); measured fractions replace this in `measure`
REACH = {"grammar": {"call_as_text", "no_call", "calls_failed"},
         "fewshot": {"call_as_text", "calls_failed", "wrong_scenario", "not_said", "refusal"}}


def prior():
    names = dict(KINDS, call_as_text="Escribió la llamada como texto")
    for size in SIZES:
        c = Counter(k for ks in by_question(base_file(size)).values() for k in ks)
        n = sum(c.values())
        print(f"\nQwen2.5 {size}, DORA 64k con los arreglos del E9 ({n} respuestas, sin {sorted(EXAMPLE_IDS)})")
        for k, v in c.most_common():
            print(f"  {v:3d}  {names.get(k, k)}")
        for knob, reach in REACH.items():
            top = sum(v for k, v in c.items() if k in reach)
            print(f"  techo de {knob}: {top} de {n - c['ok']} errores (+{100 * top / n:.0f} puntos como mucho)")


def measure(verbose: bool = True) -> dict:
    """Per size and knob, against the E9 baseline, per kind of error: the fraction fixed (a), the correct answers
    broken (b), silent failures and cost. Pairs the same question across runs by majority, so it is per question."""
    qs, ans = _qa()
    out = {}
    for size in SIZES:
        base = by_question(base_file(size))
        base_recs = [r for run in records(base_file(size)) for r in run]
        for knob in KNOBS:
            f = knob_file(size, knob)
            if not f.is_file():
                continue
            new = by_question(f)
            recs = [r for run in records(f) for r in run]
            summ = json.loads((f.parent / f"Qwen2_5-{size}-Instruct_summary.json").read_text(encoding="utf-8"))
            fixed, total, broken = Counter(), Counter(), 0
            for qid, kinds_before in base.items():
                kinds_after = new.get(qid, [])
                for i, kb in enumerate(kinds_before):      # run i against run i
                    if i >= len(kinds_after):
                        continue
                    ka = kinds_after[i]
                    if kb == "ok":
                        broken += ka != "ok"
                    else:
                        total[kb] += 1
                        fixed[kb] += ka == "ok"
            n = sum(len(v) for v in new.values())
            row = {"n": n, "ok_before": sum(k == "ok" for v in base.values() for k in v),
                   "ok_after": sum(k == "ok" for v in new.values() for k in v), "broken": broken,
                   "a": {k: round(fixed[k] / total[k], 3) for k in total}, "errors_before": dict(total),
                   "silent_before": sum(map(silent, base_recs)), "silent_after": sum(map(silent, recs)),
                   "kinds_after": dict(Counter(k for v in new.values() for k in v)),
                   "prompt_tokens": round(sum(r.get("prompt_tokens", 0) for r in recs) / max(1, len(recs))),
                   "prompt_tokens_before": round(sum(r.get("prompt_tokens", 0) for r in base_recs) / max(1, len(base_recs))),
                   "gpu_usd_estimate": summ.get("gpu_usd_estimate"),
                   "tokens": sum(r.get("prompt_tokens", 0) + r.get("completion_tokens", 0) for r in recs) / max(1, len(recs)),
                   "tokens_before": sum(r.get("prompt_tokens", 0) + r.get("completion_tokens", 0) for r in base_recs)
                   / max(1, len(base_recs)),
                   "base_usd_per_answer": json.loads((base_file(size).parent / f"Qwen2_5-{size}-Instruct_summary.json")
                                                     .read_text(encoding="utf-8"))["gpu_usd_estimate"] / 72,
                   "arm_wall_s": summ["arms"]["dora"]["wall_s"]}
            out[(size, knob)] = row
            if verbose:
                print(f"\n{size} + {knob}: correctas {row['ok_before']} -> {row['ok_after']} de {n}; "
                      f"rompió {broken}; fallas silenciosas {row['silent_before']} -> {row['silent_after']}; "
                      f"tokens de entrada {row['prompt_tokens_before']} -> {row['prompt_tokens']}")
                for k in total:
                    print(f"  {k}: arregló {fixed[k]} de {total[k]}")
    return out


def lp(q_answers: int, budget: float):
    """max sum_j y_j - sum_k b_k x_k  s.t.  y_j <= e_j,  y_j <= sum_k a_kj e_j x_k,  cost <= budget,
    silent failures added <= 0,  0 <= x_k <= 1. One program per size; prints the plan and the shadow prices."""
    from scipy.optimize import linprog
    m = measure(verbose=False)
    for size in SIZES:
        knobs = [k for k in KNOBS if (size, k) in m]
        if not knobs:
            continue
        kinds = sorted({j for k in knobs for j in m[(size, k)]["errors_before"]})
        e = {j: m[(size, knobs[0])]["errors_before"][j] for j in kinds}
        nk, nj = len(knobs), len(kinds)
        # variables: x_k (knobs), then y_j (errors fixed); linprog minimizes, so negate the gain
        c = [m[(size, k)]["broken"] for k in knobs] + [-1.0] * nj
        A, b, names = [], [], []
        for jj, j in enumerate(kinds):
            row = [-m[(size, k)]["a"].get(j, 0.0) * e[j] for k in knobs] + [0.0] * nj
            row[nk + jj] = 1.0
            A.append(row); b.append(0.0); names.append(f"cobertura de {j}")
        # extra cost of each knob for q_answers answers: the baseline's GPU cost per answer (E9 fixes64k bill
        # estimate) times the relative change in tokens per answer. Wall time is not comparable across runs
        # (different concurrency), tokens are. These knobs have no fixed cost beyond writing them.
        cost = []
        for k in knobs:
            r = m[(size, k)]
            cost.append(max(0.0, r["base_usd_per_answer"] * (r["tokens"] / r["tokens_before"] - 1)) * q_answers)
        A.append(cost + [0.0] * nj); b.append(budget); names.append("presupuesto (USD)")
        A.append([m[(size, k)]["silent_after"] - m[(size, k)]["silent_before"] for k in knobs] + [0.0] * nj)
        b.append(0.0); names.append("fallas silenciosas agregadas")
        bounds = [(0, 1)] * nk + [(0, e[j]) for j in kinds]
        res = linprog(c, A_ub=A, b_ub=b, bounds=bounds, method="highs")
        print(f"\n{size}: {res.message}")
        if res.status != 0:
            continue
        for kk, k in enumerate(knobs):
            print(f"  {k}: x = {res.x[kk]:.2f} (costo para {q_answers} respuestas: {cost[kk]:.2f} USD)")
        print(f"  respuestas arregladas netas, en las {m[(size, knobs[0])]['n']} medidas: {-res.fun:.1f}")
        for name, dual in zip(names, res.ineqlin.marginals):
            print(f"  precio sombra de {name}: {-dual:.3f}")
        for (lo, hi), dual, name in zip(bounds[nk:], res.upper.marginals[nk:], kinds):
            print(f"  precio sombra del tope de {name} ({hi}): {-dual:.3f}")
        print("  costos reducidos de las perillas: " + ", ".join(
            f"{k} {res.lower.marginals[kk]:.3f}" for kk, k in enumerate(knobs)))


if __name__ == "__main__":
    if "--clean" in sys.argv:
        sys.argv.remove("--clean")
        EXCLUDED |= LEAKED_IDS
    cmd = sys.argv[1] if len(sys.argv) > 1 else "prior"
    if cmd == "prior":
        prior()
    elif cmd == "measure":
        measure()
    elif cmd == "lp":
        args = sys.argv[2:]
        q = int(args[args.index("--q") + 1]) if "--q" in args else 1000
        bud = float(args[args.index("--budget") + 1]) if "--budget" in args else 3.0
        lp(q, bud)
    else:
        sys.exit(__doc__)
