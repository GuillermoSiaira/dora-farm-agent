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


def run_agent(model: str, text: str, images=None, audio=None, confirm: str | None = None) -> dict:
    """One farmer request through the agent, with one confirmation if it stops to ask."""
    from dora.agent import Agent
    agent = Agent(model=model, use_verifier=True)
    t0 = time.perf_counter()
    turns = []
    reply = agent.ask(text, images=images, audio=audio)
    turns.append(reply)
    if confirm:
        turns.append(agent.ask(confirm))
    elif not any(c["tool"] in COMPUTE_TOOLS and not c["error"] for c in reply.tool_calls):
        turns.append(agent.ask(CONFIRM))
    latency = time.perf_counter() - t0
    calls = [c for r in turns for c in r.tool_calls]
    # Agent.tool_results is appended in the same order as the calls log.
    for c, res in zip(calls, agent.tool_results):
        try:
            c["result"] = json.loads(res) if isinstance(res, str) else res
        except Exception:
            c["result"] = {}
    return {
        "user_text": agent.user_texts[0] if agent.user_texts else "",
        "answers": [r.text for r in turns],
        "verified": all(r.verified for r in turns),
        "unsupported_first_draft": [str(getattr(u, "text", u)) for r in turns for u in r.initial_unsupported],
        "unsupported_final": [str(getattr(u, "text", u)) for r in turns for u in r.unsupported],
        "confirmed": len(turns) > 1,
        "calls": calls,
        "turns": [{"answers": [r.text], "calls": [c for c in r.tool_calls]} for r in turns],
        "usage": dict(agent.usage),
        "latency_s": round(latency, 1),
    }


def _args(c: dict) -> dict:
    try:
        return json.loads(c["arguments"]) if isinstance(c["arguments"], str) else c["arguments"]
    except json.JSONDecodeError:
        return {}


def last_npv(run: dict) -> float | None:
    """Return the NPV from evaluate_season (preferring the call with costs_override if present), record_document plan_after, or assess_field_image."""
    npv_with_override = None
    npv_last = None
    for c in run.get("calls", []):
        r = c.get("result", {})
        args = _args(c)
        if c.get("tool") == "evaluate_season" and "npv_usd" in r:
            npv_last = r["npv_usd"]
            sc = args.get("scenario", {}) if isinstance(args, dict) else {}
            if sc.get("costs_override"):
                npv_with_override = r["npv_usd"]
        elif c.get("tool") == "record_document":
            if "plan_after" in r and isinstance(r["plan_after"], dict) and "npv_usd" in r["plan_after"]:
                npv_last = r["plan_after"]["npv_usd"]
                npv_with_override = r["plan_after"]["npv_usd"]
            elif "plan_before" in r and isinstance(r["plan_before"], dict) and "npv_usd" in r["plan_before"]:
                if npv_last is None:
                    npv_last = r["plan_before"]["npv_usd"]
        elif c.get("tool") == "assess_field_image" and "after" in r:
            npv_last = r["after"]["npv_usd"]
    return npv_with_override if npv_with_override is not None else npv_last


def eval_groups_and_npv(doc_result: dict, expected_groups: list[dict], case_lines: list[dict], scenario: dict) -> dict:
    """Evaluate groups_ok, lines_all_passed, npv_after and npv_after_ok for a record_document call."""
    from dora.tools import evaluate_season
    if not doc_result:
        return {
            "groups_ok": False,
            "lines_all_passed": False,
            "npv_after": None,
            "expected_npv_after": None,
            "npv_after_ok": False,
        }

    lines = doc_result.get("lines") or doc_result.get("items") or []
    non_tax_lines = [l for l in lines if l.get("cost_item") != "tax" and l.get("excluded") != "tax"]
    lines_all_passed = (len(non_tax_lines) == len(case_lines))

    proposals = doc_result.get("proposals", [])
    groups_ok = True
    if len(proposals) != len(expected_groups):
        groups_ok = False
    for exp_g in expected_groups:
        match = None
        for p in proposals:
            if p.get("crop") == exp_g.get("crop") and p.get("item") == exp_g.get("item"):
                match = p
                break
        if not match:
            groups_ok = False
            break
        val = match.get("proposed_usd_ha", 0.0)
        exp_val = exp_g["usd_ha"]
        if not _close(val, exp_val, 0.01):
            groups_ok = False
            break
        if bool(match.get("apply")) != bool(exp_g.get("apply")):
            groups_ok = False
            break

    plan_after = doc_result.get("plan_after")
    npv_after = plan_after.get("npv_usd") if isinstance(plan_after, dict) else None

    applied_overrides = {}
    for g in expected_groups:
        if g.get("apply") and g.get("crop"):
            applied_overrides.setdefault(g["crop"], {})[g["item"]] = g["usd_ha"]

    if applied_overrides and scenario:
        merged = {c: dict(v) for c, v in (scenario.get("costs_override") or {}).items()}
        for cr, items_dict in applied_overrides.items():
            merged.setdefault(cr, {}).update(items_dict)
        sc_exp = dict(scenario, costs_override=merged)
        try:
            expected_engine_npv = evaluate_season(sc_exp)["npv_usd"]
        except Exception:
            expected_engine_npv = None
    elif scenario:
        try:
            expected_engine_npv = evaluate_season(scenario)["npv_usd"]
        except Exception:
            expected_engine_npv = None
    else:
        expected_engine_npv = None

    if npv_after is not None and expected_engine_npv is not None:
        npv_after_ok = _close(npv_after, expected_engine_npv, 0.01)
    else:
        npv_after_ok = False

    return {
        "groups_ok": groups_ok,
        "lines_all_passed": lines_all_passed,
        "npv_after": npv_after,
        "expected_npv_after": expected_engine_npv,
        "npv_after_ok": npv_after_ok,
    }


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


