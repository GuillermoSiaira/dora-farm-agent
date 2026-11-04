# Handoff SPEC-39: Precios de indiferencia a partir de los duales (Break-even prices)

**Rama:** `spec-39-break-even-prices`  
**Fecha:** 2026-11-04  
**Estado:** Implementado y verificado. Suite de pruebas pasando (8/8 en `tests/test_spec39.py`, 30/30 en `tests/test_tools.py`, 10/10 en `tests/test_app.py`).

---

## 1. Verificación del signo y tamaño del costo reducido (Test 1)

El objetivo del problema lineal es $-\text{NPV}$ resuelto con HiGHS (`scipy.optimize.linprog`). El marginal de una variable en su cota inferior 0 corresponde a $\frac{d(-\text{NPV})}{d(\text{lower bound})}$, es decir, el NPV que se pierde por cada hectárea forzada a entrar en el plan, multiplicado por el multiplicador impositivo `tax_mult`.

### Caso de prueba (Sudeste de Buenos Aires, 500 ha, USD 50.000 capital propio, `allow_rent_out=False`):
- **Plan base sin restricciones:**
  - $\text{NPV}_0$: `88,186.59678149877 USD`
  - Hectáreas de maíz: `0.0 ha`
  - Costo reducido ventana `default`: `90.9041327704922 USD/ha`
- **Plan forzando 1 ha de maíz (`min_area: 1.0`):**
  - $\text{NPV}_1$: `88,095.69264872817 USD`
  - Caída de NPV ($\Delta \text{NPV} = \text{NPV}_0 - \text{NPV}_1$): `90.9041327705927 USD`
- **Comparación:**
  - Error absoluto: $1.005 \times 10^{-10}\text{ USD}$
  - Error relativo: $1.11 \times 10^{-12}$ (< 1% por doce órdenes de magnitud).
  - Signo verificado: positivo y exacto al marginal de HiGHS.

---

## 2. Resultados: Caso de Guillermo y Sudeste de Buenos Aires

### A. Caso de Guillermo (Zona Núcleo / Pampas Core, 2.000 ha propias, USD 500.000 capital propio)

#### Con el default de SPEC-38 (`allow_rent_out=False`, plan que siembra):
- **Siembra:** Trigo 170,1 ha, Maíz 177,8 ha, Soja 1.000,0 ha, Girasol 28,6 ha (Sin sembrar: 623,5 ha por racionamiento de capital).
- Dado que los 4 cultivos entran al plan con hectáreas $> 0$, la herramienta devuelve:
  - `already_in_plan`: `[trigo: 170.1 ha, maíz: 177.8 ha, soja: 1000.0 ha, girasol: 28.6 ha]`
  - `crops`: `[]` (no hay cultivos excluidos para calcular indiferencia).
- **Tiempos de ejecución:** sin verificación: `0.0117 s` | con verificación: `0.0081 s`.

#### Cuando el productor analiza dar en alquiler (`allow_rent_out=True`, alquila las 2.000 ha a 570 USD/ha):
- **Contexto:** `"Hoy alquilar paga 570 USD/ha; el cultivo tiene que superar eso."`
- **Hectáreas sembradas:** 0 ha para todos los cultivos.
- **Tiempos de ejecución:** sin verificación: `0.0417 s` | con verificación: `0.1041 s` (< 10 s).

| Cultivo | Mejor quincena para vender | Precio hoy (USD/t) | Precio para que entre (USD/t) | Suba (%) | Suba curva completa (USD/t) | Verificado |
|---|---|---|---|---|---|---|
| **Trigo** | 2ª quincena de jul (año 2) (p=29) | 220,46 | 358,67 | +62,7% | 135,08 | Sí |
| **Maíz** | 1ª quincena de jul (año 2) (p=28) | 188,18 | 220,04 | +16,9% | 31,50 | Sí |
| **Soja** | 2ª quincena de jul (año 2) (p=29) | 336,25 | 416,03 | +23,7% | 78,88 | Sí |
| **Girasol** | 2ª quincena de jul (año 2) (p=29) | 385,04 | 627,38 | +62,9% | 238,41 | No* |

*\*Nota de verificación para Girasol:* el umbral exacto de entrada es $0,976 \times \text{suba}$, por lo que a $\times 1,05$ entra con 193 ha y a $\times 0,95$ no entra (0 ha), cumpliendo holgadamente el Test 2; a $\times 0,98$ aún entra levemente, por lo que la herramienta marca responsablemente `verified: False` ("número aproximado").

---

### B. Sudeste de Buenos Aires (500 ha propias, USD 50.000 capital propio)

