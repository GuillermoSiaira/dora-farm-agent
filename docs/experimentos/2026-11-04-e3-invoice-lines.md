# Experimento E3: Desglose de Facturas por Renglón, Rubro y Cultivo (04/11/2026)

> **Aclaración sobre la naturaleza y origen de los precios:**
> - **Facturas de prueba con formatos reales:** Los documentos son facturas de prueba diseñadas en los formatos comerciales reales (Factura A electrónica argentina y Factura de cooperativa estadounidense con exención agropecuaria "Ag exempt"), con precios tomados de fuentes públicas vigentes al 3 de noviembre de 2026 (catálogo Campo Simple y tipo de cambio oficial BCRA).
> - **Circularidad en Iowa (r4, r5):** Los precios de los insumos en Iowa fueron tomados directamente del archivo de datos de DORA `dora/data/iowa_2026.json` (presupuesto oficial de Iowa State University Extension and Outreach FM 1712 / A1-20), debido a que las fuentes web externas de EE.UU. devolvieron 403 o no resolvieron. Por ende, **en Iowa los precios coinciden con el modelo por construcción**; no constituyen una medición independiente frente al mercado de insumos estadounidense.

---

## 1. Pregunta

¿Puede DORA procesar comprobantes comerciales que contienen múltiples insumos o ítems impositivos en una misma factura, asociar cada renglón a su cultivo y rubro de costo correspondiente, sumar las dosis del mismo rubro, excluir los impuestos recuperables (IVA), comparar cada rubro contra la referencia zonal, detener preventivamente compras parciales y, tras la confirmación explícita del productor de que cubre todo el rubro, re-planificar el plan agrícola reflejando la evolución exacta del Valor Actual Neto (VAN)?

---

## 2. Comparación: Antes (SPEC-34) vs. Después (SPEC-36 con revisión de confirmación)

En SPEC-34, DORA leía la imagen con alta fidelidad pero el procesamiento posterior perdía renglones cuando un comprobante contenía más de un insumo (en `r2` cargó solo la semilla omitiendo el glifosato; en `r4` cargó solo el fertilizante omitiendo la semilla; en `r3` no reconoció los principios activos atrazina y S-metolacloro). Además, el recálculo del plan dependía de que el modelo copiara los costos a un nuevo llamado de `evaluate_season`.

En SPEC-36:
1. Agrupa los renglones por `(cultivo, rubro)` y suma sus importes en USD/ha.
2. Reconoce principios activos de protección vegetal y fertilizantes.
3. Excluye renglones de impuestos (`IVA`, `percepciones`) como `"tax"`.
4. Detecta compras parciales de agroquímicos si no cubren todo el ciclo (`covers_whole_item`).
5. **Regla de confirmación:** Cuando el productor confirma que un comprobante cubre la totalidad del rubro (`covers_whole_item: true`), la confirmación del usuario prevalece sobre la regla preventiva del 50 %, aplicándolo con `reason = "confirmed by the farmer"`.
6. Re-planifica de forma nativa en el motor (`plan_before` y `plan_after`), entregando el cambio de VAN y hectáreas en la misma respuesta.

| Caso | Insumos / Región | Renglones Factura | Líneas Pasadas (SPEC-36) | Grupos OK (T1) | Aplicado OK (T1) | VAN Post OK (T1) | Con Confirmación (T2) | Resultado Previo en SPEC-34 |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|---|
| **r1** | Balcarce Trigo: Urea + MAP + IVA | 2 insumos + IVA | 2 / 2 (100 %) | Sí | Sí (225,00 USD/ha) | Sí (86.709,57 USD) | N/A (aplicó directo) | Sumó montos pero generó dos propuestas desconectadas |
| **r2** | Pergamino Soja: Semilla + Glifosato (ARS) | 2 insumos + 2 IVA | 2 / 2 (100 %) | Sí | Semilla sí (74,01 USD/ha); Glifosato no (parcial) | Sí (197.421,39 USD) | **Ambos aplicados** (210.629,79 USD) | Cargó solo semilla; glifosato descartado por no reconocer activo |
| **r3** | Pergamino Maíz: Atrazina + Dual Gold | 2 insumos + IVA | 2 / 2 (100 %) | Sí | No aplicado (parcial 28,99 USD/ha) | Sí (frenado OK) | **Aplicado OK** (190.399,61 USD) | No reconoció atrazina ni metolacloro; no cargó nada |
| **r4** | Iowa Corn: Anhydrous Ammonia + Seed Corn | 2 insumos | 2 / 2 (100 %) | Sí | Fertilizante sí (418,70); Semilla sí (281,00) | Sí (295.124,70 USD) | N/A (ambos aplicados) | Cargó solo fertilizante; semilla perdida |
| **r5** | Iowa Soybean: Herbicida postemergente | 1 insumo | 1 / 1 (100 %) | Sí | No aplicado (parcial 185,16 USD/ha) | Sí (frenado OK) | **Aplicado OK** (295.141,16 USD) | Leyó USD/ha y aplicó sin advertir que era herbicida parcial |

---

## 3. Resultados Detallados de la Evaluación (`eval/results/e3_invoice_lines.json`)

### Caso r1 (Balcarce — Trigo: Urea + MAP)
- **Renglones procesados:** Urea granulada (12.300 USD / 100 ha = 123 USD/ha) + MAP (10.200 USD / 100 ha = 102 USD/ha) + IVA 10,5 % (2.362,50 USD, excluido como impuesto).
- **Agrupamiento:** Consolidado en `wheat.fertilizer = 225.00 USD/ha`.
- **Comparación zonal:** 225,00 USD/ha vs. 214,20 USD/ha de referencia zonal (+5,0 % de desvío).
- **Decisión:** Aplicado directamente (`apply=True`, sin alertas).
- **Re-planificación:** VAN antes = 88.187 USD; VAN después = 86.710 USD (diferencia: -1.477 USD; trigo pasa de 121,7 ha a 119,3 ha).

