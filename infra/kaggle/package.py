"""Zip the code the Kaggle notebook needs (dora/ and the evaluation files) into dora-code.zip.

    python infra/kaggle/package.py <output folder>

The folder then holds dora-code.zip and dataset-metadata.json, ready for
`kaggle datasets create -p <folder>` (private by default) or `kaggle datasets version -p <folder> -m "..."`."""
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVAL_FILES = ["__init__.py", "run_eval.py", "run_e9.py", "baseline.py", "build_answers.py", "plan_check.py",
              "mcp_agent.py", "questions.jsonl", "answers.jsonl"]


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out / "dora-code.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for p in (ROOT / "dora").rglob("*"):
            if p.is_file() and "__pycache__" not in p.parts:
                z.write(p, p.relative_to(ROOT).as_posix())
        for name in EVAL_FILES:
            p = ROOT / "eval" / name
            if p.is_file():
                z.write(p, f"eval/{name}")
    meta = {"title": "dora-code", "id": f"{sys.argv[2] if len(sys.argv) > 2 else 'USER'}/dora-code",
            "licenses": [{"name": "other"}]}
    (out / "dataset-metadata.json").write_text(json.dumps(meta, indent=2))
    print(out / "dora-code.zip", (out / "dora-code.zip").stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
