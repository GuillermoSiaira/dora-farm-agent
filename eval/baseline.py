"""Condition A of E1 (docs/plan-de-pruebas.md): the language model alone, without tools.

It gets the farmer's question and, in text, the same data the engine uses for
that scenario: every number comes from the Scenario object the engine solves,
none is typed here. It must answer with a JSON plan (hectares per crop, when to
sell) and the number the farmer asked for.

We do not test whether the model knows prices by heart, but whether it can
reason the optimization problem with the data in front of it.
"""
from __future__ import annotations

import json
import re

from dora.scenario import FORTNIGHTS, fortnight_month, fortnightly_rate
from dora.tools import _validate

SYSTEM_PROMPT = """You are a crop-season planning assistant for grain farmers.
Answer in the farmer's language (Rioplatense Spanish if they write in Spanish).
You have no tools: reason the problem yourself with the data given, which is all the data there is.

Reply with ONE JSON object and nothing else:
{
  "hectares": {"<crop>": <ha>, ...},                 // your plan: hectares of each crop (0 if not sown)
  "sales": {"<crop>": {"YYYY-MM": <tonnes>, ...}},   // when you sell each crop's harvest
  "expected_npv_usd": <number>,                      // present value your plan reaches (definition below)
  "answer_value": <number or text>,                  // the number (or month) the farmer asked for
  "answer_text": "<your answer to the farmer, brief>"
}
If the question cannot be answered (an invalid farm, a crop with no data, a missing value),
say why in answer_text and leave hectares empty and answer_value null."""

GLOSSARY = """Definitions of the figures a farmer may ask for:
- Present value (NPV): (cash surplus - debt) at the end of fortnight 29, plus the value of land bought,
  discounted to fortnight 0 at the deposit rate. This is what the plan maximizes.
- Peak credit: the largest credit balance used in any fortnight.
- Value of one more dollar of own capital: how much the present value rises with one more dollar of own
  capital, minus 1 (what depositing it would give).
- Value of one more dollar of credit line: how much the present value rises if the credit line is one dollar larger.
- Value of one more tonne of storage capacity: how much the present value rises with one more tonne of capacity.
- Rate of a capital stretch: the annual rate that one dollar earns inside the plan between two fortnights,
  when capital is scarce (above the deposit rate).
- Storage breakeven: the net price at the end of the storage window that makes storing a tonne from harvest
  worth the same as selling it at harvest."""


def _money(x: float) -> str:
    return f"{x:,.2f}"


def _schedule(payments: dict[int, float]) -> str:
    return ", ".join(f"f{p}: {v:.2f}" for p, v in sorted(payments.items()) if abs(v) > 1e-9)


