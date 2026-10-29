# Handoff: SPEC-22 — Precios sombra con impuesto a las ganancias y renombrado en tramos de capital

Rama: `spec-22-income-tax-duals` (creada desde `main` en commit `528141e`, sin tocar `main` ni mergear).

---

## 1. Qué se cambió (archivo, función y líneas)

1. **`dora/engine.py` — `optimize` (líneas 730–920):**
   - Se definió una única regla después de calcular el impuesto a las ganancias (`profit = pre_tax_wealth - sc.own_capital_usd`, líneas 710–717):
     `tax_mult = (1.0 - sc.income_tax_rate) if (sc.income_tax_rate > 0 and profit > 0) else 1.0` (línea 731).
   - Se aplicó `tax_mult` de forma uniforme a **todos** los precios sombra informados, sin repetir el `if`:
     - `constraint_duals` (`min_area`, `max_area`, `max_payments_by`, `min_share`, `forward_sale`) en líneas 733–753.
     - `route_capacity_shadow_prices` en líneas 755–760 y `leg_shadow_prices` en líneas 766–778.
     - `land_row_shadow_price`, `livestock_share_shadow_price`, `rent_out_bound_shadow_price` y `land_shadow_price` en líneas 790–801 (usando `float(sc.max_crop_share)` explícito en línea 795 para que una restricción `min_share` nunca pise la variable `share`).
     - `rotation_shadow_price` en líneas 803–806 y `livestock_only_shadow_price` en línea 808.
     - `storage_by_option[m]["shadow_price_by_fortnight"]` y `storage_by_option[m]["shadow_price_usd_t"]` para toda opción `m` con capacidad finita en líneas 873–877, de donde también sale `Result.storage_shadow_price` (`own_silo`, líneas 892–900 y 916).
     - `Result.credit_shadow_price` (cada quincena) en líneas 902 y 917.
     - `Result.capital_shadow_price = (float(lam[0]) - 1.0) * tax_mult` en línea 914 ("lo que vale hoy un dólar más de capital propio por encima de depositarlo a la tasa de mercado, después de Ganancias": `∂NPV/∂K = λ_0·(1 − t) + t·d` menos `1 − t + t·d`, con `d = (1 + r_i)^{−29}`).
   - `Result.cash_value` (`lam`, línea 912), `Result.internal_rate_annual` (`rate`, línea 913) y las tasas de los tramos no cambian (las tasas son cocientes de `λ_p` donde cualquier factor constante se cancela).

2. **`dora/engine.py` — `Result.get_capital_stretches` (líneas 105–106):**
   - Dentro de cada tramo se renombró `"usd_today_per_extra_dollar"` a `"capital_shadow_price_today"` y se agregó `"capital_shadow_price_meaning": "what one more dollar of own capital is worth today, for the whole season; the stretch's own figure is rate_for_stretch"`.
   - Se mantuvieron sin cambios los campos `"usd_today_per_extra_dollar"` de nivel superior (campaña completa) en `Result.summary()`, `shadow_prices()` y `compare_regions()`.

3. **`dora/modeling_guide.md` (línea 86):**
   - Único consumidor fuera de tests que mencionaba `usd_today_per_extra_dollar` junto a los tramos (`capital_stretches`): se actualizó para indicar que `capital_shadow_price_today` (o `usd_today_per_extra_dollar` a nivel campaña) corresponde exclusivamente al capital propio inicial de toda la campaña y nunca a un tramo o a la peor quincena (cuya cifra propia es `rate_for_stretch_pct`).

4. **`docs/model.md` — secciones *Objective* y *Shadow prices (duals)* (líneas 54, 99, 130–141):**
   - Se documentó explícitamente que `cash_value` (`λ_p`), `internal_rate_annual` y las tasas por tramo (`rate_for_stretch`) son antes del impuesto a las ganancias, mientras que todo precio sombra informado es después del impuesto a las ganancias (`× (1 − t)` cuando `income_tax_rate > 0` y `profit > 0`), incluyendo la derivación `(λ_0 − 1)·(1 − t)` para `capital_shadow_price` y el campo `capital_shadow_price_today` en `Result.get_capital_stretches`.

