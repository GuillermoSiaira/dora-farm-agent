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

from dataclasses import dataclass

import numpy as np
from scipy.optimize import linprog

from .scenario import CALENDAR, FORTNIGHTS, Scenario, fortnight_name, fortnightly_rate


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

    def summary(self) -> dict:
        def r(x, n=2):
            return round(float(x), n)
        return {
            "npv_usd": r(self.npv),
            "final_wealth_usd": r(self.final_wealth),
            "hectares": {c: r(h, 1) for c, h in self.hectares.items() if h > 1e-6},
            "max_credit_usd": r(max(self.debt)),
            "capital_shadow_price": r(self.capital_shadow_price, 4),
            "land_shadow_price_usd_ha": r(self.land_shadow_price),
            "storage_shadow_price_usd_t": r(sum(self.storage_shadow_price)),
            "credit_line_shadow_price": r(sum(self.credit_shadow_price), 4),
            "fortnights_with_scarce_capital": [fortnight_name(p) for p in range(FORTNIGHTS - 1)
                                               if self.internal_rate_annual[p] > self.market_rate_annual + 1e-3],
        }


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
    idx = _Index()

    ha = {c: idx.new() for c in sc.crops}
    sell, stock = {}, {}
    for c in sc.crops:
        for p in range(CALENDAR[c]["harvest"], T):
            sell[c, p] = idx.new()
            stock[c, p] = idx.new()
    S = [idx.new() for _ in range(T)]
    D = [idx.new() for _ in range(T)]

    # Objective: maximize the present value of final wealth (linprog minimizes).
    discount = (1 + ri) ** -(T - 1)
    obj = np.zeros(idx.n)
    obj[S[-1]], obj[D[-1]] = -discount, discount

    # Equalities: cash in every fortnight, grain stock of every crop.
    A_eq, b_eq = [], []
    payments = {c: sc.payments_per_ha(c) for c in sc.crops}
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
        A_eq.append(row)
        b_eq.append(sc.own_capital_usd if p == 0 else 0.0)
    for c in sc.crops:
        h = CALENDAR[c]["harvest"]
        for p in range(h, T):
            row = np.zeros(idx.n)
            row[stock[c, p]], row[sell[c, p]] = 1, 1
            if p == h:
                row[ha[c]] = -sc.crop_yield(c)
            else:
                row[stock[c, p - 1]] = -1
            A_eq.append(row)
            b_eq.append(0.0)

    # Inequalities: land, storage per fortnight, credit line per fortnight.
    A_ub, b_ub = [], []
    row = np.zeros(idx.n)
    for c in sc.crops:
        row[ha[c]] = 1
    A_ub.append(row); b_ub.append(sc.area_ha)
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

    bounds = [(0, None)] * idx.n
    for c in sc.crops:
        bounds[ha[c]] = (0, sc.max_crop_share * sc.area_ha)
        bounds[stock[c, T - 1]] = (0, 0)         # no grain left at the end of the season
    bounds[D[-1]] = (0, 0)                       # and the credit is repaid

    res = linprog(obj, A_ub=np.array(A_ub), b_ub=b_ub, A_eq=np.array(A_eq), b_eq=b_eq,
                  bounds=bounds, method="highs")
    if res.status != 0:
        raise RuntimeError(f"The program has no solution: {res.message}")

    x = res.x
    # Marginals are d(objective)/d(right-hand side); the objective is -NPV.
    lam = [-m for m in res.eqlin.marginals[:T]]
    ub = [-m for m in res.ineqlin.marginals]
    rate = [(lam[p] / lam[p + 1]) ** 24 - 1 if lam[p + 1] > 1e-12 else float("inf") for p in range(T - 1)]

    return Result(
        npv=-res.fun,
        final_wealth=x[S[-1]] - x[D[-1]],
        hectares={c: x[ha[c]] for c in sc.crops},
        sales={c: {p: x[i] for (cc, p), i in sell.items() if cc == c and x[i] > 1e-6} for c in sc.crops},
        stock={c: {p: x[i] for (cc, p), i in stock.items() if cc == c and x[i] > 1e-6} for c in sc.crops},
        cash=[x[i] for i in S],
        debt=[x[i] for i in D],
        cash_value=lam,
        internal_rate_annual=rate,
        capital_shadow_price=lam[0] - 1,
        land_shadow_price=ub[0],
        storage_shadow_price=ub[first_storage_row:first_storage_row + T],
        credit_shadow_price=ub[first_credit_row:first_credit_row + T],
        market_rate_annual=sc.deposit_rate_annual,
    )
