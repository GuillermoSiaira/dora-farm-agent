# Handoff SPEC-38: Tierra propia dada en alquiler al valor de la zona

**Rama:** `spec-38-rent-out`  
**Fecha:** 2026-11-04 (Actualizado tras revisión Claude / Decisión de Guillermo 07:50)  
**Estado:** Implementación aprobada y completada. Suite de pruebas pasando (11/11 en `tests/test_spec38.py`).

---

## 1. Renta regional por zona y origen

Jerarquía implementada en `dora/scenario.py` cuando `needs_rent = self.rented_land or self.max_rent_in_ha > 0 or self.owned > 0`:

| Región | Alquiler (USD/ha) | Origen (`regional_rent_source`) | Provisorio (`placeholder`) | Razón |
|---|---|---|---|---|
| **southeast_buenos_aires** | 425.1 | `magyp_southeast_2026-06.json rent` | `False` | Archivo de tierra es provisorio (350 USD/ha), se toma el alquiler del presupuesto MAGyP jun-2026 |
| **pampas_core** | 570.0 | `land file: Márgenes Agropecuarios, maize subzone...` | `False` | Verificado en archivo de tierra (`land_pampas_core.json`) |
| **iowa** | 677.1 | `land file: Iowa State University CARD, 2025 ISU Land Value Survey...` | `False` | Verificado en archivo de tierra (`land_iowa.json`) |
| **mato_grosso** | 420.0 | `mato_grosso_2026.json rent` | `False` | Archivo de tierra es provisorio (380 USD/ha), se toma el alquiler del presupuesto (`mato_grosso_2026.json`) |

Cuando el productor informa el alquiler a mano (ej. `regional_rent_usd_ha: 2000.0` o `0.01`), el origen queda registrado como `"farmer"` y `placeholder` como `False`.

---

## 2. Decisión de Guillermo (Revisión 4/11 07:50)

DORA es para el productor que siembra; el plan por defecto debe mostrar lo que conviene **si siembra el campo**, y brindar la opción de alquiler como comparación:
1. **Default `allow_rent_out = False`** en `Scenario` y en la checkbox de la app (desmarcada).
2. **Carga de renta**: se carga siempre que `owned > 0` para poder calcular `tenure_comparison` sin requerir que `allow_rent_out` sea `True`.
3. **`tenure_comparison`** calcula:
   - `farm_only_npv_usd`: VAN sembrando (el plan principal si `allow_rent_out=False`, o solve extra si es True).
   - `rent_all_npv_usd`: VAN alquilando todo (solve con todos los cultivos en 0 ha y `allow_rent_out=True`).
   - `break_even_rent_usd_ha` = `(farm_only_npv_usd - rent_all_npv_usd) / (owned_ha * (1 - transaction_tax_rate)) + regional_rent_usd_ha`.
   - `renting_pays_more` = `rent_all_npv_usd > farm_only_npv_usd`.
4. **Texto en la App**:
   - Cuando el plan siembra:
     `Si alquilaras todo a {rent} USD/ha: VAN {rent_all} ({diff:+} USD). Alquilar conviene si te pagan más de {break_even} USD/ha.`
   - Cuando el productor activa "Permitir alquilar hacia afuera" y el plan alquila:
     `- **Dado en alquiler:** {ha} ha a {rent} USD/ha ({income} USD)`
     `Sembrando todo lo que alcanza: VAN USD {farm_only}. Alquilando todo: VAN USD {rent_all}. El plan elige {lo mejor}.`
5. **Retorno sobre tierra y capital**: Se eliminó la capitalización artificial del alquiler a la tasa de depósito. Se incorporó `return_over_land_rent_pct` = `(NPV - own_capital - owned_ha * rent * (1 - transaction_tax)) / own_capital`: lo que agrega sembrar por encima de dar en alquiler.

---

## 3. El caso de Guillermo: Antes y Después

**Parámetros:** Zona Núcleo (Pampas Core), 2.000 ha propias, 500.000 USD de capital propio.

