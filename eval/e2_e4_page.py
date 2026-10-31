"""Build a reading page for E2 and E4: the regional table, the agent's answers and the live-price runs.

Usage: python eval/e2_e4_page.py E2.json E4.json E4CURVE.json OUT.html
Same look as eval/answers_page.py (E1). Tool results are left out (E2's are 1.2 MB); tool calls stay.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

NAMES = {"southeast_buenos_aires": "Sudeste BA (Balcarce)", "pampas_core": "Zona núcleo (Pergamino)",
         "iowa": "Iowa (central)", "mato_grosso": "Mato Grosso (Sorriso)"}
CROPS = {"corn": "maíz", "soybean": "soja", "wheat": "trigo", "sunflower": "girasol"}
FLAGS = {"region_data": "región", "land": "tierra", "taxes": "impuestos", "price_curve": "curva", "routes": "rutas"}


def short_source(src: str) -> str:
    date = src.rsplit("as of ", 1)[-1] if "as of " in src else ""
    return ("MAGyP + CBOT" if "MAGyP" in src else "CBOT") + (f", {date}" if date else "")


def answer(a: dict) -> dict:
    calls = a.get("tool_calls", [])
    return {
        "text": a.get("text") or a.get("error") or "(sin respuesta)",
        "verified": a.get("verified"),
        "initial": a.get("initial_unsupported", []),
        "calls": [{"tool": c["tool"], "args": c["arguments"], "error": c.get("error")} for c in calls],
        "curve": any("price_curve_source" in c["arguments"] for c in calls),
        "prov": a.get("mentions_provisional"),
        "s": a.get("seconds"),
        "usd": a.get("cost_usd"),
    }


def main() -> None:
    e2 = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    e4 = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    e4c = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
    out = Path(sys.argv[4])

    regions = []
    farm = e2["compare_regions"]["same_farm|argentina_latest"]["result"]
    budget = e2["compare_regions"]["same_budget|region_default"]["result"]
    for key in farm["ranking"]:
        r, b = farm["regions"][key], budget["regions"][key]
        wl, fo = r["with_land_cost"], r["farming_only"]
        plan = ", ".join(f"{h:g} ha {CROPS.get(c, c)}" for c, h in (r.get("hectares") or {}).items())
        regions.append({
            "name": NAMES.get(key, key),
            "plan": plan or f"dar {wl['rent_out_ha']:g} ha en alquiler",
            "npv": r["npv_usd"], "margin": fo["profit_per_sown_ha"], "roc": fo["return_on_capital_annual_pct"],
            "rocl": wl["return_on_capital_and_land_annual_pct"], "rent": wl["regional_rent_usd_ha"],
            "land": wl["land_price_usd_ha"], "freight": r["freight_usd_t"], "fshare": r["freight_share_pct"],
            "price": short_source(r.get("price_source") or ""), "flags": [v for k, v in FLAGS.items() if r["placeholder_flags"].get(k)],
            "budget": b["npv_usd"],
        })
    live = e4["conditions"]["live"]["feeds"]
    data = {
        "regions": regions,
        "e2": [answer(a) for a in e2["answers"]],
        "e2q": e2["question"],
        "feeds": {
            "cbot": {"as_of": live["cbot"].get("as_of"), "n": sum(live["cbot"].get("contracts", {}).values()),
                     "s": live["cbot"]["seconds"],
                     "first": {c: sorted(v.items())[0] for c, v in live["cbot"].get("curve", {}).items()}},
            "magyp": {"date": live["magyp"].get("date"), "quotes": live["magyp"].get("quotes"), "s": live["magyp"]["seconds"]},
            "bcra": {"date": live["bcra"].get("date"), "rate": live["bcra"].get("ars_per_usd"), "s": live["bcra"]["seconds"]},
            "refresh": {k: c["refresh"]["status"] for k, c in e4["conditions"].items()},
        },
        "e4": [
            {"q": e4["question"], "live": [answer(a) for a in e4["conditions"]["live"]["answers"]],
             "blocked": [answer(a) for a in e4["conditions"]["all_blocked"]["answers"]]},
            {"q": e4c["question"], "live": [answer(a) for a in e4c["conditions"]["live"]["answers"]],
             "blocked": [answer(a) for a in e4c["conditions"]["all_blocked"]["answers"]]},
        ],
        "meta": {"commit": e2["commit"], "model": e2["model"],
                 "files": [Path(p).name for p in sys.argv[1:4]],
                 "usd": round(e2["cost_usd_agent_answers"] + e4["cost_usd_agent_answers"] + e4c["cost_usd_agent_answers"], 2)},
    }
    html = TEMPLATE.replace("/*DATA*/null", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size // 1024} KB)")


TEMPLATE = r"""<title>E2 y E4: regiones y precios</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600&family=Source+Sans+3:wght@400;600&family=JetBrains+Mono:wght@400;600&display=swap">
<style>
/* Layout: the E1 page's look. E2 table and answers, then E4 sources and answers (with network | source blocked), then the bugs found. */
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
.wrap{max-width:1280px;margin:0 auto;padding-block:28px 64px;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));display:grid;gap:32px}
h1,h2,h3{font-family:var(--display);font-weight:600;text-wrap:balance;margin:0}
h1{font-size:2rem} h2{font-size:1.45rem} h3{font-size:1.1rem}
p{margin:0;max-width:68ch}
.lead{color:var(--muted)}
section{display:grid;gap:14px}
.tbl{overflow-x:auto}
table{border-collapse:collapse;font-variant-numeric:tabular-nums;min-width:640px}
#reg{min-width:1100px}
th,td{padding:6px 12px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{font-size:.8rem;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);font-weight:600}
td.n{text-align:right;font-family:var(--mono);font-size:.9rem}
.flag{display:inline-block;font-size:.72rem;padding:0 6px;margin:1px 2px 1px 0;border-radius:3px;background:var(--warn-bg);color:var(--warn);font-weight:600}
.box{background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:16px;display:grid;gap:12px;min-width:0}
.qtext{font-size:1.05rem;font-weight:600}
.cols{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
@media (max-width:860px){.cols{grid-template-columns:minmax(0,1fr)}}
.col{border-top:3px solid var(--line);padding-top:8px;display:grid;gap:8px;align-content:start;min-width:0}
.col.live{border-top-color:var(--ok)} .col.blocked{border-top-color:var(--bad)}
.colname{font-weight:600}
.runs{display:flex;gap:4px;flex-wrap:wrap}
.run{width:30px;height:28px;border:1px solid var(--line);border-radius:4px;background:var(--surface);color:var(--fg);font:600 .8rem var(--mono);cursor:pointer}
.run.ok{background:var(--ok-bg);border-color:var(--ok)}
.run[aria-pressed="true"]{outline:2px solid var(--fg);outline-offset:1px}
button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.tags{display:flex;flex-wrap:wrap;gap:4px}
.tag{font-size:.75rem;padding:1px 8px;border-radius:3px;font-weight:600}
.t-ok{background:var(--ok-bg);color:var(--ok)} .t-bad{background:var(--bad-bg);color:var(--bad)} .t-warn{background:var(--warn-bg);color:var(--warn)} .t-mut{color:var(--muted)}
.calls{font-family:var(--mono);font-size:.78rem;color:var(--muted);overflow-wrap:anywhere;display:grid;gap:2px}
.reply{font-size:.92rem;line-height:1.45;max-height:30em;overflow:auto;border-left:2px solid var(--line);padding-left:10px;overflow-wrap:anywhere}
.reply p{margin:0 0 .5em} .reply ul{margin:0 0 .5em;padding-left:1.2em}
.reply code{font-family:var(--mono);font-size:.85em}
.bugs{display:grid;gap:10px;padding-left:1.2em;margin:0;max-width:80ch}
.foot{font-family:var(--mono);font-size:.8rem;color:var(--muted);overflow-wrap:anywhere}
</style>
<div class="wrap">
  <header style="display:grid;gap:8px">
    <h1>E2 y E4: las cuatro regiones y los precios en vivo</h1>
    <p class="lead">Muse Spark 1.3 Standard con DORA completo (herramientas y verificador), 31/10/2026. Los cuadraditos son las repeticiones: verde si la respuesta quedó verificada. Tocá uno para leerla. Los datos marcados como provisorios lo son: Balcarce, Mato Grosso, impuestos y rutas.</p>
  </header>

  <section>
    <h2>E2 · La foto de las cuatro regiones</h2>
    <p class="lead">Lo que da el motor solo (<code>compare_regions</code>), sin el modelo: 500 ha propias y 500.000 USD, misma finca, con los precios del día. La última columna es "misma plata": 500.000 USD sin tierra, con los precios por defecto de cada región.</p>
    <div class="tbl"><table id="reg"></table></div>
  </section>

  <section>
    <h2>E2 · El agente, 5 veces</h2>
    <div class="box" id="e2"></div>
  </section>

  <section>
    <h2>E4 · Las fuentes de precios</h2>
    <div class="tbl"><table id="feeds"></table></div>
    <p class="lead" id="refresh"></p>
  </section>

  <section>
    <h2>E4 · El agente, con red y con las fuentes bloqueadas</h2>
    <p class="lead">Dos preguntas, 3 veces cada una en cada condición. En la segunda, el productor pide la curva del día.</p>
    <div id="e4" style="display:grid;gap:16px"></div>
  </section>

  <section>
    <h2>Errores encontrados</h2>
    <p class="lead">Para arreglar después; no se tocaron en estas corridas. El detalle está en las fichas.</p>
    <ol class="bugs">
      <li><strong>"Misma plata" con la curva argentina</strong> les pone precios argentinos a Iowa y Mato Grosso (<code>compare_regions</code>, modo <code>same_budget</code>).</li>
      <li><strong>"Fresco" se mide por la fecha del archivo, no del precio</strong> (<code>feeds.refresh</code>): en un repo recién clonado, la copia del 27/10 parece de hoy.</li>
      <li><strong>La falla de una fuente no llega al agente:</strong> <code>refresh()</code> devuelve <code>kept_last</code> y las herramientas lo descartan. Ninguna respuesta pudo decir "dato guardado".</li>
      <li><strong>Si falla MAGyP, <code>refresh()</code> dice <code>updated</code> igual</strong> y la curva argentina queda vieja sin aviso.</li>
      <li><strong>La fuente de Pergamino dice "Southeast Buenos Aires"</strong> (<code>SOURCE_MAGYP</code>), aunque los números son los de la zona núcleo.</li>
      <li><strong>La marca de dato provisorio de la región no coincide:</strong> <code>compare_regions</code> no marca el núcleo; el observatorio sí.</li>
      <li><strong>El observatorio y <code>compare_regions</code> dan dos fotos distintas</strong> del mismo campo: alquiler de la tierra, flete de Iowa (12 contra 40 USD/t) y duración de la temporada.</li>
      <li><strong>El comentario del observatorio desde la línea de comandos usa el modelo "default"</strong> y queda vacío (por lectura del código).</li>
    </ol>
  </section>
  <p class="foot" id="foot"></p>
</div>
<script>
const D=/*DATA*/null;
const fmt=(v,d=2)=>v==null?"—":(typeof v==="number"?v.toLocaleString("es-AR",{maximumFractionDigits:d}):String(v));
const esc=s=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
function md(s){
  const lines=esc(s).replace(/\*\*(.+?)\*\*/g,"<strong>$1</strong>").replace(/`([^`]+)`/g,"<code>$1</code>").split(/\n/);
  let out="",inList=false;
  for(const l of lines){
    const m=l.match(/^\s*(?:[-*•]|\d+\.)\s+(.*)/);
    if(m){if(!inList){out+="<ul>";inList=true}out+="<li>"+m[1]+"</li>";continue}
    if(inList){out+="</ul>";inList=false}
    if(l.trim())out+="<p>"+l+"</p>";
  }
  return out+(inList?"</ul>":"");
}
function regions(){
  let h="<tr><th>Región</th><th>Plan óptimo</th><th>Valor actual (USD)</th><th>Margen por ha sembrada, sin tierra</th><th>Retorno anual, solo agricultura</th><th>Retorno anual, capital y tierra</th><th>Alquiler (USD/ha)</th><th>Tierra (USD/ha)</th><th>Flete (USD/t; % del ingreso)</th><th>Precios</th><th>Provisorio</th><th>Misma plata: valor actual</th></tr>";
  for(const r of D.regions)h+=`<tr><td>${esc(r.name)}</td><td>${esc(r.plan)}</td><td class="n">${fmt(r.npv,0)}</td><td class="n">${fmt(r.margin)}</td><td class="n">${fmt(r.roc,1)} %</td><td class="n">${fmt(r.rocl,1)} %</td><td class="n">${fmt(r.rent)}</td><td class="n">${fmt(r.land,0)}</td><td class="n">${fmt(r.freight)}; ${fmt(r.fshare,1)} %</td><td>${esc(r.price)}</td><td>${r.flags.map(f=>`<span class="flag">${f}</span>`).join("")}</td><td class="n">${fmt(r.budget,0)}</td></tr>`;
  document.getElementById("reg").innerHTML=h;
}
function runs(el,list,extra){
  const runsEl=document.createElement("div");runsEl.className="runs";
  const tags=document.createElement("div");tags.className="tags";
  const calls=document.createElement("div");calls.className="calls";
  const reply=document.createElement("div");reply.className="reply";
  el.append(runsEl,tags,calls,reply);
  const show=i=>{
    const a=list[i];
    runsEl.querySelectorAll(".run").forEach((b,j)=>b.setAttribute("aria-pressed",j===i));
    const t=[a.verified?'<span class="tag t-ok">verificada</span>':'<span class="tag t-bad">sin verificar</span>'];
    if(a.initial.length)t.push(`<span class="tag t-warn">primer borrador con números sin respaldo: ${esc(a.initial.join(", "))}</span>`);
    t.push(...extra(a));
    t.push(`<span class="tag t-mut">${Math.round(a.s)} s · ${fmt(a.usd,3)} USD</span>`);
    tags.innerHTML=t.join("");
    calls.innerHTML=a.calls.map(c=>`<span>→ ${esc(c.tool)}(${esc(c.args)})${c.error?" · error":""}</span>`).join("");
    reply.innerHTML=md(a.text);
  };
  list.forEach((a,i)=>{const b=document.createElement("button");b.className="run"+(a.verified?" ok":"");b.textContent=i+1;b.title=`Repetición ${i+1}`;b.onclick=()=>show(i);runsEl.append(b)});
  show(0);
}
function e2(){
  const box=document.getElementById("e2");
  box.innerHTML=`<div class="qtext">${esc(D.e2q)}</div><p class="lead">Sin datos del productor: el agente usó los supuestos del modelo (500 ha, 50.000 USD propios) y los precios del informe de junio.</p>`;
  runs(box,D.e2,a=>[a.prov?'<span class="tag t-ok">menciona datos provisorios</span>':'<span class="tag t-bad">no menciona provisorios</span>',a.curve?'<span class="tag t-ok">curva del día</span>':'<span class="tag t-mut">precios de junio</span>']);
}
function feeds(){
  const f=D.feeds,q=f.magyp.quotes||{};
  const cb=Object.entries(f.cbot.first||{}).map(([c,[m,p]])=>`${c} ${m}: ${fmt(p)} c/bu`).join(" · ");
  let h="<tr><th>Fuente</th><th>Qué trae</th><th>Fecha del dato</th><th>Tiempo</th><th>Con la fuente bloqueada</th></tr>";
  h+=`<tr><td>CBOT (Yahoo Finance, demorado)</td><td>${f.cbot.n} contratos; primero de cada cultivo: ${esc(cb)}</td><td>${f.cbot.as_of}</td><td class="n">${fmt(f.cbot.s,1)} s</td><td>0 contratos; queda la copia anterior</td></tr>`;
  h+=`<tr><td>MAGyP (FOB y FAS)</td><td>soja FOB ${fmt(q.soybean?.fob_usd_t)} USD/t · maíz FOB ${fmt(q.corn?.fob_usd_t)} · trigo FOB ${fmt(q.wheat?.fob_usd_t)} · girasol FOB ${fmt(q.sunflower?.fob_usd_t)}</td><td>${f.magyp.date}</td><td class="n">${fmt(f.magyp.s,1)} s</td><td>error de red</td></tr>`;
  h+=`<tr><td>BCRA (dólar mayorista, A 3500)</td><td>${fmt(f.bcra.rate)} ARS/USD</td><td>${f.bcra.date}</td><td class="n">${fmt(f.bcra.s,1)} s</td><td>error de red</td></tr>`;
  document.getElementById("feeds").innerHTML=h;
  const r=f.refresh;
  document.getElementById("refresh").textContent=`Lo que respondió refresh(): con red "${r.live}", todo bloqueado "${r.all_blocked}", solo MAGyP bloqueado "${r.magyp_blocked}" (dice "updated" aunque la curva argentina no se actualizó).`;
}
function e4(){
  const box=document.getElementById("e4");
  D.e4.forEach((p,k)=>{
    const el=document.createElement("article");el.className="box";
    el.innerHTML=`<div class="qtext">P${k+1}. ${esc(p.q)}</div>`;
    const cols=document.createElement("div");cols.className="cols";
    for(const [key,name] of [["live","Con red"],["blocked","Fuentes bloqueadas"]]){
      const col=document.createElement("div");col.className="col "+key;
      col.innerHTML=`<span class="colname">${name}</span>`;
      runs(col,p[key],a=>{
        const t=[a.curve?'<span class="tag t-ok">usó la curva del día</span>':'<span class="tag t-mut">precios de junio</span>'];
        if(key==="blocked")t.push('<span class="tag t-bad">no dice "dato guardado"</span>');
        return t;
      });
      cols.append(col);
    }
    el.append(cols);box.append(el);
  });
}
regions();e2();feeds();e4();
document.getElementById("foot").textContent=`Modelo ${D.meta.model} · commit ${D.meta.commit} · costo de las respuestas del agente ${fmt(D.meta.usd)} USD · eval/results/: ${D.meta.files.join(", ")}`;
</script>
"""

if __name__ == "__main__":
    main()
