"""Record the DORA demo video takes with Playwright, as sharp JPEG frames.

Each take opens the public app (or the README on GitHub) in Chromium, plays one part
of docs/guion-video.md and saves:
  out/<take>_<stamp>/frames/*.jpg   frames from the Chrome screencast (1920x1080)
  out/<take>_<stamp>/frames.json    each frame's timestamp
  out/<take>_<stamp>/markers.json   what happened when (same clock), incl. DORA's replies
infra/video/edit.py turns the takes into the final video.

Takes:
  chat_es   Spanish, Muse Spark 1.3: empty chat, the interview, invoice photo, voice note
  chat_en   English, Muse Spark Open (Baseten): farm or rent out, break-even price
  scenario  Escenario tab: start date today, plan, rent comparison, cash chart, taxes
  regions   Regional Observatory map (English), hover over the routes
  readme    README on GitHub: how it works, E1 table, E8 chart

Usage (repo root):
  .venv/Scripts/python.exe infra/video/record.py chat_es chat_en
  .venv/Scripts/python.exe infra/video/record.py scenario regions readme --headed
Only the chat takes call the models (cents per take). Retakes are reruns.
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "out"
APP_URL = "https://guillermosiaira--dora-web.us-east.modal.run"
README_URL = "https://github.com/GuillermoSiaira/dora-farm-agent"

INVOICE = ROOT / "docs/video/media/factura.png"
VOICE = ROOT / "docs/video/media/nota-de-voz.wav"

# CSS viewport x device scale = 1920 x 1080 frames.
VIEW = {"width": 1440, "height": 810}
SCALE = 4 / 3

ES_FIRST = ("Tengo 500 ha en Balcarce y 50.000 USD de capital. "
            "¿Qué me conviene sembrar? Preguntame lo que necesites.")
ES_INVOICE = "¿Cómo cambia el plan con estos costos?"
ES_ANSWERS = [
    # Order matters: the invoice question mentions crops and hectares.
    (r"cultivo|hect[áa]reas|cubre|rengl|rubro", "Es todo el fertilizante del trigo, para 150 ha."),
    (r"alquil|arrend|propi|due[ñn]", "Es propio, pero lo quiero sembrar yo."),
    (r"banco|cr[ée]dito|prest|financ|l[íi]nea", "El banco me presta hasta 30000 USD."),
    (r"contado|pag[aáo]|proveedor|plazo|insumo", "Pago al contado."),
]
ES_DONT_KNOW = "No sé, usá lo que suponés."

EN_FIRST = ("I have 500 ha in Pergamino and 100,000 USD. "
            "Should I farm it or rent it out? Ask me what you need.")
EN_FOLLOW_UP = "At what price would corn be worth sowing?"
EN_ANSWERS = [
    (r"own|rent|lease", "The land is mine."),
    (r"bank|credit|lend|loan|borrow", "The bank lends me up to 50,000 USD."),
    (r"cash|pay|supplier|days|input", "I pay cash."),
]
EN_DONT_KNOW = "I don't know, use your assumption."

MAX_TURNS = 5
TYPE_DELAY_MS = 32
ANSWER_TIMEOUT_MS = 300_000

CURSOR_JS = """
window.addEventListener('DOMContentLoaded', () => {
  const d = document.createElement('div');
  d.id = '__pw_cursor';
  Object.assign(d.style, {position: 'fixed', zIndex: 2147483647, pointerEvents: 'none',
    width: '20px', height: '20px', borderRadius: '50%', marginLeft: '-10px', marginTop: '-10px',
    background: 'rgba(255,196,0,.55)', border: '2px solid rgba(0,0,0,.55)', left: '-50px', top: '-50px',
    transition: 'transform .12s'});
  document.body.appendChild(d);
  document.addEventListener('mousemove', e => { d.style.left = e.clientX + 'px'; d.style.top = e.clientY + 'px'; }, true);
  document.addEventListener('mousedown', () => d.style.transform = 'scale(.7)', true);
  document.addEventListener('mouseup', () => d.style.transform = 'scale(1)', true);
});
"""


class Screencast:
    """Chrome's screencast: one JPEG per painted frame, with its timestamp."""

    def __init__(self, page: Page, folder: Path):
        self.dir = folder / "frames"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.frames: list[dict] = []
        self.cdp = page.context.new_cdp_session(page)
        self.cdp.on("Page.screencastFrame", self._on_frame)

    def _on_frame(self, params: dict) -> None:
        name = f"{len(self.frames):06d}.jpg"
        (self.dir / name).write_bytes(base64.b64decode(params["data"]))
        self.frames.append({"t": params["metadata"]["timestamp"], "file": name})
        try:
            self.cdp.send("Page.screencastFrameAck", {"sessionId": params["sessionId"]})
        except Exception:
            pass

    def start(self) -> None:
        self.cdp.send("Page.startScreencast", {
            "format": "jpeg", "quality": 92,
            "maxWidth": round(VIEW["width"] * SCALE), "maxHeight": round(VIEW["height"] * SCALE),
            "everyNthFrame": 1,
        })

    def stop(self) -> None:
        try:
            self.cdp.send("Page.stopScreencast")
        except Exception:
            pass


