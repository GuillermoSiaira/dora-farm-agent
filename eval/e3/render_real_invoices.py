"""Render real-price test invoices for SPEC-34 (E3).

Draws the 5 real-price invoices into eval/e3/media/real_invoices/:
- r1.png: Balcarce wheat fertilizer (Factura A, USD)
- r2.png: Pergamino soybean seed + glyphosate (Factura A, ARS)
- r3.png: Pergamino maize herbicide (Factura A, USD)
- r4.png: Iowa corn anhydrous ammonia + seed corn (US Co-op invoice, USD, Ag exempt)
- r5.png: Iowa soybean herbicide (US Co-op invoice, USD, Ag exempt)

Visibly fake seller and customer data. Includes CAE for Factura A, ticket numbers for US Co-op,
and disclaimer: 'Factura de prueba — precios reales, ver fuentes' / 'Test invoice — real prices, see sources'.
"""
from __future__ import annotations

import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
MEDIA_DIR = HERE / "media" / "real_invoices"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)


def _font(size: int, bold: bool = False):
    for name in (("arialbd.ttf" if bold else "arial.ttf"), "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _money_ar(val: float, currency: str) -> str:
    s = f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("$ " if currency == "ARS" else "USD ") + s


def _money_us(val: float) -> str:
    return f"${val:,.2f}"


def draw_factura_a(case: dict) -> Image.Image:
    W, H = 1240, 1754
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    cur = case["currency"]

    # Header border
    d.rectangle([60, 60, W - 60, 320], outline="black", width=3)
    d.line([W // 2, 130, W // 2, 320], fill="black", width=2)

    # Box for letter 'A'
    d.rectangle([W // 2 - 35, 60, W // 2 + 35, 130], fill="white", outline="black", width=3)
    d.text((W // 2, 65), "A", font=_font(44, True), fill="black", anchor="ma")
    d.text((W // 2, 112), "COD. 01", font=_font(14, True), fill="black", anchor="ma")

    # Left header: Seller details
    d.text((80, 85), case["seller"], font=_font(30, True), fill="black")
    d.text((80, 140), "Razón Social: " + case["seller"], font=_font(20), fill="black")
    if case["region"] == "southeast_buenos_aires":
        d.text((80, 175), "Domicilio: Ruta Nac. 226 km 64 - Balcarce (Bs. As.)", font=_font(20), fill="black")
    else:
        d.text((80, 175), "Domicilio: Av. de Mayo 850 - Pergamino (Bs. As.)", font=_font(20), fill="black")
    d.text((80, 210), f"CUIT: {case['cuit_seller']}", font=_font(20, True), fill="black")
    d.text((80, 245), "Condición frente al IVA: IVA Responsable Inscripto", font=_font(20), fill="black")
    d.text((80, 280), "Inicio de Actividades: 01/04/2012", font=_font(20), fill="black")

    # Right header: Factura details
    d.text((W // 2 + 40, 85), "FACTURA", font=_font(36, True), fill="black")
    d.text((W // 2 + 40, 140), f"Punto de Venta: {case['number'].split('-')[0]}  Comp. Nro: {case['number'].split('-')[1]}", font=_font(22, True), fill="black")
    d.text((W // 2 + 40, 180), f"Fecha de Emisión: {case['date']}", font=_font(22, True), fill="black")
    d.text((W // 2 + 40, 220), f"CUIT: {case['cuit_seller']}", font=_font(20), fill="black")
    d.text((W // 2 + 40, 255), "Ingresos Brutos: 30-00000000-0 (Convenio Multilateral)", font=_font(18), fill="black")
    d.text((W // 2 + 40, 285), f"Fecha de Vto. para el pago: {case['date']}", font=_font(18), fill="black")

    # Buyer box
    d.rectangle([60, 335, W - 60, 465], outline="black", width=2)
    d.text((80, 348), f"CUIT: {case['cuit_buyer']}", font=_font(22, True), fill="black")
    d.text((500, 348), "Apellido y Nombre / Razón Social: CAMPO EJEMPLO PRODUCTOR", font=_font(22, True), fill="black")
    d.text((80, 385), "Condición frente al IVA: IVA Responsable Inscripto", font=_font(20), fill="black")
    d.text((700, 385), "Domicilio Comercial: Zona Rural s/n", font=_font(20), fill="black")
    d.text((80, 425), f"Condición de Venta: {case['payment_terms']}", font=_font(20, True), fill="black")
    cur_label = "Pesos Argentinos (ARS)" if cur == "ARS" else "Dólares Estadounidenses (USD)"
    d.text((500, 425), f"Moneda: {cur_label}", font=_font(20, True), fill="black")

    # Items table header
    y = 485
    d.rectangle([60, y, W - 60, y + 50], fill=(225, 230, 235), outline="black", width=2)
    d.text((80, y + 12), "Descripción", font=_font(22, True), fill="black")
    d.text((580, y + 12), "Cantidad", font=_font(22, True), fill="black")
    d.text((710, y + 12), "U. Medida", font=_font(22, True), fill="black")
    d.text((850, y + 12), "Precio Unit.", font=_font(22, True), fill="black")
    d.text((W - 80, y + 12), "Subtotal", font=_font(22, True), fill="black", anchor="ra")

    # Table lines
    y += 65
    for line in case["lines"]:
        d.text((80, y), line["concept"], font=_font(21), fill="black")
        qty_str = f"{line['qty']:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
        d.text((580, y), qty_str, font=_font(21), fill="black")
        d.text((710, y), line["unit"], font=_font(21), fill="black")
        d.text((850, y), _money_ar(line["unit_price"], cur), font=_font(21), fill="black")
        d.text((W - 80, y), _money_ar(line["amount"], cur), font=_font(21), fill="black", anchor="ra")
        y += 50

    # Summary box
    y = max(y + 60, 950)
    d.rectangle([60, y, W - 60, y + 250], outline="black", width=2)
    d.line([550, y, 550, y + 250], fill="black", width=1)

    # Observations in left summary
    d.text((80, y + 20), "Observaciones / Destino agronómico:", font=_font(20, True), fill="black")
    d.text((80, y + 55), f"Superficie amparada por esta entrega: {case['covers_ha']:.0f} ha.", font=_font(20), fill="black")
    d.text((80, y + 90), f"Cultivo asignado: {case['crop'].capitalize()}.", font=_font(20), fill="black")
    d.text((80, y + 125), "Precios de mercado tomados de fuentes públicas oficiales/sectoriales.", font=_font(18), fill="black")

    # Breakdown in right summary
    ry = y + 20
    d.text((580, ry), "Importe Neto Gravado:", font=_font(22), fill="black")
    d.text((W - 80, ry), _money_ar(case["net"], cur), font=_font(22), fill="black", anchor="ra")
    ry += 40

    if case["id"] == "r2":
        # Mixed IVA in r2
        d.text((580, ry), "IVA 10,50% (Semillas):", font=_font(22), fill="black")
        d.text((W - 80, ry), _money_ar(778932.0, cur), font=_font(22), fill="black", anchor="ra")
        ry += 40
        d.text((580, ry), "IVA 21,00% (Herbicidas):", font=_font(22), fill="black")
        d.text((W - 80, ry), _money_ar(527077.32, cur), font=_font(22), fill="black", anchor="ra")
        ry += 40
    else:
        vat_pct = f"{case['vat_rate'] * 100:.1f}".replace(".", ",")
        d.text((580, ry), f"IVA {vat_pct}%:", font=_font(22), fill="black")
        d.text((W - 80, ry), _money_ar(case["vat"], cur), font=_font(22), fill="black", anchor="ra")
        ry += 50

    d.line([550, ry + 5, W - 60, ry + 5], fill="black", width=2)
    ry += 15
    d.text((580, ry), "IMPORTE TOTAL:", font=_font(26, True), fill="black")
    d.text((W - 80, ry), _money_ar(case["total"], cur), font=_font(26, True), fill="black", anchor="ra")

    # CAE Electronic Footer
    ey = y + 280
    d.rectangle([60, ey, W - 60, ey + 110], outline=(100, 100, 100), width=1)
    d.text((80, ey + 20), f"CAE N.º: {case['cae']}", font=_font(22, True), fill="black")
    d.text((80, ey + 60), f"Fecha de Vto. de CAE: {case['cae_vto']}", font=_font(22, True), fill="black")
    d.text((W // 2 + 40, ey + 20), "Comprobante Autorizado por AFIP / ARCA", font=_font(20, True), fill="black")
    d.text((W // 2 + 40, ey + 60), "Código de Barras Oficial CAE: 3000000000001000574438921849120", font=_font(16), fill=(60, 60, 60))

    # Disclaimer at very bottom
    d.rectangle([60, H - 120, W - 60, H - 60], fill=(245, 245, 245), outline=(150, 150, 150), width=1)
    d.text((W // 2, H - 90), "Factura de prueba — precios reales, ver fuentes", font=_font(22, True), fill=(100, 100, 100), anchor="mm")

    return img


def draw_us_coop(case: dict) -> Image.Image:
    W, H = 1240, 1754
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)

    # Top banner
    d.rectangle([60, 60, W - 60, 260], fill=(240, 244, 248), outline="black", width=3)
    d.text((90, 85), case["seller"], font=_font(34, True), fill=(20, 50, 90))
    d.text((90, 135), "1420 Agri-Commerce Way · Fort Dodge, IA 50501", font=_font(20), fill="black")
    d.text((90, 168), "Phone: (515) 555-0190 · Direct Elevator / Agronomy Branch", font=_font(20), fill="black")
    d.text((90, 202), "Tax ID: 42-0000000 · State Co-op License # 8412", font=_font(20), fill="black")

    # Invoice info box (right top)
    d.rectangle([W - 480, 80, W - 80, 240], fill="white", outline="black", width=2)
    d.text((W - 280, 95), "BILLING STATEMENT", font=_font(22, True), fill="black", anchor="ma")
    ticket = case.get("ticket_number") or case.get("number", "TK-849201")
    account = case.get("account_id") or case.get("cuit_buyer", "IA-8829104")
    d.text((W - 460, 130), f"Ticket #: {ticket}", font=_font(20, True), fill="black")
    d.text((W - 460, 160), f"Date: {case['date']}", font=_font(20), fill="black")
    d.text((W - 460, 190), f"Account: {account}", font=_font(20, True), fill="black")

    # Customer & Terms box
    d.rectangle([60, 280, W - 60, 420], outline="black", width=2)
    d.text((90, 295), "SOLD TO / CUSTOMER:", font=_font(20, True), fill="black")
    d.text((90, 330), "TEST FARM OPERATIONS LLC", font=_font(24, True), fill="black")
    d.text((90, 365), "Rural Route 3, Webster County, IA", font=_font(20), fill="black")

    d.text((680, 295), "DELIVERY & TERMS:", font=_font(20, True), fill="black")
    d.text((680, 330), f"Field: 160.0 Acres ({case['covers_ha']:.2f} ha) - Corn/Soybean Rotation", font=_font(20, True), fill="black")
    d.text((680, 365), f"Terms: {case['payment_terms']} · Customer Rep: Dan Larson", font=_font(20), fill="black")

    # Table Header
    y = 450
    d.rectangle([60, y, W - 60, y + 50], fill=(220, 228, 236), outline="black", width=2)
    d.text((80, y + 12), "Product Description", font=_font(22, True), fill="black")
    d.text((620, y + 12), "Quantity", font=_font(22, True), fill="black")
    d.text((750, y + 12), "Unit", font=_font(22, True), fill="black")
    d.text((870, y + 12), "Unit Price", font=_font(22, True), fill="black")
    d.text((W - 80, y + 12), "Amount", font=_font(22, True), fill="black", anchor="ra")

    y += 65
    for line in case["lines"]:
        d.text((80, y), line["concept"], font=_font(21), fill="black")
        d.text((620, y), f"{line['qty']:,.1f}", font=_font(21), fill="black")
        d.text((750, y), line["unit"], font=_font(21), fill="black")
        d.text((870, y), _money_us(line["unit_price"]), font=_font(21), fill="black")
        d.text((W - 80, y), _money_us(line["amount"]), font=_font(21), fill="black", anchor="ra")
        y += 55

    # Totals Section
    y = max(y + 80, 1000)
    d.rectangle([60, y, W - 60, y + 240], outline="black", width=2)
    d.line([560, y, 560, y + 240], fill="black", width=1)

    # Left note: Sales Tax Exemption
    d.text((80, y + 25), "Agricultural Exemption Certification:", font=_font(20, True), fill="black")
    d.text((80, y + 65), "State of Iowa Sales Tax Exemption (§ 423.3):", font=_font(18, True), fill=(40, 40, 40))
    d.text((80, y + 95), "Agricultural chemicals, commercial fertilizers, and seed", font=_font(18), fill="black")
    d.text((80, y + 125), "used in agricultural production are 100% tax exempt.", font=_font(18), fill="black")
    d.text((80, y + 165), "Purchaser Exemption Certificate on file: # IA-AG-9921.", font=_font(18, True), fill="black")

    # Right: Numbers
    ry = y + 25
    d.text((590, ry), "Subtotal Products:", font=_font(22), fill="black")
    d.text((W - 80, ry), _money_us(case["net"]), font=_font(22), fill="black", anchor="ra")
    ry += 45
    d.text((590, ry), "Sales Tax (Ag Exempt):", font=_font(22), fill="black")
    d.text((W - 80, ry), "$0.00", font=_font(22), fill="black", anchor="ra")
    ry += 45
    d.line([560, ry + 5, W - 60, ry + 5], fill="black", width=2)
    ry += 20
    d.text((590, ry), "TOTAL AMOUNT DUE:", font=_font(26, True), fill=(20, 50, 90))
    d.text((W - 80, ry), _money_us(case["total"]), font=_font(26, True), fill=(20, 50, 90), anchor="ra")

    # Footer Disclaimer
    d.rectangle([60, H - 120, W - 60, H - 60], fill=(245, 245, 245), outline=(150, 150, 150), width=1)
    d.text((W // 2, H - 90), "Test invoice — real prices, see sources", font=_font(22, True), fill=(100, 100, 100), anchor="mm")

    return img


def render_all():
    cases_file = HERE / "real_cases.json"
    cases = json.loads(cases_file.read_text(encoding="utf-8"))
    for c in cases:
        cid = c["id"]
        out_path = MEDIA_DIR / f"{cid}.png"
        print(f"Rendering {cid} ({c['region']}, {c['currency']}) -> {out_path}...")
        if c["region"] == "iowa":
            img = draw_us_coop(c)
        else:
            img = draw_factura_a(c)
        img.save(out_path)
    print("All 5 clean invoices successfully rendered in:", MEDIA_DIR)


if __name__ == "__main__":
    render_all()

