"""E9 analysis and chart: correct and verified answers by model size, per arm; elasticity of the error; cost.

    python eval/plot_e9.py [results folder]       (default eval/results/e9/full)

Reads <model>_<arm>.json and <model>_summary.json written by eval/run_e9.py. Writes analysis.json next to
them and docs/screenshots/e9-model-size.png. Only measured points are drawn; nothing is extrapolated."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Parameters (billions) from the Qwen2.5 model cards; dense models, so active = total.
PARAMS_B = {"Qwen2.5-1.5B-Instruct": 1.54, "Qwen2.5-3B-Instruct": 3.09, "Qwen2.5-7B-Instruct": 7.61,
            "Qwen2.5-14B-Instruct": 14.7, "Qwen2.5-32B-Instruct": 32.5, "Qwen2.5-72B-Instruct": 72.7}
ARMS = [("alone", "Model alone", "#2a78d6"), ("dora", "Model + DORA's agent", "#eb6834"),
        ("mcp", "Generic agent + MCP", "#1baf7a"), ("mcp_guide", "Generic agent + MCP + guide", "#eda100")]
THRESHOLD = 0.90
T_975 = {1: 12.71, 2: 4.30, 3: 3.18, 4: 2.78, 5: 2.57, 6: 2.45}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def slope(xs: list[float], ys: list[float]) -> dict | None:
    """OLS slope of ys on xs with a 95 % interval (t with n-2 degrees of freedom)."""
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    resid = [y - (my + b * (x - mx)) for x, y in zip(xs, ys)]
    se = math.sqrt(sum(r * r for r in resid) / (n - 2) / sxx)
    t = T_975.get(n - 2, 2.0)
    return {"slope": round(b, 3), "ci95": [round(b - t * se, 3), round(b + t * se, 3)], "points": n}


def load(folder: Path) -> dict:
    data = {}
    for f in sorted(folder.glob("*_summary.json")):
        s = json.loads(f.read_text(encoding="utf-8"))
        name = s["model"].split("/")[-1]
        walls = {a: v.get("wall_s", 0.0) for a, v in s["arms"].items()}
        total_wall = sum(walls.values()) or 1.0
        usd = s.get("gpu_usd_actual", s["gpu_usd_estimate"])
        row = {"params_b": PARAMS_B.get(name), "gpu_usd": usd, "cold_start_s": s["cold_start_s"], "arms": {}}
        for arm, _, _ in ARMS:
            p = folder / f"{name.replace('.', '_')}_{arm}.json"
            if not p.is_file():
                continue
            d = json.loads(p.read_text(encoding="utf-8"))
            recs = [r for run in d["detailed_results"] for r in run if not r.get("skipped")]
            k = sum(bool(r.get("correct_verified")) for r in recs)
            calls = [c for r in recs for c in (r.get("tool_calls") or [])]
            arm_usd = usd * walls.get(arm, 0.0) / total_wall   # cold start and idle shared by wall time
            row["arms"][arm] = {
                "n": len(recs), "correct_verified": k, "rate": k / len(recs) if recs else None,
                "ci95": wilson(k, len(recs)),
                "e1_rule_correct": sum(bool(r.get("answer_correctness")) for r in recs),
                "tool_call_ok": (sum(1 for c in calls if not c.get("error") and not c.get("rejected")) / len(calls))
                if calls else None,
                "answers_without_tool_call": sum(1 for r in recs if r.get("no_tool_call")) if arm != "alone" else None,
                "failed": sum(1 for r in recs if r.get("failed")),
                "prompt_tokens_per_answer": round(sum(r["prompt_tokens"] for r in recs) / len(recs)),
                "completion_tokens_per_answer": round(sum(r["completion_tokens"] for r in recs) / len(recs)),
                "usd": round(arm_usd, 3),
                "usd_per_correct_verified": round(arm_usd / k, 3) if k else None,
            }
        data[name] = row
    return data


def analyse(data: dict) -> dict:
    out = {"elasticity_of_error": {}, "threshold_90": {}}
    models = sorted(data, key=lambda m: data[m]["params_b"] or 0)
    for arm, _, _ in ARMS:
        pts = [(data[m]["params_b"], data[m]["arms"][arm]) for m in models if arm in data[m]["arms"]]
        # error smoothed as (errors + 0.5) / (n + 1), so that a 0 % error still has a logarithm
        xs = [math.log(p) for p, a in pts]
        ys = [math.log((a["n"] - a["correct_verified"] + 0.5) / (a["n"] + 1)) for p, a in pts]
        out["elasticity_of_error"][arm] = slope(xs, ys)
        reached = [p for p, a in pts if a["rate"] is not None and a["rate"] >= THRESHOLD]
        out["threshold_90"][arm] = min(reached) if reached else None
        above = [(x, y) for (p, a), x, y in zip(pts, xs, ys) if reached and p >= min(reached)]
        if len(above) >= 3:
            out["elasticity_of_error"][arm + "_above_threshold"] = slope([x for x, _ in above], [y for _, y in above])
    return out


def plot(data: dict, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    models = sorted(data, key=lambda m: data[m]["params_b"] or 0)
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(13, 5.4), gridspec_kw={"width_ratios": [3, 2]})
    for arm, label, color in ARMS:
        pts = [(data[m]["params_b"], data[m]["arms"][arm]) for m in models if arm in data[m]["arms"]]
        if not pts:
            continue
        x = [p for p, _ in pts]
        y = [a["rate"] * 100 for _, a in pts]
        lo = [(a["rate"] - a["ci95"][0]) * 100 for _, a in pts]
        hi = [(a["ci95"][1] - a["rate"]) * 100 for _, a in pts]
        ax.errorbar(x, y, yerr=[lo, hi], color=color, lw=2, marker="o", ms=8, capsize=3, elinewidth=1,
                    markeredgecolor="white", markeredgewidth=2, label=label)
        ax.annotate(f"{y[-1]:.0f}%", (x[-1], y[-1]), xytext=(8, 0), textcoords="offset points",
                    va="center", fontsize=10, color="#333")
        usd = [(p, a["usd_per_correct_verified"]) for p, a in pts if a["usd_per_correct_verified"]]
        if usd:
            ax2.plot([p for p, _ in usd], [u for _, u in usd], color=color, lw=2, marker="o", ms=8,
                     markeredgecolor="white", markeredgewidth=2, label=label)
    for a in (ax, ax2):
        a.set_xscale("log")
        a.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
        a.set_xticks([data[m]["params_b"] for m in models])
        a.set_xticklabels([m.split("-")[1] for m in models])
        a.set_xlabel("Qwen2.5-Instruct, parameters (log scale)")
        a.spines[["top", "right"]].set_visible(False)
        a.yaxis.grid(True, color="#e5e5e5")
        a.set_axisbelow(True)
    ax.axhline(THRESHOLD * 100, color="#999", lw=1, ls="--")
    ax.text(data[models[-1]]["params_b"], THRESHOLD * 100 + 1.5, "90 %", fontsize=9, color="#666", ha="right")
    ax.set_ylim(-3, 105)
    ax.set_ylabel("Correct and verified answers (%)")
    ax.legend(frameon=False, loc="upper left", fontsize=9.5)
    ax.set_title("Correct and verified, by model size (95 % intervals)", fontsize=12, fontweight="bold", loc="left")
    ax2.set_yscale("log")
    ax2.set_ylabel("USD of GPU per correct and verified answer (log)")
    ax2.set_title("Cost per correct answer (Modal GPU time)", fontsize=12, fontweight="bold", loc="left")
    n = {a: sorted({d["arms"][a]["n"] for d in data.values() if a in d["arms"]}) for a, _, _ in ARMS}
    fig.text(0.01, 0.01, f"E9 (6/11/2026), eval/questions.jsonl. Answers per point: alone {n['alone']}, tools "
             f"{n['dora']} (36 questions x runs; alone skips the 3 compare_regions).\n"
             "Strict scoring: numbers backed by the engine. DORA arm: 32,768-token context, prompts over it count as failed answers. Missing points in the cost panel: no correct answer.", fontsize=8.5, color="#444")
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)


def main():
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "eval" / "results" / "e9" / "full"
    data = load(folder)
    res = {"models": data, **analyse(data)}
    (folder / "analysis.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    plot(data, ROOT / "docs" / "screenshots" / "e9-model-size.png")
    for m, row in sorted(data.items(), key=lambda kv: kv[1]["params_b"] or 0):
        cells = [f"{a}: {v['correct_verified']}/{v['n']}" for a, v in row["arms"].items()]
        print(m, "|", " | ".join(cells), "| USD", round(row["gpu_usd"], 2))
    print(json.dumps({k: res[k] for k in ("elasticity_of_error", "threshold_90")}, indent=2))


if __name__ == "__main__":
    main()
