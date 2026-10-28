# DORA: mapa del código para revisar la matemática

Guía para leer el código parte por parte: qué archivo mirar, qué función, qué ecuación arma y de dónde salen sus números. Repositorio: `D:\projects\dora-hackathon`. Los números de línea corresponden al 28/10/2026 (commit `36b7136`).

Ver también: `docs/model.md` (las ecuaciones) y `docs/specs/SPEC-17-count-once.md` (los arreglos que salieron de esta revisión).

## 1. ¿Es un problema de la mochila?

No. En SIG-Agent elegíamos qué importaciones entraban en un presupuesto fijo, y cada una entraba entera o no entraba: eso es una mochila, con variables 0/1. En DORA las hectáreas, las toneladas y los dólares son divisibles, así que es un **programa lineal continuo de varios períodos**: 30 quincenas encadenadas por la caja y por el stock de granos.

La idea de la mochila está igual: la tierra, el silo y el crédito son capacidades que los cultivos se disputan. Pero el motor no elige objetos; reparte cantidades en el tiempo.

**Qué maximiza:** la riqueza al final de la campaña (plata en caja menos deuda), traída a valor de hoy con la tasa de los depósitos:

  max (S₂₉ − D₂₉) / (1 + r_depósito)²⁹ + valor final de la tierra comprada + valor final de la hacienda

No maximiza una tasa de ganancia. Las tasas se calculan después:
- **Retorno sobre el capital** = ganancia ÷ capital propio. Es una división hecha con el resultado, no algo que el modelo optimiza.
- **Cuánto rinde un dólar en cada tramo** sale de los precios sombra de la caja: si λₚ es lo que vale un dólar extra en la quincena p, la tasa entre dos quincenas es λ_inicio ÷ λ_fin − 1.

Maximizar la riqueza final y maximizar la tasa dan el mismo plan cuando el capital propio está fijo, porque la tasa es la riqueza dividida por un número que no cambia.

## 2. Recorrido de una pregunta

```
Productor ─► app.py (Gradio) o whatsapp.py
              │
              ▼
          agent.py ── Muse Spark lee SYSTEM_PROMPT + modeling_guide.md
              │        y decide qué herramienta llamar (schemas.py)
              ▼
          tools.py ── _validate() limpia los parámetros que puso el modelo
              │        y arma un Scenario
              ▼
        scenario.py ── Scenario completa lo que falta con datos de dora/data/
              │         y calcula precios netos y calendario de pagos
              ▼
          engine.py ── optimize(): arma las matrices, llama a HiGHS,
              │         devuelve Result con el plan y los precios sombra
              ▼
          tools.py ── convierte Result en JSON para el modelo
              ▼
          agent.py ── el modelo redacta; verifier.py coteja cada número
```

## 3. Archivos, en el orden en que conviene leerlos

| # | Archivo | Qué mirar | Para qué |
|---|---|---|---|
| 1 | `docs/model.md` | Todo (100 líneas) | Las ecuaciones escritas en matemática. **Está desactualizado:** la tabla de la caja no tiene tierra, impuestos ni rutas. |
| 2 | `dora/scenario.py` | `REGIONS` (l. 1–100), `class Scenario` (l. 241), `payments_per_ha` (l. 549), `net_price_route` y `farm_gate_decomposition` (l. 445–530) | Todos los parámetros con su valor por defecto; el calendario de pagos; cómo se arma el precio que recibe el productor. |
| 3 | `dora/engine.py` | `optimize()` (l. 150–620) | El modelo matemático entero. Detalle en la sección 4. |
| 4 | `dora/engine.py` | `class Result`, `get_capital_stretches`, `summary` (l. 28–140) | Cómo se leen el plan y los precios sombra después de resolver. |
| 5 | `dora/tools.py` | `_validate` (l. 88), `evaluate_season` (l. 305), `shadow_prices` (l. 426), `sensitivity` (l. 465), `compare_regions` (l. 771) | La puerta de entrada: qué acepta el modelo de lenguaje y qué devuelve. |
| 6 | `dora/schemas.py` | `TOOL_SCHEMAS` | La lista de parámetros que el modelo de lenguaje puede tocar. |
| 7 | `dora/agent.py` | `SYSTEM_PROMPT` (l. 33), `Agent.ask` (l. 103) | Las reglas del agente y el ciclo pregunta → herramientas → verificador. |
| 8 | `dora/modeling_guide.md` | Todo | Cómo traducir lo que dice un productor a parámetros. |
| 9 | `dora/verifier.py` | `verify` (l. 98) | Cómo se controla que ningún número sea inventado. |
| 10 | `tests/test_engine.py` | Las pruebas de perturbación | Cómo se comprueba que cada precio sombra es correcto: se mueve el recurso una unidad y se mide cuánto cambia el resultado. |

Archivos de apoyo: `prices.py` y `feeds.py` (precios CBOT, MAGyP, dólar BCRA), `geo.py` (hectáreas y región desde el mapa), `media.py` (voz y fotos), `observatory.py` (referencia regional diaria), `app.py` (la interfaz).