def data_text(scenario: dict) -> str:
    """The data the engine solves this scenario with, in text."""
    sc, _ = _validate(scenario)
    if sc.livestock or sc.livestock_only_ha > 0:
        raise ValueError("The baseline prompt does not describe livestock yet.")
    tau = sc.transaction_tax_rate
    lines = [f"Region: {sc.region}. Crops available: {', '.join(sc.crops)}.",
             f"Time: fortnights f0 to f{FORTNIGHTS - 1}; f0 is the first half of {sc.season_start}, f1 its second half, "
             f"f2 the first half of {fortnight_month(sc.season_start, 2)}, and so on until f{FORTNIGHTS - 1} "
             f"(second half of {fortnight_month(sc.season_start, FORTNIGHTS - 1)})."]

    lines.append("\nLAND")
    lines.append(f"- Owned: {sc.owned:.1f} ha.")
    if sc.rent_in_cap > 0:
        lines.append(f"- Can rent in up to {sc.rent_in_cap:.1f} ha at {_money(sc.regional_rent_usd_ha)} USD/ha, paid in f0"
                     + (f" plus {tau:.2%} transaction tax." if tau else "."))
    if sc.allow_rent_out and sc.regional_rent_usd_ha > 0:
        lines.append(f"- Can rent out owned land at {_money(sc.regional_rent_usd_ha)} USD/ha, received in f0"
                     + (f" minus {tau:.2%} transaction tax." if tau else "."))
    if sc.max_buy_ha > 0:
        lines.append(f"- Can buy up to {sc.max_buy_ha:.1f} ha at {_money(sc.land_price_usd_ha)} USD/ha in f0, worth that price "
                     f"times (1 + {sc.land_appreciation_annual}) ^ ({FORTNIGHTS}/24) at the end.")
    if sc.land_tax_usd_ha_year > 0:
        lines.append(f"- Land tax: {_money(sc.land_tax_usd_ha_year)} USD/ha a year on owned and bought land, paid in f0.")
    lines.append(f"- Rotation: no crop on more than {sc.max_crop_share:.0%} of the land held (owned + rented in + bought - rented out).")
    lines.append("- Sown hectares of all crops together cannot exceed the land held.")

    lines.append("\nMONEY")
    lines.append(f"- Own capital: {_money(sc.own_capital_usd)} USD, available in f0.")
    lines.append(f"- Credit line: up to {_money(sc.credit_line_usd)} USD outstanding at any time, at {sc.credit_rate_annual:.2%} "
                 f"a year ({fortnightly_rate(sc.credit_rate_annual):.6f} per fortnight, compounded). All debt must be repaid by f{FORTNIGHTS - 1}.")
    lines.append(f"- Cash surplus earns {sc.deposit_rate_annual:.2%} a year ({fortnightly_rate(sc.deposit_rate_annual):.6f} per fortnight, compounded). "
                 "Cash can never be negative: every payment comes from cash or credit.")
    if sc.gross_receipts_rate > 0:
        lines.append(f"- Gross receipts tax: {sc.gross_receipts_rate:.2%} of each sale (already taken out of the net prices below).")
    if tau > 0:
        lines.append(f"- Transaction tax: {tau:.2%} on payments and receipts (already inside the payments and net prices below).")
    if sc.income_tax_rate > 0:
        lines.append(f"- Income tax: {sc.income_tax_rate:.2%} of the season profit, at the end, if profit is positive.")

    lines.append("\nCROPS (payments in USD per hectare sown, by fortnight; net prices in USD per tonne sold, by fortnight)")
    for c in sc.crops:
        cal = sc._calendar(c)
        lines.append(f"- {c}: yield {sc.crop_yield(c):.3f} t/ha; sown in f{cal['sowing']}, harvested in f{cal['harvest']}.")
        if sc.payment_options:
            lines.append(f"  Fixed payments per ha: {_schedule(sc.fixed_payments_per_ha(c))}")
            for t in sc.payment_terms():
                inputs = sc.input_payments_per_ha(c, t["delay_fortnights"], t["surcharge"], t["installments"], t["every_fortnights"])
                lines.append(f"  Seed, fertilizer and crop protection per ha under term '{t['id']}': {_schedule(inputs)}")
        else:
            lines.append(f"  Payments per ha: {_schedule(sc.payments_per_ha(c))}")
        for r in sc.routes:
            prices = {p: sc.net_price_route(c, p, r) for p in range(cal["harvest"], FORTNIGHTS)}
            label = "" if len(sc.routes) == 1 else f" via route '{r.get('id')}'"
            lines.append(f"  Net price{label}: {_schedule(prices)}")
    if len(sc.routes) > 1:
        lines.append("Route capacities (tonnes for the season): "
                     + ", ".join(f"{r.get('id')}: {r.get('capacity_t') if r.get('capacity_t') is not None else 'no limit'}" for r in sc.routes))

    lines.append("\nGRAIN")
    lines.append("- Each crop's harvest (yield x hectares) arrives in its harvest fortnight. Every tonne must be sold "
                 f"between harvest and f{FORTNIGHTS - 1}; grain not sold at harvest must be stored.")
    for o in sc.effective_storage_options():
        cap = "no limit" if o["capacity_t"] is None else f"{o['capacity_t']:.0f} t in total at any time"
        life = "no limit" if o["max_months"] is None else f"{o['max_months']} months"
        lines.append(f"- Storage '{o['id']}': capacity {cap}; {o['fill_cost_usd_t']:.2f} USD/t when filled at harvest; "
                     f"{o['monthly_cost_usd_t']:.2f} USD/t a month held (half each fortnight); shrink {o['shrink_at_entry']:.2%} at entry "
                     f"and {o['shrink_monthly']:.2%} a month; maximum life {life}.")

    sy, sm = int(sc.season_start[:4]), int(sc.season_start[5:7])
    for k in sc.constraints:
        if k["type"] == "forward_sale":
            p = 2 * ((int(k["month"][:4]) - sy) * 12 + int(k["month"][5:7]) - sm)
            freight = sc.inland_cost(sc.routes[0], p) if sc.price_point == "port" else 0.0
            net = (float(k["price_usd_t"]) * (1 - sc.gross_receipts_rate - tau)
                   - sc.marketing_per_t(k["crop"]) - freight)
            lines.append(f"- Forward sale already signed: {k['tonnes']} t of {k['crop']} delivered in f{p} ({k['month']}) "
                         f"at {k['price_usd_t']} USD/t, which is {net:.2f} USD/t net.")
    other = [k for k in sc.constraints if k["type"] != "forward_sale"]
    if other:
        lines.append("\nFARMER'S CONDITIONS")
        for k in other:
            if k["type"] in ("min_area", "max_area"):
                lines.append(f"- {'At least' if k['type'] == 'min_area' else 'At most'} {k['ha']} ha of {k['crop']}.")
            elif k["type"] == "min_share":
                lines.append(f"- At least {k['share']:.0%} of the sown area in {k['crop']}.")
            elif k["type"] == "max_payments_by":
                lines.append(f"- Crop payments from f0 until the end of {k['month']} cannot exceed {_money(float(k['usd']))} USD.")
    return "\n".join(lines)


