"""Format evaluation metrics into a Markdown report table and save to eval/REPORT.md."""
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
) -> str:
    """Read result files or dicts and write Markdown report table."""
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

    # Auto-discover latest results if none passed
    if with_v is None and no_v is None:
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
    args = parser.parse_args()

    file1 = args.results[0] if len(args.results) > 0 else None
    file2 = args.results[1] if len(args.results) > 1 else None

    report = generate_report(file1, file2, output_path=args.output)
    print(report)


if __name__ == "__main__":
    main()