## 4. El modelo matemático dentro de `optimize()` (`engine.py`)

### Variables (l. 180–221)
| Variable | Qué es |
|---|---|
| `ha[c]` | hectáreas sembradas con el cultivo c |
| `rent_in`, `rent_out`, `buy` | hectáreas que toma en alquiler, que da en alquiler y que compra |
| `y[a]`, `y_low[a]` | hectáreas con hacienda (en tierra compartida y en bajos solo ganaderos) |
| `sell[c, p, r]` | toneladas de c vendidas en la quincena p por la ruta r |
| `stock[c, p]` | toneladas de c guardadas al final de p (solo desde la cosecha) |
| `S[p]`, `D[p]` | plata en caja y deuda al final de p |
| `f_k` | toneladas entregadas en una venta a término |

### Objetivo (l. 223–240)
Riqueza final descontada, más el valor final de la tierra comprada (`precio × (1 + valorización)^(30/24)`) y de la hacienda. El signo va al revés porque el solver minimiza.

### Restricciones temporales (las que encadenan las quincenas)

**Caja, una ecuación por quincena (l. 248–308).** Lo que hay al cierre es lo de antes con su interés, más lo que entra, menos lo que sale:

  Sₚ − Dₚ = (1 + r_depósito)·Sₚ₋₁ − (1 + r_crédito)·Dₚ₋₁ + ventas − pagos por hectárea − almacenaje ± tierra ± hacienda (+ capital propio en p = 0)

- Los pagos por hectárea caen en la quincena en que se pagan: labores y semilla al sembrar, fertilizante y agroquímicos repartidos, gastos de estructura repartidos hasta la cosecha (`payments_per_ha`, `scenario.py` l. 549). El calendario está en `REGIONS[...]["calendar"]`.
- Las ventas entran en la quincena en que se vende, al precio neto de esa quincena y esa ruta.
- Tierra: alquiler pagado o cobrado y compra, todo en la quincena 0.
- El impuesto a los débitos y créditos multiplica pagos y cobros (`tx_pay`, `tx_rec`).

**Stock de granos, una ecuación por cultivo y quincena desde la cosecha (l. 310–325):**

  en la cosecha: stock + ventas = hectáreas × rinde
  después: stock + ventas = stock de la quincena anterior

**Cierre de la campaña (cotas, l. 498–500):** no queda grano al final (stock₂₉ = 0) y la deuda se cancela (D₂₉ = 0).

**Ventas a término (l. 327–334 y 160–173):** se entregan las toneladas pactadas en la quincena pactada; no pueden ser antes de la cosecha ni después del fin de la campaña.

### Restricciones de capacidad (desigualdades, l. 336–495)
| Restricción | Línea | Precio sombra que da |
|---|---|---|
| Tierra: cultivos + hacienda + dada en alquiler ≤ propia + alquilada + comprada | 338–347 | cuánto vale una hectárea más |
| Bajos solo ganaderos; tope de hacienda | 349–364 | |
| Silo: stock total ≤ capacidad, **en cada quincena** | 366–372 | cuánto vale una tonelada más de silo en cada quincena |
| Crédito: deuda ≤ línea, **en cada quincena** | 373–377 | cuánto vale un dólar más de crédito en cada quincena |
| Capacidad de cada ruta | 379–394 | cuánto vale un camión o un cupo de tren más |
| Capacidad de cada tramo compartido (puerto, vía, barcazas), por campaña o por mes | 396–468 | ídem por tramo |
| Las del productor: mínimo o máximo de hectáreas, mínimo de participación | 470–495 | cuánto le cuesta esa decisión |
| Rotación: ningún cultivo en más de la mitad de la tierra (cota) | 498 | |

### Después de resolver (l. 510–620)
- `linprog` con HiGHS. Si no hay solución posible, dice qué restricción del productor la impide.
- Los precios sombra salen de `res.eqlin.marginals` y `res.ineqlin.marginals`, con el signo dado vuelta.
- El impuesto a las ganancias se aplica después de resolver: `tasa × ganancia` (l. 586). No cambia el plan, solo el resultado.

## 5. De dónde sale cada parámetro

| Parámetro | De dónde sale | Estado |
|---|---|---|
| Rinde, costos por hectárea, precio a cosecha, gastos de comercialización | MAGyP "Márgenes y resultados", junio 2026 (`dora/data/magyp_*.json`); Iowa: ISU 2026; Mato Grosso: provisorio | Balcarce verificado; zona núcleo y Mato Grosso provisorios |
| Calendario de siembra, pagos y cosecha | Supuesto (`REGIONS[...]["calendar"]`) | Supuesto |
| Curva de precios por mes | Futuros CBOT y MAGyP, automáticos (`feeds.py`), con la base de cada región | Base de Argentina verificada; Iowa y Mato Grosso provisorias |
| Suba mensual del precio sin curva (0,8 %), almacenaje (2 USD/t/mes) | Supuesto (`Scenario`) | Supuesto |
| Tasas: depósito 4 %, crédito 10 % anual | Supuesto | Supuesto |
| Capital 50.000, crédito 100.000, silo 1.000 t, 500 ha | Valores de ejemplo; los cambia el productor | — |
| Precio y alquiler de la tierra | `land_*.json` | Núcleo e Iowa verificados; Balcarce y Mato Grosso provisorios |
| Impuestos | `taxes_*.json` | Argentina provisorio (retenciones desactualizadas) |
| Rutas y fletes | `routes_*.json` | Las 4 provisorias |
| Hacienda | `livestock_*.json` | Provisorio |