5. **`tests/test_income_tax_duals.py` (nuevo, 7 tests sin red):**
   - Bloquea `urllib.request.urlopen` con fixture `autouse=True`.
   - Verifica para `t = 0.35` y `t = 0.0` (control): crédito (`±1` USD), silo propio (`±1` t), capital propio (`∂NPV/∂K − (1 − t + t·d)`, tol `1e-4`), tierra propia (`±1` ha), `min_area` activa (`±1` ha), `max_payments_by` activa (`±100` USD), opción `silo_bag` de SPEC-20 con `capacity_t = 200` (`±1` t), invariancia de `cash_value` / `internal_rate_annual` / `rate_for_stretch`, esquema nuevo de `get_capital_stretches()`, e igualdad con `main` a `1e-9` para `t = 0`.

---

## 2. Números del caso antes y después

Escenario base del problema:
`Scenario(owned_ha=500, own_capital_usd=50_000, credit_line_usd=100_000, storage_capacity_t=200, monthly_price_rise=0.03, income_tax_rate=0.35)`
(`NPV = 78.401,45` USD, `final_wealth = 82.206,48` USD; `d = (1 + r_i)^{-29} = 0,95371376`, valor presente después de impuestos de depositar 1 USD = `1 − t + t·d = 0,98379982`, `λ_0 = 1,16259571`).

| Magnitud (`t = 0.35`) | Antes (`main` `528141e`) | Después (`spec-22`) | Derivada finita `±1` del NPV |
|---|---:|---:|---:|
| `sum(credit_shadow_price)` (USD/USD línea) | `0.122190` | **`0.079424`** | `0.079424` |
| `sum(storage_shadow_price)` / `own_silo.shadow_price_usd_t` (USD/t) | `32.823030` | **`21.334969`** | `21.334969` |
| `capital_shadow_price` (USD hoy sobre depositar) | `0.162596` (`λ_0 − 1`) | **`0.105687`** (`(λ_0 − 1)(1 − t)`) | `∂NPV/∂K = 1.089487`; `− (1 − t + t·d) = 0.105687` |
| `land_shadow_price` (USD/ha propia) | `23.435448` | **`23.435448`** | `23.435448` |

Casos adicionales con `t = 0.35` (vs `t = 0.0` sin escalar):
- `min_area` activa (`corn >= 150 ha`, `own_capital_usd = 2_000_000`): antes `67.850739` → después **`44.102980` USD/ha** (`= 0.65 × 67.850739`, coincide con derivada `±1` ha).
- `max_payments_by` activa (`2026-09 <= 60_000 USD`): antes `0.065927` → después **`0.042852` USD/USD** (`= 0.65 × 0.065927`, coincide con derivada `±100` USD).
- Opción SPEC-20 con capacidad (`silo_bag`, `capacity_t = 200 t`): antes `23.216586` → después **`15.090781` USD/t** (`= 0.65 × 23.216586`, coincide con derivada `±1` t).
- Control `t = 0.0`: `NPV = 94.940,702874047`, `final_wealth = 99.548,425230583`, y todos los duales coinciden bit a bit (`diff = 0.0`, `< 1e-9`) con `main` (`528141e`).

---

## 3. Resultado de la suite de tests

Comando ejecutado: `.\.venv\Scripts\python -m pytest -v`

- **Resultado global:** `218 passed, 1 failed, 1 skipped` (220 recolectados: 213 de `main` + 7 nuevos en `tests/test_income_tax_duals.py`).
- **`tests/test_income_tax_duals.py`:** **7/7 pasan** (sin red).
- **Ningún test existente fue modificado.**

### Único test existente que cambió de resultado (dejado sin editar según las reglas)

- **`tests/test_agent_polish.py::test_stretch_rate_calculation`** (línea 62):
  - **Qué chequeaba:** `assert first["usd_today_per_extra_dollar"] == round(float(r.capital_shadow_price), 4)` sobre `first = r.get_capital_stretches()[0]` en el escenario base de Balcarce (`area_ha=500, own_capital_usd=50_000, region="southeast_buenos_aires"`).
  - **Valor viejo:** `first["usd_today_per_extra_dollar"] == 0.1608` (pasaba).
  - **Resultado nuevo:** `KeyError: 'usd_today_per_extra_dollar'`; el mismo valor (`0.1608`) ahora está en `first["capital_shadow_price_today"] == 0.1608` junto con `first["capital_shadow_price_meaning"]`.
  - **Por qué:** el punto 4 de SPEC-22 pide explícitamente renombrar `"usd_today_per_extra_dollar"` a `"capital_shadow_price_today"` dentro de `Result.get_capital_stretches` para evitar que se lea como valor de un dólar en ese tramo, sin editar tests existentes.
