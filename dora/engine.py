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

from .scenario import CALENDAR, FORTNIGHTS, Scenario, ScenarioError, fortnight_name, fortnightly_rate


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
    hectares_livestock: dict[str, float] = field(default_factory=dict)
    livestock_only_shadow_price: float = 0.0
    livestock_only_ha: float = 0.0


    def summary(self) -> dict:
        def r(x, n=2):
            return round(float(x), n)
        out = {
            "npv_usd": r(self.npv),
            "final_wealth_usd": r(self.final_wealth),
            "hectares": {c: r(h, 1) for c, h in self.hectares.items() if h > 1e-6},
            "rent_in_ha": r(self.rent_in_ha, 1),
            "rent_out_ha": r(self.rent_out_ha, 1),
            "buy_ha": r(self.buy_ha, 1),
            "return_on_capital": r(self.return_on_capital, 4),
            "return_on_capital_and_land": r(self.return_on_capital_and_land, 4),
            "max_credit_usd": r(max(self.debt)),
            "capital_shadow_price": r(self.capital_shadow_price, 4),
            "land_shadow_price_usd_ha": r(self.land_shadow_price),
            "storage_shadow_price_usd_t": r(sum(self.storage_shadow_price)),
            "credit_line_shadow_price": r(sum(self.credit_shadow_price), 4),
            "fortnights_with_scarce_capital": [fortnight_name(p) for p in range(FORTNIGHTS - 1)
                                                if self.internal_rate_annual[p] > self.market_rate_annual + 1e-3],
        }
        if self.hectares_livestock:
            out["hectares_livestock"] = {a: r(h, 1) for a, h in self.hectares_livestock.items() if h > 1e-6}
        if self.livestock_only_ha > 0 or self.livestock_only_shadow_price > 0:
            out["livestock_only_shadow_price_usd_ha"] = r(self.livestock_only_shadow_price)
        return out



class _Index:
    def __init__(self):
        self.n = 0

    def new(self) -> int:
        self.n += 1
        return self.n - 1


