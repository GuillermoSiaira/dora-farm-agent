# Handoff: SPEC-21 — Rotación sobre la tierra tenida, precio sombra de una hectárea propia más e impuestos en la comparación regional

Rama: `spec-21-rotation-taxes` (creada desde `main` en commit `d390cf2`, sin tocar `main` ni mergear).

---

## 1. Qué se hizo

1. **Rotación y tope ganadero sobre la tierra efectivamente tenida (`H = owned + rent_in + buy − rent_out`):**
   - Se reemplazó la cota fija por variable `x_c <= max_crop_share * total_land` por una fila de desigualdad (`A_ub`) por cultivo `c`:
     `x_c - share * rent_in - share * buy + share * rent_out <= share * owned`, dejando `bounds[ha[c]] = (0, None)`.
   - Se actualizó la fila de `max_livestock_share` con la misma formulación sobre `H`:
     `Σ_a y_a - m * rent_in - m * buy + m * rent_out <= m * owned`.
   - `total_land = owned + rent_in_cap + max_buy_ha` quedó únicamente para el chequeo previo de factibilidad de `min_area` y para la cota superior laxa `y_a <= total_land`.
   - Se expuso `Result.rotation_shadow_price` (`dict[str, float]`, USD de hoy por hectárea adicional de tope de rotación de cada cultivo) y su reporte en `Result.summary()`, `evaluate_season` (`rotation[c].meaning = "the rotation costs you X USD per hectare of <crop> you cannot add"`) y `shadow_prices` cuando es positivo.

2. **Precio sombra de la tierra igual a `∂NPV / ∂owned_ha`:**
   - `Result.land_shadow_price` suma todos los términos donde `owned_ha` entra en lados derechos o cotas del LP, multiplicados por su coeficiente (y escalados por `1 - income_tax_rate` si `income_tax_rate > 0` y hay ganancia positiva):
     - fila de tierra compartida (`+1 * ub[0]`),
     - filas de rotación de todos los cultivos (`+max_crop_share * Σ_c ub[rot_c]`),
     - fila de tope ganadero si está activa (`+max_livestock_share * ub[livestock_share_row]`),
     - cota superior `rent_out <= owned` únicamente cuando `allow_rent_out` es verdadero (`+rent_out_bound_dual`), más salvaguarda de cota laxa `y_a <= total_land` si alguna vez resultara activa,
     - impuesto inmobiliario pagado en quincena 0 (`-land_tax_usd_ha_year * lam[0]`).
   - Se actualizó `test_land_against_perturbation` en `tests/test_engine.py` (único test existente permitido) para verificar la perturbación `±1 ha` en `owned_ha` con rotación libre en Iowa y Balcarce.

3. **Impuestos dentro del motor en `compare_regions` e impuesto a las ganancias informado aparte:**
   - En `compare_regions` (modos `same_farm` y `same_budget`, incluida la corrida sin costo de tierra `farming_only`), cada región toma de su `taxes_<país>.json` `gross_receipts_rate`, `transaction_tax_rate` y `land_tax_usd_ha_year` salvo que el productor los haya pasado explícitamente en `scenario`.
   - `income_tax_rate` queda fuera del motor en `compare_regions` (`r_dict["income_tax_rate"] = 0.0`) y se informa al lado de cada región (`npv_after_income_tax_usd`, `income_tax_rate`, `income_tax_rate_pct`, `income_tax_source`, `income_tax_note` aclarando que la tasa del archivo es societaria/corporativa y supone un tipo de contribuyente).
   - Se agregó `ranking` a nivel superior ordenado por `npv_usd` antes de impuesto a las ganancias y después de los demás impuestos, y `taxes_applied` (`field`, `name`, `rate`, `unit`, `source`, `placeholder`) en cada región.
   - `evaluate_season` para un campo individual no cambió: solo aplica impuestos si vienen en `scenario`. Se agregó la indicación en `dora/modeling_guide.md` para consultar `tax_wedge` y pasar los tres campos del archivo del país cuando el productor pide el resultado después de impuestos en un campo individual.

