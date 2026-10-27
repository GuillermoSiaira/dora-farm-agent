"""Price feeds adapter architecture and live curve refreshers.

Refreshes CBOT futures from Yahoo Finance and Argentine spot prices from MAGyP
and BCRA exchange rates, maintaining local snapshots with cache and fallback.
"""
from __future__ import annotations

import datetime
import json
import re
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path

from .prices import CURVES_DIR, cents_per_bushel_to_usd_per_tonne

USER_AGENT = "DORA-farm-agent/0.1 (+https://github.com/GuillermoSiaira/dora-farm-agent)"
TIMEOUT_SECONDS = 10
PAUSE_BETWEEN_REQUESTS = 0.5

DATA_DIR = Path(__file__).parent / "data"
CBOT_LATEST_PATH = CURVES_DIR / "cbot_latest.json"
ARGENTINA_LATEST_PATH = CURVES_DIR / "argentina_latest.json"
BASIS_ARGENTINA_PATH = DATA_DIR / "basis_argentina.json"

CBOT_MONTH_CODES = {
    1: "F",
    3: "H",
    5: "K",
    7: "N",
    8: "Q",
    9: "U",
    11: "X",
    12: "Z",
}
CODE_TO_MONTH = {v: k for k, v in CBOT_MONTH_CODES.items()}

CBOT_CROPS = {
    "corn": {"prefix": "ZC", "months": ["H", "K", "N", "U", "Z"]},
    "soybean": {"prefix": "ZS", "months": ["F", "H", "K", "N", "Q", "U", "X"]},
    "wheat": {"prefix": "ZW", "months": ["H", "K", "N", "U", "Z"]},
}


class FeedError(Exception):
    """Base error for price feeds."""


class RateLimitError(FeedError):
    """Raised on HTTP 429 rate limit."""


def http_get(url: str, pause: float = PAUSE_BETWEEN_REQUESTS) -> str:
    """Fetch text content via HTTP GET adhering to network rules."""
    if pause > 0:
        time.sleep(pause)

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "*/*",
        },
    )
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS, context=ctx) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise RateLimitError(f"Rate limited (HTTP 429) for {url}") from e
        raise FeedError(f"HTTP error {e.code} for {url}") from e
    except Exception as e:
        raise FeedError(f"Request failed for {url}: {e}") from e


def parse_argentine_number(s: str) -> float:
    """Parse a number formatted in Argentine notation (dot thousands, comma decimal)."""
    s = s.strip()
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        parts = s.split(".")
        if len(parts) == 2 and len(parts[1]) == 3:
            s = parts[0] + parts[1]
        elif len(parts) > 2:
            s = "".join(parts[:-1]) + "." + parts[-1]
    return float(s)


