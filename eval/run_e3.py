"""E3 (multimodal): voice notes, invoice photos and aerial photos against the same request typed.

    python eval/run_e3.py                                  # all cases, stand-in voices
    python eval/run_e3.py --only voice --voice-dir eval/e3/media/voice   # Guillermo's recordings
    python eval/run_e3.py --only aerial --sam-only         # SAM 3.1 alone, no language model

Each case runs twice through the DORA agent (verifier on): once with the media, once with the same
request typed. Metrics (docs/plan-de-pruebas.md, E3):
- voice: the scenario built from the transcript matches the expected one (eval/run_eval.match_scenario);
- invoice: amounts read from the image against the true ones, and the cost per hectare loaded;
- aerial: share and hectares SAM measures against the pixels drawn as water;
- end to end: the present value with media equals the one typed, and the engine's on the expected scenario.
If the agent answers without computing (it asks to confirm), it gets one "yes, go ahead".
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import wave
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))

from run_eval import match_scenario  # noqa: E402

E3 = ROOT / "eval" / "e3"
MEDIA = E3 / "media"
CONFIRM = "Sí, está bien. Usá esos datos y calculá el valor presente."
COMPUTE_TOOLS = {"evaluate_season", "assess_field_image", "sensitivity", "shadow_prices"}


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"'))


def _close(a, b, tol=0.005) -> bool | None:
    if a is None or b is None:
        return None
    return abs(a - b) <= tol * max(abs(b), 1.0)


def run_agent(model: str, text: str, images=None, audio=None) -> dict:
    """One farmer request through the agent, with one confirmation if it stops to ask."""
    from dora.agent import Agent
    agent = Agent(model=model, use_verifier=True)
    t0 = time.perf_counter()
    turns = []
    reply = agent.ask(text, images=images, audio=audio)
    turns.append(reply)
    if not any(c["tool"] in COMPUTE_TOOLS and not c["error"] for c in reply.tool_calls):
        turns.append(agent.ask(CONFIRM))
    latency = time.perf_counter() - t0
    calls = [c for r in turns for c in r.tool_calls]
    # Agent.tool_results is appended in the same order as the calls log.
    for c, res in zip(calls, agent.tool_results):
        c["result"] = json.loads(res)
    return {
        "user_text": agent.user_texts[0] if agent.user_texts else "",
        "answers": [r.text for r in turns],
        "verified": all(r.verified for r in turns),
        "unsupported_first_draft": [str(getattr(u, "text", u)) for r in turns for u in r.initial_unsupported],
        "unsupported_final": [str(getattr(u, "text", u)) for r in turns for u in r.unsupported],
        "confirmed": len(turns) > 1,
        "calls": calls,
        "usage": dict(agent.usage),
        "latency_s": round(latency, 1),
    }


def _args(c: dict) -> dict:
    try:
        return json.loads(c["arguments"]) if isinstance(c["arguments"], str) else c["arguments"]
    except json.JSONDecodeError:
        return {}


def last_npv(run: dict) -> float | None:
    npv = None
    for c in run["calls"]:
        r = c.get("result", {})
        if c["tool"] == "evaluate_season" and "npv_usd" in r:
            npv = r["npv_usd"]
        elif c["tool"] == "assess_field_image" and "after" in r:
            npv = r["after"]["npv_usd"]
    return npv


def scenarios_used(run: dict) -> list[dict]:
    return [_args(c).get("scenario", {}) for c in run["calls"] if c["tool"] in ("build_scenario", "evaluate_season")]


def audio_seconds(path: Path) -> float | None:
    try:
        with wave.open(str(path)) as w:
            return w.getnframes() / w.getframerate()
    except Exception:
        return None


def do_voice(cases, model, voice_dir: Path, source: str) -> list[dict]:
    from dora.tools import evaluate_season
    out = []
    for c in cases["voice"]:
        files = sorted(voice_dir.glob(f"{c['id']}.*"))
        if not files:
            print(f"{c['id']}: no audio in {voice_dir}, skipped")
            continue
        audio = files[0]
        expected_npv = evaluate_season(dict(c["scenario"]))["npv_usd"]
        print(f"{c['id']} voice...", flush=True)
        media = run_agent(model, "", audio=str(audio))
        print(f"{c['id']} typed...", flush=True)
        typed = run_agent(model, c["typed"])
        rec = {
            "id": c["id"], "audio": str(audio.relative_to(ROOT)), "audio_source": source,
            "audio_seconds": audio_seconds(audio), "script": c["script"], "typed_text": c["typed"],
            "expected_scenario": c["scenario"], "expected_npv_usd": expected_npv,
            "transcript": media["user_text"],
            "formulation_voice": any(match_scenario(s, c["scenario"]) for s in scenarios_used(media)),
            "formulation_typed": any(match_scenario(s, c["scenario"]) for s in scenarios_used(typed)),
            "npv_voice": last_npv(media), "npv_typed": last_npv(typed),
            "media_run": media, "typed_run": typed,
        }
        rec["npv_voice_eq_typed"] = _close(rec["npv_voice"], rec["npv_typed"])
        rec["npv_voice_eq_expected"] = _close(rec["npv_voice"], expected_npv)
        out.append(rec)
        print(f"  match {rec['formulation_voice']}/{rec['formulation_typed']}  npv {rec['npv_voice']} / {rec['npv_typed']} / {expected_npv}")
    return out


def _fx_rate() -> float | None:
    from dora.feeds import BcraFxFeed
    try:
        return float(BcraFxFeed().fetch_rate_and_date(None)[0])
    except Exception:
        return None


def read_items(run: dict) -> list[dict]:
    """Money lines of the first record_document call: what the model read from the document.

    Later calls repeat or regroup the same lines, and the model sometimes passes the hectares as an
    item with unit 'ha'; neither is a reading of an amount."""
    for c in run["calls"]:
        if c["tool"] == "record_document":
            return [it for it in _args(c).get("items", []) if str(it.get("unit", "")).strip().lower() != "ha"]
    return []


def do_invoices(cases, model, truth) -> list[dict]:
    from dora.tools import evaluate_season
    out = []
    for c in cases["invoices"]:
        t = truth["invoices"][c["id"]]
        path = next(iter(sorted((MEDIA / "invoices").glob(f"{c['id']}.*"))))
        print(f"{c['id']} photo...", flush=True)
        media = run_agent(model, c["prompt"], images=[str(path)])
        print(f"{c['id']} typed...", flush=True)
        typed = run_agent(model, c["typed"])
        docs = [c2 for c2 in media["calls"] if c2["tool"] == "record_document"]
        items = read_items(media)
        read_sum = round(sum(float(it.get("amount", 0) or 0) for it in items), 2) if items else None
        rate = None
        for d in docs:
            fx = d.get("result", {}).get("fx_conversion")
            if fx:
                rate = fx["rate"]
        if c["currency"] == "ARS":
            rate = rate or _fx_rate()
            exp_per_ha = round(t["net"] / rate / c["covers_ha"], 2) if rate else None
        else:
            exp_per_ha = round(t["net"] / c["covers_ha"], 2)
        expected_sc = dict(c["scenario"], costs_override={c["crop"]: {c["item"]: exp_per_ha}}) if exp_per_ha else None
        expected_npv = evaluate_season(dict(expected_sc))["npv_usd"] if expected_sc else None

        def loaded(run):
            vals = [s.get("costs_override", {}).get(c["crop"], {}).get(c["item"]) for s in scenarios_used(run)]
            vals = [v for v in vals if v is not None]
            return vals[-1] if vals else None

        rec = {
            "id": c["id"], "image": str(path.relative_to(ROOT)), "kind": c["kind"], "currency": c["currency"],
            "crop": c["crop"], "item": c["item"], "covers_ha": c["covers_ha"], "prompt": c["prompt"], "typed_text": c["typed"],
            "true_lines": t["lines"], "true_net": t["net"], "true_total_with_vat": t["total"],
            "read_lines": [{"concept": it.get("concept"), "amount": it.get("amount"), "currency": it.get("currency")} for it in items],
            "read_sum": read_sum,
            "read_lines_exact": sorted(round(float(it.get("amount", 0) or 0), 2) for it in items) == sorted(t["lines"]) if items else False,
            "read_sum_is_net": _close(read_sum, t["net"], 0.001),
            "read_sum_is_total_with_vat": _close(read_sum, t["total"], 0.001),
            "fx_rate": rate, "expected_usd_ha": exp_per_ha,
            "loaded_usd_ha_photo": loaded(media), "loaded_usd_ha_typed": loaded(typed),
            "expected_npv_usd": expected_npv, "npv_photo": last_npv(media), "npv_typed": last_npv(typed),
            "media_run": media, "typed_run": typed,
        }
        rec["loaded_photo_ok"] = _close(rec["loaded_usd_ha_photo"], exp_per_ha, 0.01)
        rec["loaded_typed_ok"] = _close(rec["loaded_usd_ha_typed"], exp_per_ha, 0.01)
        rec["npv_photo_eq_typed"] = _close(rec["npv_photo"], rec["npv_typed"])
        rec["npv_photo_eq_expected"] = _close(rec["npv_photo"], expected_npv)
        out.append(rec)
        print(f"  read {read_sum} (net {t['net']}), loaded {rec['loaded_usd_ha_photo']}/{rec['loaded_usd_ha_typed']} (exp {exp_per_ha}), npv {rec['npv_photo']} / {rec['npv_typed']} / {expected_npv}")
    return out


def sam_alone(cases, truth) -> list[dict]:
    from dora.field_image import measure_damage
    from dora.media import encode_image
    out = []
    for c in cases["aerial"]:
        url = encode_image(MEDIA / "aerial" / f"{c['id']}.png")
        t0 = time.perf_counter()
        m = measure_damage(url, "flooding")
        rec = {"id": c["id"], "true_share": truth["aerial"][c["id"]]["share"], "sam_share": round(m["share"], 4),
               "objects_per_concept": m["objects_per_concept"], "latency_s": round(time.perf_counter() - t0, 1)}
        if m["mask"] is not None:
            import numpy as np
            from PIL import Image
            true = np.asarray(Image.open(MEDIA / "aerial" / f"{c['id']}_mask.png")) > 0
            pred = m["mask"].astype(bool)
            if pred.shape == true.shape:
                rec["iou"] = round(float((pred & true).sum() / max((pred | true).sum(), 1)), 4)
        out.append(rec)
        print(f"  SAM {c['id']}: {rec}")
    return out


def do_aerial(cases, model, truth) -> list[dict]:
    import numpy as np
    from PIL import Image

    import dora.field_image as fi
    from dora.media import encode_image
    from dora.tools import assess_field_image
    out = []
    for c in cases["aerial"]:
        t = truth["aerial"][c["id"]]
        path = MEDIA / "aerial" / f"{c['id']}.png"
        # Reference: the same re-plan with the true water mask in place of SAM's.
        true_mask = (np.asarray(Image.open(MEDIA / "aerial" / f"{c['id']}_mask.png")) > 0).astype("uint8")
        real = fi.measure_damage
        fi.measure_damage = lambda url, damage="flooding", segmenter=None: {
            "damage": damage, "share": float(true_mask.mean()), "objects": 1, "objects_per_concept": {"true mask": 1}, "mask": true_mask}
        try:
            ref = assess_field_image(dict(c["scenario"]), _images=[encode_image(path)])
        finally:
            fi.measure_damage = real
        print(f"{c['id']} photo...", flush=True)
        media = run_agent(model, c["prompt"], images=[str(path)])
        assess = [c2.get("result", {}) for c2 in media["calls"] if c2["tool"] == "assess_field_image" and not c2["error"]]
        a = assess[-1] if assess else {}
        rec = {
            "id": c["id"], "image": str(path.relative_to(ROOT)), "prompt": c["prompt"], "scenario": c["scenario"],
            "true_share": t["share"], "true_damaged_ha": t["damaged_ha"],
            "measured_share": a.get("affected_share"), "measured_ha": a.get("affected_ha"),
            "reference_npv_after": ref["after"]["npv_usd"], "reference_npv_change": ref["npv_change_usd"],
            "npv_after_photo": a.get("after", {}).get("npv_usd"), "npv_change_photo": a.get("npv_change_usd"),
            "overlay": a.get("overlay_path"),   # temporary file: copy it next to the photo to keep it
            "media_run": media,
        }
        rec["field_ha_used"] = a.get("field_ha")
        rec["ha_error"] = round(rec["measured_ha"] - t["damaged_ha"], 1) if rec["measured_ha"] is not None else None
        rec["npv_photo_eq_reference"] = _close(rec["npv_after_photo"], rec["reference_npv_after"])
        out.append(rec)
        print(f"  share {rec['measured_share']} (true {t['share']}), ha {rec['measured_ha']} (true {t['damaged_ha']}), npv {rec['npv_after_photo']} / ref {rec['reference_npv_after']}")
    return out


def cost(runs: list[dict], model: str) -> float:
    prices = json.loads((ROOT / "eval" / "pricing.json").read_text(encoding="utf-8")).get(f"{model}@meta")
    if not prices:
        return 0.0
    usd = 0.0
    for r in runs:
        u = r["usage"]
        cached = u.get("cached_prompt_tokens", 0)
        usd += ((u["prompt_tokens"] - cached) * prices["usd_per_m_input"] + cached * prices["usd_per_m_cached_input"]
                + u["completion_tokens"] * prices["usd_per_m_output"]) / 1e6
    return round(usd, 4)


def main() -> None:
    _load_dotenv(ROOT / ".env")
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=os.environ.get("DORA_MODEL", "muse-spark-1.3"))
    ap.add_argument("--only", choices=["voice", "invoices", "aerial"], action="append")
    ap.add_argument("--voice-dir", default=str(MEDIA / "voice_tts"))
    ap.add_argument("--sam-only", action="store_true")
    ap.add_argument("--rescore", help="recompute the reading metrics of a saved results file, no API calls")
    args = ap.parse_args()
    if args.rescore:
        f = Path(args.rescore)
        res = json.loads(f.read_text(encoding="utf-8"))
        for rec in res.get("invoices", []):
            items = read_items(rec["media_run"])
            rec["read_lines"] = [{"concept": it.get("concept"), "amount": it.get("amount"), "currency": it.get("currency")} for it in items]
            rec["read_sum"] = round(sum(float(it.get("amount", 0) or 0) for it in items), 2) if items else None
            rec["read_lines_exact"] = sorted(round(float(it.get("amount", 0) or 0), 2) for it in items) == sorted(rec["true_lines"]) if items else False
            rec["read_sum_is_net"] = _close(rec["read_sum"], rec["true_net"], 0.001)
            rec["read_sum_is_total_with_vat"] = _close(rec["read_sum"], rec["true_total_with_vat"], 0.001)
        for rec in res.get("aerial", []):
            a = [c["result"] for c in rec["media_run"]["calls"] if c["tool"] == "assess_field_image" and not c["error"]]
            rec["field_ha_used"] = a[-1].get("field_ha") if a else None
        res["rescored"] = datetime.now().isoformat(timespec="seconds")
        f.write_text(json.dumps(res, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(f"rescored {f}")
        return
    os.environ.setdefault("DORA_TRANSCRIBE_MODEL", "muse-voice-transcribe-1.0")
    cases = json.loads((E3 / "cases.json").read_text(encoding="utf-8"))
    truth = json.loads((MEDIA / "truth.json").read_text(encoding="utf-8"))
    parts = args.only or ["voice", "invoices", "aerial"]
    voice_dir = Path(args.voice_dir).resolve()
    source = {"voice_tts": "windows_tts_sabina_es-MX",
              "voice_polly_en": "aws_polly_neural_matthew_en-US"}.get(voice_dir.name, "recorded_by_guillermo")

    res = {"experiment": "E3", "model": args.model, "started": datetime.now().isoformat(timespec="seconds"),
           "transcribe_model": os.environ["DORA_TRANSCRIBE_MODEL"], "sam_model": os.environ.get("DORA_SAM_MODEL", "sam-3.1")}
    if "aerial" in parts:
        res["sam_alone"] = sam_alone(cases, truth)
    if not args.sam_only:
        if "voice" in parts:
            res["voice"] = do_voice(cases, args.model, voice_dir, source)
        if "invoices" in parts:
            res["invoices"] = do_invoices(cases, args.model, truth)
        if "aerial" in parts:
            res["aerial"] = do_aerial(cases, args.model, truth)
    runs = [r[k] for part in ("voice", "invoices", "aerial") for r in res.get(part, []) for k in ("media_run", "typed_run") if k in r]
    res["llm_cost_usd"] = cost(runs, args.model)
    res["audio_seconds"] = round(sum(r.get("audio_seconds") or 0 for r in res.get("voice", [])), 1)
    res["transcribe_cost_usd"] = round(res["audio_seconds"] / 3600 * 0.18, 4)   # 0.18 USD/hour, dev.meta.ai pricing page
    res["finished"] = datetime.now().isoformat(timespec="seconds")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    tag = "_".join(parts) + ("_sam" if args.sam_only else "") + ("_rec" if source.startswith("recorded") and "voice" in parts else "") + ("_polly_en" if source.startswith("aws_polly") and "voice" in parts else "")
    out = ROOT / "eval" / "results" / f"e3_{args.model.replace('.', '_')}_{tag}_{stamp}.json"
    out.write_text(json.dumps(res, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n{out}\nLLM cost {res['llm_cost_usd']} USD, transcription {res['transcribe_cost_usd']} USD")


if __name__ == "__main__":
    main()
