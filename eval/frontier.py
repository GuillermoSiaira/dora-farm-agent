"""Cost-accuracy frontier (SPEC-24).

Plots models and conditions on the cost-accuracy plane:
- x: USD per question (log scale)
- y: Share of verified correct answers (with 95% bootstrap error bars)
- Identifies Pareto-efficient frontier points (points not dominated by any other point)
- Outputs interactive HTML plot (eval/results/frontier.html) and Markdown table.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import plotly.graph_objects as go

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval.economics import compute_run_economics, get_pricing_entry, load_pricing

RESULTS_DIR = ROOT / "results"
DEFAULT_FRONTIER_HTML = RESULTS_DIR / "frontier.html"


def find_efficient_frontier(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Identify Pareto-efficient points on the cost vs accuracy plane.
    
    A point P is dominated if there exists another point Q such that:
    cost(Q) <= cost(P) and accuracy(Q) >= accuracy(P),
    with at least one strict inequality (< or >).
    An efficient point is not dominated by any other point.
    """
    def _get_cost(p: dict) -> float | None:
        for k in ("cost_per_question", "cost", "x"):
            v = p.get(k)
            if v is not None and isinstance(v, (int, float)):
                return float(v)
        return None

    def _get_acc(p: dict) -> float | None:
        for k in ("accuracy", "verified_correct_rate", "y"):
            v = p.get(k)
            if v is not None and isinstance(v, (int, float)):
                return float(v)
        return None

    results = []
    for i, p1 in enumerate(points):
        x1 = _get_cost(p1)
        y1 = _get_acc(p1)
        res = dict(p1)

        if x1 is None or y1 is None:
            res["efficient"] = False
            results.append(res)
            continue

        dominated = False
        for j, p2 in enumerate(points):
            if i == j:
                continue
            x2 = _get_cost(p2)
            y2 = _get_acc(p2)
            if x2 is None or y2 is None:
                continue

            # p2 dominates p1 if p2 has lower or equal cost AND higher or equal accuracy,
            # with at least one strict inequality.
            if x2 <= x1 and y2 >= y1 and (x2 < x1 or y2 > y1):
                dominated = True
                break

        res["efficient"] = not dominated
        results.append(res)

    return results


def build_frontier_points(results_data_list: list[dict], pricing: dict) -> list[dict[str, Any]]:
    """Build points for each result dictionary using pricing entries."""
    points = []
    for data in results_data_list:
        model = data.get("model", "unknown")
        provider = data.get("provider")
        pe = get_pricing_entry(pricing, model, provider)
        econ = compute_run_economics(data, pe)

        name = f"{model}@{provider}" if provider else model
        cond = econ["condition"]
        pt_name = f"{name} ({cond})"

        ci = econ["verified_correct_ci"]
        acc = econ["verified_correct_rate"]
        low, high = ci if isinstance(ci, tuple) else (acc, acc)

        points.append({
            "name": pt_name,
            "model": model,
            "provider": provider,
            "condition": cond,
            "cost_per_question": econ["usd_per_question"],
            "accuracy": acc,
            "ci_lower": low,
            "ci_upper": high,
            "usd_per_verified_correct": econ["usd_per_verified_correct_answer"],
            "pricing_source": econ["pricing_source"],
        })

    return find_efficient_frontier(points)


