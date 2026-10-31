"""Build a reading page for E1: each question, the three conditions side by side, 5 runs each.

Usage: python answers_page.py RESULTS_DIR OUT.html [--stamp 20261030]
Picks the newest baseline / no_verifier / with_verifier file with 39 questions for the stamp.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

COND = [("baseline", "A", "Modelo solo"), ("no_verifier", "B", "DORA sin verificador"), ("with_verifier", "C", "DORA completo")]


def pick(results: Path, cond: str, stamp: str) -> dict | None:
    best = None
    for f in sorted(results.glob(f"muse-spark-1_3_{cond}_{stamp}_*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        if len(d.get("question_ids", [])) >= 30:
            best = (f.name, d)
    return best


def run_record(cond: str, r: dict) -> dict:
    if cond == "baseline":
        text, plan = None, None
        try:
            raw = json.loads(r.get("raw") or "")
            text = raw.get("answer_text")
        except (ValueError, TypeError, AttributeError):
            pass
        if text is None:
            text = r.get("raw") or r.get("parse_error") or "(sin respuesta)"
    else:
        text = r.get("reply") or "(sin respuesta)"
    return {
        "text": text,
        "ok": r.get("answer_correctness"),
        "unsup": r.get("has_unsupported_before_correction"),
        "unsupList": r.get("unsupported") or [],
        "feasible": r.get("plan_feasible"),
        "gap": r.get("plan_gap_pct"),
        "value": r.get("reported_value"),
        "ha": r.get("plan_hectares"),
        "viol": r.get("plan_violations") or [],
        "lat": r.get("latency_s"),
        "verified": r.get("verified"),
    }


def main() -> None:
    results, out = Path(sys.argv[1]), Path(sys.argv[2])
    stamp = sys.argv[sys.argv.index("--stamp") + 1] if "--stamp" in sys.argv else "20261030"
    data = {"conds": [], "questions": {}}
    order: list[str] = []
    for cond, letter, name in COND:
        got = pick(results, cond, stamp)
        if not got:
            data["conds"].append({"key": cond, "letter": letter, "name": name, "file": None})
            continue
        fname, d = got
        agg = {k: (v["mean"] if isinstance(v, dict) else v) for k, v in d["aggregated"].items()}
        data["conds"].append({"key": cond, "letter": letter, "name": name, "file": fname,
                              "commit": d.get("commit"), "runs": d.get("runs"), "agg": agg})
        for qid in d["question_ids"]:
            if qid not in order:
                order.append(qid)
        for run in d["detailed_results"]:
            for r in run:
                q = data["questions"].setdefault(r["id"], {"id": r["id"], "text": r.get("text"), "runs": {}})
                q["expected"] = d["per_question"].get(r["id"], {}).get("expected_value")
                q["runs"].setdefault(cond, []).append(run_record(cond, r))
    data["order"] = order
    html = TEMPLATE.replace("/*DATA*/null", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size // 1024} KB), conditions:",
          [c["file"] for c in data["conds"]])


TEMPLATE = r"""<title>E1: las respuestas</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600&family=Source+Sans+3:wght@400;600&family=JetBrains+Mono:wght@400;600&display=swap">
<style>
/* Layout: summary table, then "mirá estas", then one card per question with A | B | C columns. Soil and wheat palette. */
:root{
  --bg:#f6f5f0; --surface:#ffffff; --fg:#23251f; --muted:#666a5c; --line:#dcdccf;
  --accent:#5b6b2f; --ok:#2f7a45; --ok-bg:#e3f1e6; --bad:#b03a2e; --bad-bg:#f8e3e0; --warn:#9a6a10; --warn-bg:#f6ecd5;
  --display:"Fraunces",Georgia,serif; --body:"Source Sans 3",system-ui,sans-serif; --mono:"JetBrains Mono",ui-monospace,monospace;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
  --bg:#181a15; --surface:#22251e; --fg:#e8e8de; --muted:#a3a795; --line:#3a3e33;
  --accent:#b5c77a; --ok:#7fcf94; --ok-bg:#1f3626; --bad:#f0897c; --bad-bg:#3d2320; --warn:#e3b860; --warn-bg:#3a3020; color-scheme:dark}}
:root[data-theme="dark"]{
  --bg:#181a15; --surface:#22251e; --fg:#e8e8de; --muted:#a3a795; --line:#3a3e33;
  --accent:#b5c77a; --ok:#7fcf94; --ok-bg:#1f3626; --bad:#f0897c; --bad-bg:#3d2320; --warn:#e3b860; --warn-bg:#3a3020; color-scheme:dark}
body{background:var(--bg);color:var(--fg);font:16px/1.5 var(--body)}
.wrap{max-width:1280px;margin:0 auto;padding-block:28px 64px;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));display:grid;gap:28px}
h1,h2{font-family:var(--display);font-weight:600;text-wrap:balance;margin:0}
h1{font-size:2rem} h2{font-size:1.35rem}
p{margin:0;max-width:68ch}
.lead{color:var(--muted)}
.tbl{overflow-x:auto}
table{border-collapse:collapse;font-variant-numeric:tabular-nums;min-width:560px}
th,td{padding:6px 12px;border-bottom:1px solid var(--line);text-align:left}
th{font-size:.8rem;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);font-weight:600}
.filters{display:flex;flex-wrap:wrap;gap:8px}
button{font:inherit;cursor:pointer}
.chip{border:1px solid var(--line);background:var(--surface);color:var(--fg);border-radius:999px;padding:4px 12px;font-size:.9rem}
.chip[aria-pressed="true"]{background:var(--accent);border-color:var(--accent);color:var(--bg)}
button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.q{background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:16px;display:grid;gap:12px}
.qhead{display:flex;flex-wrap:wrap;gap:8px 16px;align-items:baseline}
.qid{font-family:var(--mono);font-weight:600;color:var(--accent)}
.qtext{font-size:1.05rem;font-weight:600;flex:1 1 40ch;min-width:0}
.exp{font-family:var(--mono);font-size:.85rem;color:var(--muted)}
.why{font-size:.9rem;color:var(--warn)}
.cols{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
@media (max-width:900px){.cols{grid-template-columns:minmax(0,1fr)}}
.col{border-top:3px solid var(--line);padding-top:8px;display:grid;gap:8px;align-content:start;min-width:0}
.col.allok{border-top-color:var(--ok)} .col.someko{border-top-color:var(--warn)} .col.allko{border-top-color:var(--bad)}
.colhead{display:flex;justify-content:space-between;gap:8px;align-items:baseline}
.colname{font-weight:600}
.score{font-family:var(--mono);font-size:.85rem}
.runs{display:flex;gap:4px;flex-wrap:wrap}
.run{width:30px;height:28px;border:1px solid var(--line);border-radius:4px;background:var(--surface);color:var(--fg);font-family:var(--mono);font-size:.8rem}
.run.ok{background:var(--ok-bg);border-color:var(--ok)} .run.ko{background:var(--bad-bg);border-color:var(--bad)}
.run[aria-pressed="true"]{outline:2px solid var(--fg);outline-offset:1px}
.tags{display:flex;flex-wrap:wrap;gap:4px}
.tag{font-size:.75rem;padding:1px 8px;border-radius:3px;font-weight:600}
.t-ok{background:var(--ok-bg);color:var(--ok)} .t-bad{background:var(--bad-bg);color:var(--bad)} .t-warn{background:var(--warn-bg);color:var(--warn)}
.vals{font-family:var(--mono);font-size:.8rem;color:var(--muted);overflow-wrap:anywhere}
.reply{font-size:.92rem;line-height:1.45;max-height:26em;overflow:auto;border-left:2px solid var(--line);padding-left:10px;overflow-wrap:anywhere}
.reply p{margin:0 0 .5em} .reply ul{margin:0 0 .5em;padding-left:1.2em}
.missing{color:var(--muted);font-style:italic}
.unsup{font-size:.8rem;color:var(--warn)}
.list{display:grid;gap:16px}
</style>
<div class="wrap">
  <header style="display:grid;gap:8px">
    <h1>E1: las respuestas, pregunta por pregunta</h1>
    <p class="lead">Muse Spark 1.3 en tres condiciones, 39 preguntas, 5 repeticiones cada una. Los cuadraditos son las repeticiones: verde si la respuesta fue correcta, rojo si no. Tocá uno para leer esa respuesta.</p>
  </header>
  <section style="display:grid;gap:12px"><h2>Resumen</h2><div class="tbl"><table id="sum"></table></div></section>
  <section style="display:grid;gap:12px"><h2>Mirá estas</h2><p class="lead">Elegidas solas: donde una condición acierta y otra falla, o donde los números cambian entre repeticiones.</p><div class="list" id="picks"></div></section>
  <section style="display:grid;gap:12px">
    <h2>Todas las preguntas</h2>
    <div class="filters" id="filters"></div>
    <div class="list" id="all"></div>
  </section>
</div>
<script>
const D=/*DATA*/null;
const fmt=v=>v==null?"—":(typeof v==="number"?v.toLocaleString("es-AR",{maximumFractionDigits:2}):String(v));
const esc=s=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
function md(s){
  const lines=esc(s).replace(/\*\*(.+?)\*\*/g,"<strong>$1</strong>").split(/\n/);
  let out="",inList=false;
  for(const l of lines){
    const m=l.match(/^\s*[-*•]\s+(.*)/);
    if(m){if(!inList){out+="<ul>";inList=true}out+="<li>"+m[1]+"</li>";continue}
    if(inList){out+="</ul>";inList=false}
    if(l.trim())out+="<p>"+l+"</p>";
  }
  return out+(inList?"</ul>":"");
}
const pct=v=>v==null?"—":Math.round(v*100)+" %";
function summary(){
  const rows=[["Respuestas correctas","answer_correctness",pct],["Con números sin respaldo","unsupported_numbers_rate",pct],["Lo que deja el plan sobre la mesa (promedio)","gap_pct_mean",v=>v==null?"—":v.toLocaleString("es-AR",{maximumFractionDigits:2})+" %"],["Preguntas con el mismo número en las 5","questions_with_one_value",v=>v==null?"—":v],["Tokens de salida por pregunta","completion_tokens_per_question",v=>v==null?"—":Math.round(v).toLocaleString("es-AR")]];
  let h="<tr><th></th>"+D.conds.map(c=>`<th>${c.letter} · ${c.name}</th>`).join("")+"</tr>";
  for(const [lab,k,f] of rows)h+=`<tr><td>${lab}</td>`+D.conds.map(c=>`<td>${c.file?f(c.agg[k]):'<span class="missing">corriendo</span>'}</td>`).join("")+"</tr>";
  document.getElementById("sum").innerHTML=h;
}
function stats(q,key){
  const rs=q.runs[key]; if(!rs)return null;
  const ok=rs.filter(r=>r.ok).length, vals=rs.map(r=>r.value);
  const distinct=new Set(vals.filter(v=>v!=null).map(v=>String(v))).size;
  return {ok,n:rs.length,distinct};
}
function card(q){
  const el=document.createElement("article");el.className="q";
  const st=Object.fromEntries(D.conds.map(c=>[c.key,stats(q,c.key)]));
  el.innerHTML=`<div class="qhead"><span class="qid">${q.id}</span><span class="qtext">${esc(q.text||"")}</span><span class="exp">respuesta exacta: ${fmt(q.expected)}</span></div>`+(q.why?`<div class="why">${esc(q.why)}</div>`:"");
  const cols=document.createElement("div");cols.className="cols";
  for(const c of D.conds){
    const col=document.createElement("div");col.className="col";
    const s=st[c.key];
    if(!s){col.innerHTML=`<div class="colhead"><span class="colname">${c.letter} · ${c.name}</span></div><div class="missing">Todavía corriendo.</div>`;cols.append(col);continue}
    col.classList.add(s.ok===s.n?"allok":s.ok===0?"allko":"someko");
    const rs=q.runs[c.key];
    col.innerHTML=`<div class="colhead"><span class="colname">${c.letter} · ${c.name}</span><span class="score">${s.ok}/${s.n} bien</span></div>
      <div class="vals">números dados: ${rs.map(r=>fmt(r.value)).join(" · ")}</div><div class="runs"></div><div class="tags"></div><div class="unsup"></div><div class="reply"></div>`;
    const runsEl=col.querySelector(".runs");
    const show=i=>{
      const r=rs[i];
      runsEl.querySelectorAll(".run").forEach((b,j)=>b.setAttribute("aria-pressed",j===i));
      const t=[];
      t.push(r.ok?'<span class="tag t-ok">correcta</span>':'<span class="tag t-bad">incorrecta</span>');
      if(r.unsup)t.push('<span class="tag t-warn">números sin respaldo</span>');
      if(r.feasible===false&&r.viol.length===1&&r.viol[0]==="no plan given")t.push('<span class="tag" style="color:var(--muted)">sin plan</span>');
      else if(r.feasible===false)t.push('<span class="tag t-bad">plan imposible</span>');
      else if(r.feasible===true)t.push(`<span class="tag t-ok">plan factible${r.gap?", deja "+fmt(r.gap)+" %":""}</span>`);
      if(r.verified===true)t.push('<span class="tag t-ok">verificada</span>');
      if(r.lat!=null)t.push(`<span class="tag" style="color:var(--muted)">${Math.round(r.lat)} s</span>`);
      col.querySelector(".tags").innerHTML=t.join("");
      col.querySelector(".unsup").textContent=r.unsupList.length?"Sin respaldo: "+r.unsupList.join(", "):"";
      let txt=md(r.text);
      if(c.key==="baseline"&&r.ha)txt+=`<p class="vals">plan: ${Object.entries(r.ha).filter(([,v])=>v).map(([k,v])=>k+" "+fmt(v)+" ha").join(", ")||"nada sembrado"}${r.viol.length?" · falla: "+esc(JSON.stringify(r.viol)):""}</p>`;
      col.querySelector(".reply").innerHTML=txt;
    };
    rs.forEach((r,i)=>{const b=document.createElement("button");b.className="run "+(r.ok?"ok":"ko");b.textContent=i+1;b.title=`Repetición ${i+1}`;b.onclick=()=>show(i);runsEl.append(b)});
    show(Math.max(0,rs.findIndex(r=>!r.ok)));
    cols.append(col);
  }
  el.append(cols);return el;
}
const QS=D.order.map(id=>D.questions[id]);
function tagsOf(q){
  const s=Object.fromEntries(D.conds.map(c=>[c.key,stats(q,c.key)]));
  const t=new Set();
  const A=s.baseline,B=s.no_verifier,C=s.with_verifier;
  if(A&&A.ok<A.n)t.add("afalla");
  if((B&&B.ok<B.n)||(C&&C.ok<C.n))t.add("dorafalla");
  if(A&&C&&A.ok===0&&C.ok===C.n)t.add("brecha");
  if(B&&C&&B.ok!==C.ok)t.add("verif");
  if(A&&A.distinct>1)t.add("varia");
  return t;
}
function picks(){
  const why=q=>{
    const t=tagsOf(q),s=k=>stats(q,k);
    if(t.has("brecha"))return `El modelo solo falló las ${s("baseline").n}; DORA completo acertó todas.`+(s("baseline").distinct>1?` Además dio ${s("baseline").distinct} números distintos.`:"");
    if(t.has("dorafalla"))return "Aquí DORA falla en alguna repetición: mirar por qué.";
    if(t.has("verif"))return "El verificador cambia el resultado.";
    return "";
  };
  const chosen=[...QS.filter(q=>tagsOf(q).has("brecha")).slice(0,4),...QS.filter(q=>tagsOf(q).has("dorafalla"))];
  const box=document.getElementById("picks");
  if(!chosen.length){box.innerHTML='<p class="missing">Nada para destacar todavía.</p>';return}
  for(const q of chosen)box.append(card({...q,why:why(q)}));
}
const FILTERS=[["todas","Todas"],["afalla","El modelo solo falla"],["dorafalla","DORA falla"],["verif","El verificador cambia algo"],["varia","El modelo solo cambia de número"]];
function renderAll(f){
  const box=document.getElementById("all");box.replaceChildren();
  const list=QS.filter(q=>f==="todas"||tagsOf(q).has(f));
  if(!list.length){box.innerHTML='<p class="missing">Ninguna pregunta en este grupo.</p>';return}
  list.forEach(q=>box.append(card(q)));
}
function filters(){
  const box=document.getElementById("filters");
  FILTERS.forEach(([k,lab],i)=>{const b=document.createElement("button");b.className="chip";b.textContent=lab;b.setAttribute("aria-pressed",i===0);
    b.onclick=()=>{box.querySelectorAll(".chip").forEach(x=>x.setAttribute("aria-pressed",x===b));renderAll(k)};box.append(b)});
}
summary();picks();filters();renderAll("todas");
</script>
"""

if __name__ == "__main__":
    main()
