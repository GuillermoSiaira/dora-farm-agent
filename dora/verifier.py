"""Number verifier for the agent's answers.

Rule: every number in the answer must appear in what the tools returned or in
what the farmer wrote. The model explains; it does not calculate.

It reads numbers as written in Spanish and in English ("1.250,5", "1,250.5",
"16%", "92 mil", "1,2 millones", "16 centavos", "92k") and compares them at the
precision they are written with:
- a written number matches a source value if it is that value correctly rounded
  (within half a unit of its last digit): "88 mil" matches 88,186.6;
- numbers below 10 written without decimals must match to one decimal place:
  "2 ha" does not match 1.6, but "1,6 ha" does.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

_NUM = r"\d{1,3}(?:[.,]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?"
_PATTERN = re.compile(
    rf"(?<![\w.,])(?P<num>{_NUM})(?![ºª°])\s*"
    rf"(?P<scale>millones|millón|million|mil\b|thousand\b|M\b|k\b|centavos?|cents?)?\s*(?P<pct>%)?",
    re.IGNORECASE)
_SCALES = {"millones": 1e6, "millón": 1e6, "million": 1e6, "m": 1e6, "mil": 1e3, "thousand": 1e3, "k": 1e3,
           "centavos": 0.01, "centavo": 0.01, "cents": 0.01, "cent": 0.01}


@dataclass
class UnsupportedNumber:
    text: str
    context: str


def _collect(value, out: list[float]) -> None:
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        out.append(abs(float(value)))
    elif isinstance(value, str):
        for m in re.finditer(r"\d+(?:\.\d+)?", value):
            out.append(float(m.group()))
    elif isinstance(value, dict):
        for k, v in value.items():
            _collect(k, out)
            _collect(v, out)
    elif isinstance(value, (list, tuple)):
        for v in value:
            _collect(v, out)


def _readings(s: str) -> list[tuple[float, int]]:
    """Possible values of a written number, and how many decimals it shows."""
    if "." in s and "," in s:                       # the last separator is the decimal one
        dec = "," if s.rfind(",") > s.rfind(".") else "."
        whole, _, frac = s.replace("." if dec == "," else ",", "").partition(dec)
        return [(float(f"{whole}.{frac}"), len(frac))]
    sep = "." if "." in s else "," if "," in s else None
    if sep is None:
        return [(float(s), 0)]
    parts = s.split(sep)
    options = []
    if all(len(p) == 3 for p in parts[1:]):         # 1.250 or 1,250: thousands
        options.append((float("".join(parts)), 0))
    if len(parts) == 2:                             # 0,16 or 0.16: decimal
        options.append((float(f"{parts[0]}.{parts[1]}"), len(parts[1])))
    return options


def support(results: list, user_texts: list[str]) -> list[float]:
    """Every number available: tool outputs (JSON text or dict) and the farmer's messages."""
    numbers: list[float] = []
    for r in results:
        if isinstance(r, str):
            try:
                r = json.loads(r)
            except json.JSONDecodeError:
                pass
        _collect(r, numbers)
    for t in user_texts:
        for m in _PATTERN.finditer(t):
            factor = _SCALES.get((m.group("scale") or "").lower(), 1)
            numbers.extend(v * factor for v, _ in _readings(m.group("num")))
    return numbers


def _tolerance(value: float, decimals: int) -> float:
    if decimals == 0 and value < 10:
        return 0.05                                 # small whole numbers must match to one decimal
    return 0.5 * 10 ** -decimals                    # correctly rounded at the written precision


def _is_list_number(text: str, start: int, end: int) -> bool:
    line_start = text.rfind("\n", 0, start) + 1
    return text[line_start:start].strip(" *#>-") == "" and re.match(r"[.)]\s", text[end:end + 2]) is not None


def verify(text: str, results: list, user_texts: list[str]) -> list[UnsupportedNumber]:
    available = support(results, user_texts)
    problems = []
    for m in _PATTERN.finditer(text):
        start, end = m.start("num"), m.end("num")
        raw = m.group("num")
        if _is_list_number(text, start, end):
            continue
        if re.fullmatch(r"(19|20)\d{2}", raw) and not m.group("scale") and not m.group("pct"):
            continue                                # a year
        factor = _SCALES.get((m.group("scale") or "").lower(), 1)
        ok = False
        for value, decimals in _readings(raw):
            tol = _tolerance(value, decimals)
            candidates = [(value * factor, tol * factor)]
            if m.group("pct"):                      # 16% may come from 16 or from 0.16
                candidates.append((value / 100, tol / 100))
            if any(abs(n - c) <= t + 1e-9 for c, t in candidates for n in available):
                ok = True
                break
        if not ok:
            problems.append(UnsupportedNumber(m.group().strip(),
                                              text[max(0, start - 40):end + 40].replace("\n", " ").strip()))
    return problems


def correction_message(problems: list[UnsupportedNumber]) -> str:
    items = "\n".join(f'- "{p.text}" in: …{p.context}…' for p in problems)
    return ("Your answer has numbers that do not come from any tool or from what the farmer said:\n"
            f"{items}\nDo not calculate: use only numbers the tools returned (rounded correctly is fine), "
            "or call a tool that computes them. Rewrite the answer.")
