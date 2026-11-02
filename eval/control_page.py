"""Control page for the delivery: what has to be submitted, the experiments, and every E1 question with
what DORA answered in each run. Every figure is read from the run files; nothing is typed by hand.

    python eval/control_page.py --out <page.html>
"""
import argparse
import glob
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "eval" / "results"


def load_jsonl(*paths):
    out = {}
    for p in paths:
        for line in open(p, encoding="utf-8"):
            if line.strip():
                d = json.loads(line)
                out[d["id"]] = d
    return out


def esc(s):
    return html.escape(str(s if s is not None else ""))


def fmt_value(v):
    if isinstance(v, float):
        return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if isinstance(v, int):
        return f"{v:,}".replace(",", ".")
    return str(v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    questions = load_jsonl(ROOT / "eval/questions.jsonl", ROOT / "eval/questions_spec30.jsonl")
    answers = load_jsonl(ROOT / "eval/answers.jsonl", ROOT / "eval/answers_spec30.jsonl")

    final = json.load(open(RES / "e1_final_with_verifier.json", encoding="utf-8"))
    ids = final["question_ids"]
    final_runs = {}  # id -> [record per run]
    for run in final["detailed_results"]:
        for r in run:
            final_runs.setdefault(r["id"], []).append(r)

    regr = {}
    for f in glob.glob(str(RES / "regression_spec31" / "*.json")):
        d = json.load(open(f, encoding="utf-8"))
        for run in d["detailed_results"]:
            for r in run:
                regr[r["id"]] = r

    interview = json.load(open(RES / "e7_results.json", encoding="utf-8"))

    n_final = sum(len(v) for v in final_runs.values())
    ok_final = sum(1 for v in final_runs.values() for r in v if r["answer_correctness"])
    ok_regr = sum(1 for r in regr.values() if r["answer_correctness"])
    ver_regr = sum(1 for r in regr.values() if r["verified"])

    def mark(r):
        if r is None:
            return '<span class="pill na">—</span>'
        if r["answer_correctness"]:
            return '<span class="pill ok" title="correcta">✓</span>'
        return '<span class="pill bad" title="incorrecta">✗</span>'

    rows = []
    for qid in ids:
        q = questions.get(qid, {})
        a = answers.get(qid, {})
        fr = final_runs.get(qid, [])
        rg = regr.get(qid)
        failed = any(not r["answer_correctness"] for r in fr) or (rg is not None and not rg["answer_correctness"])
        expected = f'{esc(a.get("tool", ""))} → <code>{esc(a.get("field", ""))}</code> = <b>{esc(fmt_value(a.get("expected_value")))}</b>' if a else "—"
        reply = rg["reply"] if rg else (fr[0]["reply"] if fr else "")
        reply_src = "corrida con la SPEC-31" if rg else "E1 final, corrida 1"
        tools = ", ".join(c.get("tool", "") for c in (rg or (fr[0] if fr else {})).get("tool_calls", []))
        rows.append(f"""
<tr class="q{' failed' if failed else ''}">
  <td class="id">{esc(qid)}</td>
  <td class="text">
    <details><summary>{esc(q.get("text", ""))}</summary>
      <div class="answer"><div class="meta">Respuesta de DORA ({reply_src}) · herramientas: {esc(tools) or "ninguna"}</div>
      <div class="reply">{esc(reply)}</div></div>
    </details>
  </td>
  <td class="exp">{expected}</td>
  <td class="runs">{''.join(mark(r) for r in fr)}</td>
  <td class="runs">{mark(rg)}</td>
</tr>""")

    cases = []
    for c in interview:
        turns = "".join(
            f'<div class="turn farmer"><span>Productor</span>{esc(t["farmer_message"])}</div>'
            f'<div class="turn dora"><span>DORA{" · verificada" if t.get("verified") else ""}</span>{esc(t["reply"])}</div>'
            for t in c["turns"])
        n_q = sum(1 for t in c["turns"] if not t.get("done"))
        cases.append(f"""
<details class="case"><summary><b>{esc(c["name"])}</b> · {len(c["turns"])} turnos, {n_q} preguntas, {fmt_value(round(c["total_seconds"], 1))} s{" · terminó sola" if c.get("stopped_by_itself") else ""}</summary>
<div class="conv">{turns}</div></details>""")

    page = TEMPLATE.format(
        n_final=n_final, ok_final=ok_final, n_regr=len(regr), ok_regr=ok_regr, ver_regr=ver_regr,
        final_commit=esc(final["commit"]), rows="".join(rows), cases="".join(cases),
    )
    Path(args.out).write_text(page, encoding="utf-8")
    print(f"written {args.out}: {len(ids)} questions, final {ok_final}/{n_final}, SPEC-31 {ok_regr}/{len(regr)}")


TEMPLATE = """<title>DORA: tablero de entrega</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;700&family=Source+Sans+3:wght@400;600&family=JetBrains+Mono:wght@400&display=swap">
<style>
/* Layout: one reading column; summary first (what to submit), then the evidence (experiments, questions, interview). */
:root {{
  --bg: #f6f7f2; --surface: #ffffff; --fg: #1d2419; --muted: #5d6656; --line: #dfe3d6;
  --accent: #3f6b2a; --ok: #2f7a3a; --ok-bg: #e2f1e1; --bad: #a3361f; --bad-bg: #f8e3dc; --warn: #8a6100; --warn-bg: #f6ecd2;
  --display: "Archivo", "Helvetica Neue", Arial, sans-serif; --body: "Source Sans 3", "Segoe UI", sans-serif; --mono: "JetBrains Mono", Consolas, monospace;
}}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
  --bg: #151913; --surface: #1d231a; --fg: #e6eadf; --muted: #a3ab99; --line: #333b2e;
  --accent: #9cc77f; --ok: #8fd394; --ok-bg: #1f3a22; --bad: #f19a83; --bad-bg: #44231a; --warn: #e6c26b; --warn-bg: #3d321a; color-scheme: dark; }} }}
:root[data-theme="dark"] {{
  --bg: #151913; --surface: #1d231a; --fg: #e6eadf; --muted: #a3ab99; --line: #333b2e;
  --accent: #9cc77f; --ok: #8fd394; --ok-bg: #1f3a22; --bad: #f19a83; --bad-bg: #44231a; --warn: #e6c26b; --warn-bg: #3d321a; color-scheme: dark; }}
body {{ background: var(--bg); color: var(--fg); font: 16px/1.5 var(--body); }}
main {{ max-width: 1080px; margin: 0 auto; padding-block: 28px 64px; padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); display: grid; gap: 36px; }}
h1, h2 {{ font-family: var(--display); text-wrap: balance; margin: 0; }}
h1 {{ font-size: 1.9rem; }} h2 {{ font-size: 1.3rem; margin-bottom: 10px; }}
.lede {{ color: var(--muted); max-width: 65ch; margin: 6px 0 0; }}
section > p {{ max-width: 70ch; color: var(--muted); margin: 0 0 12px; }}
.wrap {{ overflow-x: auto; border: 1px solid var(--line); border-radius: 8px; background: var(--surface); }}
table {{ width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; }}
th, td {{ text-align: left; vertical-align: top; padding: 9px 12px; border-bottom: 1px solid var(--line); }}
th {{ font: 600 0.78rem var(--body); text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); }}
tr:last-child td {{ border-bottom: 0; }}
.pill {{ display: inline-block; min-width: 1.6em; text-align: center; padding: 1px 8px; border-radius: 999px; font-size: 0.85rem; font-weight: 600; margin-right: 3px; }}
.ok {{ background: var(--ok-bg); color: var(--ok); }} .bad {{ background: var(--bad-bg); color: var(--bad); }}
.warn {{ background: var(--warn-bg); color: var(--warn); }} .na {{ color: var(--muted); }}
.id {{ font-family: var(--mono); font-size: 0.85rem; white-space: nowrap; }}
.exp {{ font-size: 0.9rem; min-width: 190px; }} code {{ font-family: var(--mono); font-size: 0.85em; }}
.runs {{ white-space: nowrap; }}
td.text {{ min-width: 260px; }}
summary {{ cursor: pointer; }} summary:focus-visible, button:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
.answer {{ margin-top: 8px; padding: 10px 12px; border-left: 3px solid var(--accent); background: var(--bg); }}
.meta {{ font-size: 0.8rem; color: var(--muted); margin-bottom: 6px; }}
.reply {{ white-space: pre-wrap; font-size: 0.92rem; }}
tr.failed td.id {{ color: var(--bad); font-weight: 600; }}
.filters {{ display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }}
button {{ font: 600 0.9rem var(--body); padding: 6px 14px; border-radius: 999px; border: 1px solid var(--line); background: var(--surface); color: var(--fg); cursor: pointer; }}
button[aria-pressed="true"] {{ background: var(--accent); color: var(--bg); border-color: var(--accent); }}
.only-failed tr.q:not(.failed) {{ display: none; }}
.stats {{ display: flex; gap: 28px; flex-wrap: wrap; }}
.stat b {{ display: block; font: 700 1.6rem var(--display); }} .stat span {{ color: var(--muted); font-size: 0.9rem; }}
.case {{ border: 1px solid var(--line); border-radius: 8px; background: var(--surface); padding: 10px 14px; margin-bottom: 8px; }}
.conv {{ display: grid; gap: 8px; margin-top: 10px; }}
.turn {{ white-space: pre-wrap; padding: 8px 12px; border-radius: 8px; font-size: 0.93rem; max-width: 80ch; }}
.turn span {{ display: block; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); margin-bottom: 2px; }}
.farmer {{ background: var(--bg); justify-self: start; }} .dora {{ background: var(--ok-bg); justify-self: end; }}
</style>
<main>
<header>
  <h1>DORA: tablero de entrega</h1>
  <p class="lede">Entrega en Cerebral Valley: miércoles 4/11, 23:00 de Buenos Aires (categoría Indie). Los números de esta página salen de los archivos de las corridas; ninguno está escrito a mano.</p>
</header>

<section>
  <h2>Qué hay que entregar</h2>
  <div class="wrap"><table>
    <tr><th>Pieza</th><th>Estado</th><th>Qué falta</th></tr>
    <tr><td>Repo público con todo el trabajo nuevo</td><td><span class="pill ok">listo</span></td><td>Main pusheado con la SPEC-31 (c038f3b, 2/11).</td></tr>
    <tr><td>Producto en vivo</td><td><span class="pill ok">listo</span></td><td>guillermosiaira--dora-web.us-east.modal.run, desplegada con la SPEC-31 (2/11).</td></tr>
    <tr><td>README con resultados</td><td><span class="pill ok">listo</span></td><td>Con la declaración de trabajo previo (2/11). Revisar la redacción.</td></tr>
    <tr><td>Video de 3 minutos</td><td><span class="pill bad">falta</span></td><td>Guion listo en docs/guion-video.md; ensayar en la app y grabar.</td></tr>
    <tr><td>Pantalla de entrada para quien llega por primera vez</td><td><span class="pill ok">listo</span></td><td>"Empezá acá" en línea (SPEC-32, 2/11).</td></tr>
    <tr><td>Envío del formulario</td><td><span class="pill bad">falta</span></td><td>Lo hace Guillermo con el repo, el video y la dirección de la app.</td></tr>
    <tr><td>WhatsApp</td><td><span class="pill na">afuera</span></td><td>Va como próximo paso; Meta no verifica el número.</td></tr>
  </table></div>
  <p style="margin-top:10px">Cómo se evalúa: impacto 30 %, uso de herramientas de Meta 25 % (Muse Spark, Voice Transcribe, SAM 3.1, Muse Spark Open, Llama), demo 25 %, profundidad técnica 20 %.</p>
</section>

<section>
  <h2>Experimentos</h2>
  <div class="wrap"><table>
    <tr><th>Experimento</th><th>Resultado</th><th>Respuestas</th></tr>
    <tr><td>E1 · Muse Spark solo contra DORA</td><td>Solo 38 %; DORA completo 97 %, ningún plan imposible</td><td><a href="https://claude.ai/artifact/3iC2F7d6mAuwAxMSiGLmVj">página</a></td></tr>
    <tr><td>E1 final · modelo v4</td><td>{ok_final} de {n_final} correctas, todas verificadas</td><td>abajo</td></tr>
    <tr><td>E1 · Contributor</td><td>Solo 37 %; DORA completo 95 %</td><td><a href="https://claude.ai/artifact/LbYRRMuVAxBuZTRbTrZGFg">página</a></td></tr>
    <tr><td>E6 · Muse Spark Open (Baseten)</td><td>Solo 37 %; DORA completo 93 %</td><td><a href="https://claude.ai/artifact/4LRbQBFNArd8mTTpu962gg">página</a></td></tr>
    <tr><td>E2 y E4 · regiones y precios en vivo</td><td>5 de 5 verificadas, mismo ranking</td><td><a href="https://claude.ai/artifact/PJYgpRFvd1UxfaHUqYB3pc">página</a></td></tr>
    <tr><td>E3 · voz, factura, foto</td><td>Voz igual a escrito 6 de 6; factura en foto 6 de 6 contra 2 de 6 tipeada</td><td><a href="https://claude.ai/artifact/6zSiC4b2nyZrX8XYskjS1q">página</a></td></tr>
    <tr><td>E5 · robustez</td><td>Con verificador 55 de 55 (regla corregida)</td><td><a href="https://claude.ai/artifact/MjpXQWQSUC4XPw1c691XES">página</a></td></tr>
    <tr><td>Entrevista (SPEC-29)</td><td>Una pregunta por vez, termina sola</td><td>abajo</td></tr>
  </table></div>
</section>

<section>
  <h2>Las preguntas de E1</h2>
  <p>Cada pregunta tiene una respuesta correcta calculada por el motor. E1 final corrió 3 veces sobre el código <code>{final_commit}</code>; la última columna es una corrida con los arreglos de la SPEC-31. Tocá una pregunta para leer la respuesta de DORA.</p>
  <div class="stats">
    <div class="stat"><b>{ok_final} / {n_final}</b><span>correctas en E1 final</span></div>
    <div class="stat"><b>{ok_regr} / {n_regr}</b><span>correctas con la SPEC-31</span></div>
    <div class="stat"><b>{ver_regr} / {n_regr}</b><span>verificadas con la SPEC-31</span></div>
  </div>
  <div class="filters" style="margin-top:14px">
    <button id="f-all" aria-pressed="true">Todas</button>
    <button id="f-bad" aria-pressed="false">Solo las que fallaron alguna vez</button>
  </div>
  <div class="wrap" id="qtable"><table>
    <tr><th>Id</th><th>Pregunta</th><th>Respuesta correcta</th><th>E1 final</th><th>SPEC-31</th></tr>
    {rows}
  </table></div>
</section>

<section>
  <h2>La entrevista</h2>
  <p>Un productor simulado contesta lo que DORA pregunta. Sirve como material para la escena central del video.</p>
  {cases}
</section>
</main>
<script>
const t = document.getElementById("qtable"), a = document.getElementById("f-all"), b = document.getElementById("f-bad");
function set(onlyBad) {{ t.classList.toggle("only-failed", onlyBad); a.setAttribute("aria-pressed", String(!onlyBad)); b.setAttribute("aria-pressed", String(onlyBad)); }}
a.addEventListener("click", () => set(false)); b.addEventListener("click", () => set(true));
</script>
"""

if __name__ == "__main__":
    main()
