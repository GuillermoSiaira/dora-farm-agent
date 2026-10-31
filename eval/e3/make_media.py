"""Build E3's synthetic media from cases.json: invoice images, aerial photos with known damage, and
stand-in voice notes read by the local Windows voice (until Guillermo's recordings arrive).

    python eval/e3/make_media.py            # invoices and aerial photos
    python eval/e3/make_media.py --tts      # also the stand-in voice notes (Windows only)

Every number comes from cases.json. The invoices say they are synthetic; the aerial photos are drawn
here, so the flooded pixels are known exactly (saved as a mask next to each photo).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
MEDIA = HERE / "media"


def _font(size: int, bold: bool = False):
    for name in (("arialbd.ttf" if bold else "arial.ttf"), "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _money(x: float, currency: str) -> str:
    """Argentine style: 21.000,00."""
    s = f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("$ " if currency == "ARS" else "USD ") + s


def invoice(case: dict) -> Image.Image:
    W, H = 1240, 1754
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    cur = case["currency"]
    d.rectangle([60, 60, W - 60, 300], outline="black", width=3)
    d.line([W // 2, 60, W // 2, 300], fill="black", width=2)
    size = 38
    while d.textlength(case["seller"], font=_font(size, True)) > W // 2 - 60 and size > 20:
        size -= 2
    d.text((90, 90), case["seller"], font=_font(size, True), fill="black")
    d.text((90, 150), "Ruta Provincial 0 km 0 - Localidad Ficticia (Bs. As.)", font=_font(22), fill="black")
    d.text((90, 190), "CUIT 30-00000000-0  ·  IVA Responsable Inscripto", font=_font(22), fill="black")
    d.text((W // 2 + 30, 90), case["title"], font=_font(52, True), fill="black")
    d.text((W // 2 + 30, 170), f"N.º {case['number']}", font=_font(30), fill="black")
    d.text((W // 2 + 30, 220), f"Fecha: {case['date']}", font=_font(30), fill="black")
    d.text((90, 340), "Cliente: Establecimiento de prueba (datos inventados)", font=_font(28), fill="black")
    d.text((90, 385), f"Condición de pago: {case['payment_terms']}", font=_font(28), fill="black")
    d.text((90, 430), f"Moneda: {'Pesos argentinos' if cur == 'ARS' else 'Dólares estadounidenses'}", font=_font(28), fill="black")

    y = 510
    cols = [90, 640, 790, 1000]
    d.rectangle([60, y, W - 60, y + 56], fill=(225, 225, 225), outline="black")
    for x, h in zip(cols[:3], ["Descripción", "Cantidad", "Precio unit."]):
        d.text((x, y + 12), h, font=_font(26, True), fill="black")
    d.text((W - 80, y + 12), "Importe", font=_font(26, True), fill="black", anchor="ra")
    y += 70
    net = 0.0
    for line in case["lines"]:
        amount = line["qty"] * line["unit_price"]
        net += amount
        qty = f"{line['qty']:,}".replace(",", ".") + f" {line['unit']}"
        d.text((cols[0], y), line["concept"], font=_font(26), fill="black")
        d.text((cols[1], y), qty, font=_font(26), fill="black")
        d.text((cols[2], y), _money(line["unit_price"], cur), font=_font(26), fill="black")
        d.text((W - 80, y), _money(amount, cur), font=_font(26), fill="black", anchor="ra")
        y += 56
    y = max(y + 40, 1000)
    vat = round(net * case["vat_rate"], 2)
    pct = f"{case['vat_rate'] * 100:.1f}".replace(".", ",").replace(",0", "")
    for label, value, bold in (("Subtotal neto", net, False), (f"IVA {pct} %", vat, False), ("TOTAL", net + vat, True)):
        d.text((640, y), label, font=_font(30, bold), fill="black")
        d.text((W - 80, y), _money(value, cur), font=_font(30, bold), fill="black", anchor="ra")
        y += 55
    d.rectangle([60, H - 170, W - 60, H - 90], outline=(150, 150, 150), width=2)
    d.text((90, H - 150), "DOCUMENTO SINTÉTICO PARA PRUEBAS DE DORA (E3). No es una factura real.",
           font=_font(24), fill=(110, 110, 110))
    return img


def photo_like(img: Image.Image, seed: int) -> Image.Image:
    """The invoice as a phone photo: on a desk, slightly turned, uneven light and some noise."""
    rng = np.random.default_rng(seed)
    page = img.resize((img.width * 3 // 4, img.height * 3 // 4)).rotate(-4, expand=True, fillcolor=(120, 96, 70))
    bg = Image.new("RGB", (page.width + 160, page.height + 160), (120, 96, 70))
    bg.paste(page, (80, 80))
    a = np.asarray(bg).astype(np.float64)
    yy, xx = np.mgrid[0:a.shape[0], 0:a.shape[1]]
    light = 0.80 + 0.25 * (xx / a.shape[1]) - 0.10 * (yy / a.shape[0])
    a = a * light[..., None] + rng.normal(0, 6, a.shape)
    return Image.fromarray(np.clip(a, 0, 255).astype("uint8")).filter(ImageFilter.GaussianBlur(0.8))


def _blob_field(shape, cx, cy, rng, wobble=0.35, k=6):
    """Distance to (cx, cy) divided by an irregular radius profile: the patch of radius r is field < r.

    The profile varies with the angle (a few random harmonics), so patches are not circles."""
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]]
    ang = np.arctan2(yy - cy, xx - cx)
    prof = np.ones(shape)
    for n in range(2, 2 + k):
        prof += wobble / n * np.cos(n * ang + rng.uniform(0, 2 * np.pi))
    return np.hypot(xx - cx, yy - cy) / prof


def aerial(case: dict, W: int = 1280, H: int = 960):
    """A vertical photo of a sown field with standing water. Returns the photo and the water mask."""
    rng = np.random.default_rng(case["seed"])
    yy, xx = np.mgrid[0:H, 0:W]
    # Two lots with crop rows at different angles; green with soil showing between rows.
    rows_a = 0.5 + 0.5 * np.sin((xx * np.cos(0.3) + yy * np.sin(0.3)) / 3.2)
    rows_b = 0.5 + 0.5 * np.sin((xx * np.cos(1.4) + yy * np.sin(1.4)) / 3.2)
    lot_b = xx + 0.25 * yy > W * 0.62
    rows = np.where(lot_b, rows_b, rows_a)
    green = np.array([78, 118, 52], float)
    soil = np.array([112, 92, 66], float)
    patchy = Image.fromarray((rng.random((H // 40, W // 40)) * 255).astype("uint8")).resize((W, H), Image.BICUBIC)
    vigor = 0.65 + 0.35 * np.asarray(patchy, float) / 255
    img = soil + (green - soil) * (rows * vigor)[..., None]
    # Lot boundary and a dirt track.
    edge = np.abs(xx + 0.25 * yy - W * 0.62) < 5
    img[edge] = [150, 132, 100]

    if case["layout"] == "one_patch":
        specs = [(W * 0.33, H * 0.55, 1.0)]
    elif case["layout"] == "two_patches":
        specs = [(W * 0.28, H * 0.35, 1.0), (W * 0.74, H * 0.68, 0.8)]
    else:
        specs = [(rng.uniform(80, W - 80), rng.uniform(80, H - 80), rng.uniform(0.6, 1.2)) for _ in range(14)]
    # Every patch grows with one common radius; pick the radius that covers the target share exactly.
    field = np.min([_blob_field((H, W), cx, cy, np.random.default_rng(case["seed"] * 100 + i)) / sc
                    for i, (cx, cy, sc) in enumerate(specs)], axis=0)
    mask = field < np.quantile(field, case["target_share"])
    # Mud ring around the water (not counted as water), then the water itself.
    ring = np.asarray(Image.fromarray((mask * 255).astype("uint8")).filter(ImageFilter.MaxFilter(15))) > 0
    img[ring & ~mask] = img[ring & ~mask] * 0.45 + np.array([96, 80, 58]) * 0.55
    sky = np.asarray(Image.fromarray((rng.random((H // 60, W // 60)) * 255).astype("uint8")).resize((W, H), Image.BICUBIC), float) / 255
    water = np.array([58, 72, 78], float) + (np.array([130, 150, 160], float) - [58, 72, 78]) * (0.25 + 0.35 * sky)[..., None]
    img[mask] = water[mask]
    img += rng.normal(0, 4, img.shape)
    photo = Image.fromarray(np.clip(img, 0, 255).astype("uint8")).filter(ImageFilter.GaussianBlur(0.6))
    return photo, mask


def tts(case: dict, out: Path) -> None:
    """The script read by the Windows Spanish voice, saved as 24 kHz mono 16-bit WAV."""
    text = case["script"].replace("'", "''")
    ps = ("Add-Type -AssemblyName System.Speech; "
          "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
          "$v = $s.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -like 'es-*' } | Select-Object -First 1; "
          "if ($v) { $s.SelectVoice($v.VoiceInfo.Name) }; "
          "$f = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(24000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono); "
          f"$s.SetOutputToWaveFile('{out}', $f); $s.Speak('{text}'); $s.Dispose()")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tts", action="store_true")
    args = ap.parse_args()
    cases = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
    (MEDIA / "invoices").mkdir(parents=True, exist_ok=True)
    (MEDIA / "aerial").mkdir(parents=True, exist_ok=True)
    truth = {"invoices": {}, "aerial": {}}
    for i, c in enumerate(cases["invoices"]):
        img = invoice(c)
        if c.get("photo_like"):
            img = photo_like(img, seed=i)
            img.save(MEDIA / "invoices" / f"{c['id']}.jpg", quality=85)
        else:
            img.save(MEDIA / "invoices" / f"{c['id']}.png")
        net = round(sum(l["qty"] * l["unit_price"] for l in c["lines"]), 2)
        truth["invoices"][c["id"]] = {"net": net, "vat": round(net * c["vat_rate"], 2),
                                      "total": round(net * (1 + c["vat_rate"]), 2), "currency": c["currency"],
                                      "lines": [round(l["qty"] * l["unit_price"], 2) for l in c["lines"]]}
    for c in cases["aerial"]:
        photo, mask = aerial(c)
        photo.save(MEDIA / "aerial" / f"{c['id']}.png")
        Image.fromarray((mask * 255).astype("uint8")).save(MEDIA / "aerial" / f"{c['id']}_mask.png")
        share = float(mask.mean())
        truth["aerial"][c["id"]] = {"share": round(share, 4),
                                    "damaged_ha": round(share * c["scenario"]["area_ha"], 2)}
    if args.tts:
        (MEDIA / "voice_tts").mkdir(parents=True, exist_ok=True)
        for c in cases["voice"]:
            tts(c, MEDIA / "voice_tts" / f"{c['id']}.wav")
    (MEDIA / "truth.json").write_text(json.dumps(truth, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(truth, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.exit(main())