4. **Rendimientos con su período (14,5 meses vs anual):**
   - `Result`, `Result.summary()`, `evaluate_season` y `compare_regions` conservan `return_on_capital` y `return_on_capital_and_land` (sobre las 29 quincenas = `season_months = 14.5`) y agregan `return_on_capital_annual` y `return_on_capital_and_land_annual` calculados como `(1 + r)**(24/29) - 1` (con sus `*_pct`), junto a `deposit_rate_annual` / `deposit_rate_annual_pct`.
   - Se actualizó `build_comparison_table` en `app.py` para mostrar los retornos anuales junto a la tasa de depósito, y `SYSTEM_PROMPT` en `dora/agent.py` (más `dora/modeling_guide.md`) para exigir que al citar un retorno siempre se aclare si corresponde a la campaña de 14,5 meses o al equivalente anual.

5. **Datos impositivos y documentación:**
   - Se agregaron `"placeholder": true` y `"_review"` en `dora/data/taxes_brazil.json` y `dora/data/taxes_united_states.json`, y se dejó explícito en `income_tax_source` de los tres países (`taxes_argentina.json`, `taxes_brazil.json`, `taxes_united_states.json`) que la alícuota es corporativa/societaria. No se modificó ningún valor numérico ni las retenciones de `taxes_argentina.json`.
   - Se actualizaron las ecuaciones y números de línea en `docs/model.md`.
   - Se agregaron los 10 tests de aceptación en `tests/test_rotation_taxes.py` (todos sin red, bloqueando `urllib.request.urlopen`).

---

## 2. Archivo, función y líneas de cada ecuación

| Ecuación / lógica | Archivo y función | Líneas |
|---|---|---|
| Filas de rotación sobre tierra tenida: `x_c - share·rent_in - share·buy + share·rent_out <= share·owned` y `bounds[ha[c]] = (0, None)` | `dora/engine.py`, `optimize` | 444–454, 632 |
| Fila de tope ganadero sobre tierra tenida: `Σ_a y_a - m·rent_in - m·buy + m·rent_out <= m·owned` | `dora/engine.py`, `optimize` | 468–478 |
| Duales de rotación por cultivo: `Result.rotation_shadow_price` | `dora/engine.py`, `optimize` y `Result.summary` | 65, 151–152, 803–808 |
| Reporte textual de rotación activa en herramientas | `dora/tools.py`, `evaluate_season` y `shadow_prices` | 749–758, 830–839 |
| Precio sombra de la tierra `∂NPV/∂owned_ha`: `(ub[0] + share·Σ_c ub[rot_c] + m·ub[ls] + rent_out_dual - land_tax·λ_0)·(1 - income_tax_rate·[profit > 0])` | `dora/engine.py`, `optimize` | 779–801 |
| Duración de campaña (`season_months = (T - 1) / 2 = 14.5`) y retornos anualizados `(1 + r)**(24/29) - 1` | `dora/engine.py`, `optimize` y `Result.summary` | 52–54, 119–130, 743–748 |
| Inyección de impuestos regionales (`gross_receipts_rate`, `transaction_tax_rate`, `land_tax_usd_ha_year`) en `compare_regions` (respetando overrides del productor) | `dora/tools.py`, `compare_regions` | 1231–1234, 1275–1278 |
| Exclusión de `income_tax_rate` del motor en `compare_regions`, cálculo de `npv_after_income_tax_usd`, `taxes_applied` y `ranking` pre-Ganancias | `dora/tools.py`, `compare_regions` | 1180–1182, 1363–1411, 1425–1426 |
| Tabla UI con retornos de campaña (14,5 m) y anuales junto a tasa de depósito | `app.py`, `build_comparison_table` | 723–731, 764–820 |

---

## 3. Números de los casos de la revisión (antes y después)

### 3.1 Precio sombra de la tierra y rotación con alquiler (2.000.000 USD de capital propio)

| Caso | Métrica | Antes (`main` `d390cf2`) | Después (`spec-21-rotation-taxes`) | Perturbación directa `+1 ha` (`NPV(501) − NPV(500)`) |
|---|---|---:|---:|---:|
| **Iowa**, 500 ha propias, sin alquiler ni impuestos | `land_shadow_price` (USD/ha) | **0,00** | **720,65** | **720,65** (`0 + 0,5 × (778,13 + 663,17)`) |
| **Balcarce** (`southeast_buenos_aires`), 500 ha propias, sin alquiler ni impuestos | `land_shadow_price` (USD/ha) | **46,80** | **98,06** | **98,06** (`46,80 + 0,5 × (24,28 + 78,24)`) |
| **Iowa**, 500 ha propias, `max_rent_in_ha = 1000`, `regional_rent_usd_ha = 677,10` | Plan de siembra y alquiler | **750,0 ha maíz, 0,0 ha soja** (alquila 250,0 ha; VAN 2.414.325,44 USD) | **728,3 ha maíz, 728,3 ha soja** (alquila 956,6 ha, `H = 1.456,6 ha`; VAN 2.401.765,83 USD) | Respeta `x_c ≤ 0,5 × H` en ambos cultivos |