class Markers:
    def __init__(self, take: str):
        self.take = take
        self.items: list[dict] = []

    def __call__(self, scene, event: str, text: str = "") -> None:
        self.items.append({"t": time.time(), "scene": scene, "event": event, "text": text})
        short = text.replace("\n", " ")[:110]
        print(f"[{self.take} {time.strftime('%H:%M:%S')}] {scene}: {event} {short}", flush=True)


def hold(page: Page, seconds: float) -> None:
    page.wait_for_timeout(int(seconds * 1000))


def glide(page: Page, x: float, y: float, steps: int = 25) -> None:
    page.mouse.move(x, y, steps=steps)


def click_visibly(page: Page, locator) -> None:
    locator.scroll_into_view_if_needed()
    box = locator.bounding_box()
    if box:
        glide(page, box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        hold(page, 0.25)
    locator.click()


def scroll_to(page: Page, locator, block: str = "center") -> None:
    locator.evaluate("(e, block) => e.scrollIntoView({behavior: 'smooth', block})", block)
    hold(page, 1.2)


def open_tab(page: Page, name: str) -> None:
    click_visibly(page, page.get_by_role("tab", name=name).first)
    hold(page, 1.2)


# ----------------------------------------------------------------------------
# Chat
# ----------------------------------------------------------------------------

def bot_texts(page: Page) -> list[str]:
    return page.locator("[data-testid=bot]").all_inner_texts()


def wait_answer(page: Page, before: int) -> str:
    state = page.wait_for_function(
        """(n) => {
             const err = [...document.querySelectorAll('span, div')].some(
               e => e.childElementCount === 0 && e.innerText === 'Error' && e.offsetParent);
             if (err) return 'error';
             const b = document.querySelectorAll('[data-testid=bot]');
             return b.length > n && !b[b.length - 1].innerText.includes('⏳') ? 'ok' : false; }""",
        arg=before, timeout=ANSWER_TIMEOUT_MS, polling=500,
    ).json_value()
    if state == "error":
        raise RuntimeError("the app showed 'Error' (server dropped the request); rerun the take")
    hold(page, 1.0)
    return bot_texts(page)[-1]


def send(page: Page, mark: Markers, scene, text: str) -> str:
    before = len(bot_texts(page))
    if text:
        box = page.locator("textarea").first
        click_visibly(page, box)
        mark(scene, "typing", text)
        box.press_sequentially(text, delay=TYPE_DELAY_MS)
    hold(page, 0.5)
    click_visibly(page, page.get_by_role("button", name=re.compile(r"^(Enviar|Send)$")))
    mark(scene, "sent")
    reply = wait_answer(page, before)
    mark(scene, "answer", reply)
    return reply


def answer_questions(page, mark, scene, reply, answers, dont_know, used) -> str:
    turns = 0
    while reply and "?" in reply and turns < MAX_TURNS:
        hold(page, 2.5)
        # Match only the sentences that ask something, not the whole reply.
        q = " ".join(x for x in re.split(r"(?<=[.?!])\s+|\n", reply) if "?" in x).lower()
        text = dont_know
        for i, (pattern, answer) in enumerate(answers):
            if i not in used and re.search(pattern, q):
                used.add(i)
                text = answer
                break
        reply = send(page, mark, scene, text)
        turns += 1
    mark(scene, "questions answered", str(turns))
    return reply


def wait_uploads(page: Page) -> None:
    page.wait_for_function("() => !document.body.innerText.includes('Uploading')",
                           timeout=120_000, polling=300)


def open_attachments(page: Page) -> None:
    if page.locator("input[type=file][accept*=image]").count() == 0:
        click_visibly(page, page.get_by_text(re.compile("Adjuntar fotos|Attach photos")).first)
        hold(page, 0.8)


def show_last_answer(page: Page) -> None:
    """Scroll the chat so the start of DORA's last reply is at the top."""
    page.locator("[data-testid=bot]").last.evaluate(
        "e => e.scrollIntoView({behavior: 'smooth', block: 'start'})")


def take_chat_es(page: Page, mark: Markers) -> None:
    used: set[int] = set()
    open_tab(page, "Chat")
    mark("es", "empty chat")
    glide(page, 700, 320, steps=40)
    hold(page, 4)

    reply = send(page, mark, "es", ES_FIRST)
    reply = answer_questions(page, mark, "es", reply, ES_ANSWERS, ES_DONT_KNOW, used)
    show_last_answer(page)
    mark("es", "plan")
    hold(page, 6)

    open_attachments(page)
    page.locator("input[type=file][accept*=image]").first.set_input_files(str(INVOICE))
    wait_uploads(page)
    mark("invoice", "invoice attached", INVOICE.name)
    hold(page, 1.5)
    reply = send(page, mark, "invoice", ES_INVOICE)
    reply = answer_questions(page, mark, "invoice", reply, ES_ANSWERS, ES_DONT_KNOW, used)
    show_last_answer(page)
    mark("invoice", "result")
    hold(page, 5)

    open_attachments(page)
    click_visibly(page, page.get_by_role("button", name="Upload file").first)
    hold(page, 0.4)
    page.locator("input[type=file]:not([accept*=image])").first.set_input_files(str(VOICE))
    wait_uploads(page)
    mark("voice", "voice attached", VOICE.name)
    hold(page, 2)
    reply = send(page, mark, "voice", "")
    show_last_answer(page)
    mark("voice", "result")
    hold(page, 5)


def take_chat_en(page: Page, mark: Markers) -> None:
    used: set[int] = set()
    click_visibly(page, page.get_by_label("English"))
    hold(page, 2)
    open_tab(page, "Chat")
    mark("en", "english")
    click_visibly(page, page.get_by_label(re.compile("Muse Spark Open")))
    hold(page, 2.5)
    mark("en", "open model")
    reply = send(page, mark, "en", EN_FIRST)
    reply = answer_questions(page, mark, "en", reply, EN_ANSWERS, EN_DONT_KNOW, used)
    show_last_answer(page)
    mark("en", "plan")
    hold(page, 6)
    send(page, mark, "breakeven", EN_FOLLOW_UP)
    show_last_answer(page)
    mark("breakeven", "result")
    hold(page, 6)


# ----------------------------------------------------------------------------
# Other takes
# ----------------------------------------------------------------------------

def take_scenario(page: Page, mark: Markers) -> None:
    open_tab(page, "Escenario")
    mark("scenario", "tab")
    date_box = page.get_by_label(re.compile("Arranca el"))
    if date_box.count():
        click_visibly(page, date_box.first)
        date_box.first.fill("")
        date_box.first.press_sequentially(dt.date.today().strftime("%d/%m/%Y"), delay=60)
        mark("scenario", "start date")
        hold(page, 1)
    click_visibly(page, page.get_by_role("button", name="Calcular Plan Óptimo"))
    mark("scenario", "computing")
    page.get_by_text("Valor Presente Neto").first.wait_for(timeout=120_000)
    hold(page, 2)
    for label, text in [
        ("npv", "Valor Presente Neto"),
        ("rent", "Si alquilaras"),
        ("cash", "¿Cuánto rinde un dólar extra"),
        ("debt", "¿Cómo evolucionan la caja"),
        ("taxes", "Desglose Impositivo"),
    ]:
        loc = page.get_by_text(text).first
        if loc.count() == 0:
            continue
        scroll_to(page, loc, "start" if label in ("npv", "taxes") else "center")
        glide(page, 760, 420, steps=20)
        mark("scenario", label)
        hold(page, 4.5)


def take_regions(page: Page, mark: Markers) -> None:
    click_visibly(page, page.get_by_label("English"))
    hold(page, 2)
    open_tab(page, "Regional Observatory")
    page.locator("#observatory-map path.leaflet-interactive").first.wait_for(timeout=120_000)
    scroll_to(page, page.locator("#observatory-map"))
    mark("regions", "map")
    hold(page, 3)
    boxes = [b for b in (p.bounding_box() for p in page.locator("#observatory-map path.leaflet-interactive").all()) if b]
    boxes.sort(key=lambda b: b["width"] + b["height"], reverse=True)
    for i, box in enumerate(boxes[:3]):
        x0, y0 = box["x"], box["y"]
        glide(page, x0 + box["width"] * 0.25, y0 + box["height"] * 0.25)
        for f in (0.35, 0.5, 0.65):
            glide(page, x0 + box["width"] * f, y0 + box["height"] * f, steps=8)
            hold(page, 0.35)
        mark("regions", "route", str(i))
        hold(page, 2.2)
    glide(page, 300, 200)
    hold(page, 1.5)


def take_readme(page: Page, mark: Markers) -> None:
    page.goto(README_URL, wait_until="domcontentloaded")
    page.locator("article.markdown-body").first.wait_for(timeout=60_000)
    page.locator("article.markdown-body").first.evaluate("e => e.style.zoom = '1.3'")
    hold(page, 1)
    for label, selector, block in [
        ("how", "article.markdown-body h2:has-text('How it works')", "start"),
        ("e1", "article.markdown-body table >> nth=0", "center"),
        ("final", "article.markdown-body table >> nth=1", "center"),
        ("e8", "article.markdown-body img[alt*='Four Meta models']", "center"),
    ]:
        loc = page.locator(selector).first
        loc.wait_for(timeout=30_000)
        scroll_to(page, loc, block)
        mark("readme", label)
        hold(page, 6)


TAKES = {
    "chat_es": take_chat_es,
    "chat_en": take_chat_en,
    "scenario": take_scenario,
    "regions": take_regions,
    "readme": take_readme,
}


def run(take: str, headed: bool) -> Path:
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    folder = OUT / f"{take}_{stamp}"
    folder.mkdir(parents=True, exist_ok=True)
    mark = Markers(take)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        if take != "readme":
            print("Waking the app...", flush=True)
            w = browser.new_page()
            w.goto(APP_URL, timeout=240_000)
            w.get_by_role("tab", name="Chat").first.wait_for(timeout=240_000)
            w.close()
        ctx = browser.new_context(viewport=VIEW, device_scale_factor=SCALE,
                                  locale="es-AR", color_scheme="light")
        ctx.add_init_script(CURSOR_JS)
        page = ctx.new_page()
        cast = Screencast(page, folder)
        cast.start()
        ok = True
        try:
            if take != "readme":
                page.goto(APP_URL, timeout=240_000)
                page.get_by_role("tab", name="Chat").first.wait_for(timeout=240_000)
                hold(page, 1.5)
            mark("start", "loaded")
            TAKES[take](page, mark)
            hold(page, 1)
            mark("end", "done")
        except Exception as exc:
            ok = False
            mark("error", type(exc).__name__, str(exc))
        finally:
            cast.stop()
            hold(page, 0.3)
            ctx.close()
            browser.close()
    (folder / "frames.json").write_text(json.dumps(cast.frames), encoding="utf-8")
    (folder / "markers.json").write_text(json.dumps(
        {"take": take, "ok": ok, "url": README_URL if take == "readme" else APP_URL,
         "markers": mark.items}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{'OK' if ok else 'FAILED'}: {folder.relative_to(ROOT)} ({len(cast.frames)} frames)", flush=True)
    return folder


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("takes", nargs="+", choices=list(TAKES))
    ap.add_argument("--headed", action="store_true")
    args = ap.parse_args()
    for take in args.takes:
        run(take, args.headed)


if __name__ == "__main__":
    main()