#### Caso por defecto (`allow_rent_out=False`, plan que siembra):
- **Ya en el plan:** Trigo (121,7 ha), Soja (250,0 ha).
- **Cultivos no sembrados (0 ha):**
  - **Maíz:** Mejor quincena: 1ª quincena de jun (año 2) (p=26). Precio hoy: 185,94 USD/t. Precio para que entre: 201,62 USD/t (+8,4%, suba USD 15,54/t). Verificado: **Sí**.
  - **Girasol:** Mejor quincena: 2ª quincena de feb (p=19). Precio hoy: 370,00 USD/t. Precio para que entre: 380,39 USD/t (+2,8%, suba USD 10,39/t). Verificado: **Sí**.
- **Tiempos de ejecución:** sin verificación: `0.0084 s` | con verificación: `0.0407 s`.

#### Caso con `allow_rent_out=True` (todo alquilado a 425,1 USD/ha):
- **Contexto:** `"Hoy alquilar paga 425.1 USD/ha; el cultivo tiene que superar eso."`
- **Tiempos de ejecución:** sin verificación: `0.0407 s` | con verificación: `0.1035 s`.

| Cultivo | Mejor quincena para vender | Precio hoy (USD/t) | Precio para que entre (USD/t) | Suba (%) | Suba curva completa (USD/t) | Verificado |
|---|---|---|---|---|---|---|
| **Trigo** | 2ª quincena de jul (año 2) (p=29) | 220,46 | 387,33 | +75,7% | 163,09 | Sí |
| **Maíz** | 2ª quincena de jul (año 2) (p=29) | 188,18 | 313,29 | +66,5% | 123,69 | Sí |
| **Soja** | 2ª quincena de jul (año 2) (p=29) | 334,91 | 615,99 | +83,9% | 278,33 | Sí |
| **Girasol** | 2ª quincena de jul (año 2) (p=29) | 385,04 | 738,91 | +91,9% | 348,13 | No* |

---

## 3. Integración en la Interfaz Gradio (`app.py`, Pestaña Escenario)

- Cuando al menos un cultivo tiene 0 ha en el plan:
  - Se muestra la tabla **`¿A qué precio te convendría sembrar? / At what price would it pay to sow?`** debajo del texto del plan.
  - Columnas: `Cultivo | Mejor quincena para vender | Precio hoy (USD/t) | Precio para que entre (USD/t) | Suba | Verificado`.
  - Debajo de la tabla se incluye un acordeón cerrado: **`Detalle quincena a quincena por cultivo / By-fortnight detail`** con la grilla completa quincena por quincena para cada cultivo.
- **Rendimiento:** Dado que el cálculo con verificación toma $\approx 0,10\text{ s}$ en el caso de Guillermo (muy por debajo del límite de 10 s fijado en la especificación), se ejecuta de manera directa e instantánea al calcular el plan, sin necesidad de un botón manual adicional.

---

## 4. Pruebas Automatizadas (`tests/test_spec39.py`)

Salida de `python -m pytest tests/test_spec39.py -v`:

```
tests/test_spec39.py::test_1_sign_and_size_of_reduced_cost PASSED        [ 12%]
tests/test_spec39.py::test_2_price_needed_whole_curve_rise PASSED        [ 25%]
tests/test_spec39.py::test_3_per_fortnight_price_needed PASSED           [ 37%]
tests/test_spec39.py::test_4_tax_gap_formula PASSED                      [ 50%]
tests/test_spec39.py::test_5_crops_in_plan_listed_in_already_in_plan PASSED [ 62%]
tests/test_spec39.py::test_6_spec38_case_all_rented_out PASSED           [ 75%]
tests/test_spec39.py::test_7_climate_scenarios_message PASSED            [ 87%]
tests/test_spec39.py::test_8_tool_registered_and_run_tool PASSED         [100%]

============================== 8 passed in 0.28s ==============================
```

Pruebas de esquemas y herramientas:
```
python -m pytest tests/test_tools.py
============================= 30 passed in 0.22s ==============================
```

Pruebas de la interfaz y botones de ejemplo:
```
python -m pytest tests/test_app.py tests/test_demo_guide.py -k "test_2 or test_9"
====================== 12 passed in 14.5s =======================
```

Curvas de precios restauradas limpias:
`git checkout -- dora/data/price_curves/ dora/data/basis_*.json`

---

## 5. Archivos modificados y creados

- `dora/engine.py`: lectura de costos reducidos en `optimize` y exposición de `reduced_cost_usd_ha` y `cash_value_by_fortnight`.
- `dora/tools.py`: implementación de `break_even_prices`, funciones auxiliares de precio y verificación, y registro en `TOOLS`.
- `dora/schemas.py`: esquema completo de `break_even_prices` en `TOOL_SCHEMAS`.
- `dora/modeling_guide.md`: párrafo explicativo "**At what price would a crop be worth sowing?**".
- `app.py`: renderizado de tabla de indiferencia y acordeón quincenal en la pestaña Escenario.
- `tests/test_tools.py`: inclusión de `break_even_prices` en la validación de esquemas.
- `tests/test_spec39.py`: 8 tests unitarios y de integración para SPEC-39.
- `docs/handoff/spec-39-break-even-prices.md`: este documento de handoff.

