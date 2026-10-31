"""Build a reading page for E3: each case with its media, what DORA read or heard, and the same
request typed, side by side. Same look as eval/answers_page.py (E1).

Usage: python eval/e3_page.py RESULTS.json [MORE.json ...] OUT.html
Later files add or replace parts (voice, invoices, aerial, sam_alone) of earlier ones.
"""
from __future__ import annotations

import base64
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from answers_page import TEMPLATE as E1  # noqa: E402

STYLE = E1[E1.index("<style>"):E1.index("</style>") + len("</style>")]
FONTS = E1[E1.index("<link"):E1.index("<style>")]


def _img(path: Path, width: int, mime="image/jpeg") -> str:
    from PIL import Image
    img = Image.open(path).convert("RGB")
    if img.width > width:
        img = img.resize((width, round(img.height * width / img.width)))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=80)
    return f"data:{mime};base64," + base64.b64encode(buf.getvalue()).decode()


def _audio(path: Path) -> str | None:
    """The voice note at 12 kHz mono, small enough to embed."""
    import wave

    import numpy as np
    from scipy.io import wavfile
    from scipy.signal import resample_poly
    try:
        rate, x = wavfile.read(str(path))
    except Exception:
        return None
    x = x.astype(float)
    if x.ndim > 1:
        x = x.mean(axis=1)
    g = np.gcd(int(rate), 12000)
    x = resample_poly(x, 12000 // g, int(rate) // g)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(12000)
        w.writeframes(np.clip(x, -32768, 32767).astype("<i2").tobytes())
    return "data:audio/wav;base64," + base64.b64encode(buf.getvalue()).decode()


def _run(r: dict | None) -> dict | None:
    if not r:
        return None
    calls = [{"tool": c["tool"], "error": c.get("error"), "args": c.get("arguments", "")[:600]} for c in r["calls"]]
    return {"answers": r["answers"], "verified": r["verified"], "confirmed": r["confirmed"],
            "unsupported": r["unsupported_first_draft"], "lat": r["latency_s"], "calls": calls}


def main() -> None:
    *inputs, out = sys.argv[1:]
    res: dict = {}
    for f in inputs:
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        for k, v in d.items():
            if k in ("voice", "invoices", "aerial", "sam_alone"):
                res[k] = v
            elif k not in res or k in ("llm_cost_usd",):
                res[k] = v if k != "llm_cost_usd" else res.get(k, 0) + v
    data = {"model": res.get("model"), "cost": res.get("llm_cost_usd"), "voice": [], "invoices": [], "aerial": []}
    for v in res.get("voice", []):
        data["voice"].append({**{k: v[k] for k in ("id", "script", "typed_text", "transcript", "formulation_voice",
                                                   "formulation_typed", "npv_voice", "npv_typed", "expected_npv_usd",
                                                   "npv_voice_eq_typed", "audio_source", "audio_seconds")},
                              "expected": v["expected_scenario"], "audio": _audio(ROOT / v["audio"]),
                              "media": _run(v["media_run"]), "typed": _run(v["typed_run"])})
    for v in res.get("invoices", []):
        data["invoices"].append({**{k: v.get(k) for k in ("id", "kind", "currency", "crop", "item", "covers_ha", "prompt",
                                                          "typed_text", "true_lines", "true_net", "true_total_with_vat",
                                                          "read_lines", "read_sum", "read_lines_exact", "read_sum_is_net",
                                                          "read_sum_is_total_with_vat", "fx_rate", "expected_usd_ha",
                                                          "loaded_usd_ha_photo", "loaded_usd_ha_typed", "loaded_photo_ok",
                                                          "loaded_typed_ok", "expected_npv_usd", "npv_photo", "npv_typed",
                                                          "npv_photo_eq_typed")},
                                 "img": _img(ROOT / v["image"], 900), "media": _run(v["media_run"]), "typed": _run(v["typed_run"])})
    sam = {s["id"]: s for s in res.get("sam_alone", [])}
    for v in res.get("aerial", []):
        ov = v.get("overlay")
        data["aerial"].append({**{k: v.get(k) for k in ("id", "prompt", "true_share", "true_damaged_ha", "measured_share",
                                                        "measured_ha", "ha_error", "reference_npv_after", "npv_after_photo",
                                                        "reference_npv_change", "npv_change_photo", "npv_photo_eq_reference")},
                               "area": v["scenario"]["area_ha"], "sam": sam.get(v["id"]),
                               "img": _img(ROOT / v["image"], 640),
                               "overlay": _img(Path(ov), 640) if ov and Path(ov).is_file() else None,
                               "media": _run(v["media_run"])})
    html = TEMPLATE.replace("/*FONTS*/", FONTS).replace("/*STYLE*/", STYLE).replace(
        "/*DATA*/null", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
    Path(out).write_text(html, encoding="utf-8")
    print(f"wrote {out} ({Path(out).stat().st_size // 1024} KB)")


TEMPLATE = r"""<title>E3 voz y fotos</title>
<meta name="claude:viewport-fit-sides" content="cover">
/*FONTS*/
/*STYLE*/
<style>
.media{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,2fr);gap:16px;align-items:start}
@media (max-width:900px){.media{grid-template-columns:minmax(0,1fr)}}
.media img{width:100%;height:auto;border:1px solid var(--line);border-radius:4px;display:block}
.pair{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
@media (max-width:700px){.pair{grid-template-columns:minmax(0,1fr)}}
.kv{display:grid;grid-template-columns:auto minmax(0,1fr);gap:2px 12px;font-size:.9rem}
.kv dt{color:var(--muted)} .kv dd{margin:0;font-family:var(--mono);font-size:.85rem;overflow-wrap:anywhere}
details{font-size:.85rem} summary{cursor:pointer;color:var(--muted)}
pre{white-space:pre-wrap;overflow-wrap:anywhere;font-family:var(--mono);font-size:.75rem;margin:4px 0}
audio{width:100%}
.quote{font-style:italic;border-left:2px solid var(--accent);padding-left:10px}
.tabs{display:flex;gap:8px;flex-wrap:wrap}
</style>
<div class="wrap">
  <header style="display:grid;gap:8px">
    <h1>E3: el productor habla o manda una foto</h1>
    <p class="lead" id="lead"></p>
  </header>
  <section style="display:grid;gap:12px"><h2>Resumen</h2><div class="tbl"><table id="sum"></table></div></section>
  <div class="tabs" id="tabs"></div>
  <div class="list" id="list"></div>
</div>
<script>
const D=/*DATA*/null;
const fmt=v=>v==null?"—":(typeof v==="number"?v.toLocaleString("es-AR",{maximumFractionDigits:2}):String(v));
const esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
function md(s){
  const lines=esc(s).replace(/\*\*(.+?)\*\*/g,"<strong>$1</strong>").split(/\n/);
  let out="",inList=false;
  for(const l of lines){const m=l.match(/^\s*[-*•]\s+(.*)/);
    if(m){if(!inList){out+="<ul>";inList=true}out+="<li>"+m[1]+"</li>";continue}
    if(inList){out+="</ul>";inList=false}
    if(l.trim())out+="<p>"+l+"</p>";}
  return out+(inList?"</ul>":"");
}
const tag=(ok,yes,no)=>ok==null?`<span class="tag" style="color:var(--muted)">${no||"—"}</span>`:ok?`<span class="tag t-ok">${yes}</span>`:`<span class="tag t-bad">${no}</span>`;
const n=(arr,f)=>arr.filter(f).length;
document.getElementById("lead").textContent=`${D.model}, con verificador. Cada caso corre dos veces: con la nota de voz o la foto, y con lo mismo escrito. Todos los campos, facturas y fotos son inventados. Costo del modelo de lenguaje en esta corrida: ${fmt(D.cost)} USD.`;
function summary(){
  const V=D.voice,I=D.invoices,A=D.aerial;
  const rows=[];
  if(V.length){rows.push(["Voz: escenario armado igual al esperado",`${n(V,v=>v.formulation_voice)}/${V.length}`,`${n(V,v=>v.formulation_typed)}/${V.length}`]);
    rows.push(["Voz: mismo valor presente que escrito","",`${n(V,v=>v.npv_voice_eq_typed)}/${V.length}`]);}
  if(I.length){rows.push(["Factura: importes leídos exactos",`${n(I,v=>v.read_lines_exact)}/${I.length}`,""]);
    rows.push(["Factura: costo por ha cargado correcto",`${n(I,v=>v.loaded_photo_ok)}/${I.length}`,`${n(I,v=>v.loaded_typed_ok)}/${I.length}`]);
    rows.push(["Factura: mismo valor presente que escrito","",`${n(I,v=>v.npv_photo_eq_typed)}/${I.length}`]);}
  if(A.length){rows.push(["Foto aérea: hectáreas medidas (error)",A.map(a=>`${a.id}: ${fmt(a.measured_ha)} vs ${fmt(a.true_damaged_ha)}`).join(" · "),""]);
    rows.push(["Foto aérea: mismo resultado que con la máscara verdadera","",`${n(A,a=>a.npv_photo_eq_reference)}/${A.length}`]);}
  document.getElementById("sum").innerHTML="<tr><th></th><th>Con voz o foto</th><th>Escrito / comparación</th></tr>"+rows.map(r=>`<tr><td>${r[0]}</td><td>${r[1]}</td><td>${r[2]}</td></tr>`).join("");
}
function runBox(title,r){
  if(!r)return `<div class="col"><div class="missing">Sin corrida.</div></div>`;
  const t=[tag(r.verified,"verificada","no verificada")];
  if(r.confirmed)t.push('<span class="tag t-warn">pidió confirmar</span>');
  t.push(`<span class="tag" style="color:var(--muted)">${Math.round(r.lat)} s</span>`);
  return `<div class="col"><div class="colhead"><span class="colname">${title}</span></div><div class="tags">${t.join("")}</div>
   ${r.unsupported.length?`<div class="unsup">Sin respaldo en el primer borrador: ${esc(r.unsupported.join(", "))}</div>`:""}
   <div class="reply">${r.answers.map(md).join("<hr>")}</div>
   <details><summary>Herramientas (${r.calls.length})</summary>${r.calls.map(c=>`<pre>${esc(c.tool)}${c.error?" (error)":""} ${esc(c.args)}</pre>`).join("")}</details></div>`;
}
function voiceCard(v){
  const el=document.createElement("article");el.className="q";
  el.innerHTML=`<div class="qhead"><span class="qid">${v.id}</span><span class="qtext">Nota de voz</span><span class="exp">valor presente exacto: ${fmt(v.expected_npv_usd)}</span></div>
  <div class="media"><div style="display:grid;gap:8px">${v.audio?`<audio controls src="${v.audio}"></audio>`:""}
    <div class="vals">${v.audio_source==="windows_tts_sabina_es-MX"?"Voz sintética de Windows (Sabina, es-MX), mientras llegan las grabaciones":"Grabada por Guillermo"} · ${fmt(v.audio_seconds)} s</div></div>
   <dl class="kv"><dt>Guion</dt><dd>${esc(v.script)}</dd><dt>Lo que oyó</dt><dd class="quote">${esc(v.transcript)}</dd>
    <dt>Esperado</dt><dd>${esc(JSON.stringify(v.expected))}</dd>
    <dt>Valor presente</dt><dd>voz ${fmt(v.npv_voice)} · escrito ${fmt(v.npv_typed)}</dd></dl></div>
  <div class="tags">${tag(v.formulation_voice,"escenario correcto (voz)","escenario distinto (voz)")}${tag(v.formulation_typed,"escenario correcto (escrito)","escenario distinto (escrito)")}${tag(v.npv_voice_eq_typed,"mismo resultado","resultado distinto")}</div>
  <div class="pair">${runBox("Con la nota de voz",v.media)}${runBox("Escrito: "+esc(v.typed_text),v.typed)}</div>`;
  return el;
}
function invCard(v){
  const el=document.createElement("article");el.className="q";
  const cur=v.currency==="ARS"?"$":"USD";
  el.innerHTML=`<div class="qhead"><span class="qid">${v.id}</span><span class="qtext">${esc(v.prompt)}</span></div>
  <div class="media"><a href="${v.img}" target="_blank" rel="noopener"><img src="${v.img}" alt="Factura sintética ${v.id}"></a>
   <dl class="kv"><dt>Renglones verdaderos</dt><dd>${v.true_lines.map(x=>cur+" "+fmt(x)).join(" + ")} = neto ${fmt(v.true_net)} (con IVA ${fmt(v.true_total_with_vat)})</dd>
    <dt>Lo que leyó</dt><dd>${v.read_lines.length?v.read_lines.map(l=>esc(l.concept)+": "+fmt(l.amount)+" "+esc(l.currency||"")).join("<br>"):"no llamó a record_document"}</dd>
    ${v.fx_rate?`<dt>Dólar BCRA</dt><dd>${fmt(v.fx_rate)}</dd>`:""}
    <dt>Costo esperado</dt><dd>${esc(v.crop)}.${esc(v.item)} = ${fmt(v.expected_usd_ha)} USD/ha</dd>
    <dt>Cargó</dt><dd>foto ${fmt(v.loaded_usd_ha_photo)} · escrito ${fmt(v.loaded_usd_ha_typed)}</dd>
    <dt>Valor presente</dt><dd>foto ${fmt(v.npv_photo)} · escrito ${fmt(v.npv_typed)} · exacto ${fmt(v.expected_npv_usd)}</dd></dl></div>
  <div class="tags">${tag(v.read_lines_exact,"importes exactos","importes distintos")}${v.read_sum_is_total_with_vat?'<span class="tag t-warn">tomó el total con IVA</span>':""}${tag(v.loaded_photo_ok,"costo bien cargado (foto)","costo mal cargado (foto)")}${tag(v.npv_photo_eq_typed,"mismo resultado que escrito","resultado distinto")}</div>
  <div class="pair">${runBox("Con la foto",v.media)}${runBox("Escrito: "+esc(v.typed_text),v.typed)}</div>`;
  return el;
}
function aerCard(v){
  const el=document.createElement("article");el.className="q";
  el.innerHTML=`<div class="qhead"><span class="qid">${v.id}</span><span class="qtext">${esc(v.prompt)}</span></div>
  <div class="pair"><figure style="margin:0"><img src="${v.img}" alt="Foto aérea sintética ${v.id}"><figcaption class="vals">Foto sintética: el agua está dibujada, así que se sabe cuánta hay.</figcaption></figure>
   <figure style="margin:0">${v.overlay?`<img src="${v.overlay}" alt="Lo que marcó SAM en ${v.id}">`:'<div class="missing">Sin imagen de SAM</div>'}<figcaption class="vals">En rojo, lo que marcó SAM 3.1.</figcaption></figure></div>
  <dl class="kv"><dt>Agua verdadera</dt><dd>${fmt(v.true_share*100)} % · ${fmt(v.true_damaged_ha)} ha de ${fmt(v.area)}</dd>
   <dt>SAM midió</dt><dd>${v.measured_share==null?"—":fmt(v.measured_share*100)+" % · "+fmt(v.measured_ha)+" ha"}${v.sam&&v.sam.iou!=null?" · coincidencia con el agua dibujada (IoU) "+fmt(v.sam.iou):""}</dd>
   <dt>Valor presente después</dt><dd>con SAM ${fmt(v.npv_after_photo)} · con el agua verdadera ${fmt(v.reference_npv_after)}</dd></dl>
  <div class="tags">${tag(v.npv_photo_eq_reference,"mismo resultado que con el agua verdadera","resultado distinto")}</div>
  <div class="pair">${runBox("DORA con la foto",v.media)}<div></div></div>`;
  return el;
}
const TABS=[["voice","Voz",voiceCard],["invoices","Facturas",invCard],["aerial","Fotos aéreas",aerCard]];
function show(k){
  const box=document.getElementById("list");box.replaceChildren();
  const [, ,f]=TABS.find(t=>t[0]===k);
  if(!D[k].length){box.innerHTML='<p class="missing">Todavía sin resultados.</p>';return}
  D[k].forEach(v=>box.append(f(v)));
  document.querySelectorAll("#tabs .chip").forEach(b=>b.setAttribute("aria-pressed",b.dataset.k===k));
}
TABS.forEach(([k,lab])=>{const b=document.createElement("button");b.className="chip";b.dataset.k=k;b.textContent=`${lab} (${D[k].length})`;b.onclick=()=>show(k);document.getElementById("tabs").append(b)});
summary();show(D.voice.length?"voice":D.invoices.length?"invoices":"aerial");
</script>
"""

if __name__ == "__main__":
    main()
