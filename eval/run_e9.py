"""E9: one model served on Modal (infra/modal/serve_open.py), the three arms, one results folder.

    python eval/run_e9.py --model Qwen/Qwen2.5-7B-Instruct --base <server URL>/v1 --ids q01,q04,q08 \
        --env D:/projects/dora-main/.env --out eval/results/e9/pilot

Keys are read from the .env file inside this process (--key-var, MODAL_API_KEY by default, DORA_MCP_API_KEY
for the MCP): they never go on the command line or into the results.

Writes <out>/<model>_<arm>.json per arm and <out>/<model>_summary.json with the wall-clock window the GPU
was up (cold start + arms + the 5 idle minutes before Modal scales to zero), to estimate its cost."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))

from eval.run_eval import _load_dotenv, run_evaluation  # noqa: E402

ARMS = {"alone": {"baseline": True}, "dora": {}, "mcp": {"arm": "mcp"}, "mcp_guide": {"arm": "mcp", "mcp_guide": True}}
SCALEDOWN_S = 300


def warm_up(client, model: str) -> float:
    """One tiny request; the first after a scale-to-zero waits for the container to load the weights."""
    t0 = time.perf_counter()
    client.chat.completions.create(model=model, messages=[{"role": "user", "content": "ok"}], max_tokens=8)
    return time.perf_counter() - t0


def capped(client, max_tokens: int):
    """The same client, with a ceiling on the tokens of each answer: a small model that loops writing JSON
    (Qwen 7B alone wrote 30,000 tokens on q09 in the pilot) ends as a wrong answer, not as GPU time."""
    create = client.chat.completions.create

    def create_capped(**kw):
        kw.setdefault("max_tokens", max_tokens)
        return create(**kw)
    client.chat.completions.create = create_capped
    return client


_CALL_AS_TEXT = re.compile(r"<tool_call>|\{\s*\"name\"\s*:\s*\"\w+\"\s*,\s*\"(arguments|parameters)\"", re.I)


def with_grammar(client, log: list):
    """E12 knob "grammar": the tool call can only come out in the tools' JSON schema. vLLM does it with guided
    decoding when tool_choice="required". Applied (1) to the first request of the farmer's question, so the
    model has to call the engine, and (2) once more when the model writes a call as text instead of making it.
    The other requests stay on "auto", so the model can still write its answer. Only in the eval harness."""
    create = client.chat.completions.create

    def create_guided(**kw):
        msgs = kw.get("messages") or []
        first = bool(kw.get("tools")) and msgs and msgs[-1].get("role") == "user" \
            and not any(m.get("role") == "assistant" for m in msgs)
        if first:
            log.append("first")
            return create(**kw, tool_choice="required")
        resp = create(**kw)
        msg = resp.choices[0].message
        if kw.get("tools") and not msg.tool_calls and _CALL_AS_TEXT.search(msg.content or ""):
            log.append("call_as_text")
            return create(**kw, tool_choice="required")
        return resp
    client.chat.completions.create = create_guided
    return client


FEWSHOT_IDS = ("q01", "q09")   # left out of the E12 comparison (eval/e12_mechanic.py EXAMPLE_IDS)


def fewshot_block(path: Path) -> str:
    """Two worked examples from DeepSeek V4.1 Flash inside DORA (E10, both correct and verified): the farmer's
    words, the tool calls with their arguments, and the answer. Tool results are left out (they are long)."""
    d = json.loads(path.read_text(encoding="utf-8"))
    recs = {r["id"]: r for r in d["detailed_results"][0]}
    parts = ["Worked examples (two past sessions that were correct and verified). Follow the same steps: call "
             "build_scenario with only what the farmer said, then the tool that answers, then a short answer "
             "that quotes only numbers from the tool results. Never reuse the numbers of these examples."]
    for i, qid in enumerate(FEWSHOT_IDS, 1):
        r = recs[qid]
        assert r.get("correct_verified"), qid
        calls = "\n".join(f"call {c['tool']}({c['arguments']})" for c in r["tool_calls"])
        parts.append(f"Example {i}\nFarmer: {r['text']}\n{calls}\nAnswer:\n{r['reply']}")
    return "\n\n".join(parts)


def with_fewshot(client, block: str):
    """E12 knob "fewshot": the examples go at the end of the system prompt, the same text in every request."""
    create = client.chat.completions.create

    def create_fewshot(**kw):
        msgs = kw.get("messages") or []
        if msgs and msgs[0].get("role") == "system":
            kw["messages"] = [dict(msgs[0], content=msgs[0]["content"] + "\n\n" + block)] + list(msgs[1:])
        return create(**kw)
    client.chat.completions.create = create_fewshot
    return client


def rescore(folder: Path) -> list[dict]:
    """Apply the E9 rule (strict_score) to saved results, without calling any model; rewrites the files."""
    from eval.run_eval import DEFAULT_ANSWERS_PATH, DEFAULT_QUESTIONS_PATH, _read_jsonl, _rate, strict_score
    qs = {q["id"]: q for q in _read_jsonl(DEFAULT_QUESTIONS_PATH)}
    answers = {a["id"]: a["expected_value"] for a in _read_jsonl(DEFAULT_ANSWERS_PATH)}
    rows = []
    for f in sorted(folder.glob("*.json")):
        if f.name.endswith("_summary.json") or f.name == "analysis.json":
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        tools = d.get("condition") != "baseline"
        for run in d["detailed_results"]:
            for rec in run:
                strict_score(qs[rec["id"]], rec, answers, with_tools=tools)
        for m, run in zip(d["run_metrics"], d["detailed_results"]):
            scored = [r for r in run if not r.get("skipped")]
            m["correct_strict_rate"] = _rate(scored, "correct_strict")
            m["correct_verified_rate"] = _rate(scored, "correct_verified")
        f.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
        recs = [r for run in d["detailed_results"] for r in run if not r.get("skipped")]
        rows.append({"file": f.name, "n": len(recs),
                     "e1_rule": sum(bool(r.get("answer_correctness")) for r in recs),
                     "strict": sum(bool(r.get("correct_strict")) for r in recs),
                     "strict_verified": sum(bool(r.get("correct_verified")) for r in recs)})
    return rows


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--rescore":
        for r in rescore(Path(sys.argv[2])):
            print(f"{r['file']}: of {r['n']}, E1 rule {r['e1_rule']}, strict {r['strict']}, "
                  f"strict and verified {r['strict_verified']}")
        return
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--model", required=True)
    p.add_argument("--base", required=True, help="OpenAI-compatible base URL of the vLLM server (ends in /v1)")
    p.add_argument("--max-tokens", type=int, default=4096, help="ceiling on each answer's tokens")
    p.add_argument("--ids", default=None, help="comma-separated question ids (default: all)")
    p.add_argument("--arms", default="alone,dora,mcp", help=f"comma-separated, of {', '.join(ARMS)}")
    p.add_argument("--runs", type=int, default=1)
    p.add_argument("--concurrency", type=int, default=4)
    p.add_argument("--env", nargs="+", default=[str(ROOT.parent / ".env")],
                   help="one or more .env files (the first one that sets a variable wins)")
    p.add_argument("--gpu-usd-per-s", type=float, default=0.000542, help="Modal L40S by default")
    p.add_argument("--key-var", default="MODAL_API_KEY",
                   help="variable of --env with the server's key (e.g. BASETEN_OWN_API_KEY for a model API)")
    p.add_argument("--usd-per-m", type=float, nargs=3, default=None, metavar=("IN", "CACHED_IN", "OUT"),
                   help="per-token billing (USD per million tokens): cost from tokens instead of GPU time")
    p.add_argument("--out", default=str(ROOT / "results" / "e9"))
    p.add_argument("--knob", choices=["grammar", "fewshot", "both"], default=None,
                   help="E12: one knob on the model (eval/e12_mechanic.py); only the dora arm makes sense")
    p.add_argument("--fewshot-from", default=str(ROOT / "results" / "e10" / "api" / "DeepSeek-V4_1-Flash_dora.json"))
    a = p.parse_args()

    for env_file in a.env:
        _load_dotenv(Path(env_file))
    if not os.environ.get(a.key_var):
        sys.exit(f"{a.key_var} missing in --env")
    os.environ["DORA_API_BASE"] = a.base
    os.environ["DORA_API_KEY"] = os.environ[a.key_var]
    os.environ["DORA_MODEL"] = a.model
    from dora.agent import default_client
    # many retries with backoff: a new account on a model API has a low per-minute limit (429)
    client = capped(default_client().with_options(max_retries=12), a.max_tokens)
    grammar_log: list = []
    if a.knob in ("grammar", "both"):
        client = with_grammar(client, grammar_log)
    if a.knob in ("fewshot", "both"):      # applied last, so the examples are in every request, forced or not
        client = with_fewshot(client, fewshot_block(Path(a.fewshot_from)))

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^\w\-]", "_", a.model.split("/")[-1])
    t_start = time.time()
    cold_s = warm_up(client, a.model)
    print(f"{a.model}: first answer after {cold_s:.0f} s", flush=True)
    summary = {"model": a.model, "cold_start_s": round(cold_s, 1), "arms": {}, "knob": a.knob}
    for arm in a.arms.split(","):
        t0 = time.time()
        res = run_evaluation(client=client, model=a.model, runs=a.runs, concurrency=a.concurrency,
                             ids=a.ids.split(",") if a.ids else None, provider="modal",
                             output_path=out / f"{slug}_{arm}.json", **ARMS[arm])
        agg = {k: v["mean"] for k, v in res["aggregated"].items() if isinstance(v, dict)}
        agg["failed"] = sum(m["failed_count"] for m in res["run_metrics"])
        agg["wall_s"] = round(time.time() - t0, 1)
        if a.usd_per_m:
            recs = [r for run in res["detailed_results"] for r in run]
            p_in, p_cached, p_out = a.usd_per_m
            cached = sum(r.get("cached_prompt_tokens", 0) for r in recs)
            prompt = sum(r.get("prompt_tokens", 0) for r in recs)
            agg["token_usd"] = round(((prompt - cached) * p_in + cached * p_cached
                                      + sum(r.get("completion_tokens", 0) for r in recs) * p_out) / 1e6, 4)
        summary["arms"][arm] = agg
        cv = agg.get("correct_verified_rate")
        print(f"  {arm}: correct+verified {cv if cv is None else round(cv, 2)}, "
              f"correct {agg.get('answer_correctness')}, tool calls ok {agg.get('tool_call_ok_rate')}, "
              f"no call {agg.get('no_tool_call_rate')}, failed {agg['failed']}, {agg['wall_s']} s", flush=True)
    if a.knob in ("grammar", "both"):
        summary["grammar_forced"] = {k: grammar_log.count(k) for k in ("first", "call_as_text")}
    up_s = time.time() - t_start + SCALEDOWN_S
    if a.usd_per_m:
        total = sum(v.get("token_usd", 0) for v in summary["arms"].values())
        summary["billing"] = "per_token"
        summary["gpu_usd_estimate"] = round(total, 3)       # same field, so plot_e9 reads it; it is token cost
        (out / f"{slug}_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"  token cost ~{total:.2f} USD (list prices; the provider's bill has the real number)")
        return
    summary["gpu_up_s_estimate"] = round(up_s, 1)
    summary["gpu_usd_estimate"] = round(up_s * a.gpu_usd_per_s, 3)
    (out / f"{slug}_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"  GPU up ~{up_s / 60:.1f} min, ~{summary['gpu_usd_estimate']} USD (estimate; Modal's dashboard has the bill)")


if __name__ == "__main__":
    main()
