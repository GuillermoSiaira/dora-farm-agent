"""E2 (regional picture) and E4 (live prices and what happens when a source fails), docs/plan-de-pruebas.md.

    python eval/run_e2_e4.py e4 --env PATH/.env      # prices with network, then with the sources blocked
    python eval/run_e2_e4.py e4curve --env PATH/.env # same, asking for today's curve (agent only)
    python eval/run_e2_e4.py e2 --env PATH/.env      # observatory, compare_regions and the agent, 5 times

Run E4 first: it refreshes dora/data/price_curves/, and E2 then uses those prices ("datos del día").
Results go to eval/results/{e2,e4}_<model>_<stamp>.json. The .env is read, never printed."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

RESULTS_DIR = ROOT / "results"
PRICING = json.loads((ROOT / "pricing.json").read_text(encoding="utf-8"))

E2_QUESTION = "¿Cómo viene la campaña en las cuatro regiones?"
E4_QUESTION = ("¿A cuánto están hoy la soja y el maíz para un campo en Pergamino? "
               "Decime de qué fecha y de qué fuente es cada precio.")
# Second E4 question: the farmer asks for today's market curve, so the tools have to load the live snapshot.
E4_QUESTION_CURVE = ("Tengo 500 ha propias en Pergamino y 500.000 USD. Con la curva de precios de hoy "
                     "(futuros de Chicago más la base de MAGyP), ¿cuánto me conviene sembrar de soja y de maíz? "
                     "Decime de qué fecha y de qué fuente son los precios que usaste.")
FARM = {"area_ha": 500, "own_capital_usd": 500000}

# What counts as "the reply says the data are provisional" (E2) and "the reply says it is a saved copy" (E4).
PROVISIONAL = re.compile(r"provisori|provisional|placeholder|prelimin|a confirmar|sin verificar|no verificad|"
                         r"referencia|orientativ|aproximad|estimad", re.I)
SAVED_COPY = re.compile(r"guardad|copia|cach|últim[oa]s? (dato|precio|copia|cotizaci)|no (se )?pud|"
                        r"sin conexi|no respond|desactualiz|del \d{1,2}/10|27 de octubre|26 de octubre", re.I)
DATE = re.compile(r"\b(20\d\d-\d\d-\d\d|\d{1,2}/\d{1,2}(/\d{2,4})?|\d{1,2} de (octubre|noviembre))\b", re.I)


def load_env(path: str | None) -> None:
    if not path or not Path(path).is_file():
        return
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"'))


def cost_usd(usage: dict, model: str) -> float:
    p = PRICING[f"{model}@meta"]
    cached = usage.get("cached_prompt_tokens", 0)
    return round(((usage.get("prompt_tokens", 0) - cached) * p["usd_per_m_input"]
                  + cached * p["usd_per_m_cached_input"]
                  + usage.get("completion_tokens", 0) * p["usd_per_m_output"]) / 1e6, 5)


def ask_agent(model: str, question: str) -> dict:
    from dora.agent import Agent
    agent = Agent(model=model, use_verifier=True)
    t = time.time()
    try:
        reply = agent.ask(question)
    except Exception as e:                       # keep going: one failure is a result too
        return {"error": f"{type(e).__name__}: {e}", "seconds": round(time.time() - t, 1),
                "usage": dict(agent.usage), "cost_usd": cost_usd(agent.usage, model)}
    return {
        "text": reply.text,
        "verified": reply.verified,
        "unsupported": [str(getattr(u, "text", u)) for u in reply.unsupported],
        "initial_unsupported": [str(getattr(u, "text", u)) for u in reply.initial_unsupported],
        "tool_calls": reply.tool_calls,
        "tool_results": agent.tool_results,
        "seconds": round(time.time() - t, 1),
        "usage": reply.usage,
        "cost_usd": cost_usd(reply.usage, model),
    }


def snapshot_files() -> dict:
    from dora.feeds import ARGENTINA_LATEST_PATH, BASIS_ARGENTINA_PATH, CBOT_LATEST_PATH
    out = {}
    for p in (CBOT_LATEST_PATH, ARGENTINA_LATEST_PATH, BASIS_ARGENTINA_PATH):
        out[p.name] = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None
    return out


def age_files(hours: float) -> None:
    """Make the saved snapshots look old, so refresh() really tries the network."""
    from dora.feeds import ARGENTINA_LATEST_PATH, BASIS_ARGENTINA_PATH, CBOT_LATEST_PATH
    t = time.time() - hours * 3600
    for p in (CBOT_LATEST_PATH, ARGENTINA_LATEST_PATH, BASIS_ARGENTINA_PATH):
        if p.is_file():
            os.utime(p, (t, t))


def fetch_each_feed() -> dict:
    """Each source on its own, with its date, so a failure shows which one."""
    from dora import feeds
    out = {}
    t = time.time()
    try:
        snap = feeds.YahooCbotFeed().fetch()
        out["cbot"] = {"ok": True, "as_of": snap["as_of"], "source": snap["source"],
                       "contracts": {c: len(v) for c, v in snap["curve"].items()}, "curve": snap["curve"]}
    except Exception as e:
        out["cbot"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}
    out["cbot"]["seconds"] = round(time.time() - t, 1)
    t = time.time()
    try:
        m = feeds.MagypPricesFeed().fetch()
        out["magyp"] = {"ok": True, "date": m["date"], "quotes": m["quotes"]}
    except Exception as e:
        out["magyp"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}
    out["magyp"]["seconds"] = round(time.time() - t, 1)
    t = time.time()
    try:
        rate, date = feeds.BcraFxFeed().fetch_rate_and_date(out["magyp"].get("date"))
        out["bcra"] = {"ok": True, "ars_per_usd": rate, "date": date}
    except Exception as e:
        out["bcra"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}
    out["bcra"]["seconds"] = round(time.time() - t, 1)
    return out


def block(sources: tuple[str, ...]) -> None:
    """Point the chosen feeds at a host that does not exist (.invalid never resolves, RFC 2606)."""
    from dora import feeds
    if "cbot" in sources:
        feeds.YahooCbotFeed.URL_TEMPLATE = "https://dora-blocked.invalid/{symbol}"
    if "magyp" in sources:
        feeds.MagypPricesFeed.URL = "https://dora-blocked.invalid/magyp"
    if "bcra" in sources:
        feeds.BcraFxFeed.URL = "https://dora-blocked.invalid/bcra"


def marks(text: str) -> dict:
    return {"mentions_date": bool(DATE.search(text or "")),
            "mentions_saved_copy": bool(SAVED_COPY.search(text or "")),
            "mentions_provisional": bool(PROVISIONAL.search(text or ""))}


def run_e4(model: str, runs: int) -> dict:
    from dora import feeds
    out: dict = {"question": E4_QUESTION, "conditions": {}}

    # 1. With network: each source, then the refresh the tools use.
    live = {"feeds": fetch_each_feed()}
    age_files(48)
    live["refresh"] = feeds.refresh(max_age_hours=24)
    live["files"] = snapshot_files()
    live["answers"] = []
    for i in range(runs):
        a = ask_agent(model, E4_QUESTION)
        a.update(marks(a.get("text", "")))
        live["answers"].append(a)
        print(f"e4 live {i + 1}: {a.get('seconds')} s, {a.get('cost_usd')} USD", flush=True)
    out["conditions"]["live"] = live

    # 2. Every source blocked: the copy from step 1 has to be used, and said.
    originals = (feeds.YahooCbotFeed.URL_TEMPLATE, feeds.MagypPricesFeed.URL, feeds.BcraFxFeed.URL)
    block(("cbot", "magyp", "bcra"))
    blocked = {"feeds": fetch_each_feed()}
    age_files(48)
    blocked["refresh"] = feeds.refresh(max_age_hours=24)
    blocked["files"] = snapshot_files()
    blocked["answers"] = []
    for i in range(runs):
        age_files(48)                             # the tools call refresh() again: keep it trying the network
        a = ask_agent(model, E4_QUESTION)
        a.update(marks(a.get("text", "")))
        blocked["answers"].append(a)
        print(f"e4 blocked {i + 1}: {a.get('seconds')} s, {a.get('cost_usd')} USD", flush=True)
    out["conditions"]["all_blocked"] = blocked

    # 3. Only MAGyP blocked: CBOT updates, the Argentine curve cannot.
    feeds.YahooCbotFeed.URL_TEMPLATE, feeds.MagypPricesFeed.URL, feeds.BcraFxFeed.URL = originals
    block(("magyp",))
    partial = {"feeds": fetch_each_feed()}
    age_files(48)
    partial["refresh"] = feeds.refresh(max_age_hours=24)
    partial["files"] = snapshot_files()
    out["conditions"]["magyp_blocked"] = partial
    feeds.YahooCbotFeed.URL_TEMPLATE, feeds.MagypPricesFeed.URL, feeds.BcraFxFeed.URL = originals
    return out


def run_e4_curve(model: str, runs: int) -> dict:
    """Agent only, with the curve question: the snapshot from run_e4 (fresh), then every source blocked."""
    from dora import feeds
    out: dict = {"question": E4_QUESTION_CURVE, "conditions": {}}
    for name, blocked in (("live", ()), ("all_blocked", ("cbot", "magyp", "bcra"))):
        originals = (feeds.YahooCbotFeed.URL_TEMPLATE, feeds.MagypPricesFeed.URL, feeds.BcraFxFeed.URL)
        block(blocked)
        cond = {"blocked": list(blocked), "answers": []}
        if blocked:
            age_files(48)
            cond["refresh"] = feeds.refresh(max_age_hours=24)
        cond["files"] = snapshot_files()
        for i in range(runs):
            if blocked:
                age_files(48)
            a = ask_agent(model, E4_QUESTION_CURVE)
            a.update(marks(a.get("text", "")))
            cond["answers"].append(a)
            print(f"e4curve {name} {i + 1}: {a.get('seconds')} s, {a.get('cost_usd')} USD", flush=True)
        feeds.YahooCbotFeed.URL_TEMPLATE, feeds.MagypPricesFeed.URL, feeds.BcraFxFeed.URL = originals
        out["conditions"][name] = cond
    return out


def run_e2(model: str, runs: int) -> dict:
    from dora.observatory import run_observatory
    from dora.tools import compare_regions
    out: dict = {"question": E2_QUESTION, "farm": FARM}

    key = os.environ.pop("DORA_API_KEY", None)      # observatory without commentary first: engine only
    out["observatory"] = run_observatory(scenario_template=dict(FARM), save=False)
    if key:
        os.environ["DORA_API_KEY"] = key
    from dora.agent import default_client
    obs_c = run_observatory(scenario_template=dict(FARM), save=False, client=default_client(), model=model)
    out["observatory_commentary"] = obs_c["commentary"]

    out["compare_regions"] = {}
    for mode in ("same_farm", "same_budget"):
        for curve in ("argentina_latest", None):
            sc = dict(FARM, **({"price_curve_source": curve} if curve else {}))
            t = time.time()
            try:
                res = compare_regions(sc, mode=mode, lang="es")
            except Exception as e:
                res = {"error": f"{type(e).__name__}: {e}"}
            out["compare_regions"][f"{mode}|{curve or 'region_default'}"] = {
                "scenario": sc, "seconds": round(time.time() - t, 1), "result": res}

    out["answers"] = []
    for i in range(runs):
        a = ask_agent(model, E2_QUESTION)
        a.update(marks(a.get("text", "")))
        out["answers"].append(a)
        print(f"e2 {i + 1}: {a.get('seconds')} s, {a.get('cost_usd')} USD", flush=True)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("experiment", choices=["e2", "e4", "e4curve"])
    parser.add_argument("--model", default="muse-spark-1.3")
    parser.add_argument("--runs", type=int, default=None)
    parser.add_argument("--env", default=str(PROJECT_ROOT / ".env"))
    args = parser.parse_args()
    load_env(args.env)

    import subprocess
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                            cwd=PROJECT_ROOT).stdout.strip()
    started = datetime.now(timezone.utc)
    if args.experiment == "e4":
        data = run_e4(args.model, args.runs or 3)
    elif args.experiment == "e4curve":
        data = run_e4_curve(args.model, args.runs or 3)
    else:
        data = run_e2(args.model, args.runs or 5)

    answers = data.get("answers", []) + [a for c in data.get("conditions", {}).values() for a in c.get("answers", [])]
    usage = {k: sum(a.get("usage", {}).get(k, 0) for a in answers)
             for k in ("prompt_tokens", "cached_prompt_tokens", "completion_tokens", "requests")}
    data = {"experiment": args.experiment, "model": args.model, "provider": "meta", "commit": commit,
            "started": started.isoformat(), "finished": datetime.now(timezone.utc).isoformat(),
            "usage_agent_answers": usage, "cost_usd_agent_answers": round(sum(a.get("cost_usd", 0) for a in answers), 4),
            **data}
    RESULTS_DIR.mkdir(exist_ok=True)
    stamp = started.strftime("%Y%m%d_%H%M%S")
    path = RESULTS_DIR / f"{args.experiment}_{args.model.replace('.', '_')}_{stamp}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"saved {path} | agent answers: {data['cost_usd_agent_answers']} USD")


if __name__ == "__main__":
    main()
