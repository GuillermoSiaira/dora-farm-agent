"""E9 reading page: every answer of every model and arm, with the verdict and the kind of error.

    python eval/e9_page.py [out.html]      (default docs/experimentos/2026-11-07-e9-respuestas.html)

Reads eval/results/e9/full (the four arms, 32,768-token context) and eval/results/e9/ctx64k (DORA's arm again
with 65,536 tokens), and also prints the table of error kinds per model and arm for the write-up."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from eval.run_eval import DEFAULT_ANSWERS_PATH, DEFAULT_QUESTIONS_PATH, _number, _read_jsonl  # noqa: E402

SIZES = ["1.5B", "3B", "7B", "14B", "32B", "72B"]
ARMS = [("full", "alone", "Solo"), ("full", "dora", "DORA (32k)"), ("ctx64k", "dora", "DORA (64k)"),
        ("full", "mcp", "MCP genérico"), ("full", "mcp_guide", "MCP + guía")]
KINDS = {
    "ok": "Correcta y verificada",
    "context": "Cortada: no entró en el contexto",
    "crash": "Falló el pedido (otro error)",
    "no_call": "No llamó ninguna herramienta",
    "calls_failed": "Llamó herramientas, todas con error",
    "wrong_scenario": "El motor devolvió otro número (escenario mal armado)",
    "not_said": "El motor tenía el número; la respuesta no lo dice",
    "unverified": "Número correcto, pero con números sin respaldo",
    "refusal": "Debía negarse o preguntar, y no lo hizo",
    "wrong_alone": "Número equivocado (modelo solo)",
    "unverified_alone": "Número correcto, pero con números inventados (modelo solo)",
    "other": "Otra",
}


def kind(q: dict, r: dict, expected, tools: bool) -> str:
    """One label per answer, in the order a reader would check: did it run, did it call, what came back."""
    if r.get("correct_verified"):
        return "ok"
    if r.get("failed"):
        return "context" if "maximum context length" in r["failed"] else "crash"
    if q.get("expect") == "refuse":
        return "refusal"
    if not tools:
        return "unverified_alone" if r.get("correct_strict") else "wrong_alone"
    calls = r.get("tool_calls") or []
    if not calls:
        return "no_call"
    if all(c.get("error") or c.get("rejected") for c in calls):
        return "calls_failed"
    if r.get("correct_strict"):
        return "unverified"
    rv = _number(r.get("reported_value"))
    if isinstance(expected, (int, float)) and rv is not None:
        if abs(rv - float(expected)) > max(1e-6, 0.005 * abs(float(expected))):
            return "wrong_scenario"
        return "not_said"
    if isinstance(expected, (int, float)):
        return "wrong_scenario"
    return "other"


def baseline_text(r: dict) -> str:
    try:
        return json.loads(r.get("raw") or "").get("answer_text") or r.get("raw") or ""
    except (ValueError, TypeError, AttributeError):
        return r.get("raw") or r.get("parse_error") or ""


def load() -> tuple[dict, dict]:
    qs = {q["id"]: q for q in _read_jsonl(DEFAULT_QUESTIONS_PATH)}
    answers = {a["id"]: a["expected_value"] for a in _read_jsonl(DEFAULT_ANSWERS_PATH)}
    data, counts = {}, {}
    for size in SIZES:
        for folder, arm, label in ARMS:
            f = ROOT / "eval" / "results" / "e9" / folder / f"Qwen2_5-{size.replace('.', '_')}-Instruct_{arm}.json"
            if not f.is_file():
                continue
            d = json.loads(f.read_text(encoding="utf-8"))
            tools = d.get("condition") != "baseline"
            c = Counter()
            for run_i, run in enumerate(d["detailed_results"]):
                for r in run:
                    if r.get("skipped"):
                        continue
                    k = kind(qs[r["id"]], r, answers.get(r["id"]), tools)
                    c[k] += 1
                    text = r.get("reply") if tools else baseline_text(r)
                    data.setdefault(r["id"], {}).setdefault(size, {}).setdefault(label, []).append({
                        "run": run_i + 1, "kind": k, "text": (text or "")[:3000],
                        "engine": r.get("reported_value"), "failed": (r.get("failed") or "")[:200],
                        "unsupported": (r.get("unsupported") or [])[:8],
                        "calls": [{"t": c_.get("mcp_tool") or c_.get("tool"),
                                   "ok": not (c_.get("error") or c_.get("rejected")),
                                   "a": (c_.get("arguments") or "")[:300]} for c_ in (r.get("tool_calls") or [])][:8],
                        "tokens": [r.get("prompt_tokens", 0), r.get("completion_tokens", 0)],
                    })
            counts[(size, label)] = c
    meta = {qid: {"text": q["text"], "expected": answers.get(qid), "type": q.get("type")} for qid, q in qs.items()}
    return {"questions": meta, "answers": data, "sizes": SIZES, "arms": [a[2] for a in ARMS], "kinds": KINDS}, counts


PAGE = """<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>E9 respuestas</title>
<style>
:root{--bg:#fbfaf7;--card:#fff;--ink:#1d1d1b;--mut:#6b6a63;--line:#e4e2da;--ok:#1d7a46;--bad:#b3261e;--warn:#946200;--chip:#f1efe8}
@media (prefers-color-scheme:dark){:root{--bg:#1a1a19;--card:#232321;--ink:#f0efec;--mut:#a9a89f;--line:#3a3935;--ok:#5fc48a;--bad:#f08a80;--warn:#e0b44c;--chip:#2e2d2a}}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,sans-serif}
main{max-width:1200px;margin:0 auto;padding:16px}
h1{font-size:22px;margin:8px 0} p.lead{color:var(--mut);margin-top:0}
.bar{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin:12px 0}
select{font:inherit;padding:6px 8px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--ink)}
table{border-collapse:collapse;font-size:13px;width:100%} th,td{border-bottom:1px solid var(--line);padding:4px 6px;text-align:left;vertical-align:top}
.grid{overflow-x:auto} td.cell{cursor:pointer;white-space:nowrap;font-variant-numeric:tabular-nums}
.k-ok{color:var(--ok);font-weight:600} .k-bad{color:var(--bad)} .k-warn{color:var(--warn)}
.cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px;margin-top:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px}
.card h3{margin:0 0 6px;font-size:15px} .run{border-top:1px solid var(--line);padding-top:8px;margin-top:8px}
.txt{white-space:pre-wrap;font-size:13px;max-height:260px;overflow:auto;background:var(--chip);border-radius:6px;padding:6px}
.chip{display:inline-block;background:var(--chip);border-radius:6px;padding:1px 6px;margin:2px 4px 2px 0;font-size:12px}
.mut{color:var(--mut);font-size:12px} code{font-size:12px;word-break:break-all}
</style></head><body><main>
<h1>E9: todas las respuestas</h1>
<p class="lead">Qwen2.5-Instruct de 1,5B a 72B. Para cada pregunta, lo que respondió cada brazo, el veredicto con la regla estricta del E9 y el tipo de error. Elegí un tamaño; tocá una celda de la tabla para ver las respuestas de esa pregunta.</p>
<div class="bar"><label>Tamaño <select id="size"></select></label><span class="mut" id="sum"></span></div>
<div class="grid"><table id="grid"></table></div>
<div id="detail"></div>
<h2 style="font-size:17px;margin-top:24px">Tipos de error</h2><div class="grid"><table id="legend"></table></div>
</main>
<script>
const D = __DATA__;
const KCLASS = k => k === "ok" ? "k-ok" : (k === "context" || k === "crash" ? "k-warn" : "k-bad");
const esc = s => String(s ?? "").replace(/[&<>]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
const sel = document.getElementById("size");
D.sizes.forEach(s => sel.add(new Option(s, s)));
sel.value = "72B";
function cell(list){ if(!list) return "—"; const ok = list.filter(r => r.kind === "ok").length; return ok + "/" + list.length; }
function render(){
  const size = sel.value, qids = Object.keys(D.questions);
  let h = "<tr><th>Pregunta</th><th>Esperado</th>" + D.arms.map(a => "<th>" + a + "</th>").join("") + "</tr>";
  const tot = {};
  qids.forEach(q => {
    const row = (D.answers[q] || {})[size] || {};
    h += "<tr><td>" + q + " <span class='mut'>" + esc(D.questions[q].text.slice(0, 70)) + "…</span></td><td>" + esc(D.questions[q].expected ?? "negarse") + "</td>";
    D.arms.forEach(a => { const l = row[a]; if(l){ tot[a] = tot[a] || [0,0]; tot[a][0] += l.filter(r => r.kind==="ok").length; tot[a][1] += l.length; }
      const k = l ? (l.every(r => r.kind === "ok") ? "k-ok" : l.some(r => r.kind === "ok") ? "k-warn" : "k-bad") : "";
      h += "<td class='cell " + k + "' data-q='" + q + "'>" + cell(l) + "</td>"; });
    h += "</tr>";
  });
  h += "<tr><th>Total</th><th></th>" + D.arms.map(a => "<th>" + (tot[a] ? tot[a][0] + "/" + tot[a][1] : "—") + "</th>").join("") + "</tr>";
  document.getElementById("grid").innerHTML = h;
  document.querySelectorAll("td.cell").forEach(td => td.onclick = () => detail(td.dataset.q));
  document.getElementById("detail").innerHTML = "";
}
function detail(q){
  const size = sel.value, row = (D.answers[q] || {})[size] || {}, meta = D.questions[q];
  let h = "<div class='card' style='margin-top:16px'><h3>" + q + ": " + esc(meta.text) + "</h3><span class='mut'>Respuesta del motor: " + esc(meta.expected ?? "debe negarse o pedir datos") + "</span></div><div class='cols'>";
  D.arms.forEach(a => {
    const list = row[a]; if(!list) return;
    h += "<div class='card'><h3>" + a + "</h3>";
    list.forEach(r => {
      h += "<div class='run'><b class='" + KCLASS(r.kind) + "'>" + esc(D.kinds[r.kind]) + "</b> <span class='mut'>corrida " + r.run + " · tokens " + r.tokens[0] + " / " + r.tokens[1] + "</span>";
      if(r.engine !== null && r.engine !== undefined) h += "<div class='mut'>Número del motor para el escenario: " + esc(r.engine) + "</div>";
      if(r.failed) h += "<div class='mut'>" + esc(r.failed) + "</div>";
      if(r.calls.length) h += "<div>" + r.calls.map(c => "<span class='chip' title='" + esc(c.a) + "'>" + (c.ok ? "✓ " : "✗ ") + esc(c.t) + "</span>").join("") + "</div>";
      if(r.unsupported.length) h += "<div class='mut'>Sin respaldo: " + esc(r.unsupported.join(", ")) + "</div>";
      h += "<div class='txt'>" + esc(r.text || "(sin texto)") + "</div></div>";
    });
    h += "</div>";
  });
  document.getElementById("detail").innerHTML = h + "</div>";
  document.getElementById("detail").scrollIntoView({behavior: "smooth"});
}
document.getElementById("legend").innerHTML = Object.entries(D.kinds).map(([k, v]) => "<tr><td class='" + KCLASS(k) + "'>" + v + "</td></tr>").join("");
sel.onchange = render; render();
</script></body></html>"""


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "experimentos" / "2026-11-07-e9-respuestas.html"
    data, counts = load()
    out.write_text(PAGE.replace("__DATA__", json.dumps(data, ensure_ascii=False)), encoding="utf-8")
    print(f"{out} ({out.stat().st_size // 1024} KB)")
    labels = [a[2] for a in ARMS]
    for label in labels:
        print(f"\n{label}\n| tipo | " + " | ".join(SIZES) + " |")
        for k, name in KINDS.items():
            row = [counts.get((s, label), Counter()).get(k, 0) for s in SIZES]
            if any(row):
                print(f"| {name} | " + " | ".join(str(x) for x in row) + " |")


if __name__ == "__main__":
    main()
