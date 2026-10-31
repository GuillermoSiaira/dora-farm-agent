"""Build a reading page for E5 (robustness): each trap question, DORA without and with the verifier, 5 runs each.

Usage: python e5_page.py NO_VERIFIER.json WITH_VERIFIER.json QUESTIONS.jsonl OUT.html
Same look as the E1 page (eval/answers_page.py).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from answers_page import TEMPLATE as E1_TEMPLATE

STYLE = E1_TEMPLATE[E1_TEMPLATE.index("<meta"):E1_TEMPLATE.index("</style>")]
KINDS = {"missing_data": "Falta un dato", "out_of_scope": "Fuera de alcance", "impossible": "Escenario imposible",
         "pressure": "Presión"}
COND = [("no_verifier", "B", "DORA sin verificador"), ("with_verifier", "C", "DORA completo")]


def run_record(r: dict) -> dict:
    return {
        "text": r.get("reply") or "(sin respuesta)",
        "ok": r.get("answer_correctness"),
        "e5": r.get("e5") or {},
        "unsupInitial": r.get("unsupported_initial") or [],
        "unsup": r.get("unsupported") or [],
        "verified": r.get("verified"),
        "tools": [{"tool": c.get("tool"), "error": c.get("error")} for c in r.get("tool_calls") or []],
        "lat": r.get("latency_s"),
    }


def build(no_ver: Path, with_ver: Path, questions: Path) -> dict:
    qs = [json.loads(l) for l in questions.read_text(encoding="utf-8").splitlines() if l.strip()]
    data = {"conds": [], "order": [q["id"] for q in qs],
            "questions": {q["id"]: {"id": q["id"], "text": q["text"], "kind": KINDS[q["e5"]["kind"]],
                                    "rule": q["e5"]["rule"], "runs": {}} for q in qs}}
    for path, (cond, letter, name) in zip((no_ver, with_ver), COND):
        d = json.loads(path.read_text(encoding="utf-8"))
        data["conds"].append({"key": cond, "letter": letter, "name": name, "file": path.name,
                              "commit": d.get("commit"), "runs": d.get("runs")})
        for run in d["detailed_results"]:
            for r in run:
                data["questions"][r["id"]]["runs"].setdefault(cond, []).append(run_record(r))
    return data


def main() -> None:
    no_ver, with_ver, questions, out = (Path(a) for a in sys.argv[1:5])
    data = build(no_ver, with_ver, questions)
    html = TEMPLATE.replace("/*STYLE*/", STYLE).replace(
        "/*DATA*/null", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size // 1024} KB)")


TEMPLATE = r"""<title>Preguntas trampa E5</title>
/*STYLE*/
.cols{grid-template-columns:repeat(2,minmax(0,1fr))}
@media (max-width:760px){.cols{grid-template-columns:minmax(0,1fr)}}
.kind{font-size:.75rem;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);font-weight:600}
.rule{font-size:.9rem;color:var(--muted);max-width:none}
.tools{font-family:var(--mono);font-size:.78rem;color:var(--muted);overflow-wrap:anywhere}
</style>
<div class="wrap">
  <header style="display:grid;gap:8px">
    <h1>E5: preguntas trampa, pregunta por pregunta</h1>
    <p class="lead">Muse Spark 1.3 Standard con las herramientas de DORA, sin y con verificador. Once preguntas armadas para tentar al modelo a inventar: falta un dato, piden algo que el modelo no cubre, el escenario es imposible o lo presionan por un número. Cada pregunta tiene su regla de "pasa"; los cuadraditos son las 5 repeticiones, verde si pasó. Tocá uno para leer esa respuesta.</p>
  </header>
  <section style="display:grid;gap:12px"><h2>Resumen</h2><div class="tbl"><table id="sum"></table></div></section>
  <section style="display:grid;gap:12px"><h2>Mirá estas</h2><p class="lead">Donde el verificador cambia algo: la regla de la pregunta o los números sin respaldo que llegan al productor.</p><div class="list" id="picks"></div></section>
  <section style="display:grid;gap:12px">
    <h2>Todas las preguntas</h2>
    <div class="filters" id="filters"></div>
    <div class="list" id="all"></div>
  </section>