def build_messages(question: dict) -> list[dict]:
    """The two messages condition A sends. Questions that refuse get their region's default data."""
    scenario = question["scenario"]
    if question.get("expect") == "refuse":
        scenario = {"region": question["region"]} if question.get("region") else {}
    user = f"Farmer's question:\n{question['text']}\n\nDATA\n{data_text(scenario)}\n\n{GLOSSARY}"
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


def parse_reply(content: str) -> dict:
    """The JSON object in the model's reply, or an error if there is none."""
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", (content or "").strip())
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in the reply")
    obj = json.loads(text[start:end + 1])
    if not isinstance(obj, dict):
        raise ValueError("the reply is not a JSON object")
    return obj


def ask_baseline(client, model: str, question: dict) -> dict:
    """One condition-A answer: the parsed plan and number, the raw reply and the tokens used."""
    messages = build_messages(question)
    resp = client.chat.completions.create(model=model, messages=messages)
    content = resp.choices[0].message.content or ""
    usage = getattr(resp, "usage", None)
    pt = usage.get("prompt_tokens", 0) if isinstance(usage, dict) else getattr(usage, "prompt_tokens", 0)
    ct = usage.get("completion_tokens", 0) if isinstance(usage, dict) else getattr(usage, "completion_tokens", 0)
    usage_dict = {
        "requests": 1,
        "prompt_tokens": pt or 0,
        "completion_tokens": ct or 0,
    }
    details = usage.get("prompt_tokens_details") if isinstance(usage, dict) else getattr(usage, "prompt_tokens_details", None)
    cached = 0
    if isinstance(details, dict):
        cached = details.get("cached_tokens", 0) or 0
    elif details is not None:
        cached = getattr(details, "cached_tokens", 0) or 0
    if cached:
        usage_dict["cached_prompt_tokens"] = cached

    out = {
        "raw": content,
        "prompt": messages[1]["content"],
        "usage": usage_dict,
        "parse_error": None, "hectares": None, "answer_value": None, "expected_npv_usd": None, "text": content,
    }
    try:
        obj = parse_reply(content)
    except (ValueError, json.JSONDecodeError) as e:
        out["parse_error"] = str(e)
        return out
    hectares = obj.get("hectares") or {}
    if isinstance(hectares, dict):
        try:
            out["hectares"] = {str(c): float(h) for c, h in hectares.items() if h is not None}
        except (TypeError, ValueError):
            out["parse_error"] = "hectares are not numbers"
    out["answer_value"] = obj.get("answer_value")
    out["expected_npv_usd"] = obj.get("expected_npv_usd")
    out["sales"] = obj.get("sales")
    out["text"] = str(obj.get("answer_text") or "")
    return out