def compute_invoice_metrics(net: float, covers_ha: float, currency: str, rate: float | None, model_usd_ha: float | None) -> tuple[float | None, float | None]:
    """Calculate (invoice_usd_ha, diff_pct) for an invoice."""
    if covers_ha <= 0:
        return None, None
    if currency == "ARS":
        if not rate:
            return None, None
        invoice_usd_ha = round(net / rate / covers_ha, 2)
    else:
        invoice_usd_ha = round(net / covers_ha, 2)
    diff_pct = round((invoice_usd_ha - model_usd_ha) / model_usd_ha, 4) if model_usd_ha else None
    return invoice_usd_ha, diff_pct


def do_invoices(cases, model, truth, media_dir: Path | None = None, case_id: str | None = None) -> list[dict]:
    from dora.tools import evaluate_season
    from dora.scenario import load_region_data
    if media_dir is None:
        media_dir = MEDIA / "invoices"
    invoice_cases = cases.get("invoices", cases) if isinstance(cases, dict) else cases
    if case_id:
        invoice_cases = [c for c in invoice_cases if c["id"] == case_id]

    out = []
    for c in invoice_cases:
        if "invoices" in truth and c["id"] in truth["invoices"]:
            t = truth["invoices"][c["id"]]
        else:
            t = {"lines": [line.get("amount", 0) for line in c.get("lines", [])], "net": c.get("net"), "total": c.get("total")}

        image_targets = []
        for p in sorted(media_dir.glob(f"{c['id']}.*")):
            if "_photo" not in p.stem:
                image_targets.append((p, "clean"))
        for p in sorted(media_dir.glob(f"{c['id']}_photo.*")):
            image_targets.append((p, "photo"))

        if not image_targets:
            print(f"{c['id']}: no image in {media_dir}, skipped")
            continue

        typed_cache = None

        for path, img_type in image_targets:
            print(f"{c['id']} ({img_type}) {path.name}...", flush=True)
            confirm_text = c.get("confirm_text")
            media = run_agent(model, c["prompt"], images=[str(path)], confirm=confirm_text)
            if typed_cache is None:
                print(f"{c['id']} typed...", flush=True)
                typed_cache = run_agent(model, c["typed"], confirm=confirm_text)
            typed = typed_cache

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

            model_usd_ha = None
            region = c.get("region")
            if not region and "scenario" in c and isinstance(c["scenario"], dict):
                region = c["scenario"].get("region")
            if region:
                try:
                    reg_data = load_region_data(region)
                    model_usd_ha = reg_data.get("crops", {}).get(c["crop"], {}).get(c["item"])
                except Exception:
                    pass

            exp_per_ha, diff_pct = compute_invoice_metrics(t["net"], c["covers_ha"], c["currency"], rate, model_usd_ha)

            expected_sc = dict(c["scenario"], costs_override={c["crop"]: {c["item"]: exp_per_ha}}) if (exp_per_ha and "scenario" in c and isinstance(c["scenario"], dict)) else None
            expected_npv = evaluate_season(dict(expected_sc))["npv_usd"] if expected_sc else None

            def loaded(run):
                vals = [s.get("costs_override", {}).get(c["crop"], {}).get(c["item"]) for s in scenarios_used(run)]
                vals = [v for v in vals if v is not None]
                return vals[-1] if vals else None

            rec = {
                "id": c["id"], "image": str(path.relative_to(ROOT)), "image_type": img_type,
                "kind": c.get("kind", "invoice"), "region": region, "currency": c["currency"],
                "crop": c["crop"], "item": c["item"], "covers_ha": c["covers_ha"], "prompt": c["prompt"], "typed_text": c["typed"],
                "true_lines": t["lines"], "true_net": t["net"], "true_total_with_vat": t["total"],
                "lines": c.get("lines", []), "expected_groups": c.get("expected_groups", []),
                "read_lines": [{"concept": it.get("concept"), "amount": it.get("amount"), "currency": it.get("currency")} for it in items],
                "read_sum": read_sum,
                "read_lines_exact": sorted(round(float(it.get("amount", 0) or 0), 2) for it in items) == sorted(t["lines"]) if items else False,
                "read_sum_is_net": _close(read_sum, t["net"], 0.001),
                "read_sum_is_total_with_vat": _close(read_sum, t["total"], 0.001),
                "fx_rate": rate, "expected_usd_ha": exp_per_ha,
                "model_usd_ha": model_usd_ha, "invoice_usd_ha": exp_per_ha, "diff_pct": diff_pct,
                "loaded_usd_ha_photo": loaded(media), "loaded_usd_ha_typed": loaded(typed),
                "expected_npv_usd": expected_npv, "npv_photo": last_npv(media), "npv_typed": last_npv(typed),
                "media_run": media, "typed_run": typed,
            }
            rec["loaded_photo_ok"] = _close(rec["loaded_usd_ha_photo"], exp_per_ha, 0.01)
            rec["loaded_typed_ok"] = _close(rec["loaded_usd_ha_typed"], exp_per_ha, 0.01)
            rec["npv_photo_eq_typed"] = _close(rec["npv_photo"], rec["npv_typed"])
            rec["npv_photo_eq_expected"] = _close(rec["npv_photo"], expected_npv)

            # SPEC-36: evaluate turn 1 last record_document
            turn1_calls = media.get("turns", [{}])[0].get("calls", media.get("calls", []))
            doc1_calls = [call for call in turn1_calls if call.get("tool") == "record_document"]
            last_doc1 = doc1_calls[-1].get("result", {}) if doc1_calls else (docs[-1].get("result", {}) if docs else {})
            m1 = eval_groups_and_npv(last_doc1, c.get("expected_groups", []), c.get("lines", []), c.get("scenario", {}))
            rec["groups_ok"] = m1["groups_ok"]
            rec["lines_all_passed"] = m1["lines_all_passed"]
            rec["npv_after"] = m1["npv_after"]
            rec["npv_after_ok"] = m1["npv_after_ok"]

            # SPEC-36: evaluate turn 2 (after_confirm) if confirm_text was present
            if confirm_text:
                if len(media.get("turns", [])) > 1:
                    turn2_calls = media["turns"][1].get("calls", [])
                    doc2_calls = [call for call in turn2_calls if call.get("tool") == "record_document"]
                    last_doc2 = doc2_calls[-1].get("result", {}) if doc2_calls else last_doc1
                else:
                    last_doc2 = docs[-1].get("result", {}) if docs else last_doc1
                confirm_exp_groups = [
                    dict(g, apply=True) if g["item"] == "crop_protection" else dict(g)
                    for g in c.get("expected_groups", [])
                ]
                m2 = eval_groups_and_npv(last_doc2, confirm_exp_groups, c.get("lines", []), c.get("scenario", {}))
                # Fallback if model used evaluate_season instead of record_document in turn 2
                if m2["npv_after"] is None and len(media.get("turns", [])) > 1:
                    npv2 = last_npv({"calls": media["turns"][1].get("calls", [])})
                    if npv2 is not None:
                        m2["npv_after"] = npv2
                        if m2["expected_npv_after"] is not None:
                            m2["npv_after_ok"] = _close(npv2, m2["expected_npv_after"], 0.01)
                rec["after_confirm"] = m2

            out.append(rec)
            print(f"  read {read_sum} (net {t['net']}), loaded {rec['loaded_usd_ha_photo']}/{rec['loaded_usd_ha_typed']} (exp {exp_per_ha}), model {model_usd_ha} (diff {diff_pct}), npv {rec['npv_photo']} / {rec['npv_typed']} / {expected_npv}, groups_ok={rec['groups_ok']}, npv_after={rec['npv_after']}")
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
    ap.add_argument("--cases", help="path to custom cases JSON file")
    ap.add_argument("--media-dir", help="directory with invoice images/photos")
    ap.add_argument("--case-id", help="filter to run a single case id")
    ap.add_argument("--output", help="path to write output results JSON")
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
            rec["npv_photo"] = last_npv(rec["media_run"])
            rec["npv_typed"] = last_npv(rec["typed_run"])
            rec["npv_photo_eq_typed"] = _close(rec["npv_photo"], rec["npv_typed"])
            rec["npv_photo_eq_expected"] = _close(rec["npv_photo"], rec["expected_npv_usd"])
            if "expected_groups" in rec:
                turn1_calls = rec["media_run"].get("turns", [{}])[0].get("calls", rec["media_run"].get("calls", []))
                doc1_calls = [call for call in turn1_calls if call.get("tool") == "record_document"]
                docs = [c for c in rec["media_run"].get("calls", []) if c.get("tool") == "record_document"]
                last_doc1 = doc1_calls[-1].get("result", {}) if doc1_calls else (docs[-1].get("result", {}) if docs else {})
                m1 = eval_groups_and_npv(last_doc1, rec.get("expected_groups", []), rec.get("lines", []), rec.get("scenario", {}))
                rec["groups_ok"] = m1["groups_ok"]
                rec["lines_all_passed"] = m1["lines_all_passed"]
                rec["npv_after"] = m1["npv_after"]
                rec["npv_after_ok"] = m1["npv_after_ok"]
                if "after_confirm" in rec or any(g.get("item") == "crop_protection" for g in rec.get("expected_groups", [])):
                    if len(rec["media_run"].get("turns", [])) > 1:
                        turn2_calls = rec["media_run"]["turns"][1].get("calls", [])
                        doc2_calls = [call for call in turn2_calls if call.get("tool") == "record_document"]
                        last_doc2 = doc2_calls[-1].get("result", {}) if doc2_calls else last_doc1
                    else:
                        last_doc2 = docs[-1].get("result", {}) if docs else last_doc1
                    confirm_exp_groups = [
                        dict(g, apply=True) if g["item"] == "crop_protection" else dict(g)
                        for g in rec.get("expected_groups", [])
                    ]
                    m2 = eval_groups_and_npv(last_doc2, confirm_exp_groups, rec.get("lines", []), rec.get("scenario", {}))
                    if m2["npv_after"] is None and len(rec["media_run"].get("turns", [])) > 1:
                        npv2 = last_npv({"calls": rec["media_run"]["turns"][1].get("calls", [])})
                        if npv2 is not None:
                            m2["npv_after"] = npv2
                            if m2["expected_npv_after"] is not None:
                                m2["npv_after_ok"] = _close(npv2, m2["expected_npv_after"], 0.01)
                    rec["after_confirm"] = m2
        for rec in res.get("aerial", []):
            a = [c["result"] for c in rec["media_run"]["calls"] if c["tool"] == "assess_field_image" and not c["error"]]
            rec["field_ha_used"] = a[-1].get("field_ha") if a else None
        res["rescored"] = datetime.now().isoformat(timespec="seconds")
        f.write_text(json.dumps(res, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(f"rescored {f}")
        return
    os.environ.setdefault("DORA_TRANSCRIBE_MODEL", "muse-voice-transcribe-1.0")
    if args.cases:
        cases_file = Path(args.cases)
        cases_data = json.loads(cases_file.read_text(encoding="utf-8"))
        if isinstance(cases_data, dict):
            cases = cases_data
        else:
            cases = {"invoices": cases_data}
    else:
        cases = json.loads((E3 / "cases.json").read_text(encoding="utf-8"))
    truth = json.loads((MEDIA / "truth.json").read_text(encoding="utf-8"))
    parts = args.only or ["voice", "invoices", "aerial"]
    voice_dir = Path(args.voice_dir).resolve()
    invoice_media_dir = Path(args.media_dir).resolve() if args.media_dir else (MEDIA / "invoices")
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
            res["invoices"] = do_invoices(cases, args.model, truth, media_dir=invoice_media_dir, case_id=args.case_id)
        if "aerial" in parts:
            res["aerial"] = do_aerial(cases, args.model, truth)
    runs = [r[k] for part in ("voice", "invoices", "aerial") for r in res.get(part, []) for k in ("media_run", "typed_run") if k in r]
    res["llm_cost_usd"] = cost(runs, args.model)
    res["audio_seconds"] = round(sum(r.get("audio_seconds") or 0 for r in res.get("voice", [])), 1)
    res["transcribe_cost_usd"] = round(res["audio_seconds"] / 3600 * 0.18, 4)   # 0.18 USD/hour, dev.meta.ai pricing page
    res["finished"] = datetime.now().isoformat(timespec="seconds")
    if args.output:
        out = Path(args.output)
        if not out.is_absolute():
            out = ROOT / out
        out.parent.mkdir(parents=True, exist_ok=True)
    else:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        tag = "_".join(parts) + ("_sam" if args.sam_only else "") + ("_rec" if source.startswith("recorded") and "voice" in parts else "") + ("_polly_en" if source.startswith("aws_polly") and "voice" in parts else "")
        out = ROOT / "eval" / "results" / f"e3_{args.model.replace('.', '_')}_{tag}_{stamp}.json"
    out.write_text(json.dumps(res, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n{out}\nLLM cost {res['llm_cost_usd']} USD, transcription {res['transcribe_cost_usd']} USD")


if __name__ == "__main__":
    main()
