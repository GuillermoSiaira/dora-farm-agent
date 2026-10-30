"""One end-to-end question against the model served on Modal: does it answer, call DORA's tools, and how long does it take.

    .venv/Scripts/python.exe infra/modal/probe.py [question id, default q08]

Reads MODAL_API_BASE, MODAL_API_KEY and MODAL_MODEL from .env. The first request after an idle
period includes the cold start (loading the weights); the second one does not.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from openai import OpenAI

from dora.agent import Agent
from eval.run_eval import _load_dotenv, text_contains_expected_value

_load_dotenv(ROOT / ".env")
qid = sys.argv[1] if len(sys.argv) > 1 else "q08"
question = next(q for q in map(json.loads, (ROOT / "eval" / "questions.jsonl").read_text(encoding="utf-8").splitlines())
                if q["id"] == qid)
expected = next(a for a in map(json.loads, (ROOT / "eval" / "answers.jsonl").read_text(encoding="utf-8").splitlines())
                if a["id"] == qid)["expected_value"]

client = OpenAI(base_url=os.environ["MODAL_API_BASE"], api_key=os.environ["MODAL_API_KEY"], timeout=900)
runs = []
for attempt in ("first (may include cold start)", "second (warm)"):
    agent = Agent(client=client, model=os.environ["MODAL_MODEL"], use_verifier=True)
    t0 = time.perf_counter()
    reply = agent.ask(question["text"])
    elapsed = time.perf_counter() - t0
    correct = text_contains_expected_value(reply.text, expected)
    print(f"--- {qid}, {attempt}: {elapsed:.1f} s")
    print("tools:", [c["tool"] + (" (error)" if c["error"] else "") for c in reply.tool_calls])
    print("tokens:", reply.usage)
    print("verified:", reply.verified, "| correct:", correct, f"(expected {expected})")
    print(reply.text[:1200])
    runs.append({"attempt": attempt, "latency_s": round(elapsed, 1), "tool_calls": reply.tool_calls, "usage": reply.usage,
                 "verified": reply.verified, "correct_by_text_match": correct,
                 "unsupported": [u.text for u in reply.initial_unsupported], "reply": reply.text})

# The whole record, reply included, so the experiment can be read later and not only this summary.
out = ROOT / "docs" / "experimentos" / "raw" / f"{time.strftime('%Y-%m-%d_%H%M')}_modal_{qid}.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({"question": question, "expected": expected, "model": os.environ["MODAL_MODEL"],
                           "api_host": os.environ["MODAL_API_BASE"].split("/")[2], "runs": runs},
                          ensure_ascii=False, indent=2), encoding="utf-8")
print("saved:", out)