## 6. Cómo el modelo de lenguaje arma el modelo matemático

1. **No escribe ecuaciones.** Solo llena un formulario: el escenario, con los campos que define `schemas.py` (hectáreas, cultivos, capital, crédito, región, restricciones, etc.).
2. Las reglas para llenarlo están en `modeling_guide.md`. Por ejemplo: "no quiero más de 200 ha de soja" se traduce en `{"type": "max_area", "crop": "soybean", "ha": 200}`; si no dice nada de la tierra, se supone propia.
3. `tools._validate` revisa cada campo (tipo, rango, región válida) y devuelve errores que el modelo tiene que corregir.
4. `Scenario` completa todo lo que el productor no dijo con los datos de la región y los supuestos.
5. `build_scenario` le devuelve al modelo lo que entendió, marcando qué dijo el productor, qué viene del MAGyP y qué es supuesto, para que lo muestre antes de calcular.
6. Las ecuaciones las arma siempre el mismo código (`optimize`). El modelo de lenguaje solo cambia los números de entrada y qué restricciones del productor se agregan.

## 7. Lo que encontré para revisar juntos

1. **[Resuelto en SPEC-17, 28/10] Flete contado dos veces al comparar regiones.** El gasto de comercialización del MAGyP ya incluye flete; con rutas, además se resta el flete de la ruta (`farm_gate_decomposition`, `scenario.py` l. 506–508). Arreglo previsto: SPEC-17.
2. **[Resuelto en SPEC-17, 28/10] Alquiler contado dos veces.** Si `rented_land` es verdadero, `payments_per_ha` suma el alquiler del MAGyP a cada hectárea sembrada (l. 573) y, a la vez, la variable `rent_in` paga el alquiler regional. **Confirmado el 28/10** con 500 ha alquiladas y 50.000 USD: en Iowa, con un solo alquiler, siembra 79 ha de maíz y gana 8.245 USD; con los dos alquileres a la vez no siembra nada y solo gana el interés del depósito (2.427). Pasa en `compare_regions` cuando el productor dice que alquila, porque ahí se agrega el alquiler regional. Además, con `rented_land` el motor informa 500 ha tomadas en alquiler aunque siembre menos, porque esas hectáreas no le cuestan nada. Arreglo: un solo alquiler (la variable `rent_in`), en la SPEC-17 junto con el flete.
3. **Todo el alquiler se paga en la quincena 0.** Es lo habitual en Argentina (por adelantado), pero en Iowa se paga en dos cuotas. Es un supuesto a declarar.
4. **El impuesto a las ganancias no está dentro del modelo.** Se aplica al final. No cambia el plan, pero sí el precio sombra después de impuestos (l. 604–615).
5. **[Resuelto en SPEC-17, 28/10] `docs/model.md`** reescrito desde el código (tierra, impuestos, rutas, tramos, hacienda, regla del precio).
6. **En un campo solo, sin comparar regiones, no hay precio de alquiler** (`regional_rent_usd_ha` = 0 por defecto), así que dar el campo en alquiler no aparece como alternativa. Es la vista "margen de la campaña"; la del costo de la tierra solo está en la comparación.

## 8. Cambios del 28/10 (SPEC-17 y SPEC-18)

- **Regla del precio (SPEC-17):** cada fuente declara dónde cotiza su precio (`price_point` en `dora/data/*.json`). MAGyP cotiza en puerto y su gasto de comercialización incluye el flete: ese flete (`freight_in_marketing_usd_t`, provisorio: tarifa CATAC) sale de la comercialización y lo lleva la ruta. Iowa y Mato Grosso cotizan en el acopio local: la base ya descuenta el viaje. Funciones: `Scenario.marketing_per_t`, `Scenario.inland_cost`, `Scenario.destination_price` (`scenario.py`).
- **Alquiler (SPEC-17):** se paga solo por la variable `rent_in`. `payments_per_ha` ya no lo suma.
- **Foto aérea (SPEC-18):** `dora/sam_mask.py` decodifica las máscaras de SAM 3.1; `dora/field_image.py` llama al modelo; `tools.assess_field_image` mide las hectáreas dañadas y vuelve a optimizar con lo sembrado fijo. El agente le pasa las fotos a la herramienta (`run_tool(..., images=...)`).
