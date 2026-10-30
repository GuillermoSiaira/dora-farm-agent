"""One end-to-end question against the model served on Modal: does it answer, call DORA's tools, and how long does it take.

    .venv/Scripts/python.exe infra/modal/probe.py q08 [--attempts 2] [--required-first] [--label name]

Reads MODAL_API_BASE, MODAL_API_KEY and MODAL_MODEL from .env. The first request after an idle
period includes the cold start (loading the weights); later ones do not.

--required-first sends tool_choice="required" on the agent's first request only, so the server must
return a tool call (vLLM enforces valid JSON with guided decoding); later requests stay on "auto",
so the model can still write its answer. The agent itself is not changed: only the client is wrapped.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from openai import OpenAI

from dora.agent import Agent
from eval.run_eval import _load_dotenv, text_contains_expected_value


class RequiredFirst:
    """An OpenAI client whose first chat completion must call a tool."""

    def __init__(self, client):
        self._client, self._first = client, True
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        if self._first:
            self._first = False
            kwargs["tool_choice"] = "required"
        return self._client.chat.completions.create(**kwargs)


parser = argparse.ArgumentParser()
parser.add_argument("qid", nargs="?", default="q08")
parser.add_argument("--attempts", type=int, default=2)
parser.add_argument("--required-first", action="store_true")
parser.add_argument("--label", default="auto")
args = parser.parse_args()

_load_dotenv(ROOT / ".env")
question = next(q for q in map(json.loads, (ROOT / "eval" / "questions.jsonl").read_text(encoding="utf-8").splitlines())
                if q["id"] == args.qid)
expected = next(a for a in map(json.loads, (ROOT / "eval" / "answers.jsonl").read_text(encoding="utf-8").splitlines())
                if a["id"] == args.qid)["expected_value"]

client = OpenAI(base_url=os.environ["MODAL_API_BASE"], api_key=os.environ["MODAL_API_KEY"], timeout=900)
runs = []
for i in range(args.attempts):
    agent_client = RequiredFirst(client) if args.required_first else client
    agent = Agent(client=agent_client, model=os.environ["MODAL_MODEL"], use_verifier=True)
    t0 = time.perf_counter()
    try:
        reply = agent.ask(question["text"])
    except Exception as e:                                  # a server error is a result too
        elapsed = time.perf_counter() - t0
        print(f"--- {args.qid}, attempt {i + 1}: error after {elapsed:.1f} s: {e}")
        runs.append({"attempt": i + 1, "latency_s": round(elapsed, 1), "error": str(e)})
        continue
    elapsed = time.perf_counter() - t0
    correct = text_contains_expected_value(reply.text, expected)
    print(f"--- {args.qid}, attempt {i + 1}: {elapsed:.1f} s")
    print("tools:", [c["tool"] + (" (error)" if c["error"] else "") for c in reply.tool_calls])
    print("tokens:", reply.usage)
    print("verified:", reply.verified, "| correct:", correct, f"(expected {expected})")
    print(reply.text[:1200])
    runs.append({"attempt": i + 1, "latency_s": round(elapsed, 1), "tool_calls": reply.tool_calls, "usage": reply.usage,
                 "verified": reply.verified, "correct_by_text_match": correct,
                 "unsupported": [u.text for u in reply.initial_unsupported], "reply": reply.text})

# The whole record, reply included, so the experiment can be read later and not only this summary.
out = ROOT / "docs" / "experimentos" / "raw" / f"{time.strftime('%Y-%m-%d_%H%M')}_modal_{args.qid}_{args.label}.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({"question": question, "expected": expected, "model": os.environ["MODAL_MODEL"],
                           "api_host": os.environ["MODAL_API_BASE"].split("/")[2], "required_first": args.required_first,
                           "runs": runs}, ensure_ascii=False, indent=2), encoding="utf-8")
print("saved:", out)
