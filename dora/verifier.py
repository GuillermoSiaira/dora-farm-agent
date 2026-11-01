"""Number and scenario verifier for the agent's answers.

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
from typing import Any

from .scenario import REGIONS, normalize_region

_NUM = r"\d{1,3}(?:[.,]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?"
_PATTERN = re.compile(
    rf"(?<![\w.,])(?P<num>{_NUM})(?![ºª°\d])\s*"
    rf"(?P<scale>millones|millón|million|mil\b|thousand\b|M\b|k\b|centavos?|cents?)?\s*(?P<pct>%)?",
    re.IGNORECASE)
_SCALES = {"millones": 1e6, "millón": 1e6, "million": 1e6, "m": 1e6, "mil": 1e3, "thousand": 1e3, "k": 1e3,
           "lucas": 1e3, "luca": 1e3,
           "centavos": 0.01, "centavo": 0.01, "cents": 0.01, "cent": 0.01}

_PATTERN_SCENARIO = re.compile(
    r"(?<![\w.,])(?P<sign>[-−])?(?P<num>\d{1,3}(?:[.,]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)(?![ºª°\d])\s*"
    r"(?P<scale>millones|millón|million|mil\b|thousand\b|M\b|k\b|centavos?|cents?|lucas?\b)?\s*"
    r"(?P<pct>%)?\s*"
    r"(?P<unit>acres?|ha\b|hect[aá]reas?|has\b|d[ií]as?|days?|por\s*ciento)?",
    re.IGNORECASE,
)

CROP_PATTERNS = {
    "wheat": re.compile(r"\b(trigo|wheat)\b", re.IGNORECASE),
    "corn": re.compile(r"\b(ma[ií]z|corn|maize)\b", re.IGNORECASE),
    "soybean": re.compile(r"\b(soja|soybean|soybeans)\b", re.IGNORECASE),
    "sunflower": re.compile(r"\b(girasol|sunflower|sunflowers)\b", re.IGNORECASE),
}

RESTRICTION_OR_SOWING_RE = re.compile(
    r"^(solo|s[oó]lo|[uú]nicamente|nada|only|just|sembr\w*|siembr\w*|hac\w*|hag\w*|plant\w*|grow\w*|sow\w*)$",
    re.IGNORECASE,
)

SEASON_SOLVING_TOOLS = {
    "evaluate_season", "shadow_prices", "sensitivity",
    "compare_regions", "climate_scenarios", "assess_field_image",
}


@dataclass
class UnsupportedNumber:
    text: str
    context: str


@dataclass
class ScenarioProblem:
    parameter: str
    value: Any = None
    reason: str = ""


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


FRACTIONS = [
    (re.compile(r"\b(la\s+mitad|mitad|half)\b", re.IGNORECASE), 0.5, [0.5]),
    (re.compile(r"\b(un\s+tercio|tercio|one\s+third|third)\b", re.IGNORECASE), 1.0 / 3.0, [1.0 / 3.0, 0.33, 0.3333]),
    (re.compile(r"\b(un\s+cuarto|cuarto|one\s+fourth|quarter)\b", re.IGNORECASE), 0.25, [0.25]),
]

IDENTIFIER_RE = re.compile(r"^[a-zA-Z0-9]+(?:[-_][a-zA-Z0-9]+)+$")


def _is_share_param(name: str) -> bool:
    clean = name.lower()
    return clean.endswith("_share") or clean == "share" or clean.endswith("_share_pct") or clean in ("max_crop_share", "min_crop_share", "loss_share")


def _extract_farmer_numbers(user_texts: list[str]) -> tuple[list[float], list[float]]:
    farmer_nums: list[float] = []
    area_nums: list[float] = []
    for t in user_texts:
        # Check if screen JSON context
        for m in re.finditer(r"\{[^{}]+\}", t):
            try:
                d = json.loads(m.group(0))
                if isinstance(d, dict):
                    if "area_ha" in d and isinstance(d["area_ha"], (int, float)):
                        area_nums.append(float(d["area_ha"]))
                    if "owned_ha" in d and isinstance(d["owned_ha"], (int, float)):
                        area_nums.append(float(d["owned_ha"]))
            except Exception:
                pass

        has_thousand = bool(re.search(r"\b(lucas?|mil|thousand|k)\b", t, re.IGNORECASE))
        for m in _PATTERN_SCENARIO.finditer(t):
            sign = -1.0 if m.group("sign") in ("-", "−") else 1.0
            scale_str = (m.group("scale") or "").lower()
            base_scale = _SCALES.get(scale_str, 1.0)
            is_pct = bool(m.group("pct")) or (m.group("unit") or "").lower() in ("%", "por ciento")
            unit = (m.group("unit") or "").lower()

            raw_num = m.group("num")
            for v, _ in _readings(raw_num):
                val = v * sign * base_scale
                farmer_nums.append(val)
                if is_pct:
                    farmer_nums.append(val / 100.0)
                if unit in ("días", "dias", "days"):
                    farmer_nums.append(val / 15.0)
                if unit in ("acres", "acre"):
                    ha_val = val * 0.404686
                    farmer_nums.append(ha_val)
                    area_nums.append(ha_val)
                elif unit in ("ha", "hectáreas", "hectareas", "has"):
                    area_nums.append(val)
                if has_thousand and not scale_str:
                    farmer_nums.append(val * 1000.0)
                    if is_pct:
                        farmer_nums.append((val * 1000.0) / 100.0)

    for t in user_texts:
        for pat, frac, props in FRACTIONS:
            if pat.search(t):
                farmer_nums.extend(props)
                for a in list(area_nums):
                    frac_a = a * frac
                    farmer_nums.append(frac_a)
                    area_nums.append(frac_a)

    return farmer_nums, area_nums


def _matches_any(val: float, available: list[float]) -> bool:
    if abs(val) < 1e-9:
        return any(abs(a) < 1e-9 for a in available)
    for a in available:
        if (val > 0 and a > 0) or (val < 0 and a < 0):
            if abs(a - val) <= 0.01 * abs(val) + 1e-9:
                return True
    return False


def check_scenario(tool: str, args: dict, user_texts: list[str], tool_results: list) -> list[ScenarioProblem]:
    if tool not in SEASON_SOLVING_TOOLS:
        return []

    scenario = args.get("scenario") if isinstance(args.get("scenario"), dict) else args
    if not isinstance(scenario, dict):
        scenario = {}
    mode = str(args.get("mode") or scenario.get("mode") or "same_farm").strip().lower()

    problems: list[ScenarioProblem] = []
    farmer_nums, area_nums = _extract_farmer_numbers(user_texts)
    tool_nums = support(tool_results, [])
    all_available = farmer_nums + tool_nums

    # Rule 1: Farm size
    is_same_budget = (tool == "compare_regions" and mode == "same_budget")
    area_val = scenario.get("area_ha") if "area_ha" in scenario else scenario.get("owned_ha")
    if not is_same_budget:
        if not area_nums:
            problems.append(ScenarioProblem("area_ha", area_val, "area_ha missing: ask the farmer"))
        elif area_val is None:
            if not _matches_any(500.0, area_nums):
                problems.append(ScenarioProblem("area_ha", None, "area_ha missing: ask the farmer"))
        elif not _matches_any(float(area_val), area_nums):
            problems.append(ScenarioProblem("area_ha", area_val, f"farmer wrote {area_nums[0]:.1f}"))

    # Rule 2: Numbers the agent set
    flagged_params = {p.parameter for p in problems}
    for k, v in scenario.items():
        if k in ("crops", "region", "price_curve_source", "export_fx_regime", "routes", "livestock"):
            continue
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)):
            if k in flagged_params:
                continue
            if _is_share_param(k) and float(v) in (0.0, 1.0):
                continue
            if not _matches_any(float(v), all_available):
                problems.append(ScenarioProblem(k, v, f"number {v} does not match farmer words or tool results"))
        elif isinstance(v, dict):
            for sub_k, sub_v in v.items():
                if isinstance(sub_v, (int, float)) and not isinstance(sub_v, bool):
                    if _is_share_param(sub_k) and float(sub_v) in (0.0, 1.0):
                        continue
                    if not _matches_any(float(sub_v), all_available):
                        problems.append(ScenarioProblem(f"{k}.{sub_k}", sub_v, f"number {sub_v} does not match farmer words or tool results"))
        elif isinstance(v, list) and k in ("constraints", "payment_options"):
            for idx, item in enumerate(v):
                if isinstance(item, dict):
                    for ck, cv in item.items():
                        if isinstance(cv, (int, float)) and not isinstance(cv, bool):
                            if _is_share_param(ck) and float(cv) in (0.0, 1.0):
                                continue
                            if not _matches_any(float(cv), all_available):
                                problems.append(ScenarioProblem(f"{k}[{idx}].{ck}", cv, f"number {cv} does not match farmer words or tool results"))

    # Rule 3: Narrowing crops & rented_land
    reg_name = normalize_region(scenario.get("region", "southeast_buenos_aires"))
    allowed_crops = REGIONS.get(reg_name, {}).get("crops", ("wheat", "corn", "soybean", "sunflower"))
    if "crops" in scenario and isinstance(scenario["crops"], list):
        if len(scenario["crops"]) < len(allowed_crops):
            for c in scenario["crops"]:
                pat = CROP_PATTERNS.get(c)
                found_crop = False
                restricted = False
                for t in user_texts:
                    words = re.findall(r"[\wáéíóúüñ]+", t.lower())
                    for i, w in enumerate(words):
                        if pat and pat.search(w):
                            found_crop = True
                            window = words[max(0, i - 5):i]
                            for prev in window:
                                if RESTRICTION_OR_SOWING_RE.match(prev):
                                    restricted = True
                                    break
                if not (found_crop and restricted):
                    problems.append(ScenarioProblem("crops", scenario["crops"], f"crop {c} restricted without farmer instruction"))
                    break

    if scenario.get("rented_land") is True:
        has_rent_word = any(re.search(r"\b(alquil\w*|arrend\w*|rent\w*|lease\w*)\b", t, re.IGNORECASE) for t in user_texts)
        if not has_rent_word:
            problems.append(ScenarioProblem("rented_land", True, "farmer did not mention renting or leasing land"))

    return problems


def jargon(text: str) -> list[str]:
    """Find snake_case words and back-ticked identifiers in text."""
    found: list[str] = []
    # Back-ticked identifiers: `...` (only snake_case or hyphen-separated identifiers)
    for m in re.finditer(r"`([^`\n]+)`", text):
        w = m.group(1).strip()
        if w and IDENTIFIER_RE.match(w) and w not in found:
            found.append(w)
    # snake_case words: \b[a-z]+(?:_[a-z0-9]+)+\b
    for m in re.finditer(r"\b[a-z]+(?:_[a-z0-9]+)+\b", text):
        w = m.group(0).strip()
        if w and w not in found:
            found.append(w)
    return found


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


def correction_message(problems: list[UnsupportedNumber], style_problems: list[str] | None = None) -> str:
    lines = []
    if problems:
        items = "\n".join(f'- "{p.text}" in: …{p.context}…' for p in problems)
        lines.append(
            "Your answer has numbers that do not come from any tool or from what the farmer said:\n"
            f"{items}\nDo not calculate: use only numbers the tools returned (rounded correctly is fine), "
            "or call a tool that computes them. Rewrite the answer in the same language, tone and format, "
            "changing only those numbers; round to what a farmer reads (USD without decimals, rates as %).\n"
            "If you remove a number, rewrite the whole sentence so it still reads well; never leave an empty parenthesis or a sentence cut in the middle."
        )
    if style_problems:
        lines.append(f"Write these in plain words: {', '.join(style_problems)}.")
    return "\n\n".join(lines)