def optimize(sc: Scenario) -> Result:
    T = FORTNIGHTS
    ri, rc = fortnightly_rate(sc.deposit_rate_annual), fortnightly_rate(sc.credit_rate_annual)
    storage_cost = sc.storage_cost_usd_t_month / 2
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

    ha = {c: idx.new() for c in sc.crops}
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

    sell, stock = {}, {}
    for c in sc.crops:
        for p in range(cal[c]["harvest"], T):
            sell[c, p] = idx.new()
            stock[c, p] = idx.new()
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
    payments = {c: sc.payments_per_ha(c) for c in sc.crops}
    tx_pay = 1.0 + sc.transaction_tax_rate if sc.transaction_tax_rate > 0 else 1.0
    tx_rec = 1.0 - sc.transaction_tax_rate if sc.transaction_tax_rate > 0 else 1.0

    for p in range(T):
        row = np.zeros(idx.n)
        row[S[p]], row[D[p]] = 1, -1
        if p > 0:
            row[S[p - 1]], row[D[p - 1]] = -(1 + ri), 1 + rc
        for c in sc.crops:
            row[ha[c]] += payments[c].get(p, 0.0)
            if (c, p) in sell:
                row[sell[c, p]] = -sc.net_price(c, p)
                row[stock[c, p]] = storage_cost
        for (_, c_fwd, f_k, p_k) in forward_vars:
            if p == p_k:
                crop = c_fwd["crop"]
                marketing_per_t = sc.data[crop]["marketing_harvest"] / sc.data[crop]["yield"]
                net_fwd_price = float(c_fwd["price_usd_t"]) - marketing_per_t
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
        h = cal[c]["harvest"]
        for p in range(h, T):
            row = np.zeros(idx.n)
            row[stock[c, p]], row[sell[c, p]] = 1, 1
            for (_, c_fwd, f_k, p_k) in forward_vars:
                if c_fwd["crop"] == c and p == p_k:
                    row[f_k] += 1.0
            if p == h:
                row[ha[c]] = -sc.crop_yield(c)
            else:
                row[stock[c, p - 1]] = -1
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

    # Inequalities: land, storage per fortnight, credit line per fortnight.
    A_ub, b_ub = [], []
    row = np.zeros(idx.n)
    for c in sc.crops:
        row[ha[c]] = 1.0
    if sc.livestock:
        for a in sc.livestock:
            row[y[a]] = 1.0
    row[rent_in] = -1.0
    row[buy] = -1.0
    row[rent_out] = 1.0
    A_ub.append(row); b_ub.append(sc.owned)

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
        b_ub.append(sc.max_livestock_share * total_land)

    first_storage_row = len(A_ub)
    for p in range(T):
        row = np.zeros(idx.n)
        for c in sc.crops:
            if (c, p) in stock:
                row[stock[c, p]] = 1
        A_ub.append(row); b_ub.append(sc.storage_capacity_t)
    first_credit_row = len(A_ub)
    for p in range(T):
        row = np.zeros(idx.n)
        row[D[p]] = 1
        A_ub.append(row); b_ub.append(sc.credit_line_usd)


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

    bounds = [(0, None)] * idx.n
    for c in sc.crops:
        bounds[ha[c]] = (0, sc.max_crop_share * total_land)
        bounds[stock[c, T - 1]] = (0, 0)         # no grain left at the end of the season
    bounds[D[-1]] = (0, 0)                       # and the credit is repaid
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
            raise ScenarioError(f"The scenario is infeasible with constraints: {', '.join(names)}.")
        raise ScenarioError(f"The program has no solution: {res.message}")

    x = res.x
    # Marginals are d(objective)/d(right-hand side); the objective is -NPV.
    lam = [-m for m in res.eqlin.marginals[:T]]
    ub = [-m for m in res.ineqlin.marginals]
    rate = [(lam[p] / lam[p + 1]) ** 24 - 1 if lam[p + 1] > 1e-12 else float("inf") for p in range(T - 1)]

    # Compute opportunity cost duals for user constraints
    constraint_duals = []
    total_sown = sum(x[ha[c]] for c in sc.crops)
    for i, c in enumerate(sc.constraints):
        if i in user_ub_rows:
            kind, row_idx = user_ub_rows[i]
            dual_val = ub[row_idx]
            if kind in ("min_area", "max_area"):
                opp_cost = float(dual_val)
            elif kind == "min_share":
                opp_cost = float(dual_val * total_sown * 0.01)
        elif i in forward_eq_rows:
            row_idx = forward_eq_rows[i]
            # minus the dual of f_k = tonnes: in HiGHS res.eqlin.marginals is -dNPV/d(RHS)
            opp_cost = float(res.eqlin.marginals[row_idx])
        else:
            opp_cost = 0.0
        if abs(opp_cost) < 1e-12:
            opp_cost = 0.0
        constraint_duals.append(opp_cost)

    sales = {}
    for c in sc.crops:
        c_sales = {}
        for (cc, p), i in sell.items():
            if cc == c and x[i] > 1e-6:
                c_sales[p] = c_sales.get(p, 0.0) + x[i]
        for (_, c_fwd, f_k, p_k) in forward_vars:
            if c_fwd["crop"] == c and x[f_k] > 1e-6:
                c_sales[p_k] = c_sales.get(p_k, 0.0) + x[f_k]
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

    rent_out_bound_dual = 0.0
    if hasattr(res, "upper") and res.upper is not None and rent_out < len(res.upper.marginals):
        rent_out_bound_dual = -float(res.upper.marginals[rent_out])

    land_sp = ub[0] + rent_out_bound_dual
    if sc.income_tax_rate > 0 and profit > 0:
        land_sp *= (1.0 - sc.income_tax_rate)

    livestock_only_sp = 0.0
    if cattle_land_row is not None:
        livestock_only_sp = ub[cattle_land_row]
        if sc.income_tax_rate > 0 and profit > 0:
            livestock_only_sp *= (1.0 - sc.income_tax_rate)

    hectares_livestock = {}
    if sc.livestock:
        for a in sc.livestock:
            tot = float(x[y[a]]) + (float(x[y_low[a]]) if a in y_low else 0.0)
            hectares_livestock[a] = tot

    return Result(
        npv=npv,
        final_wealth=final_wealth,
        hectares={c: x[ha[c]] for c in sc.crops},
        sales=sales,
        stock={c: {p: x[i] for (cc, p), i in stock.items() if cc == c and x[i] > 1e-6} for c in sc.crops},
        cash=[x[i] for i in S],
        debt=[x[i] for i in D],
        cash_value=lam,
        internal_rate_annual=rate,
        capital_shadow_price=lam[0] - 1,
        land_shadow_price=land_sp,
        storage_shadow_price=ub[first_storage_row:first_storage_row + T],
        credit_shadow_price=ub[first_credit_row:first_credit_row + T],
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
        hectares_livestock=hectares_livestock,
        livestock_only_shadow_price=livestock_only_sp,
        livestock_only_ha=sc.livestock_only_ha,
    )

