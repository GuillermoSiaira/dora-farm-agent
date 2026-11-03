"""Runs the 3 live farmer-DORA dialogues (r1, r2, r4) and saves them to eval/e3/dialogues/rN.json."""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from dora.agent import Agent

E3 = ROOT / "eval" / "e3"
MEDIA = E3 / "media" / "real_invoices"
OUT_DIR = E3 / "dialogues"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"'))


def run_dialogue(case_id: str, turns: list[dict], model: str = "muse-spark-1.3") -> dict:
    print(f"\n==========================================")
    print(f"Starting dialogue for {case_id} with {model}")
    print(f"==========================================")
    agent = Agent(model=model, use_verifier=True)
    results = []

    for i, t in enumerate(turns, 1):
        prompt = t["prompt"]
        images = [str(MEDIA / img) for img in t.get("images", [])]
        print(f"\n--- Turn {i} ({case_id}) ---")
        print(f"Farmer: {prompt}")
        if images:
            print(f"Images: {images}")

        prev_results_count = len(agent.tool_results)
        t0 = time.perf_counter()
        reply = agent.ask(prompt, images=images if images else None)
        latency = round(time.perf_counter() - t0, 2)

        new_results = agent.tool_results[prev_results_count:]
        parsed_results = []
        for res_str in new_results:
            try:
                parsed_results.append(json.loads(res_str))
            except Exception:
                parsed_results.append(res_str)

        turn_record = {
            "turn": i,
            "farmer_prompt": prompt,
            "images": t.get("images", []),
            "reply_text": reply.text,
            "verified": reply.verified,
            "unsupported": [str(getattr(u, "text", u)) for u in reply.unsupported],
            "initial_unsupported": [str(getattr(u, "text", u)) for u in reply.initial_unsupported],
            "tool_calls": reply.tool_calls,
            "tool_results": parsed_results,
            "latency_s": latency,
        }
        results.append(turn_record)

        print(f"\nDORA (verified={reply.verified}, latency={latency}s):")
        print(reply.text)
        print(f"Tools called: {[c['tool'] for c in reply.tool_calls]}")

    full_dialogue = {
        "case_id": case_id,
        "model": model,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "turns": results,
        "usage": dict(agent.usage),
    }

    out_file = OUT_DIR / f"{case_id}.json"
    out_file.write_text(json.dumps(full_dialogue, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\nSaved dialogue to {out_file}")
    return full_dialogue


def main():
    _load_dotenv(ROOT / ".env")
    model = os.environ.get("DORA_MODEL", "muse-spark-1.3")

    # r1: Balcarce wheat fertilizer (100 ha)
    r1_turns = [
        {
            "prompt": "Te mando la factura del fertilizante del trigo. Cubre 100 ha. Tengo 500 ha en Balcarce y 50.000 USD. ¿Cómo cambia el plan?",
            "images": ["r1.png"],
        },
        {
            "prompt": "¿Ese precio está caro o barato comparado con lo que usás vos?",
        },
        {
            "prompt": "Si consigo la urea un 10 % más barata, ¿cuánto gano?",
        },
    ]

    # r2: Pergamino soybean seed + glyphosate (80 ha)
    r2_turns = [
        {
            "prompt": "Te mando la factura de la semilla de soja y el glifosato en pesos. Cubre 80 ha. Tengo 400 ha en Pergamino y 70.000 USD. ¿Cómo cambia el plan?",
            "images": ["r2.png"],
        },
        {
            "prompt": "¿Ese precio está caro o barato comparado con lo que usás vos?",
        },
        {
            "prompt": "Si consigo la semilla un 10 % más barata, ¿cuánto gano?",
        },
    ]

    # r4: Iowa anhydrous ammonia + seed corn (160 acres)
    r4_turns = [
        {
            "prompt": "Here is the invoice for anhydrous ammonia and seed corn. It covers 160 acres. I have 500 acres in Iowa and $150,000 capital. How does the plan change?",
            "images": ["r4.png"],
        },
        {
            "prompt": "Is that price high or low compared to what you use?",
        },
        {
            "prompt": "If I get the anhydrous ammonia 10% cheaper, how much do I gain?",
        },
    ]

    print(f"Running dialogues with model: {model}")
    run_dialogue("r1", r1_turns, model=model)
    run_dialogue("r2", r2_turns, model=model)
    run_dialogue("r4", r4_turns, model=model)


if __name__ == "__main__":
    main()

