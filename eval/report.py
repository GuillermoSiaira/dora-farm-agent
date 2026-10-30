"""Format evaluation metrics into a Markdown report table and save to eval/REPORT.md (SPEC-24)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval.economics import (
    calculate_breakeven_volume,
    calculate_overhead_share,
    compute_run_economics,
    get_pricing_entry,
    load_pricing,
    paired_mcnemar_comparison,
)

DEFAULT_REPORT_PATH = ROOT / "REPORT.md"
RESULTS_DIR = ROOT / "results"


def _format_metric(agg_data: dict[str, float] | None, is_pct: bool = True, decimals: int = 1) -> str:
    """Format aggregated metric into 'mean% (min% – max%)' or 'mean (min – max)'."""
    if not agg_data:
        return "N/A"
    m = agg_data.get("mean", 0.0)
    mn = agg_data.get("min", 0.0)
    mx = agg_data.get("max", 0.0)

    if is_pct:
        if abs(mn - mx) < 1e-6:
            return f"{m * 100:.{decimals}f}%"
        return f"{m * 100:.{decimals}f}% ({mn * 100:.{decimals}f}% - {mx * 100:.{decimals}f}%)"
    else:
        if abs(mn - mx) < 1e-6:
            return f"{m:.{decimals}f}"
        return f"{m:.{decimals}f} ({mn:.{decimals}f} - {mx:.{decimals}f})"


def generate_report(
    with_verifier_data: dict | Path | str | None = None,
    no_verifier_data: dict | Path | str | None = None,
    output_path: Path | str = DEFAULT_REPORT_PATH,
    pricing_path: Path | str | None = None,
    results_path: dict | Path | str | None = None,
    *extra_data: Any,
    **kwargs: Any,
) -> str:
    """Read result files or dicts and write Markdown report table with Economics section."""
    if with_verifier_data is None and results_path is not None:
        with_verifier_data = results_path
    def load_data(source: Any) -> dict | None:
        if isinstance(source, dict):
            return source
        if isinstance(source, (str, Path)):
            p = Path(source)
            if p.is_file():
                with open(p, encoding="utf-8") as f:
                    return json.load(f)
        return None

    with_v = load_data(with_verifier_data)
    no_v = load_data(no_verifier_data)
    extras = [load_data(e) for e in extra_data if load_data(e) is not None]

    # Auto-discover latest results if none passed
    if with_v is None and no_v is None and not extras:
        results_files = sorted(RESULTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        for rf in results_files:
            d = load_data(rf)
            if d:
                if d.get("use_verifier") is True and with_v is None:
                    with_v = d
                elif d.get("use_verifier") is False and no_v is None:
                    no_v = d
            if with_v and no_v:
                break

    # If only one source was passed as first argument, check its use_verifier
    if with_v is not None and no_v is None and with_v.get("use_verifier") is False:
        no_v = with_v
        with_v = None

    model_name = (
        (with_v.get("model") if with_v else None)
        or (no_v.get("model") if no_v else "DORA")
    )

    agg_with = with_v.get("aggregated", {}) if with_v else {}
    agg_no = no_v.get("aggregated", {}) if no_v else {}

    metrics_def = [
        ("Tool accuracy", "tool_accuracy", True, 1),
        ("Answer correctness", "answer_correctness", True, 1),
        ("Formulation accuracy", "formulation_accuracy", True, 1),
        ("Unsupported numbers (before correction)", "unsupported_numbers_rate", True, 1),
        ("Verified after correction", "verified_rate", True, 1),
        ("Calls per question", "calls_per_question", False, 1),
        ("Prompt tokens / question", "prompt_tokens_per_question", False, 0),
        ("Completion tokens / question", "completion_tokens_per_question", False, 0),
    ]

    lines = [
        f"# DORA Evaluation Report — {model_name}",
        "",
        "| Metric | With Verifier | Without Verifier |",
        "|---|---|---|",
    ]

    for label, key, is_pct, dec in metrics_def:
        col_with = _format_metric(agg_with.get(key), is_pct, dec) if with_v else "N/A"
        col_no = _format_metric(agg_no.get(key), is_pct, dec) if no_v else "N/A"
        lines.append(f"| {label} | {col_with} | {col_no} |")

    lines.append("")

    # --- Section: Economics (SPEC-24) ---
    all_runs = [d for d in [with_v, no_v, *extras] if d is not None and isinstance(d, dict)]
    runs_with_details = [d for d in all_runs if "detailed_results" in d or "per_question" in d]

    if runs_with_details:
        pricing = load_pricing(pricing_path)
        econ_list = []
        for d in runs_with_details:
            m = d.get("model", "unknown")
            prov = d.get("provider")
            pe = get_pricing_entry(pricing, m, prov)
            econ = compute_run_economics(d, pe)
            econ_list.append((d, econ))

        lines.append("## Economics")
        lines.append("")
        lines.append("| Model @ provider | Condition | Verified correct (95% CI) | USD / question | USD / verified correct answer (95% CI) | Latency p50 / p95 | Prices read on |")
        lines.append("|---|---|---|---|---|---|---|")

        for d, econ in econ_list:
            mod_prov = f"{econ['model']}@{econ['provider']}" if econ['provider'] else econ['model']
            cond = econ["condition"]

            vc_rate = econ["verified_correct_rate"]
            vc_ci = econ["verified_correct_ci"]
            vc_str = f"{vc_rate:.1%} [{vc_ci[0]:.1%}, {vc_ci[1]:.1%}]"

            if econ["has_pricing"]:
                cost_q = econ["usd_per_question"]
                note = f" ({econ['usd_per_question_label']})" if econ.get("usd_per_question_label") else ""
                cost_q_str = f"${cost_q:.4f}{note}" if cost_q is not None else "price unknown"

                ans_cost = econ["usd_per_verified_correct_answer"]
                if isinstance(ans_cost, (int, float)):
                    ci_vc = econ["usd_per_verified_correct_ci"]
                    ci_str = f" [${ci_vc[0]:.4f}, ${ci_vc[1]:.4f}]" if isinstance(ci_vc, tuple) else ""
                    ans_cost_str = f"${ans_cost:.4f}{ci_str}"
                else:
                    ans_cost_str = str(ans_cost)
            else:
                cost_q_str = "price unknown"
                ans_cost_str = str(econ["usd_per_verified_correct_answer"])

            lat_p50 = econ.get("latency_p50_s")
            lat_p95 = econ.get("latency_p95_s")
            if lat_p50 is not None and lat_p95 is not None:
                lat_str = f"{lat_p50:.2f}s / {lat_p95:.2f}s"
            elif lat_p50 is not None:
                lat_str = f"{lat_p50:.2f}s"
            else:
                lat_str = "N/A"

            date_str = str(econ.get("prices_read_on") or "unknown")

            lines.append(f"| {mod_prov} | {cond} | {vc_str} | {cost_q_str} | {ans_cost_str} | {lat_str} | {date_str} |")

        lines.append("")

        # Paired comparisons (McNemar test) between pairs
        if len(runs_with_details) >= 2:
            lines.append("### Paired Comparisons (McNemar exact test)")
            lines.append("")
            pairs_seen = set()
            for i in range(len(runs_with_details)):
                for j in range(i + 1, len(runs_with_details)):
                    d1, econ1 = econ_list[i]
                    d2, econ2 = econ_list[j]
                    c1_name = f"{econ1['model']} ({econ1['condition']})"
                    c2_name = f"{econ2['model']} ({econ2['condition']})"
                    pair_key = (c1_name, c2_name)
                    if pair_key in pairs_seen:
                        continue
                    pairs_seen.add(pair_key)

                    mc = paired_mcnemar_comparison(d1, d2)
                    if mc.get("questions_compared", 0) > 0:
                        lines.append(f"- **{c1_name} vs {c2_name}**: b = {mc['b']}, c = {mc['c']}, p = {mc['p_value']:.4f}")
            lines.append("")

        # Fixed prompt overhead line
        overhead_tokens = None
        for d, econ in econ_list:
            fixed_oh = d.get("fixed_prompt_overhead")
            if fixed_oh is not None:
                overhead_tokens = fixed_oh
                avg_req = econ.get("avg_requests", 1.0)
                avg_in = econ.get("avg_prompt_tokens", 0.0)
                share = calculate_overhead_share(fixed_oh, avg_req, avg_in)
                lines.append(f"**Fixed prompt overhead**: {overhead_tokens:,} tokens ({share:.1%} of prompt tokens)")
                lines.append("")
                break

        # Dedicated GPU break-even volume
        dedicated_entries = [econ for _, econ in econ_list if econ.get("billing") == "dedicated"]
        per_token_entries = [econ for _, econ in econ_list if econ.get("billing") == "per_token" and econ.get("usd_per_question") is not None]

        if dedicated_entries and per_token_entries:
            lines.append("### Break-even Volume (Dedicated GPU vs Per-Token)")
            lines.append("")
            ded = dedicated_entries[0]
            tok = per_token_entries[0]
            tok_cost = tok["usd_per_question"]
            pe_ded = get_pricing_entry(pricing, ded["model"], ded.get("provider"))
            gpu_hr = pe_ded.get("usd_per_gpu_hour") if pe_ded else None
            gpus = pe_ded.get("gpus", 1) if pe_ded else 1
            if gpu_hr is not None and tok_cost and tok_cost > 0:
                q730 = calculate_breakeven_volume(gpu_hr, gpus=gpus, hours_on_per_month=730.0, usd_per_question_per_token=tok_cost)
                q220 = calculate_breakeven_volume(gpu_hr, gpus=gpus, hours_on_per_month=220.0, usd_per_question_per_token=tok_cost)
                lines.append(f"- **Break-even vs {tok['model']}**: Q* = {q730:,.0f} questions/month (always on, 730 h); Q* = {q220:,.0f} questions/month (business hours, 220 h). Below Q*, paying per token is cheaper.")
                lines.append("")

    report_content = "\n".join(lines)

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(report_content)

    return report_content


def main():
    parser = argparse.ArgumentParser(description="Generate DORA evaluation report")
    parser.add_argument("results", nargs="*", help="Path to result JSON file(s)")
    parser.add_argument("--output", type=str, default=str(DEFAULT_REPORT_PATH), help="Path to output REPORT.md")
    parser.add_argument("--pricing", type=str, default=str(ROOT / "pricing.json"), help="Path to pricing.json")
    args = parser.parse_args()

    file1 = args.results[0] if len(args.results) > 0 else None
    file2 = args.results[1] if len(args.results) > 1 else None
    extra = args.results[2:] if len(args.results) > 2 else []

    report = generate_report(file1, file2, output_path=args.output, pricing_path=args.pricing, *extra)
    print(report)


if __name__ == "__main__":
    main()