def generate_frontier_html(
    points: list[dict[str, Any]],
    output_path: Path | str = DEFAULT_FRONTIER_HTML,
) -> go.Figure:
    """Generate Plotly scatter plot of the cost-accuracy frontier and write HTML."""
    valid_points = [p for p in points if p.get("cost_per_question") is not None and p.get("accuracy") is not None]
    
    fig = go.Figure()

    if valid_points:
        eff_points = [p for p in valid_points if p.get("efficient")]
        dom_points = [p for p in valid_points if not p.get("efficient")]

        # Sort efficient points by cost to draw frontier curve
        eff_sorted = sorted(eff_points, key=lambda p: float(p["cost_per_question"]))

        if len(eff_sorted) > 1:
            fig.add_trace(go.Scatter(
                x=[p["cost_per_question"] for p in eff_sorted],
                y=[p["accuracy"] for p in eff_sorted],
                mode="lines",
                name="Pareto Frontier",
                line=dict(color="#16a34a", dash="dash", width=2),
                hoverinfo="skip",
            ))

        if eff_points:
            x_eff = [p["cost_per_question"] for p in eff_points]
            y_eff = [p["accuracy"] for p in eff_points]
            err_plus = [p["ci_upper"] - p["accuracy"] for p in eff_points]
            err_minus = [p["accuracy"] - p["ci_lower"] for p in eff_points]
            hover_eff = [
                f"<b>{p['name']}</b><br>Cost/q: ${p['cost_per_question']:.5f}<br>Verified Correct: {p['accuracy']:.1%} [{p['ci_lower']:.1%}, {p['ci_upper']:.1%}]<br><b>Pareto Efficient</b>"
                for p in eff_points
            ]

            fig.add_trace(go.Scatter(
                x=x_eff,
                y=y_eff,
                mode="markers+text",
                name="Efficient Points",
                text=[p["name"] for p in eff_points],
                textposition="top right",
                marker=dict(size=12, color="#16a34a", symbol="star"),
                error_y=dict(type="data", symmetric=False, array=err_plus, arrayminus=err_minus, color="#16a34a"),
                hovertext=hover_eff,
                hoverinfo="text",
            ))

        if dom_points:
            x_dom = [p["cost_per_question"] for p in dom_points]
            y_dom = [p["accuracy"] for p in dom_points]
            err_plus_d = [p["ci_upper"] - p["accuracy"] for p in dom_points]
            err_minus_d = [p["accuracy"] - p["ci_lower"] for p in dom_points]
            hover_dom = [
                f"<b>{p['name']}</b><br>Cost/q: ${p['cost_per_question']:.5f}<br>Verified Correct: {p['accuracy']:.1%} [{p['ci_lower']:.1%}, {p['ci_upper']:.1%}]<br>Dominated"
                for p in dom_points
            ]

            fig.add_trace(go.Scatter(
                x=x_dom,
                y=y_dom,
                mode="markers+text",
                name="Dominated Points",
                text=[p["name"] for p in dom_points],
                textposition="top right",
                marker=dict(size=9, color="#9ca3af", symbol="circle"),
                error_y=dict(type="data", symmetric=False, array=err_plus_d, arrayminus=err_minus_d, color="#9ca3af"),
                hovertext=hover_dom,
                hoverinfo="text",
            ))

    fig.update_layout(
        title="<b>Cost–Accuracy Frontier</b> (Verified Correct Answers vs USD per Question)",
        xaxis=dict(
            title="USD per question (log scale)",
            type="log",
            showgrid=True,
        ),
        yaxis=dict(
            title="Verified Correct Answers (%)",
            tickformat=".1%",
            range=[0.0, 1.05],
            showgrid=True,
        ),
        template="plotly_white",
        height=550,
        margin=dict(l=60, r=40, t=60, b=50),
    )

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(out))
    return fig


def generate_frontier_markdown(points: list[dict[str, Any]]) -> str:
    """Format the frontier points as a clean Markdown table."""
    lines = [
        "| Model @ Provider (Condition) | USD / question | Verified correct (95% CI) | Efficient |",
        "|---|---|---|---|",
    ]
    for p in points:
        cost_str = f"${p['cost_per_question']:.5f}" if p.get("cost_per_question") is not None else "price unknown"
        acc = p.get("accuracy", 0.0)
        low = p.get("ci_lower", acc)
        high = p.get("ci_upper", acc)
        acc_str = f"{acc:.1%} [{low:.1%}, {high:.1%}]"
        eff_str = "**Yes**" if p.get("efficient") else "No"
        lines.append(f"| {p['name']} | {cost_str} | {acc_str} | {eff_str} |")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate cost-accuracy frontier plot and table")
    parser.add_argument("results", nargs="+", help="Result JSON files")
    parser.add_argument("--pricing", type=str, default=str(ROOT / "pricing.json"), help="Path to pricing.json")
    parser.add_argument("--output", type=str, default=str(DEFAULT_FRONTIER_HTML), help="Output HTML path")
    args = parser.parse_args()

    pricing = load_pricing(args.pricing)
    results_list = []
    for r in args.results:
        p = Path(r)
        if p.is_file():
            with open(p, encoding="utf-8") as f:
                results_list.append(json.load(f))

    points = build_frontier_points(results_list, pricing)
    generate_frontier_html(points, output_path=args.output)
    md = generate_frontier_markdown(points)
    print(md)
    print(f"\nPlot saved to {args.output}")


if __name__ == "__main__":
    main()
