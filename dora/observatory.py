"""DORA Regional Observatory: tracking grain production economics across key regions.

Monitors Southeast Buenos Aires, Pampas Core (Pergamino), Iowa (Central),
and Mato Grosso (Sorriso), calculating return on capital, shadow prices,
crop mix, and impact of freight to port.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from .engine import FORTNIGHTS, fortnight_name, optimize
from .scenario import REGIONS, Scenario, fortnight_month, normalize_region, load_land_data
from .verifier import verify

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OBSERVATORY_DIR = ROOT / "observatory"

DEFAULT_REGIONS = ["southeast_buenos_aires", "pampas_core", "iowa", "mato_grosso"]


def run_observatory(
    regions: list[str] | None = None,
    scenario_template: dict[str, Any] | None = None,
    client: Any = None,
    model: str = "default",
    output_dir: Path | str | None = None,
    save: bool = True,
) -> dict[str, Any]:
    """Run observatory optimization over specified regions and optionally save report."""
    target_regions = regions if regions is not None else DEFAULT_REGIONS
    out_dir = Path(output_dir) if output_dir is not None else DEFAULT_OBSERVATORY_DIR

    tmpl = dict(scenario_template) if scenario_template else {}
    area_ha = float(tmpl.get("area_ha", 500.0))
    user_own_capital = tmpl.get("own_capital_usd")
    user_credit_line = tmpl.get("credit_line_usd")
    storage_capacity_t = float(tmpl.get("storage_capacity_t", 2.0 * area_ha))
    credit_rate_annual = float(tmpl.get("credit_rate_annual", 0.10))
    deposit_rate_annual = float(tmpl.get("deposit_rate_annual", 0.04))
    monthly_price_rise = float(tmpl.get("monthly_price_rise", 0.008))

    now = datetime.now(timezone.utc)
    date_str = tmpl.get("date", now.strftime("%Y-%m-%d"))
    timestamp_str = now.isoformat()

    regions_output: dict[str, Any] = {}

    for r_raw in target_regions:
        reg_key = normalize_region(r_raw)
        if reg_key not in REGIONS:
            continue
        reg_info = REGIONS[reg_key]

        # Determine freight to port
        freight = float(tmpl.get("freight_usd_t", reg_info.get("default_freight_usd_t", 0.0)))

        # Determine price curve source
        curve_source = tmpl.get("price_curve_source")
        if curve_source is None:
            if reg_key in ("southeast_buenos_aires", "pampas_core"):
                curve_source = "argentina_latest"
            else:
                curve_source = "cbot_latest"

        # Determine capital and credit: if not specified, calibrate to ~50% of direct costs per ha
        data_file = reg_info["data_file"]
        raw_reg_data = json.loads(data_file.read_text(encoding="utf-8"))
        raw_crops = raw_reg_data.get("crops", {})
        reg_crops = reg_info.get("crops", tuple(raw_crops.keys()))
        direct_costs = [
            raw_crops[c].get("field_operations", 0) + raw_crops[c].get("seed", 0) +
            raw_crops[c].get("crop_protection", 0) + raw_crops[c].get("fertilizer", 0)
            for c in reg_crops if c in raw_crops
        ]
        avg_direct_cost = (sum(direct_costs) / len(direct_costs)) if direct_costs else 400.0

        if user_own_capital is not None:
            reg_own_capital = float(user_own_capital)
            reg_credit_line = float(user_credit_line) if user_credit_line is not None else 200.0 * area_ha
        else:
            reg_own_capital = round(0.50 * avg_direct_cost * area_ha, 2)
            reg_credit_line = float(user_credit_line) if user_credit_line is not None else round(0.50 * avg_direct_cost * area_ha, 2)

        sc_kwargs = {
            "region": reg_key,
            "area_ha": area_ha,
            "own_capital_usd": reg_own_capital,
            "credit_line_usd": reg_credit_line,
            "storage_capacity_t": storage_capacity_t,
            "credit_rate_annual": credit_rate_annual,
            "deposit_rate_annual": deposit_rate_annual,
            "monthly_price_rise": monthly_price_rise,
            "freight_usd_t": freight,
            "price_curve_source": curve_source,
        }
        for k, v in tmpl.items():
            if k not in sc_kwargs and hasattr(Scenario, k):
                sc_kwargs[k] = v

        try:
            sc = Scenario(**sc_kwargs)
        except Exception:
            # Fallback to default prices if curve snapshot unavailable
            sc_kwargs["price_curve_source"] = None
            sc = Scenario(**sc_kwargs)

        res = optimize(sc)

        # Annualized rate of return on capital committed (season is 30 fortnights = 1.25 years)
        years = FORTNIGHTS / 24.0
        if sc.own_capital_usd > 0:
            wealth_ratio = max(0.0, res.final_wealth / sc.own_capital_usd)
            return_on_capital = round(wealth_ratio ** (1.0 / years) - 1.0, 4)
        else:
            return_on_capital = 0.0

        land_info = load_land_data(reg_key)
        is_placeholder = bool(raw_reg_data.get("placeholder", False) or land_info.get("placeholder", False))
        land_price_usd_ha = land_info.get("land_price_usd_ha", 0.0)
        total_cap_and_land = sc.own_capital_usd + sc.owned_ha * land_price_usd_ha
        if total_cap_and_land > 0:
            wealth_ratio_land = max(0.0, (sc.owned_ha * land_price_usd_ha + res.final_wealth) / total_cap_and_land)
            return_on_capital_and_land = round(wealth_ratio_land ** (1.0 / years) - 1.0, 4)
        else:
            return_on_capital_and_land = return_on_capital

        scarce_fortnights = [
            fortnight_name(p)
            for p in range(FORTNIGHTS - 1)
            if res.internal_rate_annual[p] > res.market_rate_annual + 1e-3
        ]

        crop_mix = {c: round(float(h), 1) for c, h in res.hectares.items() if h > 1e-3}
        crop_shares = {c: round(float(h) / sc.area_ha, 3) for c, h in res.hectares.items() if h > 1e-3}

        # Source description
        if sc.price_curve_metadata and sc.price_curve_metadata.get("source"):
            meta = sc.price_curve_metadata
            source_desc = f"{meta['source']} as of {meta.get('as_of', date_str)}"
        else:
            source_desc = f"MAGyP ({date_str})" if "buenos_aires" in reg_key or "core" in reg_key else f"ISU/IMEA ({date_str})"

        regions_output[reg_key] = {
            "key": reg_key,
            "name": reg_info.get("name", reg_key),
            "placeholder": is_placeholder,
            "port": reg_info.get("port", "Port"),
            "distance_km": reg_info.get("distance_km", 0),
            "coords": list(reg_info.get("coords", [0.0, 0.0])),
            "freight_usd_t": freight,
            "freight_source": reg_info.get("freight_source", ""),
            "area_ha": sc.area_ha,
            "land_price_usd_ha": land_price_usd_ha,
            "land_source": land_info.get("source", ""),
            "npv_usd": round(res.npv, 2),
            "npv_per_ha": round(res.npv / sc.area_ha, 2),
            "final_wealth_usd": round(res.final_wealth, 2),
            "capital_committed_usd": sc.own_capital_usd,
            "return_on_capital": return_on_capital,
            "return_on_capital_pct": round(return_on_capital * 100.0, 2),
            "return_on_capital_and_land": return_on_capital_and_land,
            "return_on_capital_and_land_pct": round(return_on_capital_and_land * 100.0, 2),
            "capital_shadow_price": round(res.capital_shadow_price, 4),
            "scarce_fortnights": scarce_fortnights,
            "land_shadow_price_usd_ha": round(res.land_shadow_price, 2),
            "storage_shadow_price_usd_t": round(sum(res.storage_shadow_price), 2),
            "crop_mix": crop_mix,
            "crop_shares": crop_shares,
            "price_source": source_desc,
            "price_curve_metadata": sc.price_curve_metadata,
            "internal_rates": [
                {
                    "fortnight": p,
                    "month": fortnight_month(sc.season_start, p),
                    "rate_annual": round(float(r), 4),
                }
                for p, r in enumerate(res.internal_rate_annual)
            ],
        }

    report = {
        "date": date_str,
        "timestamp": timestamp_str,
        "regions": regions_output,
        "commentary": None,
    }

    # Optional model commentary if API key or client is provided
    api_key = os.environ.get("DORA_API_KEY", "")
    if client is not None or api_key:
        report["commentary"] = _generate_commentary(report, client=client, model=model)

    if save:
        out_dir.mkdir(parents=True, exist_ok=True)
        latest_file = out_dir / "latest.json"
        dated_file = out_dir / f"{date_str}.json"

        content = json.dumps(report, indent=2, ensure_ascii=False)
        latest_file.write_text(content, encoding="utf-8")
        dated_file.write_text(content, encoding="utf-8")

    return report


def _generate_commentary(report: dict, client: Any = None, model: str = "default") -> str | None:
    """Generate ~120 word comparative commentary and verify all numbers before publishing."""
    try:
        from .agent import Agent

        # Prompt asking for ~120 words summary
        regions_summary = {
            k: {
                "name": v["name"],
                "return_on_capital_pct": v["return_on_capital_pct"],
                "npv_per_ha": v["npv_per_ha"],
                "capital_shadow_price": v["capital_shadow_price"],
                "freight_usd_t": v["freight_usd_t"],
                "port": v["port"],
            }
            for k, v in report["regions"].items()
        }
        prompt = (
            "Write a concise comparative analysis of about 120 words summarizing crop season economics across these regions:\n"
            f"{json.dumps(regions_summary, ensure_ascii=False)}\n"
            "Compare return on capital, capital bottlenecks, and the role of freight to port. "
            "CRITICAL REQUIREMENT: Every single number in your text must come directly from the data above. "
            "Never invent or round into numbers not supported by the data."
        )

        agent = Agent(client=client, model=model, use_verifier=False)
        reply = agent.ask(prompt)
        text = reply.text.strip()

        # Run verifier: any unsupported number blocks publication
        problems = verify(text, [report], [])
        if problems:
            return None
        return text
    except Exception:
        return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run DORA Regional Observatory")
    parser.add_argument("--regions", nargs="*", default=None, help="Regions to evaluate")
    parser.add_argument("--out", default=None, help="Output directory")
    args = parser.parse_args()

    result = run_observatory(regions=args.regions, output_dir=args.out)
    print(f"Observatory run completed for {len(result['regions'])} regions on {result['date']}.")
    for k, v in result["regions"].items():
        print(f" - {v['name']}: Return={v['return_on_capital_pct']}%, NPV/ha=${v['npv_per_ha']}")