*(Nota: en Iowa con 500 ha propias y 500.000 USD de capital propio en `evaluate_season` sin impuestos, `land_shadow_price` también pasa de `0,00` a `720,65` USD/ha; dentro de `compare_regions` con `land_tax_usd_ha_year = 75,0` USD/ha y rutas regionales, vale `698,94` USD/ha.)*

### 3.2 Comparación regional `compare_regions` (500 ha, 500.000 USD, `same_farm`)

| Región | VAN antes (sin impuestos, USD) | VAN después (con impuestos en LP, antes de Ganancias, USD) | VAN después de Ganancias societario informado (USD) | Retorno cap.+tierra campaña (14,5 m) antes → después | Retorno cap.+tierra **anual** después (vs tasa dep. 4,0%) | `placeholder_flags.taxes` antes → después |
|---|---:|---:|---:|---:|---:|---|
| **Iowa** | 894.289,55 | **856.531,29** | 761.612,69 (25%) | 2,96% → 2,68% (`2,7%`) | **2,21%** (`2,2%`) | `false` → **`true`** |
| **Zona Núcleo** (`pampas_core`) | 785.000,00 | **775.790,00** | 671.163,41 (35%) | 3,42% → 3,31% (`3,3%`) | **2,73%** (`2,7%`) | `true` → **`true`** |
| **Mato Grosso** | 690.000,00 | **688.500,00** | 616.541,34 (34%) | 3,88% → 3,85% (`3,8%`) | **3,18%** (`3,2%`) | `false` → **`true`** |
| **Sudeste de Bs. As.** (`southeast_buenos_aires`) | 675.000,00 | **666.450,00** | 600.092,41 (35%) | **3,46%** → 3,26% (`3,3%`) *(sin imp.: 3,46% → anual **2,86%**)* | **2,69%** (`2,7%`) | `true` → **`true`** |

Ranking resultante (`out["ranking"]`, pre-Ganancias y post-impuestos operativos/inmobiliario): `["iowa", "pampas_core", "mato_grosso", "southeast_buenos_aires"]`.

---

## 4. Respuestas esperadas reconstruidas en `eval/answers.jsonl`

Se ejecutó `.\.venv\Scripts\python eval/build_answers.py` (33 respuestas generadas). De las 4 preguntas vinculadas a comparación regional (`q33`, `q34`, `q35`, `q36`; ninguna pregunta en `eval/questions.jsonl` invoca `tax_wedge` en `check`), cambiaron las 3 cuyo `check.tool` es `compare_regions` (`q35` verifica `evaluate_season`, que no inyecta impuestos regionales y mantuvo `5.95`):

| Pregunta | Herramienta y campo verificado | Valor viejo | Valor nuevo | Motivo del cambio |
|---|---|---:|---:|---|
| `q33` | `compare_regions` → `regions.pampas_core.farming_only.profit_per_sown_ha` | `417.51` | **`372.18`** | `compare_regions` ahora aplica en `pampas_core` Ingresos Brutos (`1,0%`), impuesto al cheque (`0,6%`) e Inmobiliario Rural (`15 USD/ha/año`). |
| `q34` | `compare_regions` → `regions.southeast_buenos_aires.farming_only.profit_per_sown_ha` | `114.24` | **`76.95`** | `compare_regions` ahora aplica en `southeast_buenos_aires` Ingresos Brutos (`1,0%`), impuesto al cheque (`0,6%`) e Inmobiliario Rural (`15 USD/ha/año`). |
| `q36` | `compare_regions` → `regions.iowa.freight_share_pct` | `22.6` | **`17.34`** | Con 500 ha y 50.000 USD en Iowa (`same_farm`), el pago de `500 × 75 = 37.500 USD` de property tax en `p = 0` lleva a dar más hectáreas en alquiler, y con la rotación sobre la tierra retenida (`H = owned − rent_out`) el lote sembrado pasa de 100% maíz (mayor tonelaje/ha y menor precio/t) a 50% maíz + 50% soja, bajando la incidencia ponderada del flete sobre el precio bruto. |