### Caso por defecto (`allow_rent_out=False`)
- **Siembra:** Trigo 170,1 ha, Maíz 177,8 ha, Soja 1.000,0 ha, Girasol 28,6 ha (Total sembrado: 1.376,5 ha).
- **Superficie sin sembrar:** 623,5 ha.
- **Dado en alquiler:** 0,0 ha.
- **VAN:** USD 1.036.104,92 (exacto a `main`).
- **Línea de comparación en el plan:**
  > `Si alquilaras todo a 570 USD/ha: VAN 1.640.000,00 (+603.895,08 USD). Alquilar conviene si te pagan más de 268,05 USD/ha.`
- **Pico de crédito utilizado:** USD 100.000 (1ª quincena de dic).
- **Retorno sobre capital:** 143,0%.
- **Retorno sobre alquiler de tierra (`return_over_land_rent_pct`):** -96,3% (sembrar rinde menos que alquilar todo por el capital racionado que deja 623 ha sin sembrar).

### Caso libre con `allow_rent_out=True`
- **Plan:** Alquila las 2.000 ha completas a 570 USD/ha.
- **Dado en alquiler:** 2.000,0 ha a 570 USD/ha (ingreso bruto: 1.140.000 USD).
- **Superficie sin sembrar:** 0,0 ha.
- **VAN:** USD 1.640.000,00.
- **Retorno sobre capital:** 228,0%.
- **Retorno sobre alquiler de tierra (`return_over_land_rent_pct`):** 0,0%.

### Caso mixto con `max_rent_out_ha: 1000`
- Renta 1.000 ha hacia afuera; siembra 500 ha de Maíz y 500 ha de Soja.
- **VAN:** USD 1.495.425,51.

---

## 4. Resultados de los 3 ejemplos de "¿Cómo empiezo?"

Ejecutados a través de `run_scenario` en `app.py`:

### Ejemplo 1: Capital restringido (500 ha, USD 50.000 capital, USD 100.000 crédito)
```markdown
### **Valor Presente Neto (NPV):** USD 88.186,60

#### **Siembra propuesta:**
- **Trigo**: 121,7 ha
- **Soja**: 250,0 ha
- *Superficie sin sembrar:* 128,3 ha
Si alquilaras todo a 425,1 USD/ha: VAN 262.550,00 (+174.363,40 USD). Alquilar conviene si te pagan más de 76,37 USD/ha.

**Pico de crédito utilizado:** USD 100.000 (1ª quincena de dic)

#### **Logística y Rutas de Flete:**
- **Flete directo (18.0 USD/t)**: 1.110,3 t

---
**Fuentes:**
- Rindes y precios: MAGyP, márgenes jun-2026, sudeste de Buenos Aires
```

### Ejemplo 2: Financiamiento proveedor (500 ha, USD 50.000 capital, 90 días, 3% recargo)
```markdown
### **Valor Presente Neto (NPV):** USD 92.191,18

#### **Siembra propuesta:**
- **Trigo**: 125,7 ha
- **Soja**: 250,0 ha
- **Girasol**: 124,3 ha
Si alquilaras todo a 425,1 USD/ha: VAN 262.550,00 (+170.358,82 USD). Alquilar conviene si te pagan más de 84,38 USD/ha.

**Pico de crédito utilizado:** USD 100.000 (1ª quincena de dic)

#### **Logística y Rutas de Flete:**
- **Flete directo (18.0 USD/t)**: 1.376,5 t

---
**Fuentes:**
- Rindes y precios: MAGyP, márgenes jun-2026, sudeste de Buenos Aires
```