### Caso r2 (Pergamino — Soja: Semilla DM 46E25 + Glifosato)
- **Renglones procesados:** Semilla de soja (9.175.225,14 ARS) y Glifosato (2.551.763,20 ARS) convertidos a tipo de cambio oficial BCRA (1.549,72 ARS/USD) sobre 80 ha; dos renglones de IVA excluidos.
- **Turno 1:**
  - `soybean.seed = 74,01 USD/ha` vs. 61,80 USD/ha zonal (+19,8 % desvío) → **Aplicado**.
  - `soybean.crop_protection = 20,58 USD/ha` vs. 72,40 USD/ha zonal (-71,6 % desvío) → **Frenado preventivamente** por compra parcial de agroquímicos.
  - Re-planificación parcial: VAN = 197.421 USD.
- **Turno 2 (Confirmación: *"Sí, es todo lo que gasto en agroquímicos para ese cultivo"*):**
  - Con `covers_whole_item: true`, la confirmación del productor valida el insumo a pesar del desvío de -71,6 %, adoptando `reason = "confirmed by the farmer"`.
  - Ambos costos se integran a `costs_override`.
  - **Re-planificación total:** VAN pasa a **210.629,79 USD** (`npv_after_ok = True`).

### Caso r3 (Pergamino — Maíz: Atrazina + Dual Gold)
- **Renglones procesados:** Atrazina 90 % (1.560 USD / 120 ha = 13,00 USD/ha) + Dual Gold / S-metolacloro (1.918,80 USD / 120 ha = 15,99 USD/ha) + IVA (730,55 USD, excluido).
- **Turno 1:**
  - Consolidado en `corn.crop_protection = 28,99 USD/ha` vs. 91,20 USD/ha zonal (-68,2 % desvío).
  - Frenado preventivamente como protección parcial. `npv_after` es None.
- **Turno 2 (Confirmación: *"Sí, es todo lo que gasto en agroquímicos para ese cultivo"*):**
  - Con `covers_whole_item: true`, se aplica el costo confirmado (`reason = "confirmed by the farmer"`).
  - **Re-planificación:** VAN pasa de 180.301 USD a **190.399,61 USD** (+10.098 USD de ganancia). `npv_after_ok = True`.

### Caso r4 (Iowa — Corn: Anhydrous Ammonia + Seed Corn)
- **Renglones procesados:** Anhydrous ammonia (27.110,83 USD / 64,75 ha = 418,70 USD/ha) + Seed corn (18.194,75 USD / 64,75 ha = 281,00 USD/ha).
- **Agrupamiento y aplicación:**
  - `corn.fertilizer = 418,70 USD/ha` (coincidencia exacta 0,0 % con ISU default) → **Aplicado**.
  - `corn.seed = 281,00 USD/ha` (coincidencia exacta 0,0 % con ISU default) → **Aplicado**.
- **Re-planificación:** Ambos costos ingresan simultáneamente en `costs_override`. VAN = 295.124,70 USD.

### Caso r5 (Iowa — Soybean: Herbicida postemergente)
- **Renglones procesados:** Herbicida postemergente (11.998,18 USD / 64,75 ha = 185,16 USD/ha).
- **Turno 1:** `soybean.crop_protection = 185,16 USD/ha` vs. 185,30 USD/ha zonal (-0,1 % desvío) → **Frenado** como compra parcial de agroquímicos.
- **Turno 2 (Confirmación: *"Yes, that is all my crop protection for that crop"*):**
  - Al confirmarse cobertura total, se aplica inmediatamente.
  - **Re-planificación:** VAN pasa a **295.141,16 USD** (+14 USD de ganancia). `npv_after_ok = True`.

---

## 4. Costo Real del Experimento

Cifras consolidadas del archivo de resultados (`eval/results/e3_invoice_lines.json`):

| Métrica | Valor |
|---|:---:|
| **Casos evaluados** | 5 (r1 a r5) |
| **Turnos con confirmación interactiva** | 3 (r2, r3, r5) |
| **Costo total de inferencia (LLM)** | **0,8728 USD** |

---

## 5. Qué Aprendimos

1. **Lo que se trasladó del modelo al código determinístico:**
   - **Agrupación aditiva por rubro:** En r1 y r4, múltiples insumos para un mismo cultivo se suman en USD/ha en código exacto sin pérdidas ni sobreescrituras.
   - **Exclusión tributaria garantizada:** El IVA y las percepciones se excluyen automáticamente en la herramienta (`cost_item: "tax"`), impidiendo que distorsionen los márgenes brutos.
   - **Confirmación del productor como fuente soberana de verdad:** El sistema detiene preventivamente compras parciales o atípicas; cuando el productor confirma explícitamente que el insumo cubre el total del ciclo, la herramienta adopta el dato con `reason = "confirmed by the farmer"`, manteniendo la trazabilidad del desvío en la UI.
   - **Re-planificación instantánea en una sola ronda:** La optimización dual (`plan_before` y `plan_after`) ocurre dentro de la ejecución de `record_document`. El modelo ya no necesita coordinar llamadas secundarias a `evaluate_season`, reduciendo latencia y consumo de tokens.

2. **Lo que sigue siendo tarea del modelo multimodal:**
   - La transcripción visual de la factura (cantidades, importes netos, monedas, descripciones técnicas).
   - La inferencia del cultivo (`crop`) y rubro (`cost_item`) de cada línea cuando no vienen explícitos en el encabezado.
   - La formulación clara y empática de las preguntas de confirmación al productor.