class YahooCbotFeed:
    """CBOT futures adapter fetching contract prices from Yahoo Finance."""

    URL_TEMPLATE = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=5d&interval=1d"

    def build_symbols(
        self,
        start_year: int | None = None,
        start_month: int | None = None,
        months_ahead: int = 18,
    ) -> dict[str, list[tuple[str, str]]]:
        """Build contract symbols up to months_ahead from start date.

        Returns {crop: [(symbol, YYYY-MM), ...]}.
        """
        if start_year is None or start_month is None:
            today = datetime.date.today()
            start_year, start_month = today.year, today.month

        result: dict[str, list[tuple[str, str]]] = {}
        for crop, spec in CBOT_CROPS.items():
            contracts: list[tuple[str, str]] = []
            prefix = spec["prefix"]
            allowed_codes = set(spec["months"])
            allowed_months = {CODE_TO_MONTH[code] for code in allowed_codes}

            for offset in range(months_ahead + 1):
                total_months = (start_month - 1) + offset
                y = start_year + (total_months // 12)
                m = (total_months % 12) + 1
                if m in allowed_months:
                    code = CBOT_MONTH_CODES[m]
                    yy = y % 100
                    symbol = f"{prefix}{code}{yy:02d}.CBT"
                    month_str = f"{y:04d}-{m:02d}"
                    contracts.append((symbol, month_str))
            result[crop] = contracts
        return result

    def fetch_contract_price(self, symbol: str) -> float | None:
        """Fetch regularMarketPrice in cents/bu for a symbol."""
        url = self.URL_TEMPLATE.format(symbol=symbol)
        try:
            content = http_get(url)
            data = json.loads(content)
            result = data.get("chart", {}).get("result")
            if not result or not isinstance(result, list):
                return None
            meta = result[0].get("meta", {})
            price = meta.get("regularMarketPrice")
            if price is None or not isinstance(price, (int, float)) or price <= 0:
                return None
            return float(price)
        except RateLimitError:
            raise
        except Exception:
            return None

    def fetch(
        self,
        start_year: int | None = None,
        start_month: int | None = None,
        as_of: str | None = None,
    ) -> dict:
        """Fetch all contracts and return a snapshot dictionary."""
        if as_of is None:
            as_of = datetime.date.today().isoformat()

        symbol_map = self.build_symbols(start_year=start_year, start_month=start_month)
        curve: dict[str, dict[str, float]] = {}

        for crop, contracts in symbol_map.items():
            curve[crop] = {}
            for symbol, month_str in contracts:
                price = self.fetch_contract_price(symbol)
                if price is not None:
                    curve[crop][month_str] = price

        return {
            "source": "CBOT futures via Yahoo Finance (delayed)",
            "as_of": as_of,
            "unit": "cents/bu",
            "placeholder": False,
            "curve": curve,
        }


class MagypPricesFeed:
    """MAGyP official spot prices feed for Argentine grains."""

    URL = "https://www.magyp.gob.ar/mercadosagropecuarios/precios.php"

    CROPS_CONFIG = {
        "wheat": r"(?:alt=[\"']trigo[\"']|trigopan-ico\.png|<!--\s*Trigo pan\s*-->)",
        "corn": r"(?:alt=[\"']maiz[\"']|maiz-ico\.png|<!--\s*Maiz\s*-->)",
        "sunflower": r"(?:alt=[\"']girasol[\"']|girasol-ico\.png|<!--\s*Girasol\s*-->)",
        "soybean": r"(?:alt=[\"']soja[\"']|soja-ico\.png|<!--\s*Soja\s*-->)",
    }

    def parse(self, html: str) -> dict:
        """Parse raw HTML and extract quote date, FOB (USD/t) and FAS (ARS/t)."""
        m_date = re.search(r"Cotizaciones de granos a:\s*(\d{1,2}/\d{1,2}/\d{4})", html, re.I)
        if not m_date:
            raise ValueError("Could not find quote date in MAGyP HTML (table structure may have changed)")

        raw_date = m_date.group(1)
        d, m, y = raw_date.split("/")
        iso_date = f"{int(y):04d}-{int(m):02d}-{int(d):02d}"

        quotes: dict[str, dict[str, float]] = {}
        for crop, pattern in self.CROPS_CONFIG.items():
            m_crop = re.search(pattern, html, re.I)
            if not m_crop:
                raise ValueError(f"Could not find crop '{crop}' in MAGyP HTML (table structure may have changed)")

            snippet = html[m_crop.start(): m_crop.start() + 450]
            m_fob = re.search(r"FOB:\s*([\d\.,]+)\s*USD/t", snippet, re.I)
            if not m_fob:
                raise ValueError(f"Could not find FOB for '{crop}' in MAGyP HTML")

            m_fas = re.search(r":\s*([\d\.,]+)\s*\$/t", snippet, re.I)
            if not m_fas:
                raise ValueError(f"Could not find FAS for '{crop}' in MAGyP HTML")

            quotes[crop] = {
                "fob_usd_t": parse_argentine_number(m_fob.group(1)),
                "fas_ars_t": parse_argentine_number(m_fas.group(1)),
            }

        return {
            "date": iso_date,
            "quotes": quotes,
        }

    def fetch(self) -> dict:
        """Fetch and parse MAGyP official spot prices."""
        html = http_get(self.URL)
        return self.parse(html)


class BcraFxFeed:
    """Official wholesale exchange rate from the Central Bank of Argentina (BCRA)."""

    URL = "https://api.bcra.gob.ar/estadisticas/v4.0/Monetarias/5"

    def fetch_rate(self, target_date_iso: str | None = None) -> float:
        """Fetch the official wholesale ARS/USD rate (Communication A 3500)."""
        content = http_get(self.URL)
        data = json.loads(content)
        results = data.get("results", [])
        if not results:
            raise ValueError("No results in BCRA response")

        detalle = results[0].get("detalle", [])
        if not detalle:
            raise ValueError("No exchange rate records in BCRA response")

        if target_date_iso:
            for item in detalle:
                if item.get("fecha") == target_date_iso:
                    return float(item["valor"])

        # Fallback to the latest available date
        return float(detalle[0]["valor"])


def compute_argentine_basis(
    magyp_data: dict, fx_rate: float, cbot_snapshot: dict
) -> dict[str, float]:
    """Basis per crop = FAS in USD/t - nearest CBOT price (USD/t).

    Sunflower has no CBOT contract, basis is 0.0.
    """
    basis: dict[str, float] = {}
    for crop in ("wheat", "corn", "soybean"):
        fas_ars = magyp_data["quotes"][crop]["fas_ars_t"]
        fas_usd = fas_ars / fx_rate

        cbot_contracts = cbot_snapshot.get("curve", {}).get(crop, {})
        if not cbot_contracts:
            raise ValueError(f"No CBOT contracts found for {crop} to compute basis")

        nearest_month = min(cbot_contracts.keys())
        nearest_cents = cbot_contracts[nearest_month]
        nearest_usd = cents_per_bushel_to_usd_per_tonne(crop, nearest_cents)
        basis[crop] = round(fas_usd - nearest_usd, 2)

    basis["sunflower"] = 0.0
    return basis


def build_argentine_curve(
    magyp_data: dict, fx_rate: float, cbot_snapshot: dict, basis: dict[str, float]
) -> dict:
    """Argentine curve = CBOT curve + basis. Sunflower uses flat FAS price."""
    curve: dict[str, dict[str, float]] = {}
    for crop in ("wheat", "corn", "soybean"):
        curve[crop] = {}
        for month, cents in cbot_snapshot.get("curve", {}).get(crop, {}).items():
            cbot_usd = cents_per_bushel_to_usd_per_tonne(crop, cents)
            curve[crop][month] = round(cbot_usd + basis[crop], 2)

    sunflower_fas_usd = round(magyp_data["quotes"]["sunflower"]["fas_ars_t"] / fx_rate, 2)
    all_months = sorted({m for crop_curve in curve.values() for m in crop_curve.keys()})
    curve["sunflower"] = {m: sunflower_fas_usd for m in all_months}

    return {
        "source": "MAGyP official spot prices and CBOT futures via Yahoo Finance",
        "as_of": magyp_data["date"],
        "unit": "usd/t",
        "placeholder": False,
        "curve": curve,
    }


def refresh(
    feed: YahooCbotFeed | None = None,
    max_age_hours: float = 24.0,
    target_path: Path | None = None,
) -> dict:
    """Refresh the CBOT curve snapshot and Argentine curve.

    Writes dora/data/price_curves/cbot_latest.json only if older than max_age_hours.
    Never overwrites with an empty or partial fetch (<2 contracts per crop).
    On network error, keeps the last file.
    """
    if target_path is None:
        target_path = CBOT_LATEST_PATH

    # Check cache freshness
    if target_path.is_file() and max_age_hours > 0:
        try:
            mtime = target_path.stat().st_mtime
            age_hours = (time.time() - mtime) / 3600.0
            if age_hours < max_age_hours:
                data = json.loads(target_path.read_text(encoding="utf-8"))
                total_contracts = sum(len(c) for c in data.get("curve", {}).values())
                return {
                    "status": "fresh",
                    "as_of": data.get("as_of", ""),
                    "contracts": total_contracts,
                }
        except Exception:
            pass

    # Attempt fetch
    try:
        if feed is None:
            feed = YahooCbotFeed()
        snapshot = feed.fetch()
    except Exception:
        if target_path.is_file():
            try:
                data = json.loads(target_path.read_text(encoding="utf-8"))
                total_contracts = sum(len(c) for c in data.get("curve", {}).values())
                return {
                    "status": "kept_last",
                    "as_of": data.get("as_of", ""),
                    "contracts": total_contracts,
                }
            except Exception:
                pass
        return {"status": "kept_last", "as_of": "", "contracts": 0}

    # Validate against empty or partial fetch (at least 2 contracts per crop)
    curve_data = snapshot.get("curve", {})
    for crop in ("corn", "soybean", "wheat"):
        if len(curve_data.get(crop, {})) < 2:
            if target_path.is_file():
                try:
                    data = json.loads(target_path.read_text(encoding="utf-8"))
                    total_contracts = sum(len(c) for c in data.get("curve", {}).values())
                    return {
                        "status": "kept_last",
                        "as_of": data.get("as_of", ""),
                        "contracts": total_contracts,
                    }
                except Exception:
                    pass
            return {"status": "kept_last", "as_of": "", "contracts": 0}

    # Successful fetch: write cbot_latest.json
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    total_contracts = sum(len(c) for c in curve_data.values())

    # Refresh Argentine curve and basis
    try:
        magyp = MagypPricesFeed()
        magyp_data = magyp.fetch()
        bcra = BcraFxFeed()
        fx_rate = bcra.fetch_rate(magyp_data["date"])
        basis = compute_argentine_basis(magyp_data, fx_rate, snapshot)

        basis_doc = {
            "source": "MAGyP FAS vs CBOT nearest futures",
            "as_of": magyp_data["date"],
            "unit": "usd/t",
            "placeholder": False,
            "basis": basis,
        }
        BASIS_ARGENTINA_PATH.write_text(json.dumps(basis_doc, indent=2), encoding="utf-8")

        arg_snap = build_argentine_curve(magyp_data, fx_rate, snapshot, basis)
        ARGENTINA_LATEST_PATH.write_text(json.dumps(arg_snap, indent=2), encoding="utf-8")
    except Exception:
        pass

    return {
        "status": "updated",
        "as_of": snapshot.get("as_of", ""),
        "contracts": total_contracts,
    }


if __name__ == "__main__":
    result = refresh(max_age_hours=0)
    print(f"CBOT refresh status: {result['status']}, as_of: {result.get('as_of')}, contracts: {result.get('contracts')}")
    if CBOT_LATEST_PATH.is_file():
        snap = json.loads(CBOT_LATEST_PATH.read_text(encoding="utf-8"))
        print("\nCBOT Latest Curve (cents/bu):")
        for c, contracts in snap.get("curve", {}).items():
            print(f"  {c}:")
            for m, p in sorted(contracts.items()):
                print(f"    {m}: {p}")