---

## 5. Resultado de los tests

Ejecución completa con `.\.venv\Scripts\python -m pytest`:
- **`209 passed, 3 failed, 1 skipped`** (sobre 213 tests totales = 203 previos + 10 nuevos).
- `tests/test_rotation_taxes.py`: **10/10 pasan** (Tests 1 a 10 de SPEC-21, sin red).
- `tests/test_engine.py`: **8/8 pasan** (incluido `test_land_against_perturbation` actualizado según SPEC-21).
- `tests/test_calibration.py`: **4/4 pasan** (incluido `test_eval_answers_match_current_engine`).

### Tests existentes cuyo resultado cambió y NO se editaron (según regla explícita)

Siguiendo la instrucción de modificar únicamente `test_land_against_perturbation` (`tests/test_engine.py`) y **no editar** ningún otro test existente cuyo número cambie, se dejaron intactos los siguientes 3 tests heredados:

1. **`tests/test_compare.py::test_1_same_farm_one_region_matches_evaluate_season` (línea 35)**
   - **Número viejo:** `compare_regions(...)[reg]["npv_usd"] = 225000.0`, igual a `evaluate_season(...)["npv_usd"] = 225000.0`.
   - **Número nuevo:** `compare_regions(...)[reg]["npv_usd"] = 216450.0`, mientras `evaluate_season(...)["npv_usd"]` sigue en `225000.0`.
   - **Por qué:** El test construye un escenario de `southeast_buenos_aires` sin pasar tasas impositivas (50.000 USD de capital propio y 500 ha dadas en alquiler a 350 USD/ha = 175.000 USD) y comprueba la invariante vieja de que `compare_regions` sin impuestos coincidía con `evaluate_season` sin impuestos. Con SPEC-21 §3, `evaluate_season` individual sigue sin impuestos (`225.000,00 USD`), mientras que `compare_regions` aplica `taxes_argentina.json`: `500 ha × 15 USD/ha = 7.500,00 USD` de inmobiliario rural más `0,6% × 175.000 USD = 1.050,00 USD` de impuesto al cheque sobre el cobro del alquiler (`225.000,00 − 7.500,00 − 1.050,00 = 216.450,00 USD`).

2. **`tests/test_land_taxes.py::test_land_shadow_price_passes_perturbation_with_options` (líneas 72–79)**
   - **Número viejo:** `r.land_shadow_price = 46.802073` USD/ha (con `r.npv = 2069165.45` USD sembrando 350 ha de soja y 150 ha de trigo sobre 500 ha propias gracias al tope viejo `0,5 × (500 + 100 + 100) = 350 ha`) y derivada reescalando `max_crop_share = cap / (a + 200)` igual a `46.802073` USD/ha.
   - **Número nuevo:** `r.land_shadow_price = 98.061614` USD/ha (con `r.npv = 2057836.97` USD, alquilando 100 ha a 47 USD/ha para tener `H = 600 ha` y sembrar 300 ha de soja + 300 ha de trigo), mientras la perturbación del test que achica artificialmente `max_crop_share = 350 / (a + 200)` al subir `owned_ha` da `2057836.968300 - 2057762.027265 = 74.941035` USD/ha.
   - **Por qué:** Ese test replicaba exactamente el truco viejo de `test_engine.py` (`max_crop_share = cap / total_land` para congelar el tope de rotación en hectáreas al perturbar `owned_ha`). Con SPEC-21 §2, `r.land_shadow_price` mide `∂NPV/∂owned_ha` manteniendo `max_crop_share = 0,5` constante (`98,061614` USD/ha, verificado en `test_5_land_shadow_price_with_land_tax_and_rent`).