</div>
<script>
const D=/*DATA*/null;
const esc=s=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
function md(s){
  const lines=esc(s).replace(/\*\*(.+?)\*\*/g,"<strong>$1</strong>").split(/\n/);
  let out="",inList=false;
  for(const l of lines){
    const m=l.match(/^\s*(?:[-*•]|\d+[.)])\s+(.*)/);
    if(m){if(!inList){out+="<ul>";inList=true}out+="<li>"+m[1]+"</li>";continue}
    if(inList){out+="</ul>";inList=false}
    if(l.trim())out+="<p>"+l.replace(/^#+\s*/,"")+"</p>";
  }
  return out+(inList?"</ul>":"");
}
const QS=D.order.map(id=>D.questions[id]);
const count=(q,k,f)=>(q.runs[k]||[]).filter(f).length;
function summary(){
  const kinds=[...new Set(QS.map(q=>q.kind))];
  let h="<tr><th></th>"+D.conds.map(c=>`<th>${c.letter} · ${c.name}</th>`).join("")+"</tr>";
  const row=(lab,list,f)=>`<tr><td>${lab}</td>`+D.conds.map(c=>{
    const n=list.reduce((a,q)=>a+(q.runs[c.key]||[]).length,0),k=list.reduce((a,q)=>a+count(q,c.key,f),0);
    return `<td>${k} de ${n}</td>`}).join("")+"</tr>";
  for(const k of kinds)h+=row(k,QS.filter(q=>q.kind===k),r=>r.ok);
  h+=row("<strong>Total que pasa</strong>",QS,r=>r.ok);
  h+=row("Con números sin respaldo en el primer borrador",QS,r=>r.unsupInitial.length>0);
  h+=row("Con números sin respaldo en lo que ve el productor",QS,r=>r.unsup.length>0);
  document.getElementById("sum").innerHTML=h;
}
function card(q){
  const el=document.createElement("article");el.className="q";
  el.innerHTML=`<div class="qhead"><span class="qid">${q.id}</span><span class="qtext">${esc(q.text)}</span><span class="kind">${esc(q.kind)}</span></div><p class="rule">Pasa si: ${esc(q.rule)}</p>`+(q.why?`<div class="why">${esc(q.why)}</div>`:"");
  const cols=document.createElement("div");cols.className="cols";
  for(const c of D.conds){
    const rs=q.runs[c.key]||[],ok=rs.filter(r=>r.ok).length;
    const col=document.createElement("div");col.className="col "+(ok===rs.length?"allok":ok===0?"allko":"someko");
    col.innerHTML=`<div class="colhead"><span class="colname">${c.letter} · ${c.name}</span><span class="score">${ok}/${rs.length} pasan</span></div><div class="runs"></div><div class="tags"></div><div class="tools"></div><div class="unsup"></div><div class="reply"></div>`;
    const runsEl=col.querySelector(".runs");
    const show=i=>{
      const r=rs[i];
      runsEl.querySelectorAll(".run").forEach((b,j)=>b.setAttribute("aria-pressed",j===i));
      const t=[r.ok?'<span class="tag t-ok">pasa</span>':'<span class="tag t-bad">no pasa</span>'];
      if(r.e5.failed_by)t.push('<span class="tag t-bad">dijo lo que no debía</span>');
      if(!r.e5.verified_ok)t.push('<span class="tag t-bad">número sin respaldo</span>');
      if(r.unsupInitial.length&&!r.unsup.length)t.push('<span class="tag t-ok">el verificador lo corrigió</span>');
      if(r.verified===true)t.push('<span class="tag t-ok">verificada</span>');
      if(r.lat!=null)t.push(`<span class="tag" style="color:var(--muted)">${Math.round(r.lat)} s</span>`);
      col.querySelector(".tags").innerHTML=t.join("");
      col.querySelector(".tools").textContent=r.tools.length?"herramientas: "+r.tools.map(x=>x.tool+(x.error?" (error)":"")).join(" · "):"no llamó herramientas";
      const u=[];
      if(r.unsupInitial.length)u.push("Sin respaldo en el borrador: "+r.unsupInitial.join(", "));
      if(r.unsup.length)u.push("Sin respaldo en la respuesta: "+r.unsup.join(", "));
      col.querySelector(".unsup").textContent=u.join(" · ");
      col.querySelector(".reply").innerHTML=md(r.text);
    };
    rs.forEach((r,i)=>{const b=document.createElement("button");b.className="run "+(r.ok?"ok":"ko");b.textContent=i+1;b.title=`Repetición ${i+1}`;b.onclick=()=>show(i);runsEl.append(b)});
    if(rs.length)show(Math.max(0,rs.findIndex(r=>!r.ok)));
    cols.append(col);
  }
  el.append(cols);return el;
}
function tagsOf(q){
  const t=new Set(),okB=count(q,"no_verifier",r=>r.ok),okC=count(q,"with_verifier",r=>r.ok);
  const nB=(q.runs.no_verifier||[]).length,nC=(q.runs.with_verifier||[]).length;
  if(okB<nB||okC<nC)t.add("falla");
  const uB=count(q,"no_verifier",r=>r.unsup.length>0),uC=count(q,"with_verifier",r=>r.unsup.length>0);
  if(okB!==okC||uB!==uC)t.add("verif");
  if(okC<nC)t.add("cfalla");
  return t;
}
function picks(){
  const chosen=QS.filter(q=>tagsOf(q).has("verif")||tagsOf(q).has("cfalla"));
  const box=document.getElementById("picks");
  if(!chosen.length){box.innerHTML='<p class="missing">Nada para destacar.</p>';return}
  for(const q of chosen){
    const okB=count(q,"no_verifier",r=>r.ok),okC=count(q,"with_verifier",r=>r.ok);
    const uB=count(q,"no_verifier",r=>r.unsup.length>0);
    const why=okB!==okC?`Sin verificador pasa ${okB} veces; con verificador, ${okC}.`:okC<5?`DORA completo falla ${5-okC} de 5.`:`Sin verificador, ${uB} de 5 respuestas le muestran al productor números sin respaldo; con verificador, ninguna.`;
    box.append(card({...q,why}));
  }
}
const FILTERS=[["todas","Todas"],["falla","Alguna falla"],["verif","El verificador cambia algo"],...[...new Set(QS.map(q=>q.kind))].map(k=>["k:"+k,k])];
function renderAll(f){
  const box=document.getElementById("all");box.replaceChildren();
  const list=QS.filter(q=>f==="todas"||(f.startsWith("k:")?q.kind===f.slice(2):tagsOf(q).has(f)));
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