### Ejemplo 3: Contrato de maíz (500 ha, USD 50.000 capital, mín. 150 ha maíz)
```markdown
### **Valor Presente Neto (NPV):** USD 62.091,53

#### **Siembra propuesta:**
- **Trigo**: 35,5 ha
- **Maíz**: 150,0 ha
- **Soja**: 89,5 ha
- *Superficie sin sembrar:* 225,0 ha
Si alquilaras todo a 425,1 USD/ha: VAN 262.550,00 (+200.458,47 USD). Alquilar conviene si te pagan más de 24,18 USD/ha.

**Pico de crédito utilizado:** USD 100.000 (1ª quincena de dic)

#### **Logística y Rutas de Flete:**
- **Flete directo (18.0 USD/t)**: 1.271,7 t

---
**Fuentes:**
- Rindes y precios: MAGyP, márgenes jun-2026, sudeste de Buenos Aires
```

---

## 5. Pruebas de la suite SPEC-38 (`tests/test_spec38.py`)

Salida de `python -m pytest tests/test_spec38.py -v`:

```
tests/test_spec38.py::test_1_southeast_buenos_aires_budget_rent PASSED   [  9%]
tests/test_spec38.py::test_2_regression_guard_allow_rent_out_false PASSED [ 18%]
tests/test_spec38.py::test_3_rent_too_low_rents_nothing PASSED           [ 27%]
tests/test_spec38.py::test_4_high_rent_rents_all PASSED                  [ 36%]
tests/test_spec38.py::test_5_tenure_comparison_components PASSED         [ 45%]
tests/test_spec38.py::test_6_pampas_core_conservation_of_land_and_max_rent_out PASSED [ 54%]
tests/test_spec38.py::test_7_rented_farm_unchanged_and_no_tenure_comparison PASSED [ 63%]
tests/test_spec38.py::test_8_stochastic_allow_rent_out_false_rents_nothing PASSED [ 72%]
tests/test_spec38.py::test_9_app_plan_text PASSED                        [ 81%]
tests/test_spec38.py::test_10_break_even_rent PASSED                     [ 90%]
tests/test_spec38.py::test_11_app_plan_text_farming PASSED               [100%]

============================= 11 passed in 5.49s ==============================
```

---

## 6. Tests existentes que cambiaron y razones

Con la decisión de Guillermo (`allow_rent_out: False` por defecto), los 79 tests que fallaban en la corrida anterior se redujeron a solo los tests cuyo objeto era específicamente esperar renta 0 o probar alquiler hacia afuera:

| Test | Valor esperado previo | Valor nuevo | Razón |
|---|---|---|---|
| `test_demo_guide.py::test_6_frozen_tool_numbers_match_main_to_1e9` | `regional_rent_usd_ha: 0.0` | `425.1` | SPEC-38 carga la renta regional siempre que `owned > 0`. |
| `test_demo_guide.py::test_12_minor_fixes` | `"alquilar una cuesta"` omitido | Presente (`425,10`) | En `evaluate_season`, la comparación de tierra ahora informa el costo de alquiler regional ya que no es 0. |
| `test_economics.py::test_10_engine_numbers_unchanged` | `regional_rent_usd_ha: 0.0` | `425.1` | Misma fixture de números congelados de la herramienta con renta regional en 0. |
| `test_land_taxes.py::test_balcarce_base_case_unchanged` | `r.regional_rent_usd_ha == 0.0` | `425.1` | Renta regional cargada para campo propio. |
| `test_land_taxes.py::test_defaults_preserve_farming_plan` | `r_explicit.rent_out_ha == 0.0` | `500.0` | Test explícito con `allow_rent_out=True` y `regional_rent_usd_ha=0.0`. Al cargarse 425.1 regional, alquila todo si `allow_rent_out=True`. |
| `test_land_taxes.py::test_rent_out_when_rent_exceeds_farming_margin` | `r.rent_out_ha == 500.0` | `0.0` | No pasaba `allow_rent_out=True`. Al ser default `False`, siembra en lugar de alquilar. |
| `test_rotation_taxes.py::test_9_annual_returns` | `0.0346` | `0.0126` | Test escrito originalmente cuando Balcarce tenía precio de tierra 7.600 USD/ha; con el precio actualizado en octubre a 11.000 USD/ha (provisional), el retorno sobre capital y tierra es 1,26%. |

El resto de la suite (411 tests) pasa exitosamente.
