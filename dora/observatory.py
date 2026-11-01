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

from .engine import FORTNIGHTS, fortnight_name
from .scenario import REGIONS, fortnight_month, normalize_region, load_land_data
from .tools import compare_regions
from .verifier import verify

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OBSERVATORY_DIR = ROOT / "observatory"

DEFAULT_REGIONS = ["southeast_buenos_aires", "pampas_core", "iowa", "mato_grosso"]
SEASON_MONTHS = 14.5


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

    # Compute all regions by calling the same code as compare_regions(mode="same_farm")
    cr_entries: dict[str, Any] = {}
    if user_own_capital is not None:
        cr_res = compare_regions(scenario=tmpl, regions=target_regions, mode="same_farm")
        cr_entries = cr_res.get("regions", {})
    else:
        for r_raw in target_regions:
            reg_key = normalize_region(r_raw)
            if reg_key not in REGIONS:
                continue
            reg_info = REGIONS[reg_key]
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
            reg_own_capital = round(0.50 * avg_direct_cost * area_ha, 2)
            reg_credit_line = float(user_credit_line) if user_credit_line is not None else round(0.50 * avg_direct_cost * area_ha, 2)

            sub_tmpl = dict(tmpl, own_capital_usd=reg_own_capital, credit_line_usd=reg_credit_line)
            sub_res = compare_regions(scenario=sub_tmpl, regions=[reg_key], mode="same_farm")
            if reg_key in sub_res.get("regions", {}):
                cr_entries[reg_key] = sub_res["regions"][reg_key]
                cr_entries[reg_key]["_calibrated_capital"] = reg_own_capital

    regions_output: dict[str, Any] = {}

    for r_raw in target_regions:
        reg_key = normalize_region(r_raw)
        if reg_key not in REGIONS or reg_key not in cr_entries:
            continue
        reg_info = REGIONS[reg_key]
        cr_entry = cr_entries[reg_key]

        land_info = load_land_data(reg_key)
        land_price_usd_ha = land_info.get("land_price_usd_ha", 0.0)
        raw_reg_data = json.loads(reg_info["data_file"].read_text(encoding="utf-8"))
        is_placeholder = bool(raw_reg_data.get("placeholder", False) or land_info.get("placeholder", False))
        cap_committed = cr_entry.get("_calibrated_capital", float(tmpl.get("own_capital_usd", 50000.0)))
        final_wealth = cr_entry.get("profit_usd", 0.0) + cap_committed

        # Scarce fortnights
        internal_rates = cr_entry.get("internal_rate_annual", [])
        mkt_rate = float(cr_entry.get("deposit_rate_annual", deposit_rate_annual))
        scarce_fortnights = [
            fortnight_name(p)
            for p, r in enumerate(internal_rates)
            if r > mkt_rate + 1e-3
        ]

        crop_mix = {c: round(float(h), 1) for c, h in cr_entry.get("hectares", {}).items() if h > 1e-3}
        farmed_area = float(cr_entry.get("area_ha", area_ha))
        crop_shares = {c: round(float(h) / farmed_area, 3) for c, h in cr_entry.get("hectares", {}).items() if h > 1e-3}

        with_land = cr_entry.get("with_land_cost", {})
        farming_only = cr_entry.get("farming_only", {})

        price_src = cr_entry.get("price_source", "")
        if not price_src:
            price_src = f"MAGyP ({date_str})" if "buenos_aires" in reg_key or "core" in reg_key else f"ISU/IMEA ({date_str})"

        regions_output[reg_key] = {
            "key": reg_key,
            "name": reg_info.get("name", reg_key),
            "placeholder": is_placeholder,
            "provisional": cr_entry.get("provisional", []),
            "port": reg_info.get("port", "Port"),
            "distance_km": reg_info.get("distance_km", 0),
            "coords": list(reg_info.get("coords", [0.0, 0.0])),
            "freight_usd_t": cr_entry.get("freight_usd_t", 0.0),
            "freight_source": reg_info.get("freight_source", ""),
            "area_ha": farmed_area,
            "land_price_usd_ha": land_price_usd_ha,
            "land_source": land_info.get("source", ""),
            "npv_usd": cr_entry.get("npv_usd", 0.0),
            "npv_per_ha": cr_entry.get("npv_per_ha", 0.0),
            "final_wealth_usd": final_wealth,
            "capital_committed_usd": cap_committed,
            "return_on_capital": farming_only.get("return_on_capital", 0.0),
            "return_on_capital_pct": farming_only.get("return_on_capital_pct", 0.0),
            "return_on_capital_and_land": with_land.get("return_on_capital_and_land", 0.0),
            "return_on_capital_and_land_pct": with_land.get("return_on_capital_and_land_pct", 0.0),
            "capital_shadow_price": cr_entry.get("capital_shadow_price", 0.0),
            "scarce_fortnights": scarce_fortnights,
            "land_shadow_price_usd_ha": cr_entry.get("land_shadow_price_usd_ha", 0.0),
            "storage_shadow_price_usd_t": round(sum(cr_entry.get("storage_shadow_price", []) if isinstance(cr_entry.get("storage_shadow_price"), list) else []), 2),
            "crop_mix": crop_mix,
            "crop_shares": crop_shares,
            "price_source": price_src,
            "price_curve_metadata": cr_entry.get("price_curve_metadata"),
            "internal_rates": [
                {
                    "fortnight": p,
                    "month": fortnight_month("2026-05" if "iowa" not in reg_key else "2026-04", p),
                    "rate_annual": round(float(r), 4),
                }
                for p, r in enumerate(internal_rates)
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
        comm, err = _generate_commentary(report, client=client, model=model)
        report["commentary"] = comm
        if err:
            report["commentary_error"] = err

    if save:
        out_dir.mkdir(parents=True, exist_ok=True)
        latest_file = out_dir / "latest.json"
        dated_file = out_dir / f"{date_str}.json"

        content = json.dumps(report, indent=2, ensure_ascii=False)
        latest_file.write_text(content, encoding="utf-8")
        dated_file.write_text(content, encoding="utf-8")

    return report


def _generate_commentary(report: dict, client: Any = None, model: str | None = None) -> tuple[str | None, str | None]:
    """Generate ~120 word comparative commentary and verify all numbers before publishing."""
    model_name = os.environ.get("DORA_MODEL", "")
    if not model_name:
        if model and model != "default":
            model_name = model
        elif client is not None:
            model_name = "default"
        else:
            return None, "No model specified and DORA_MODEL environment variable is empty"

    try:
        from .agent import Agent

        lang = report.get("lang", "es")
        regions_summary = {
            k: {
                "name": v["name"],
                "return_on_capital_pct": f"{v['return_on_capital_pct']}%",
                "npv_per_ha": f"{v['npv_per_ha']} USD/ha",
                "capital_shadow_price": f"{v['capital_shadow_price']} USD",
                "freight_usd_t": f"{v['freight_usd_t']} USD/t",
                "port": v["port"],
                "provisional": v.get("provisional", []),
            }
            for k, v in report["regions"].items()
        }
        prompt = (
            f"Write a concise comparative analysis of about 120 words in {'Spanish' if lang == 'es' else 'English'} summarizing crop season economics across these regions:\n"
            f"{json.dumps(regions_summary, ensure_ascii=False)}\n"
            "Compare return on capital, capital bottlenecks, freight to port, and state the provisional data of each region. "
            "CRITICAL REQUIREMENT: Every single number in your text must have its unit (%, USD, USD/ha, USD/t) and come directly from the data above. "
            "Never invent or round into numbers not supported by the data."
        )

        agent = Agent(client=client, model=model_name, use_verifier=False)
        reply = agent.ask(prompt)
        text = reply.text.strip()

        # Run verifier: any unsupported number blocks publication
        problems = verify(text, [report], [])
        if problems:
            return None, f"Verification failed: {problems}"
        return text, None
    except Exception as e:
        return None, str(e)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run DORA Regional Observatory")
    parser.add_argument("--regions", nargs="*", default=None, help="Regions to evaluate")
    parser.add_argument("--out", default=None, help="Output directory")
    args = parser.parse_args()

    result = run_observatory(regions=args.regions, output_dir=args.out)
    print(f"Observatory run completed for {len(result['regions'])} regions on {result['date']}.")
    for k, v in result["regions"].items():
        print(f" - {v['name']}: Return={v['return_on_capital_pct']}%, NPV/ha=${v['npv_per_ha']}")
