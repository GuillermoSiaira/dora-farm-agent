"""The season engine: one linear program over fortnights.

It decides how many hectares of each crop to sow, when to sell, how much to
store and how much credit to take, to maximize the present value of wealth at
the end of the season. The duals of the constraints are the shadow prices:

- cash in fortnight p (λ_p): what one more dollar available in p is worth today.
  Without a capital shortage, λ_p = 1/(1+r)^p, with r the deposit rate.
  The internal rate between p and p+1 is λ_p/λ_{p+1} - 1.
- own capital: λ_0 - 1, what one more dollar of capital is worth beyond depositing it.
- land, storage and credit line: what one more unit of each is worth.

Solved with HiGHS (scipy.optimize.linprog), which returns the duals of every
constraint, single-variable ones included. docs/model.md maps each equation
to the lines below.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import linprog

from .scenario import CALENDAR, FORTNIGHTS, Scenario, ScenarioError, fortnight_name, fortnight_month, fortnightly_rate


@dataclass
class Result:
    npv: float                                  # present value of final wealth, USD
    final_wealth: float
    hectares: dict[str, float]
    sales: dict[str, dict[int, float]]          # crop -> fortnight -> tonnes
    stock: dict[str, dict[int, float]]
    cash: list[float]                           # surplus at the end of each fortnight
    debt: list[float]                           # credit used at the end of each fortnight
    cash_value: list[float]                     # λ_p
    internal_rate_annual: list[float]           # implied rate between p and p+1, annualized
    capital_shadow_price: float
    land_shadow_price: float                    # USD today per extra hectare
    storage_shadow_price: list[float]           # USD today per extra tonne of capacity, per fortnight
    credit_shadow_price: list[float]            # USD today per extra dollar of credit line, per fortnight
    market_rate_annual: float
    constraint_duals: list[float] = field(default_factory=list)
    rent_in_ha: float = 0.0
    rent_out_ha: float = 0.0
    buy_ha: float = 0.0
    owned_ha: float = 0.0
    land_price_usd_ha: float = 0.0
    regional_rent_usd_ha: float = 0.0
    return_on_capital: float = 0.0
    return_on_capital_and_land: float = 0.0
    season_months: float = 14.5
    return_on_capital_annual: float = 0.0
    return_on_capital_and_land_annual: float = 0.0
    hectares_livestock: dict[str, float] = field(default_factory=dict)
    livestock_only_shadow_price: float = 0.0
    livestock_only_ha: float = 0.0
    sales_by_route: dict[str, dict[str, dict[int, float]]] = field(default_factory=dict)
    tonnes_by_route: dict[str, float] = field(default_factory=dict)
    route_capacity_shadow_prices: dict[str, float] = field(default_factory=dict)
    leg_shadow_prices: dict[str, dict] = field(default_factory=dict)
    tonnes_by_leg: dict[str, float] = field(default_factory=dict)
    payment_term_ha: dict[str, dict[str, float]] = field(default_factory=dict)   # crop -> term -> ha (SPEC-19)
    storage_by_option: dict[str, dict] = field(default_factory=dict)             # option_id -> report (SPEC-20)
    rotation_shadow_price: dict[str, float] = field(default_factory=dict)        # crop -> USD/ha of cap (SPEC-21)
    land_row_shadow_price: float = 0.0
    livestock_share_shadow_price: float = 0.0
    rent_out_bound_shadow_price: float = 0.0
    hectares_by_window: dict[str, dict[str, float]] = field(default_factory=dict) # crop -> window -> ha (SPEC-25)
    harvest_t_by_fortnight: dict[int, float] = field(default_factory=dict)         # p -> total tonnes harvested (SPEC-25)
    sowing_windows_used: list[dict] = field(default_factory=list)                 # metadata of active windows (SPEC-25)
    sowing_capacity_shadow_prices: dict[int, float] = field(default_factory=dict) # fortnight -> USD/ha (SPEC-25)
    harvest_capacity_shadow_prices: dict[int, float] = field(default_factory=dict) # fortnight -> USD/ha (SPEC-25)
    double_cropped_ha: dict[str, float] = field(default_factory=dict)              # pair -> ha (SPEC-25 amendment)
    double_crop_shadow_prices: dict[str, float] = field(default_factory=dict)      # prec or pair -> USD/ha (SPEC-25 amendment)
    expected_npv: float | None = None                                               # expected NPV (SPEC-25)
    value_of_stochastic_solution_usd: float | None = None                           # VSS (SPEC-25)
    climate_results: dict[str, dict] = field(default_factory=dict)                  # per-climate details (SPEC-25)


    def get_capital_stretches(self, lang: str = "en") -> list[dict]:
        scarce = [p for p in range(len(self.cash_value) - 1)
                  if self.internal_rate_annual[p] > self.market_rate_annual + 1e-3]
        if not scarce:
            return []

        runs = []
        curr_run = [scarce[0]]
        for p in scarce[1:]:
            if p == curr_run[-1] + 1:
                curr_run.append(p)
            else:
                runs.append(curr_run)
                curr_run = [p]
        runs.append(curr_run)

        stretches = []
        for run in runs:
            s = run[0]
            e = min(run[-1] + 1, len(self.cash_value) - 1)
            worst_p = max(run, key=lambda p: self.internal_rate_annual[p])
            rate_stretch = float(self.cash_value[s] / self.cash_value[e] - 1.0)
            stretches.append({
                "start_fortnight": fortnight_name(s, lang),
                "end_fortnight": fortnight_name(e, lang),
                "start_fortnight_idx": s,
                "end_fortnight_idx": e,
                "duration_days": (e - s) * 15,
                "duration_months": round((e - s) / 2),     # so the agent can say "en esos N meses" without computing
                "rate_for_stretch": round(rate_stretch, 4),
                "rate_for_stretch_pct": round(rate_stretch * 100.0, 1),
                "worst_fortnight": fortnight_name(worst_p, lang),
                "worst_fortnight_idx": worst_p,
                "worst_internal_rate_annual": round(float(self.internal_rate_annual[worst_p]), 4),
                "capital_shadow_price_today": round(float(self.capital_shadow_price), 4),
                "capital_shadow_price_meaning": "what one more dollar of own capital is worth today, for the whole season; the stretch's own figure is rate_for_stretch",
            })
        return stretches

    def summary(self, lang: str = "en") -> dict:
        def r(x, n=2):
            return round(float(x), n)
        out = {
            "npv_usd": r(self.npv),
            "final_wealth_usd": r(self.final_wealth),
            "hectares": {c: r(h, 1) for c, h in self.hectares.items() if h > 1e-6},
            "rent_in_ha": r(self.rent_in_ha, 1),
            "rent_out_ha": r(self.rent_out_ha, 1),
            "buy_ha": r(self.buy_ha, 1),
            "season_months": self.season_months,
            "return_on_capital": r(self.return_on_capital, 4),
            "return_on_capital_pct": round(100.0 * self.return_on_capital, 1),
            "return_on_capital_annual": r(self.return_on_capital_annual, 4),
            "return_on_capital_annual_pct": round(100.0 * self.return_on_capital_annual, 1),
            "return_on_capital_pct": round(100.0 * self.return_on_capital, 1),
            "return_on_capital_and_land": r(self.return_on_capital_and_land, 4),
            "return_on_capital_and_land_pct": round(100.0 * self.return_on_capital_and_land, 1),
            "return_on_capital_and_land_annual": r(self.return_on_capital_and_land_annual, 4),
            "return_on_capital_and_land_annual_pct": round(100.0 * self.return_on_capital_and_land_annual, 1),
            "deposit_rate_annual": r(self.market_rate_annual, 4),
            "deposit_rate_annual_pct": round(100.0 * self.market_rate_annual, 1),
            "max_credit_usd": r(max(self.debt)),
            "capital_shadow_price": r(self.capital_shadow_price, 4),
            "usd_today_per_extra_dollar": r(self.capital_shadow_price, 4),
            "land_shadow_price_usd_ha": r(self.land_shadow_price),
            "storage_shadow_price_usd_t": r(sum(self.storage_shadow_price)),
            "credit_line_shadow_price": r(sum(self.credit_shadow_price), 4),
            "fortnights_with_scarce_capital": [fortnight_name(p, lang) for p in range(FORTNIGHTS - 1)
                                                if self.internal_rate_annual[p] > self.market_rate_annual + 1e-3],
            "capital_stretches": self.get_capital_stretches(lang),
        }
        if self.hectares_livestock:
            out["hectares_livestock"] = {a: r(h, 1) for a, h in self.hectares_livestock.items() if h > 1e-6}
        if self.livestock_only_ha > 0 or self.livestock_only_shadow_price > 0:
            out["livestock_only_shadow_price_usd_ha"] = r(self.livestock_only_shadow_price)
        if self.tonnes_by_route:
            out["tonnes_by_route"] = {k: r(v, 1) for k, v in self.tonnes_by_route.items()}
        if self.route_capacity_shadow_prices:
            out["route_capacity_shadow_prices"] = {k: r(v, 4) for k, v in self.route_capacity_shadow_prices.items()}
        if self.leg_shadow_prices:
            out["leg_shadow_prices"] = self.leg_shadow_prices
        if self.tonnes_by_leg:
            out["tonnes_by_leg"] = {k: r(v, 1) for k, v in self.tonnes_by_leg.items()}
        if any(v > 1e-6 for v in self.rotation_shadow_price.values()):
            out["rotation_shadow_price_usd_ha"] = {c: r(v) for c, v in self.rotation_shadow_price.items() if v > 1e-6}
        if self.hectares_by_window:
            out["hectares_by_window"] = {
                c: {w: r(h, 1) for w, h in wmap.items() if h > 1e-6}
                for c, wmap in self.hectares_by_window.items()
                if any(h > 1e-6 for h in wmap.values())
            }
        if self.harvest_t_by_fortnight:
            out["harvest_t_by_fortnight"] = {p: r(t, 1) for p, t in self.harvest_t_by_fortnight.items() if t > 1e-6}
        if self.sowing_capacity_shadow_prices:
            out["sowing_capacity_shadow_prices"] = {p: r(v, 4) for p, v in self.sowing_capacity_shadow_prices.items() if v > 1e-6}
        if self.harvest_capacity_shadow_prices:
            out["harvest_capacity_shadow_prices"] = {p: r(v, 4) for p, v in self.harvest_capacity_shadow_prices.items() if v > 1e-6}
        if self.double_cropped_ha:
            out["double_cropped_ha"] = {k: r(v, 1) for k, v in self.double_cropped_ha.items() if v > 1e-6}
        if self.double_crop_shadow_prices:
            out["double_crop_shadow_prices"] = {k: r(v, 2) for k, v in self.double_crop_shadow_prices.items() if v > 1e-6}
        if any(w.get("placeholder") for w in self.sowing_windows_used):
            out["sowing_windows_placeholders"] = [w for w in self.sowing_windows_used if w.get("placeholder")]
        return out




class PairDict(dict):
    def __getitem__(self, key):
        if key in self:
            return super().__getitem__(key)
        if isinstance(key, str):
            alt = key.replace("/", "_") if "/" in key else key.replace("_", "/")
            if alt in self:
                return super().__getitem__(alt)
        return super().__getitem__(key)

    def get(self, key, default=None):
        if key in self:
            return super().get(key, default)
        if isinstance(key, str):
            alt = key.replace("/", "_") if "/" in key else key.replace("_", "/")
            if alt in self:
                return super().get(alt, default)
        return default


class _Index:
    def __init__(self):
        self.n = 0

    def new(self) -> int:
        self.n += 1
        return self.n - 1


def optimize(sc: Scenario) -> Result:
    if sc.climate_scenarios:
        return _optimize_stochastic(sc)

    T = FORTNIGHTS
    ri, rc = fortnightly_rate(sc.deposit_rate_annual), fortnightly_rate(sc.credit_rate_annual)
    storage_opts = sc.effective_storage_options()
    cal = getattr(sc, "calendar", CALENDAR)
    idx = _Index()

    # Pre-flight validation on forward sale dates
    sy, sm = int(sc.season_start[:4]), int(sc.season_start[5:7])
    for c in sc.constraints:
        if c["type"] == "forward_sale":
            y, m = int(c["month"][:4]), int(c["month"][5:7])
            offset = (y - sy) * 12 + (m - sm)
            p_k = 2 * offset
            crop = c["crop"]
            h = cal[crop]["harvest"]
            if p_k < h:
                raise ScenarioError(
                    f"Forward sale month '{c['month']}' (fortnight {p_k}) is before harvest of {crop} (fortnight {h})."
                )
            if p_k >= T:
                raise ScenarioError(
                    f"Forward sale month '{c['month']}' (fortnight {p_k}) is beyond the season."
                )

    # Check obvious area infeasibilities before solver
    total_land = sc.owned + sc.rent_in_cap + sc.max_buy_ha
    min_areas = [c for c in sc.constraints if c["type"] == "min_area"]
    if sum(c["ha"] for c in min_areas) > total_land:
        names = [f"min_area of {c['crop']} ({c['ha']} ha)" for c in min_areas]
        raise ScenarioError(f"The scenario is infeasible: {', '.join(names)} exceed total land ({total_land} ha).")

    win_map = sc.resolved_sowing_windows()   # crop -> list of window dicts
    H_crops = {c: sorted(set(int(w["harvest"]) for w in win_map[c])) for c in sc.crops}
    h_c0_map = {c: min(H_crops[c]) for c in sc.crops}

    # Validate 'after' windows (SPEC-25 amendment)
    for c in sc.crops:
        for w in win_map[c]:
            after_crop = w.get("after")
            if after_crop:
                if after_crop not in sc.crops:
                    raise ScenarioError(
                        f"Window '{w.get('id', '')}' of {c} specifies 'after': '{after_crop}', "
                        f"but '{after_crop}' is not a valid crop in {sc.region}."
                    )
                H_prec = H_crops[after_crop]
                if int(w["sowing"]) < min(H_prec):
                    raise ScenarioError(
                        f"Window '{w.get('id', '')}' of {c} declares 'after': '{after_crop}', "
                        f"but its sowing fortnight {w['sowing']} is before harvest of {after_crop} ({min(H_prec)})."
                    )

    ha = {c: idx.new() for c in sc.crops}
    ha_w = {}
    for c in sc.crops:
        wins = win_map[c]
        if len(wins) == 1:
            ha_w[c, wins[0]["id"]] = ha[c]
        else:
            for w in wins:
                ha_w[c, w["id"]] = idx.new()

    terms = sc.payment_terms() if sc.payment_options else []
    z = {}
    if terms:
        for c in sc.crops:
            for w in win_map[c]:
                wid = w["id"]
                for t in terms:
                    z[c, wid, t["id"]] = idx.new()

    rent_in = idx.new()
    rent_out = idx.new()
    buy = idx.new()

    y = {}
    y_low = {}
    if sc.livestock:
        for a in sc.livestock:
            y[a] = idx.new()
            if sc.livestock_only_ha > 0:
                y_low[a] = idx.new()

    routes = sc.routes if hasattr(sc, "routes") and sc.routes else [
        {
            "id": "default",
            "name": f"Direct freight ({sc.freight_usd_t:.1f} USD/t)",
            "capacity_t": None,
            "legs": [{"mode": "truck", "from": "farm", "to": "terminal", "usd_t": float(sc.freight_usd_t)}],
        }
    ]

    sell, put_in, stock_opt, take_out = {}, {}, {}, {}
    for c in sc.crops:
        H_c = H_crops[c]
        h0 = h_c0_map[c]
        for p in H_c:
            for opt in storage_opts:
                put_in[c, p, opt["id"]] = idx.new()
        for p in range(h0, T):
            for opt in storage_opts:
                m = opt["id"]
                stock_opt[c, p, m] = idx.new()
                if p > h0:
                    take_out[c, p, m] = idx.new()
            for r in routes:
                sell[c, p, r["id"]] = idx.new()
    S = [idx.new() for _ in range(T)]
    D = [idx.new() for _ in range(T)]

    # Forward sale variables f_k >= 0 per commitment
    forward_vars = []
    for i, c in enumerate(sc.constraints):
        if c["type"] == "forward_sale":
            y, m = int(c["month"][:4]), int(c["month"][5:7])
            offset = (y - sy) * 12 + (m - sm)
            p_k = 2 * offset
            f_k = idx.new()
            forward_vars.append((i, c, f_k, p_k))

    # Objective: maximize the present value of final wealth (linprog minimizes).
    discount = (1 + ri) ** -(T - 1)
    obj = np.zeros(idx.n)
    obj[S[-1]], obj[D[-1]] = -discount, discount

    # End value of bought land adds to final wealth
    end_value = sc.land_price_usd_ha * ((1 + sc.land_appreciation_annual) ** (T / 24))
    if sc.max_buy_ha > 0 or sc.land_price_usd_ha > 0:
        obj[buy] -= discount * end_value

    if sc.livestock:
        for a in sc.livestock:
            herd_ev = sc.livestock_herd_end_value(a)
            if herd_ev > 0:
                obj[y[a]] -= discount * herd_ev
                if a in y_low:
                    obj[y_low[a]] -= discount * herd_ev


    # Equalities: cash in every fortnight, grain stock of every crop.
    A_eq, b_eq = [], []
    fixed_pay = {(c, w["id"]): sc.fixed_payments_per_ha_window(c, w) for c in sc.crops for w in win_map[c]}
    if terms:
        term_pay = {(c, w["id"], t["id"]): sc.input_payments_per_ha_window(c, w, t["delay_fortnights"], t["surcharge"],
                                                                           t["installments"], t["every_fortnights"])
                    for c in sc.crops for w in win_map[c] for t in terms}
    else:
        base = sc.payment_terms()[0]
        term_pay = {}
        for c in sc.crops:
            for w in win_map[c]:
                inp = sc.input_payments_per_ha_window(c, w, base["delay_fortnights"], base["surcharge"])
                for p, amt in inp.items():
                    fixed_pay[c, w["id"]][p] = fixed_pay[c, w["id"]].get(p, 0.0) + amt

    def add_payments(row, c, p):
        """Coefficients of the per-hectare payments of crop c falling in fortnight p."""
        for w in win_map[c]:
            wid = w["id"]
            row[ha_w[c, wid]] += fixed_pay[c, wid].get(p, 0.0)
            if terms:
                for t in terms:
                    row[z[c, wid, t["id"]]] += term_pay[c, wid, t["id"]].get(p, 0.0)
    tx_pay = 1.0 + sc.transaction_tax_rate if sc.transaction_tax_rate > 0 else 1.0
    tx_rec = 1.0 - sc.transaction_tax_rate if sc.transaction_tax_rate > 0 else 1.0

    for p in range(T):
        row = np.zeros(idx.n)
        row[S[p]], row[D[p]] = 1, -1
        if p > 0:
            row[S[p - 1]], row[D[p - 1]] = -(1 + ri), 1 + rc
        for c in sc.crops:
            add_payments(row, c, p)
            H_c = H_crops[c]
            h0 = h_c0_map[c]
            if p in H_c:
                for opt in storage_opts:
                    fill_c = float(opt.get("fill_cost_usd_t", 0.0))
                    if fill_c:
                        row[put_in[c, p, opt["id"]]] += fill_c
            if p >= h0:
                for opt in storage_opts:
                    row[stock_opt[c, p, opt["id"]]] += float(opt.get("monthly_cost_usd_t", 0.0)) / 2.0
                for r in routes:
                    net_p = sc.net_price_route(c, p, r)
                    row[sell[c, p, r["id"]]] = -net_p

        for (_, c_fwd, f_k, p_k) in forward_vars:
            if p == p_k:
                crop = c_fwd["crop"]
                # The contract price is quoted at the price point: freight to it is paid once, by the
                # first route, and marketing excludes it (SPEC-17).
                freight_fwd = sc.inland_cost(routes[0], p) if sc.price_point == "port" else 0.0
                net_fwd_price = float(c_fwd["price_usd_t"]) - sc.marketing_per_t(crop) - freight_fwd
                if sc.gross_receipts_rate > 0:
                    net_fwd_price -= sc.gross_receipts_rate * float(c_fwd["price_usd_t"])
                if sc.transaction_tax_rate > 0:
                    net_fwd_price -= sc.transaction_tax_rate * float(c_fwd["price_usd_t"])
                row[f_k] += -net_fwd_price

        if p == 0:
            # Rent in outflow
            row[rent_in] += sc.regional_rent_usd_ha * tx_pay
            # Rent out inflow
            row[rent_out] -= sc.regional_rent_usd_ha * tx_rec
            # Buy land outflow: purchase price + property tax
            row[buy] += (sc.land_price_usd_ha * tx_pay + sc.land_tax_usd_ha_year)

        if sc.livestock:
            for a in sc.livestock:
                # Operational payments
                ls_pay = sc.livestock_payments_per_ha(a)
                if p in ls_pay:
                    row[y[a]] += ls_pay[p]
                    if a in y_low:
                        row[y_low[a]] += ls_pay[p]
                # Herd purchase outflow at p=0
                if p == 0:
                    herd_price = sc.livestock_herd_purchase_price(a)
                    if herd_price > 0:
                        outflow = herd_price * tx_pay
                        row[y[a]] += outflow
                        if a in y_low:
                            row[y_low[a]] += outflow
                # Livestock income at sale fortnight
                sale_p, net_income = sc.livestock_net_income(a)
                if p == sale_p:
                    row[y[a]] -= net_income
                    if a in y_low:
                        row[y_low[a]] -= net_income


        A_eq.append(row)
        if p == 0:
            b_eq.append(sc.own_capital_usd - sc.land_tax_usd_ha_year * sc.owned)
        else:
            b_eq.append(0.0)

    for c in sc.crops:
        H_c = H_crops[c]
        h0 = h_c0_map[c]
        for p in range(h0, T):
            # Sales and inflow balance at fortnight p
            row = np.zeros(idx.n)
            for r in routes:
                row[sell[c, p, r["id"]]] = 1.0
            for (_, c_fwd, f_k, p_k) in forward_vars:
                if c_fwd["crop"] == c and p_k == p:
                    row[f_k] += 1.0
            if p in H_c:
                for opt in storage_opts:
                    row[put_in[c, p, opt["id"]]] = 1.0
            if p > h0:
                for opt in storage_opts:
                    row[take_out[c, p, opt["id"]]] = -1.0
            for w in win_map[c]:
                if w["harvest"] == p:
                    row[ha_w[c, w["id"]]] -= float(w["yield_t_ha"])
            A_eq.append(row)
            b_eq.append(0.0)

            # Stock evolution for each option m at fortnight p
            for opt in storage_opts:
                m = opt["id"]
                keep_entry = 1.0 - float(opt.get("shrink_at_entry", 0.0))
                row = np.zeros(idx.n)
                row[stock_opt[c, p, m]] = 1.0
                if p > h0:
                    keep_fortnight = (1.0 - float(opt.get("shrink_monthly", 0.0))) ** 0.5
                    row[stock_opt[c, p - 1, m]] = -keep_fortnight
                    row[take_out[c, p, m]] = 1.0
                if p in H_c:
                    row[put_in[c, p, m]] = -keep_entry
                A_eq.append(row)
                b_eq.append(0.0)

    # Forward sale delivery equalities: f_k = tonnes
    forward_eq_rows = {}
    for (i, c_fwd, f_k, _) in forward_vars:
        row = np.zeros(idx.n)
        row[f_k] = 1.0
        forward_eq_rows[i] = len(A_eq)
        A_eq.append(row)
        b_eq.append(float(c_fwd["tonnes"]))

    # Sowing windows area split for crops with multiple windows
    for c in sc.crops:
        if len(win_map[c]) > 1:
            row = np.zeros(idx.n)
            row[ha[c]] = -1.0
            for w in win_map[c]:
                row[ha_w[c, w["id"]]] = 1.0
            A_eq.append(row)
            b_eq.append(0.0)

    # The hectares of each crop (or window) are split among the supplier terms.
    if terms:
        for c in sc.crops:
            wins = win_map[c]
            if len(wins) == 1:
                wid = wins[0]["id"]
                row = np.zeros(idx.n)
                row[ha[c]] = -1.0
                for t in terms:
                    row[z[c, wid, t["id"]]] = 1.0
                A_eq.append(row)
                b_eq.append(0.0)
            else:
                for w in wins:
                    wid = w["id"]
                    row = np.zeros(idx.n)
                    row[ha_w[c, wid]] = -1.0
                    for t in terms:
                        row[z[c, wid, t["id"]]] = 1.0
                    A_eq.append(row)
                    b_eq.append(0.0)

    # Inequalities: land, storage per fortnight, credit line per fortnight.
    A_ub, b_ub = [], []
    row = np.zeros(idx.n)
    for c in sc.crops:
        for w in win_map[c]:
            if not w.get("after"):
                row[ha_w[c, w["id"]]] += 1.0
    if sc.livestock:
        for a in sc.livestock:
            row[y[a]] = 1.0
    row[rent_in] = -1.0
    row[buy] = -1.0
    row[rent_out] = 1.0
    A_ub.append(row); b_ub.append(sc.owned)

    # Rotation on the land held H = owned + rent_in + buy - rent_out (SPEC-21):
    # Second crops on 'after' do not count toward the rotation share of land held (SPEC-25 amendment)
    rotation_ub_rows = {}
    share = float(sc.max_crop_share)
    for c in sc.crops:
        rotation_ub_rows[c] = len(A_ub)
        row = np.zeros(idx.n)
        for w in win_map[c]:
            if not w.get("after"):
                row[ha_w[c, w["id"]]] += 1.0
        row[rent_in] = -share
        row[buy] = -share
        row[rent_out] = share
        A_ub.append(row)
        b_ub.append(share * sc.owned)

    # After constraints: second crops cannot exceed the preceding crop sown (SPEC-25 amendment)
    after_ub_rows = {}
    for prec in sc.crops:
        second_windows = [
            (c_other, w)
            for c_other in sc.crops
            for w in win_map[c_other]
            if w.get("after") == prec
        ]
        if second_windows:
            row = np.zeros(idx.n)
            for c_other, w in second_windows:
                row[ha_w[c_other, w["id"]]] += 1.0
            row[ha[prec]] -= 1.0
            after_ub_rows[prec] = len(A_ub)
            A_ub.append(row)
            slack = 0.0
            if getattr(sc, "double_crop_slack_ha", None) is not None:
                if isinstance(sc.double_crop_slack_ha, dict):
                    slack = float(sc.double_crop_slack_ha.get(prec, 0.0))
                else:
                    slack = float(sc.double_crop_slack_ha)
            b_ub.append(slack)

    livestock_share_row = None

    cattle_land_row = None
    if sc.livestock and sc.livestock_only_ha > 0:
        cattle_land_row = len(A_ub)
        row = np.zeros(idx.n)
        for a in sc.livestock:
            if a in y_low:
                row[y_low[a]] = 1.0
        A_ub.append(row)
        b_ub.append(sc.livestock_only_ha)

    if sc.livestock and sc.max_livestock_share is not None:
        row = np.zeros(idx.n)
        for a in sc.livestock:
            row[y[a]] = 1.0
        A_ub.append(row)
        m_ls = float(sc.max_livestock_share)
        row[rent_in] = -m_ls
        row[buy] = -m_ls
        row[rent_out] = m_ls
        livestock_share_row = len(A_ub) - 1
        b_ub.append(m_ls * sc.owned)

    storage_ub_rows = {}
    for opt in storage_opts:
        cap = opt.get("capacity_t")
        if cap is not None:
            m = opt["id"]
            storage_ub_rows[m] = len(A_ub)
            cap_val = float(cap)
            for p in range(T):
                row = np.zeros(idx.n)
                for c in sc.crops:
                    if (c, p, m) in stock_opt:
                        row[stock_opt[c, p, m]] = 1.0
                A_ub.append(row)
                b_ub.append(cap_val)
    sowing_cap_rows = {}
    if sc.sowing_capacity_ha_per_fortnight is not None and sc.sowing_capacity_ha_per_fortnight > 0:
        cap_val = float(sc.sowing_capacity_ha_per_fortnight)
        for p in range(T):
            wins_at_p = [(c, w) for c in sc.crops for w in win_map[c] if w["sowing"] == p]
            if wins_at_p:
                row = np.zeros(idx.n)
                for c, w in wins_at_p:
                    row[ha_w[c, w["id"]]] += 1.0
                sowing_cap_rows[p] = len(A_ub)
                A_ub.append(row)
                b_ub.append(cap_val)

    harvest_cap_rows = {}
    if sc.harvest_capacity_ha_per_fortnight is not None and sc.harvest_capacity_ha_per_fortnight > 0:
        cap_val = float(sc.harvest_capacity_ha_per_fortnight)
        for p in range(T):
            wins_at_p = [(c, w) for c in sc.crops for w in win_map[c] if w["harvest"] == p]
            if wins_at_p:
                row = np.zeros(idx.n)
                for c, w in wins_at_p:
                    row[ha_w[c, w["id"]]] += 1.0
                harvest_cap_rows[p] = len(A_ub)
                A_ub.append(row)
                b_ub.append(cap_val)

    first_credit_row = len(A_ub)
    for p in range(T):
        row = np.zeros(idx.n)
        row[D[p]] = 1
        A_ub.append(row); b_ub.append(sc.credit_line_usd)

    # Route capacity constraints
    route_ub_rows = {}
    for r in routes:
        cap = r.get("capacity_t")
        if cap is not None and float(cap) >= 0 and float(cap) < 1e8:
            row = np.zeros(idx.n)
            for c in sc.crops:
                for p in range(h_c0_map[c], T):
                    if (c, p, r["id"]) in sell:
                        row[sell[c, p, r["id"]]] = 1.0
            if routes and r["id"] == routes[0]["id"]:
                for (_, c_fwd, f_k, _) in forward_vars:
                    row[f_k] += 1.0
            route_ub_rows[r["id"]] = len(A_ub)
            A_ub.append(row)
            b_ub.append(float(cap))

    # Shared leg capacity constraints
    legs_meta = {}
    for r in routes:
        r_id = r["id"]
        for leg in r.get("legs", []):
            lid = leg.get("leg_id")
            if not lid:
                continue
            if lid not in legs_meta:
                legs_meta[lid] = {
                    "leg_id": lid,
                    "mode": leg.get("mode", "unknown"),
                    "name": leg.get("name") or (f"{leg.get('from', '')} -> {leg.get('to', '')}" if leg.get("from") else lid),
                    "routes": [],
                    "capacity_t": None,
                    "capacity_t_by_month": None,
                }
            if r_id not in legs_meta[lid]["routes"]:
                legs_meta[lid]["routes"].append(r_id)
            if leg.get("capacity_t") is not None:
                legs_meta[lid]["capacity_t"] = float(leg["capacity_t"])
            if leg.get("capacity_t_by_month"):
                legs_meta[lid]["capacity_t_by_month"] = leg["capacity_t_by_month"]

    month_names_en = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
    month_names_es = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

    leg_ub_rows = {}
    for lid, meta in legs_meta.items():
        r_ids = meta["routes"]
        if meta["capacity_t"] is not None and float(meta["capacity_t"]) >= 0 and float(meta["capacity_t"]) < 1e8:
            cap = float(meta["capacity_t"])
            row = np.zeros(idx.n)
            for r_id in r_ids:
                for c in sc.crops:
                    for p in range(h_c0_map[c], T):
                        if (c, p, r_id) in sell:
                            row[sell[c, p, r_id]] += 1.0
            if routes and routes[0]["id"] in r_ids:
                for (_, c_fwd, f_k, _) in forward_vars:
                    row[f_k] += 1.0
            leg_ub_rows[lid] = (lid, len(A_ub), cap, meta)
            A_ub.append(row)
            b_ub.append(cap)

        if meta["capacity_t_by_month"]:
            for m_key, cap_val in meta["capacity_t_by_month"].items():
                if cap_val is not None and float(cap_val) >= 0 and float(cap_val) < 1e8:
                    cap = float(cap_val)
                    m_lower = str(m_key).lower().strip()
                    row = np.zeros(idx.n)
                    for r_id in r_ids:
                        for c in sc.crops:
                            for p in range(h_c0_map[c], T):
                                cal_m = fortnight_month(sc.season_start, p)
                                m_int = int(cal_m.split("-")[1])
                                m_en = month_names_en[m_int - 1]
                                m_es = month_names_es[m_int - 1]
                                if m_lower in (cal_m, m_en, m_es, str(m_int)):
                                    if (c, p, r_id) in sell:
                                        row[sell[c, p, r_id]] += 1.0
                    if routes and routes[0]["id"] in r_ids:
                        for (_, c_fwd, f_k, p_k) in forward_vars:
                            cal_m = fortnight_month(sc.season_start, p_k)
                            m_int = int(cal_m.split("-")[1])
                            m_en = month_names_en[m_int - 1]
                            m_es = month_names_es[m_int - 1]
                            if m_lower in (cal_m, m_en, m_es, str(m_int)):
                                row[f_k] += 1.0
                    row_key = f"{lid}_{m_key}"
                    leg_ub_rows[row_key] = (lid, len(A_ub), cap, meta)
                    A_ub.append(row)
                    b_ub.append(cap)

    # User constraint rows in A_ub: min_area, max_area, min_share
    user_ub_rows = {}
    for i, c in enumerate(sc.constraints):
        ctype = c["type"]
        if ctype == "min_area":
            row = np.zeros(idx.n)
            row[ha[c["crop"]]] = -1.0
            user_ub_rows[i] = ("min_area", len(A_ub))
            A_ub.append(row)
            b_ub.append(-float(c["ha"]))
        elif ctype == "max_area":
            row = np.zeros(idx.n)
            row[ha[c["crop"]]] = 1.0
            user_ub_rows[i] = ("max_area", len(A_ub))
            A_ub.append(row)
            b_ub.append(float(c["ha"]))
        elif ctype == "min_share":
            row = np.zeros(idx.n)
            share = float(c["share"])
            for k in sc.crops:
                row[ha[k]] = share
            row[ha[c["crop"]]] -= 1.0
            user_ub_rows[i] = ("min_share", len(A_ub))
            A_ub.append(row)
            b_ub.append(0.0)
        elif ctype == "max_payments_by":
            # Payments for inputs, field operations and overhead from the start of the season up to the
            # end of the given month (SPEC-19): "I cannot pay out more than X until February".
            y_c, m_c = int(c["month"][:4]), int(c["month"][5:7])
            p_end = min(2 * ((y_c - sy) * 12 + (m_c - sm)) + 1, T - 1)
            row = np.zeros(idx.n)
            for crop in sc.crops:
                for p in range(0, p_end + 1):
                    add_payments(row, crop, p)
            user_ub_rows[i] = ("max_payments_by", len(A_ub))
            A_ub.append(row)
            b_ub.append(float(c["usd"]))

    bounds = [(0, None)] * idx.n
    for c in sc.crops:
        h0 = h_c0_map[c]
        bounds[ha[c]] = (0, None)
        for opt in storage_opts:
            m = opt["id"]
            bounds[stock_opt[c, T - 1, m]] = (0, 0)     # no grain left at the end of the season
            max_m = opt.get("max_months")
            if max_m is not None:
                limit_p = h0 + 2.0 * float(max_m)
                for p in range(h0, T):
                    if p > limit_p + 1e-9:
                        bounds[stock_opt[c, p, m]] = (0, 0)
    if not sc.final_debt_allowed:
        bounds[D[-1]] = (0, 0)                   # and the credit is repaid
    bounds[rent_in] = (0, sc.rent_in_cap)
    bounds[rent_out] = (0, sc.owned if sc.allow_rent_out else 0.0)
    bounds[buy] = (0, sc.max_buy_ha)
    if sc.livestock:
        for a in sc.livestock:
            bounds[y[a]] = (0, total_land)
            if a in y_low:
                bounds[y_low[a]] = (0, None)

    res = linprog(obj, A_ub=np.array(A_ub), b_ub=b_ub, A_eq=np.array(A_eq), b_eq=b_eq,
                  bounds=bounds, method="highs")
    if res.status != 0:
        if sc.constraints:
            names = []
            for c in sc.constraints:
                if c["type"] in ("min_area", "max_area"):
                    names.append(f"{c['type']} of {c['crop']} ({c['ha']} ha)")
                elif c["type"] == "min_share":
                    names.append(f"min_share of {c['crop']} ({c['share']})")
                elif c["type"] == "forward_sale":
                    names.append(f"forward_sale of {c['crop']} {c['month']} ({c['tonnes']} t)")
                elif c["type"] == "max_payments_by":
                    names.append(f"max_payments_by {c['month']} ({c['usd']} USD)")
            raise ScenarioError(f"The scenario is infeasible with constraints: {', '.join(names)}.")
        raise ScenarioError(f"The program has no solution: {res.message}")

    x = res.x
    # Marginals are d(objective)/d(right-hand side); the objective is -NPV.
    lam = [-m for m in res.eqlin.marginals[:T]]
    ub = [-m for m in res.ineqlin.marginals]
    rate = [(lam[p] / lam[p + 1]) ** 24 - 1 if lam[p + 1] > 1e-12 else float("inf") for p in range(T - 1)]

    sales = {}
    sales_by_route = {}
    tonnes_by_route = {r["id"]: 0.0 for r in routes}
    for c in sc.crops:
        c_sales = {}
        for (cc, p, r_id), i in sell.items():
            if cc == c and x[i] > 1e-6:
                c_sales[p] = c_sales.get(p, 0.0) + x[i]
                sales_by_route.setdefault(c, {}).setdefault(r_id, {})[p] = float(x[i])
                tonnes_by_route[r_id] = tonnes_by_route.get(r_id, 0.0) + float(x[i])
        for (_, c_fwd, f_k, p_k) in forward_vars:
            if c_fwd["crop"] == c and x[f_k] > 1e-6:
                c_sales[p_k] = c_sales.get(p_k, 0.0) + x[f_k]
                first_r_id = routes[0]["id"]
                sales_by_route.setdefault(c, {}).setdefault(first_r_id, {})[p_k] = (
                    sales_by_route.setdefault(c, {}).setdefault(first_r_id, {}).get(p_k, 0.0) + float(x[f_k])
                )
                tonnes_by_route[first_r_id] = tonnes_by_route.get(first_r_id, 0.0) + float(x[f_k])
        sales[c] = c_sales

    rent_in_val = float(x[rent_in])
    rent_out_val = float(x[rent_out])
    buy_val = float(x[buy])

    total_herd_end_val = 0.0
    if sc.livestock:
        for a in sc.livestock:
            herd_ev = sc.livestock_herd_end_value(a)
            if herd_ev > 0:
                tot_ha = float(x[y[a]]) + (float(x[y_low[a]]) if a in y_low else 0.0)
                total_herd_end_val += herd_ev * tot_ha

    pre_tax_wealth = float(x[S[-1]] - x[D[-1]] + end_value * buy_val + total_herd_end_val)
    profit = pre_tax_wealth - sc.own_capital_usd
    if sc.income_tax_rate > 0 and profit > 0:
        tax_usd = sc.income_tax_rate * profit
        final_wealth = pre_tax_wealth - tax_usd
        npv = -float(res.fun) - discount * tax_usd
    else:
        final_wealth = pre_tax_wealth
        npv = -float(res.fun)

    season_profit = final_wealth - sc.own_capital_usd
    return_on_capital = season_profit / sc.own_capital_usd if sc.own_capital_usd > 0 else 0.0
    total_capital_and_land = sc.own_capital_usd + sc.owned * sc.land_price_usd_ha
    return_on_capital_and_land = season_profit / total_capital_and_land if total_capital_and_land > 0 else 0.0
    season_months = (T - 1) / 2.0
    annual_exp = 24.0 / (T - 1)
    return_on_capital_annual = (1.0 + return_on_capital) ** annual_exp - 1.0 if 1.0 + return_on_capital > 0.0 else -1.0
    return_on_capital_and_land_annual = (
        (1.0 + return_on_capital_and_land) ** annual_exp - 1.0 if 1.0 + return_on_capital_and_land > 0.0 else -1.0
    )

    # Every reported shadow price is after income tax when profit > 0; cash_value (lam) and internal rates stay pre-tax.
    tax_mult = (1.0 - sc.income_tax_rate) if (sc.income_tax_rate > 0 and profit > 0) else 1.0

    constraint_duals = []
    total_sown = sum(x[ha[c]] for c in sc.crops)
    for i, c in enumerate(sc.constraints):
        if i in user_ub_rows:
            kind, row_idx = user_ub_rows[i]
            dual_val = ub[row_idx]
            if kind in ("min_area", "max_area", "max_payments_by"):
                opp_cost = float(dual_val) * tax_mult
            elif kind == "min_share":
                opp_cost = float(dual_val * total_sown * 0.01) * tax_mult
            else:
                opp_cost = 0.0
        elif i in forward_eq_rows:
            row_idx = forward_eq_rows[i]
            # minus the dual of f_k = tonnes: in HiGHS res.eqlin.marginals is -dNPV/d(RHS)
            opp_cost = float(res.eqlin.marginals[row_idx]) * tax_mult
        else:
            opp_cost = 0.0
        if abs(opp_cost) < 1e-12:
            opp_cost = 0.0
        constraint_duals.append(opp_cost)

    route_capacity_shadow_prices = {}
    for r in routes:
        if r["id"] in route_ub_rows:
            row_idx = route_ub_rows[r["id"]]
            dual_val = float(ub[row_idx]) * tax_mult
            route_capacity_shadow_prices[r["id"]] = round(dual_val, 4) if abs(dual_val) > 1e-12 else 0.0

    tonnes_by_leg = {}
    for lid, meta in legs_meta.items():
        tonnes_by_leg[lid] = sum(tonnes_by_route.get(r_id, 0.0) for r_id in meta["routes"])

    leg_shadow_prices = {}
    for key, (lid, row_idx, cap, meta) in leg_ub_rows.items():
        dual_val = float(ub[row_idx]) * tax_mult
        sp_val = round(dual_val, 4) if abs(dual_val) > 1e-12 else 0.0
        used = tonnes_by_leg.get(lid, 0.0)
        leg_shadow_prices[key] = {
            "leg_id": lid,
            "mode": meta["mode"],
            "name": meta["name"],
            "shadow_price_usd_t": sp_val,
            "capacity_t": cap,
            "tonnes_used": round(used, 2),
        }

    rent_out_bound_dual = 0.0
    if sc.allow_rent_out and hasattr(res, "upper") and res.upper is not None and rent_out < len(res.upper.marginals):
        rent_out_bound_dual = -float(res.upper.marginals[rent_out])

    y_bound_dual = 0.0
    if sc.livestock and hasattr(res, "upper") and res.upper is not None:
        for a in sc.livestock:
            if y[a] < len(res.upper.marginals):
                y_bound_dual += -float(res.upper.marginals[y[a]])

    land_row_sp = float(ub[0]) * tax_mult
    livestock_share_sp = float(ub[livestock_share_row]) * tax_mult if livestock_share_row is not None else 0.0
    rent_out_bound_sp = rent_out_bound_dual * tax_mult
    raw_land_sp = (
        float(ub[0])
        + float(sc.max_crop_share) * sum(float(ub[rotation_ub_rows[c]]) for c in sc.crops)
        + (float(sc.max_livestock_share) * float(ub[livestock_share_row]) if livestock_share_row is not None else 0.0)
        + rent_out_bound_dual
        + y_bound_dual
        - float(sc.land_tax_usd_ha_year) * float(lam[0])
    )
    land_sp = raw_land_sp * tax_mult

    rotation_sp = {}
    for c in sc.crops:
        rot_dual = float(ub[rotation_ub_rows[c]]) * tax_mult
        rotation_sp[c] = rot_dual if abs(rot_dual) > 1e-12 else 0.0

    livestock_only_sp = float(ub[cattle_land_row]) * tax_mult if cattle_land_row is not None else 0.0

    hectares_livestock = {}
    if sc.livestock:
        for a in sc.livestock:
            tot = float(x[y[a]]) + (float(x[y_low[a]]) if a in y_low else 0.0)
            hectares_livestock[a] = tot

    total_stock = {}
    for c in sc.crops:
        c_st = {}
        for p in range(h_c0_map[c], T):
            tot_s = sum(float(x[stock_opt[c, p, opt["id"]]]) for opt in storage_opts)
            if tot_s > 1e-6:
                c_st[p] = tot_s
        total_stock[c] = c_st

    storage_by_option = {}
    for opt in storage_opts:
        m = opt["id"]
        put_in_by_crop = {}
        stock_by_crop = {}
        shrink_by_crop = {}
        fill_cost_total = 0.0
        monthly_cost_total = 0.0
        fill_rate = float(opt.get("fill_cost_usd_t", 0.0))
        half_monthly_rate = float(opt.get("monthly_cost_usd_t", 0.0)) / 2.0

        for c in sc.crops:
            H_c = H_crops[c]
            h0 = h_c0_map[c]
            in_val = sum(float(x[put_in[c, p, m]]) for p in H_c)
            if in_val > 1e-6:
                put_in_by_crop[c] = in_val
            fill_cost_total += fill_rate * max(0.0, in_val)

            c_opt_stock = {}
            for p in range(h0, T):
                s_val = float(x[stock_opt[c, p, m]])
                if s_val > 1e-6:
                    c_opt_stock[p] = s_val
                monthly_cost_total += half_monthly_rate * max(0.0, s_val)
            stock_by_crop[c] = c_opt_stock

            out_val = sum(float(x[take_out[c, p, m]]) for p in range(h0 + 1, T))
            sh_c = in_val - out_val
            shrink_by_crop[c] = 0.0 if abs(sh_c) < 1e-10 else max(0.0, sh_c)

        fortnight_totals = [
            sum(float(x[stock_opt[c, p, m]]) for c in sc.crops if (c, p, m) in stock_opt)
            for p in range(T)
        ]
        peak_t = max([0.0] + [v for v in fortnight_totals if v > 1e-9])
        opt_info = {
            "id": m,
            "kind": opt.get("kind", m),
            "capacity_t": opt.get("capacity_t"),
            "peak_tonnes": peak_t,
            "tonnes_put_in": put_in_by_crop,
            "stock_by_crop": stock_by_crop,
            "fill_cost_usd": fill_cost_total,
            "monthly_cost_usd": monthly_cost_total,
            "total_cost_usd": fill_cost_total + monthly_cost_total,
            "shrink_by_crop": {c: v for c, v in shrink_by_crop.items() if v > 1e-9},
            "shrink_tonnes": sum(shrink_by_crop.values()),
        }
        if m in storage_ub_rows:
            row0 = storage_ub_rows[m]
            sp_list = [float(v) * tax_mult for v in ub[row0:row0 + T]]
            opt_info["shadow_price_by_fortnight"] = sp_list
            opt_info["shadow_price_usd_t"] = float(sum(sp_list))
        storage_by_option[m] = opt_info

    for c in sc.crops:
        harvest_c = sum(float(x[ha_w[c, w["id"]]]) * float(w["yield_t_ha"]) for w in win_map[c])
        h0 = h_c0_map[c]
        sold_and_fwd_c = (
            sum(float(x[sell[c, p, r["id"]]]) for p in range(h0, T) for r in routes)
            + sum(float(x[f_k]) for (_, c_fwd, f_k, _) in forward_vars if c_fwd["crop"] == c)
        )
        shrink_c_tot = sum(storage_by_option[opt["id"]]["shrink_by_crop"].get(c, 0.0) for opt in storage_opts)
        if abs(harvest_c - (sold_and_fwd_c + shrink_c_tot)) > 1e-4:
            raise ScenarioError(
                f"Grain mass balance violated for {c}: harvest={harvest_c}, sales+forwards={sold_and_fwd_c}, shrink={shrink_c_tot}"
            )

    sowing_capacity_shadow_prices = {}
    for p, row_idx in sowing_cap_rows.items():
        dual_val = float(ub[row_idx]) * tax_mult
        sowing_capacity_shadow_prices[p] = round(dual_val, 4) if abs(dual_val) > 1e-12 else 0.0

    harvest_capacity_shadow_prices = {}
    for p, row_idx in harvest_cap_rows.items():
        dual_val = float(ub[row_idx]) * tax_mult
        harvest_capacity_shadow_prices[p] = round(dual_val, 4) if abs(dual_val) > 1e-12 else 0.0

    hectares_by_window = {
        c: {w["id"]: float(x[ha_w[c, w["id"]]]) for w in win_map[c]}
        for c in sc.crops
    }
    harvest_t_by_fortnight = {}
    for p in range(T):
        tot_p = sum(float(x[ha_w[c, w["id"]]]) * float(w["yield_t_ha"]) for c in sc.crops for w in win_map[c] if w["harvest"] == p)
        if tot_p > 1e-6:
            harvest_t_by_fortnight[p] = round(tot_p, 4)

    double_cropped_ha = PairDict()
    double_crop_shadow_prices = PairDict()
    for prec, row_idx in after_ub_rows.items():
        second_windows = [
            (c_other, w)
            for c_other in sc.crops
            for w in win_map[c_other]
            if w.get("after") == prec
        ]
        for c_other, w in second_windows:
            h_2nd = float(x[ha_w[c_other, w["id"]]])
            if h_2nd > 1e-6:
                pair_key = f"{prec}/{c_other}"
                double_cropped_ha[pair_key] = double_cropped_ha.get(pair_key, 0.0) + h_2nd
        dual_val = float(ub[row_idx]) * tax_mult
        if abs(dual_val) > 1e-12:
            double_crop_shadow_prices[prec] = round(dual_val, 4)
            for c_other, w in second_windows:
                double_crop_shadow_prices[f"{prec}/{c_other}"] = round(dual_val, 4)

    all_windows_used = [w for c in sc.crops for w in win_map[c]]

    own_silo_sp = [0.0] * T
    if "own_silo" in storage_by_option and "shadow_price_by_fortnight" in storage_by_option["own_silo"]:
        own_silo_sp = list(storage_by_option["own_silo"]["shadow_price_by_fortnight"])
    else:
        for opt in storage_opts:
            m_id = opt["id"]
            if opt.get("kind") == "own_silo" and "shadow_price_by_fortnight" in storage_by_option.get(m_id, {}):
                own_silo_sp = list(storage_by_option[m_id]["shadow_price_by_fortnight"])
                break

    credit_sp = [float(v) * tax_mult for v in ub[first_credit_row:first_credit_row + T]]

    term_ha_res = {}
    if terms:
        for c in sc.crops:
            if x[ha[c]] > 1e-6:
                c_terms = {}
                for t in terms:
                    tot_z = sum(float(x[z[c, w["id"], t["id"]]]) for w in win_map[c])
                    if tot_z > 1e-6:
                        c_terms[t["id"]] = tot_z
                if c_terms:
                    term_ha_res[c] = c_terms

    return Result(
        npv=npv,
        final_wealth=final_wealth,
        hectares={c: x[ha[c]] for c in sc.crops},
        sales=sales,
        stock=total_stock,
        cash=[x[i] for i in S],
        debt=[x[i] for i in D],
        cash_value=lam,
        internal_rate_annual=rate,
        capital_shadow_price=(float(lam[0]) - 1.0) * tax_mult,
        land_shadow_price=land_sp,
        storage_shadow_price=own_silo_sp,
        credit_shadow_price=credit_sp,
        market_rate_annual=sc.deposit_rate_annual,
        constraint_duals=constraint_duals,
        rent_in_ha=rent_in_val,
        rent_out_ha=rent_out_val,
        buy_ha=buy_val,
        owned_ha=sc.owned,
        land_price_usd_ha=sc.land_price_usd_ha,
        regional_rent_usd_ha=sc.regional_rent_usd_ha,
        return_on_capital=return_on_capital,
        return_on_capital_and_land=return_on_capital_and_land,
        season_months=season_months,
        return_on_capital_annual=return_on_capital_annual,
        return_on_capital_and_land_annual=return_on_capital_and_land_annual,
        hectares_livestock=hectares_livestock,
        livestock_only_shadow_price=livestock_only_sp,
        livestock_only_ha=sc.livestock_only_ha,
        sales_by_route=sales_by_route,
        tonnes_by_route=tonnes_by_route,
        route_capacity_shadow_prices=route_capacity_shadow_prices,
        leg_shadow_prices=leg_shadow_prices,
        tonnes_by_leg=tonnes_by_leg,
        payment_term_ha=term_ha_res,
        storage_by_option=storage_by_option,
        rotation_shadow_price=rotation_sp,
        land_row_shadow_price=land_row_sp,
        livestock_share_shadow_price=livestock_share_sp,
        rent_out_bound_shadow_price=rent_out_bound_sp,
        hectares_by_window=hectares_by_window,
        harvest_t_by_fortnight=harvest_t_by_fortnight,
        sowing_windows_used=all_windows_used,
        sowing_capacity_shadow_prices=sowing_capacity_shadow_prices,
        harvest_capacity_shadow_prices=harvest_capacity_shadow_prices,
        double_cropped_ha=double_cropped_ha,
        double_crop_shadow_prices=double_crop_shadow_prices,
    )



def _optimize_stochastic(sc: Scenario) -> Result:
    """Solve two-stage stochastic optimization over climate_scenarios (SPEC-25).
    
    Stage 1: crop choices x_{c,w}, land tenure (rent/buy), supplier financing terms z_{c,w,t}.
    Stage 2: sales, storage, cash, and debt under each realized climate scenario s.
    Objective: maximize expected NPV = sum_s prob_s * NPV_s.
    """
    climates = sc.climate_scenarios
    tot_p = sum(float(c.get("probability", c.get("prob", 1.0))) for c in climates)
    sc_list = []
    for c in climates:
        p = float(c.get("probability", c.get("prob", 1.0))) / tot_p
        cid = c.get("id", f"climate_{len(sc_list)}")
        y_dict = c.get("yields", {})
        sc_list.append({"id": cid, "prob": p, "yields": y_dict})

    T = FORTNIGHTS
    rc = fortnightly_rate(sc.credit_rate_annual)
    rd = fortnightly_rate(sc.deposit_rate_annual)
    idx = _Index()

    # Stage 1 variables
    win_map = sc.resolved_sowing_windows()
    ha = {}
    ha_w = {}
    z = {}
    terms = sc.payment_terms()
    for c in sc.crops:
        windows = win_map[c]
        if len(windows) == 1:
            w0 = windows[0]
            ha[c] = idx.new()
            ha_w[c, w0["id"]] = ha[c]
            if terms:
                for t in terms:
                    z[c, w0["id"], t["id"]] = idx.new()
        else:
            ha[c] = idx.new()
            for w in windows:
                wid = w["id"]
                ha_w[c, wid] = idx.new()
                if terms:
                    for t in terms:
                        z[c, wid, t["id"]] = idx.new()

    rent_in = idx.new()
    rent_out = idx.new()
    buy = idx.new()

    y = {}
    y_low = {}
    if sc.livestock:
        for a in sc.livestock:
            y[a] = idx.new()
            if sc.livestock_only_ha > 0:
                y_low[a] = idx.new()

    routes = sc.routes if hasattr(sc, "routes") and sc.routes else [
        {
            "id": "default",
            "name": f"Direct freight ({sc.freight_usd_t:.1f} USD/t)",
            "capacity_t": None,
            "legs": [{"mode": "truck", "from": "farm", "to": "terminal", "usd_t": float(sc.freight_usd_t)}],
        }
    ]
    storage_opts = sc.effective_storage_options()

    sy, sm = int(sc.season_start[:4]), int(sc.season_start[5:7])
    forward_vars = []
    forward_eq_rows = {}
    for i, c_spec in enumerate(sc.constraints):
        if c_spec["type"] == "forward_sale":
            cy, cm = int(c_spec["month"][:4]), int(c_spec["month"][5:7])
            offset = (cy - sy) * 12 + (cm - sm)
            p_k = 2 * offset
            f_k = idx.new()
            forward_vars.append((i, c_spec, f_k, p_k))

    H_crops = {}
    h_c0_map = {}
    for c in sc.crops:
        h_set = sorted(list({w["harvest"] for w in win_map[c]}))
        H_crops[c] = h_set
        h_c0_map[c] = min(h_set)

    # Stage 2 variables per climate s
    sell, put_in, stock_opt, take_out = {}, {}, {}, {}
    S, D = {}, {}
    for s_idx, sc_info in enumerate(sc_list):
        S[s_idx] = [idx.new() for _ in range(T)]
        D[s_idx] = [idx.new() for _ in range(T)]
        for c in sc.crops:
            H_c = H_crops[c]
            h0 = h_c0_map[c]
            for p in H_c:
                for opt in storage_opts:
                    put_in[s_idx, c, p, opt["id"]] = idx.new()
            for p in range(h0, T):
                for opt in storage_opts:
                    m = opt["id"]
                    stock_opt[s_idx, c, p, m] = idx.new()
                    if p > h0:
                        take_out[s_idx, c, p, m] = idx.new()
                for r in routes:
                    sell[s_idx, c, p, r["id"]] = idx.new()

    # Objective: maximize expected NPV = sum_s p_s * NPV_s
    discount = (1 + rd) ** -(T - 1)
    obj = np.zeros(idx.n)
    for s_idx, sc_info in enumerate(sc_list):
        prob_s = sc_info["prob"]
        obj[S[s_idx][-1]] -= prob_s * discount
        obj[D[s_idx][-1]] += prob_s * discount

    end_value = sc.land_price_usd_ha * ((1 + sc.land_appreciation_annual) ** (T / 24))
    if sc.max_buy_ha > 0 or sc.land_price_usd_ha > 0:
        obj[buy] -= discount * end_value

    if sc.livestock:
        for a in sc.livestock:
            herd_ev = sc.livestock_herd_end_value(a)
            if herd_ev > 0:
                obj[y[a]] -= discount * herd_ev
                if a in y_low:
                    obj[y_low[a]] -= discount * herd_ev

    A_eq, b_eq = [], []
    A_ub, b_ub = [], []

    # Window splitting equalities: sum_w x_{c,w} = x_c
    for c in sc.crops:
        if len(win_map[c]) > 1:
            row = np.zeros(idx.n)
            row[ha[c]] = -1.0
            for w in win_map[c]:
                row[ha_w[c, w["id"]]] = 1.0
            A_eq.append(row)
            b_eq.append(0.0)

    # Supplier terms: sum_t z_{c,w,t} = x_{c,w}
    if terms:
        for c in sc.crops:
            for w in win_map[c]:
                row = np.zeros(idx.n)
                row[ha_w[c, w["id"]]] = -1.0
                for t in terms:
                    row[z[c, w["id"], t["id"]]] = 1.0
                A_eq.append(row)
                b_eq.append(0.0)

    # Land balance: second crops do not take land of their own
    land_eq_row = np.zeros(idx.n)
    land_eq_row[rent_in] = -1.0
    land_eq_row[buy] = -1.0
    land_eq_row[rent_out] = 1.0
    for c in sc.crops:
        for w in win_map[c]:
            if not w.get("after"):
                land_eq_row[ha_w[c, w["id"]]] += 1.0
    if sc.livestock:
        for a in sc.livestock:
            land_eq_row[y[a]] = 1.0
    A_ub.append(land_eq_row)
    b_ub.append(sc.owned)
    land_row_idx = len(A_ub) - 1

    # Rotation: second crops do not count toward rotation share
    rot_rows = {}
    for c in sc.crops:
        row = np.zeros(idx.n)
        for w in win_map[c]:
            if not w.get("after"):
                row[ha_w[c, w["id"]]] += 1.0
        row[rent_in] = -sc.max_crop_share
        row[buy] = -sc.max_crop_share
        A_ub.append(row)
        b_ub.append(sc.max_crop_share * sc.owned)
        rot_rows[c] = len(A_ub) - 1

    # After constraints in stochastic engine
    after_ub_rows = {}
    for prec in sc.crops:
        second_windows = [
            (c_other, w)
            for c_other in sc.crops
            for w in win_map[c_other]
            if w.get("after") == prec
        ]
        if second_windows:
            row = np.zeros(idx.n)
            for c_other, w in second_windows:
                row[ha_w[c_other, w["id"]]] += 1.0
            row[ha[prec]] -= 1.0
            after_ub_rows[prec] = len(A_ub)
            A_ub.append(row)
            slack = 0.0
            if getattr(sc, "double_crop_slack_ha", None) is not None:
                if isinstance(sc.double_crop_slack_ha, dict):
                    slack = float(sc.double_crop_slack_ha.get(prec, 0.0))
                else:
                    slack = float(sc.double_crop_slack_ha)
            b_ub.append(slack)

    # Sowing machinery capacity
    sow_cap_rows = {}
    if getattr(sc, "sowing_capacity_ha_per_fortnight", None) is not None:
        cap_val = float(sc.sowing_capacity_ha_per_fortnight)
        sow_fn_map = {}
        for c in sc.crops:
            for w in win_map[c]:
                sow_fn_map.setdefault(w["sowing"], []).append((c, w["id"]))
        for p_sow, cw_list in sow_fn_map.items():
            row = np.zeros(idx.n)
            for c, wid in cw_list:
                row[ha_w[c, wid]] = 1.0
            A_ub.append(row)
            b_ub.append(cap_val)
            sow_cap_rows[p_sow] = len(A_ub) - 1

    # Farmer constraints
    user_ub_rows = {}
    for i, c_spec in enumerate(sc.constraints):
        ctype = c_spec["type"]
        if ctype in ("min_area", "max_area"):
            c_name = c_spec["crop"]
            row = np.zeros(idx.n)
            sign = -1.0 if ctype == "min_area" else 1.0
            row[ha[c_name]] = sign
            A_ub.append(row)
            b_ub.append(sign * float(c_spec["ha"]))
            user_ub_rows[i] = (ctype, len(A_ub) - 1)
        elif ctype == "min_share":
            c_name = c_spec["crop"]
            sh = float(c_spec["share"])
            row = np.zeros(idx.n)
            for c in sc.crops:
                row[ha[c]] = sh
            row[ha[c_name]] -= 1.0
            A_ub.append(row)
            b_ub.append(0.0)
            user_ub_rows[i] = (ctype, len(A_ub) - 1)

    fixed_pay = {(c, w["id"]): sc.fixed_payments_per_ha_window(c, w) for c in sc.crops for w in win_map[c]}
    term_pay = {}
    if terms:
        term_pay = {(c, w["id"], t["id"]): sc.input_payments_per_ha_window(c, w, t["delay_fortnights"], t["surcharge"],
                                                                           t["installments"], t["every_fortnights"])
                    for c in sc.crops for w in win_map[c] for t in terms}
    else:
        base = sc.payment_terms()[0]
        for c in sc.crops:
            for w in win_map[c]:
                inp = sc.input_payments_per_ha_window(c, w, base["delay_fortnights"], base["surcharge"])
                for p, amt in inp.items():
                    fixed_pay[c, w["id"]][p] = fixed_pay[c, w["id"]].get(p, 0.0) + amt

    def add_payments(row, c, p):
        for w in win_map[c]:
            wid = w["id"]
            if (c, wid) in fixed_pay and p in fixed_pay[c, wid]:
                row[ha_w[c, wid]] += fixed_pay[c, wid][p]
            if terms:
                for t in terms:
                    key = (c, wid, t["id"])
                    if key in term_pay and p in term_pay[key]:
                        row[z[c, wid, t["id"]]] += term_pay[key][p]

    initial_cash_rows = {}
    cash_eq_rows = {}
    credit_ub_rows = {}
    storage_ub_rows = {}
    for s_idx, sc_info in enumerate(sc_list):
        s_yields = sc_info["yields"]

        # Sales balance per crop and fortnight
        for c in sc.crops:
            H_c = H_crops[c]
            h0 = h_c0_map[c]
            base_cy = sc.crop_yield(c)
            clim_y = float(s_yields.get(c, base_cy))
            y_factor = (clim_y / base_cy) if base_cy > 1e-6 else 1.0

            for p in range(h0, T):
                row = np.zeros(idx.n)
                if p in H_c:
                    for w in win_map[c]:
                        if w["harvest"] == p:
                            if "yield_t_ha" in w and w["yield_t_ha"] is not None:
                                w_y = float(w["yield_t_ha"]) * y_factor
                            elif "yield_factor" in w:
                                w_y = clim_y * float(w["yield_factor"])
                            else:
                                w_y = clim_y
                            row[ha_w[c, w["id"]]] -= w_y
                    for opt in storage_opts:
                        row[put_in[s_idx, c, p, opt["id"]]] = 1.0
                if p > h0:
                    for opt in storage_opts:
                        row[take_out[s_idx, c, p, opt["id"]]] = -1.0
                for r in routes:
                    row[sell[s_idx, c, p, r["id"]]] = 1.0
                for _, c_spec, f_k, p_k in forward_vars:
                    if c_spec["crop"] == c and p_k == p:
                        row[f_k] = 1.0
                A_eq.append(row)
                b_eq.append(0.0)

        # Storage stock balance
        for c in sc.crops:
            h0 = h_c0_map[c]
            H_c = H_crops[c]
            for opt in storage_opts:
                m = opt["id"]
                shrink_entry = float(opt["fill_cost_usd_t"] and opt["shrink_at_entry"])
                shrink_monthly = float(opt["shrink_monthly"])
                retain_f = (1.0 - shrink_monthly) ** 0.5
                for p in range(h0, T):
                    row = np.zeros(idx.n)
                    row[stock_opt[s_idx, c, p, m]] = 1.0
                    if p > h0:
                        row[stock_opt[s_idx, c, p - 1, m]] = -retain_f
                        row[take_out[s_idx, c, p, m]] = 1.0
                    if p in H_c:
                        row[put_in[s_idx, c, p, m]] = -(1.0 - shrink_entry)
                    A_eq.append(row)
                    b_eq.append(0.0)

        # Storage capacity
        for opt in storage_opts:
            m = opt["id"]
            if opt["capacity_t"] is not None:
                cap_m = float(opt["capacity_t"])
                h_min = min(h_c0_map[c] for c in sc.crops)
                row_start = len(A_ub)
                for p in range(h_min, T):
                    row = np.zeros(idx.n)
                    for c in sc.crops:
                        if p >= h_c0_map[c]:
                            row[stock_opt[s_idx, c, p, m]] = 1.0
                    A_ub.append(row)
                    b_ub.append(cap_m)
                storage_ub_rows[s_idx, m] = row_start

        # Credit line
        first_cr = len(A_ub)
        for p in range(T):
            row = np.zeros(idx.n)
            row[D[s_idx][p]] = 1.0
            A_ub.append(row)
            b_ub.append(sc.credit_line_usd)
        credit_ub_rows[s_idx] = first_cr

        # Cash balance
        first_cash = len(A_eq)
        for p in range(T):
            row = np.zeros(idx.n)
            row[S[s_idx][p]] = 1.0
            row[D[s_idx][p]] = -1.0
            if p > 0:
                row[S[s_idx][p - 1]] = -(1 + rd)
                row[D[s_idx][p - 1]] = (1 + rc)
            for c in sc.crops:
                add_payments(row, c, p)
                if p >= h_c0_map[c]:
                    for r in routes:
                        net_p = sc.net_price_route(c, p, r)
                        row[sell[s_idx, c, p, r["id"]]] -= net_p
                    for opt in storage_opts:
                        m = opt["id"]
                        if p in H_crops[c]:
                            row[put_in[s_idx, c, p, m]] += float(opt["fill_cost_usd_t"])
                        row[stock_opt[s_idx, c, p, m]] += float(opt["monthly_cost_usd_t"]) / 2.0
            for _, c_spec, f_k, p_k in forward_vars:
                if p_k == p:
                    row[f_k] -= float(c_spec["price_usd_t"])
            A_eq.append(row)
            if p == 0:
                b_eq.append(sc.own_capital_usd)
                initial_cash_rows[s_idx] = len(A_eq) - 1
            else:
                b_eq.append(0.0)
        cash_eq_rows[s_idx] = first_cash

    # Bounds
    bounds = [(0, None)] * idx.n
    bounds[rent_in] = (0, sc.rent_in_cap)
    bounds[rent_out] = (0, sc.owned)
    bounds[buy] = (0, sc.max_buy_ha)
    for _, c_spec, f_k, _ in forward_vars:
        bounds[f_k] = (float(c_spec["tonnes"]), float(c_spec["tonnes"]))

    res = linprog(
        obj,
        A_ub=np.array(A_ub) if A_ub else None,
        b_ub=np.array(b_ub) if b_ub else None,
        A_eq=np.array(A_eq) if A_eq else None,
        b_eq=np.array(b_eq) if b_eq else None,
        bounds=bounds,
        method="highs",
    )
    if not res.success:
        raise ScenarioError(f"Stochastic optimization failed: {res.message}")

    x_sol = res.x
    ub = -res.ineqlin.marginals
    eq = -res.eqlin.marginals

    exp_npv = -float(res.fun)
    profit = exp_npv - sc.own_capital_usd
    tax_mult = (1.0 - sc.income_tax_rate) if (sc.income_tax_rate > 0 and profit > 0) else 1.0

    hectares = {c: float(x_sol[ha[c]]) for c in sc.crops}
    hectares_by_window = {
        c: {w["id"]: float(x_sol[ha_w[c, w["id"]]]) for w in win_map[c]}
        for c in sc.crops
    }

    # Duals
    lam_0_total = sum(float(eq[initial_cash_rows[s_idx]]) for s_idx in range(len(sc_list)))
    cap_shadow_price = (lam_0_total - 1.0) * tax_mult

    rot_sum = sum(float(ub[rot_rows[c]]) for c in sc.crops)
    raw_land_sp = (
        float(ub[land_row_idx])
        + float(sc.max_crop_share) * rot_sum
        - float(sc.land_tax_usd_ha_year) * lam_0_total
    )
    land_sp = raw_land_sp * tax_mult

    # Sowing capacity duals
    sowing_capacity_shadow_prices = {}
    for p, row_idx in sow_cap_rows.items():
        val = float(ub[row_idx]) * tax_mult
        sowing_capacity_shadow_prices[p] = round(val, 4) if abs(val) > 1e-12 else 0.0

    # Per-climate results
    climate_res_dict = {}
    for s_idx, sc_info in enumerate(sc_list):
        cid = sc_info["id"]
        prob_s = sc_info["prob"]
        c_rows_start = cash_eq_rows[s_idx]
        lam_s = [float(eq[c_rows_start + p]) / prob_s for p in range(T)]
        cr_start = credit_ub_rows[s_idx]
        cr_s = [float(ub[cr_start + p]) / prob_s * tax_mult for p in range(T)]
        w_end = float(x_sol[S[s_idx][-1]]) - float(x_sol[D[s_idx][-1]])
        npv_s = w_end * discount
        climate_res_dict[cid] = {
            "id": cid,
            "probability": prob_s,
            "npv_usd": round(npv_s, 2),
            "cash": [float(x_sol[S[s_idx][p]]) for p in range(T)],
            "debt": [float(x_sol[D[s_idx][p]]) for p in range(T)],
            "cash_value": lam_s,
            "credit_shadow_price": cr_s,
        }

    # Primary scenario view (first scenario)
    primary_s = 0
    c_start = cash_eq_rows[primary_s]
    lam_primary = [float(eq[c_start + p]) / sc_list[primary_s]["prob"] for p in range(T)]
    rate_primary = [(lam_primary[p] / lam_primary[p + 1]) ** (24.0 / 1.0) - 1.0 if lam_primary[p + 1] > 1e-9 else 0.0
                    for p in range(T - 1)]

    sales_primary = {}
    for c in sc.crops:
        h0 = h_c0_map[c]
        c_sales = {}
        for p in range(h0, T):
            tot_p = sum(float(x_sol[sell[primary_s, c, p, r["id"]]]) for r in routes)
            if tot_p > 1e-6:
                c_sales[p] = tot_p
        sales_primary[c] = c_sales

    stock_primary = {}
    for c in sc.crops:
        h0 = h_c0_map[c]
        c_st = {}
        for p in range(h0, T):
            tot_s = sum(float(x_sol[stock_opt[primary_s, c, p, opt["id"]]]) for opt in storage_opts)
            if tot_s > 1e-6:
                c_st[p] = tot_s
        stock_primary[c] = c_st

    cr_start_p = credit_ub_rows[primary_s]
    credit_sp_primary = [float(ub[cr_start_p + p]) / sc_list[primary_s]["prob"] * tax_mult for p in range(T)]

    own_silo_sp = [0.0] * T
    if (primary_s, "own_silo") in storage_ub_rows:
        row0 = storage_ub_rows[primary_s, "own_silo"]
        own_silo_sp = [float(ub[row0 + p]) / sc_list[primary_s]["prob"] * tax_mult for p in range(T - min(h_c0_map.values()))]

    term_ha_res = {}
    if terms:
        for c in sc.crops:
            if hectares[c] > 1e-6:
                c_terms = {}
                for t in terms:
                    tot_z = sum(float(x_sol[z[c, w["id"], t["id"]]]) for w in win_map[c])
                    if tot_z > 1e-6:
                        c_terms[t["id"]] = tot_z
                if c_terms:
                    term_ha_res[c] = c_terms

    # Calculate Value of Stochastic Solution (VSS) if normal exists
    vss = None
    try:
        from .plan_check import evaluate_plan
        norm_sc_info = next((s for s in sc_list if "normal" in s["id"]), sc_list[0])
        sc_normal = Scenario(**{**sc.__dict__, "climate_scenarios": None, "yields": norm_sc_info["yields"]})
        det_normal = optimize(sc_normal)
        exp_det_norm = 0.0
        for s_info in sc_list:
            sc_eval = Scenario(**{**sc.__dict__, "climate_scenarios": None, "yields": s_info["yields"]})
            ev = evaluate_plan(sc_eval, det_normal.hectares_by_window or det_normal.hectares)
            val = ev["npv_plan_usd"] if ev["feasible"] and ev["npv_plan_usd"] is not None else (det_normal.npv - 50_000.0)
            exp_det_norm += s_info["prob"] * val
        vss = max(0.0, exp_npv - exp_det_norm)
    except Exception:
        pass

    season_profit = exp_npv - sc.own_capital_usd
    return_on_capital = season_profit / sc.own_capital_usd if sc.own_capital_usd > 0 else 0.0
    total_capital_and_land = sc.own_capital_usd + sc.owned * sc.land_price_usd_ha
    return_on_capital_and_land = season_profit / total_capital_and_land if total_capital_and_land > 0 else 0.0
    season_months = (T - 1) / 2.0
    annual_exp = 24.0 / (T - 1)
    return_on_capital_annual = (1.0 + return_on_capital) ** annual_exp - 1.0 if 1.0 + return_on_capital > 0.0 else -1.0
    return_on_capital_and_land_annual = (
        (1.0 + return_on_capital_and_land) ** annual_exp - 1.0 if 1.0 + return_on_capital_and_land > 0.0 else -1.0
    )

    rotation_sp = {c: float(ub[rot_rows[c]]) * tax_mult for c in sc.crops if abs(float(ub[rot_rows[c]])) > 1e-12}

    double_cropped_ha = PairDict()
    double_crop_shadow_prices = PairDict()
    for prec, row_idx in after_ub_rows.items():
        second_windows = [
            (c_other, w)
            for c_other in sc.crops
            for w in win_map[c_other]
            if w.get("after") == prec
        ]
        for c_other, w in second_windows:
            h_2nd = float(x_sol[ha_w[c_other, w["id"]]])
            if h_2nd > 1e-6:
                pair_key = f"{prec}/{c_other}"
                double_cropped_ha[pair_key] = double_cropped_ha.get(pair_key, 0.0) + h_2nd
        dual_val = float(ub[row_idx]) * tax_mult
        if abs(dual_val) > 1e-12:
            double_crop_shadow_prices[prec] = round(dual_val, 4)
            for c_other, w in second_windows:
                double_crop_shadow_prices[f"{prec}/{c_other}"] = round(dual_val, 4)

    return Result(
        npv=exp_npv,
        final_wealth=exp_npv / discount,
        hectares=hectares,
        sales=sales_primary,
        stock=stock_primary,
        cash=[float(x_sol[S[primary_s][p]]) for p in range(T)],
        debt=[float(x_sol[D[primary_s][p]]) for p in range(T)],
        cash_value=lam_primary,
        internal_rate_annual=rate_primary,
        capital_shadow_price=cap_shadow_price,
        land_shadow_price=land_sp,
        storage_shadow_price=own_silo_sp,
        credit_shadow_price=credit_sp_primary,
        market_rate_annual=sc.deposit_rate_annual,
        constraint_duals=[],
        rent_in_ha=float(x_sol[rent_in]),
        rent_out_ha=float(x_sol[rent_out]),
        buy_ha=float(x_sol[buy]),
        owned_ha=sc.owned,
        land_price_usd_ha=sc.land_price_usd_ha,
        regional_rent_usd_ha=sc.regional_rent_usd_ha,
        return_on_capital=return_on_capital,
        return_on_capital_and_land=return_on_capital_and_land,
        season_months=season_months,
        return_on_capital_annual=return_on_capital_annual,
        return_on_capital_and_land_annual=return_on_capital_and_land_annual,
        payment_term_ha=term_ha_res,
        rotation_shadow_price=rotation_sp,
        hectares_by_window=hectares_by_window,
        sowing_capacity_shadow_prices=sowing_capacity_shadow_prices,
        expected_npv=exp_npv,
        value_of_stochastic_solution_usd=vss,
        climate_results=climate_res_dict,
        double_cropped_ha=double_cropped_ha,
        double_crop_shadow_prices=double_crop_shadow_prices,
    )