3. **`tests/test_regions_map.py::test_scenario_iowa_and_shadow_prices_perturbation` (líneas 64–69)**
   - **Número viejo:** Para `Scenario(region="iowa", own_capital_usd=2_000_000, max_crop_share=0.7)`, `r_land.land_shadow_price = 665.070780` USD/ha, igual a la diferencia finita congelando `cap = 350 ha` mediante `max_crop_share = cap / a` (`665.070780` USD/ha).
   - **Número nuevo:** `r_land.land_shadow_price = 744.214980` USD/ha (`= 665.070780 + 0.7 × 113.063143`), mientras la diferencia finita del test con `max_crop_share = cap / a` congelado sigue dando `2372107.489788 - 2371442.419009 = 665.070780` USD/ha.
   - **Por qué:** Es otra copia directa del viejo `test_land_against_perturbation` de `tests/test_engine.py`: al mantener `max_crop_share = 0,7` fijo, una hectárea propia más en Iowa agrega 0,7 ha de maíz y 0,3 ha de soja (`744,21` USD/ha), mientras que el test achica `max_crop_share` para obligar a que la hectárea extra sea 100% soja (`665,07` USD/ha).

---

## 6. Datos que quedaron provisorios y por qué

- **`dora/data/taxes_argentina.json` (`"placeholder": true`):** Se mantuvieron sin cambios las retenciones (`export_duties`: soja 33%, maíz 12%, trigo 12%, girasol 7%) y la estimación de Inmobiliario Rural (`15.0` USD/ha/año) tal como exige la spec y las reglas, dado que los precios MAGyP ya son netos de retenciones (`export_duties` solo se informa en `tax_wedge`) y no se leyó durante esta sesión el texto oficial del decreto vigente en Boletín Oficial. Se aclaró en `income_tax_source` que el 35% corresponde a la tasa societaria/corporativa.
- **`dora/data/taxes_brazil.json` (`"placeholder": true` agregado):** El ITR (`~$3 USD/ha/ano` promedio en Mato Grosso) figuraba como estimación sin bandera `placeholder`. Se marcó `"placeholder": true` con nota `"_review"` hasta abrir una publicación primaria de Receita Federal / IMEA, y se aclaró en `income_tax_source` que el 34% (`IRPJ + CSLL`) es tasa societaria (`lucro real`).
- **`dora/data/taxes_united_states.json` (`"placeholder": true` agregado):** El impuesto inmobiliario agrícola (`~$30/acre`, redondeado a `75.0` USD/ha) y la tasa combinada efectiva corporativa (`~25%`) figuraban como estimaciones sin bandera `placeholder`. Se marcó `"placeholder": true` con nota `"_review"` hasta verificar contra una publicación primaria de Iowa Department of Revenue / ISU Extension, y se aclaró en `income_tax_source` que es tasa corporativa mientras la mayoría de las explotaciones tributan como personas físicas o pass-through.

---

## 7. Puntos ambiguos o decisiones de implementación

1. **Dual de la cota `rent_out <= owned` cuando `allow_rent_out=False`:**
   - Cuando `allow_rent_out` es `False`, la cota superior de la variable `rent_out` es `0.0` (no `sc.owned`). Si el alquiler regional supera el margen agrícola, el solver deja `rent_out = 0` con marginal de cota superior no nulo, pero `∂(0)/∂owned = 0`. En `dora/engine.py` (línea 780) se condicionó `rent_out_bound_dual` a `if sc.allow_rent_out:` para que `Result.land_shadow_price` coincida exactamente con `∂NPV/∂owned_ha` tanto con `allow_rent_out=True` como con `allow_rent_out=False` (verificado en `test_5_land_shadow_price_with_land_tax_and_rent`).
2. **`income_tax_rate` pasado en `scenario` al llamar a `compare_regions`:**
   - La spec pide que el impuesto a las ganancias quede fuera del motor en la comparación y que ni el plan ni el ranking dependan de la tasa de ganancias. Si el usuario pasa `income_tax_rate` en `scenario`, `compare_regions` valida su rango, fuerza `r_dict["income_tax_rate"] = 0.0` dentro del LP para preservar intactos el plan y el ranking pre-Ganancias, y usa esa tasa para calcular `npv_after_income_tax_usd` informado al lado.
3. **Campos de descomposición en `Result`:**
   - Además de `Result.rotation_shadow_price`, se expusieron `land_row_shadow_price`, `livestock_share_shadow_price` y `rent_out_bound_shadow_price` con defaults en `0.0` para que la descomposición de `Result.land_shadow_price` (Test 6) pueda auditarse directamente sobre `Result` sin recalcular el LP.
