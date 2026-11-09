"""One new experiment a day on Kaggle's model proxy (free quota: 10 USD a day, 100 a month).

    python eval/daily/run_daily.py            # runs the next pending entry of eval/daily/queue.json
    python eval/daily/run_daily.py --dry-run  # says what it would run, calls nothing

Meant to be started once a day by the Windows scheduled task "DORA experimento diario"
(infra/daily/register_task.ps1), from its own worktree, so it never touches a worktree someone is working in.

Each day:
1. refreshes the proxy token with the Kaggle CLI (`kaggle benchmarks init`; the token lasts a few hours);
2. reads the quota and stops if today's spend is already >= DAILY_CAP or the month has < MONTH_RESERVE left;
3. runs the entry's arms one at a time with eval/run_e9.py, checking the quota between arms;
4. writes eval/results/daily/<date>_<id>/ (raw results, log, summary.json with the quota before and after),
   appends a line to eval/daily/log.md, marks the entry done in eval/daily/done.json and commits those
   paths only (no push).

Keys: KAGGLE_API_TOKEN comes from D:/projects/dora-hackathon/.env, the proxy key from the kbench .env that the
CLI writes, and the MCP key from D:/projects/dora-main/.env. They are read into this process's environment only;
no key is printed, logged or written to the results."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QUEUE = ROOT / "eval" / "daily" / "queue.json"
DONE = ROOT / "eval" / "daily" / "done.json"
LOG = ROOT / "eval" / "daily" / "log.md"
RESULTS = ROOT / "eval" / "results" / "daily"
PYTHON = Path("D:/projects/dora-hackathon/.venv/Scripts/python.exe")
KAGGLE = [r"D:\projects\tools\venv\Scripts\python.exe", "-m", "kaggle"]
KBENCH = Path("D:/projects/tools/kbench")
KAGGLE_ENV = Path("D:/projects/dora-hackathon/.env")
MCP_ENV = Path("D:/projects/dora-main/.env")
DAILY_CAP = 3.0        # USD a day: 90 USD left for the month spread over its days, with some room
MONTH_RESERVE = 10.0   # USD of the month kept for hand-run experiments


def dotenv(path: Path, prefix: str = "") -> dict[str, str]:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            if k.startswith(prefix):
                out[k.strip()] = v.strip().strip('"')
    return out


def kaggle_env() -> dict[str, str]:
    return {**os.environ, **dotenv(KAGGLE_ENV, "KAGGLE_"), "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}


def quota() -> dict[str, float]:
    """Today's and this month's used and remaining USD, from `kaggle benchmarks quota`."""
    out = subprocess.run([r"D:\projects\tools\venv\Scripts\python.exe", "-m", "kaggle", "benchmarks", "quota"], capture_output=True, text=True,
                         env=kaggle_env(), timeout=120).stdout
    q = {}
    for line in out.splitlines():
        m = re.match(r"\s*(Daily|Monthly)\s+\$([\d.]+)\s+\$([\d.]+)", line)
        if m:
            q[m.group(1).lower() + "_used"] = float(m.group(2))
            q[m.group(1).lower() + "_left"] = float(m.group(3))
    if "daily_used" not in q:
        raise RuntimeError("could not read the Kaggle quota (is KAGGLE_API_TOKEN valid?)")
    return q


def refresh_proxy_token() -> str:
    env_file = KBENCH / ".env"
    env_file.unlink(missing_ok=True)
    subprocess.run([r"D:\projects\tools\venv\Scripts\python.exe", "-m", "kaggle", "benchmarks", "init", "-y", "--env-file", str(env_file),
                    "--example-file", str(KBENCH / "example_task.py")],
                   capture_output=True, text=True, env=kaggle_env(), timeout=300, check=True)
    url = dotenv(env_file).get("MODEL_PROXY_URL", "")
    if not url:
        raise RuntimeError("kaggle benchmarks init did not write MODEL_PROXY_URL")
    return url.rstrip("/") + "/openapi"


def next_entry(done: dict) -> dict | None:
    for e in json.loads(QUEUE.read_text(encoding="utf-8"))["queue"]:
        if e["id"] not in done:
            return e
    return None


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    today = dt.date.today().isoformat()
    done = json.loads(DONE.read_text(encoding="utf-8")) if DONE.exists() else {}
    if any(v.get("date") == today and v.get("status") == "done" for v in done.values()):
        print(f"{today}: an experiment already ran today")
        return
    entry = next_entry(done)
    if entry is None:
        line = f"- {today}: la cola está vacía; Claude tiene que agregar experimentos a eval/daily/queue.json"
        print(line)
        if not a.dry_run:
            with LOG.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        return
    q0 = quota()
    print(f"{today}: next is {entry['id']} ({entry['model']}, arms {entry['arms']}); quota {q0}")
    if a.dry_run:
        return
    if q0["daily_used"] >= DAILY_CAP or q0["monthly_left"] < MONTH_RESERVE:
        msg = f"- {today}: no corrió {entry['id']}: cupo (hoy {q0['daily_used']} USD, quedan {q0['monthly_left']} en el mes)"
        with LOG.open("a", encoding="utf-8") as f:
            f.write(msg + "\n")
        return

    out = RESULTS / f"{today}_{entry['id']}"
    out.mkdir(parents=True, exist_ok=True)
    base = refresh_proxy_token()
    slug = re.sub(r"[^\w\-]", "_", entry["model"].split("/")[-1])
    summary = {"id": entry["id"], "date": today, "model": entry["model"], "question_es": entry["question_es"],
               "knob": entry.get("knob"), "ids": entry.get("ids"), "quota_before": q0, "arms": {}, "skipped_arms": []}
    with (out / "run.log").open("a", encoding="utf-8") as log:
        for arm in entry["arms"]:
            q = quota()
            if q["daily_used"] >= DAILY_CAP:
                summary["skipped_arms"].append(arm)
                log.write(f"skip {arm}: daily spend {q['daily_used']} >= {DAILY_CAP}\n")
                continue
            runner = entry.get("runner", "e9")
            script_name = "eval/run_sheets.py" if runner == "sheets" else "eval/run_e9.py"
            cmd = [str(PYTHON), script_name, "--model", entry["model"], "--base", base,
                   "--key-var", "MODEL_PROXY_API_KEY", "--env", str(KBENCH / ".env"), str(MCP_ENV),
                   "--arms", arm, "--runs", str(entry.get("runs", 1)), "--concurrency", "2",
                   "--max-tokens", str(entry.get("max_tokens", 8192)), "--gpu-usd-per-s", "0", "--out", str(out)]
            if entry.get("ids"):
                cmd += ["--ids", ",".join(entry["ids"])]
            if entry.get("knob") and runner != "sheets":
                cmd += ["--knob", entry["knob"]]
            log.write(f"run {arm}\n")
            log.flush()
            r = subprocess.run(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, env=kaggle_env(), timeout=4 * 3600)
            s = out / f"{slug}_summary.json"
            if s.exists():
                summary["arms"].update(json.loads(s.read_text(encoding="utf-8")).get("arms", {}))
                s.unlink()
            if r.returncode:
                summary["arms"].setdefault(arm, {})["exit_code"] = r.returncode
            git("checkout", "--", "dora/data")   # the run refreshes prices: keep the data files as committed
    summary["quota_after"] = quota()
    summary["usd"] = round(summary["quota_after"]["daily_used"] - q0["daily_used"], 2)
    (out / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    parts = []
    for arm, v in summary["arms"].items():
        cv = v.get("correct_verified_rate")
        parts.append(f"{arm} {'error' if cv is None else f'{cv:.0%}'}")
    line = (f"- {today} · {entry['id']} · {entry['model']}{' + ' + entry['knob'] if entry.get('knob') else ''}: "
            f"{', '.join(parts) or 'sin resultados'} (correctas y verificadas) · {summary['usd']} USD"
            f"{' · brazos sin correr: ' + ', '.join(summary['skipped_arms']) if summary['skipped_arms'] else ''}")
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    done[entry["id"]] = {"date": today, "status": "done", "usd": summary["usd"]}
    DONE.write_text(json.dumps(done, indent=2), encoding="utf-8")
    print(line)
    git("add", str(out.relative_to(ROOT)), str(LOG.relative_to(ROOT)), str(DONE.relative_to(ROOT)))
    git("commit", "-q", "-m", f"Daily experiment {today}: {entry['id']}\n\n"
        "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>")


if __name__ == "__main__":
    main()
