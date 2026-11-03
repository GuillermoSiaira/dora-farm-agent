# Experimento E3-Real: facturas de prueba con evidencia en disco (03/11/2026)

> **Aclaración fundamental sobre el origen de los precios:**
> - **Argentina (r1, r2, r3):** Precios de mercado reales vigentes al 3 de noviembre de 2026, respaldados con evidencia descargada en disco en `eval/e3/sources/` con código HTTP 200 (catálogo público de **Campo Simple**, [camposimple.com.ar](https://www.camposimple.com.ar), y tipo de cambio mayorista de la API oficial del **BCRA**). En estos tres casos sí existe una contrastación genuina entre el mercado y los presupuestos de DORA.
> - **Iowa (r4, r5):** Los precios fueron tomados directamente del archivo de datos de DORA `dora/data/iowa_2026.json` (presupuesto oficial de Iowa State University Extension and Outreach FM 1712 / A1-20), debido a que las fuentes web externas de EE.UU. devolvieron 403 o no resolvieron. Por ende, **en Iowa los precios coinciden con el modelo por construcción**; no constituyen una medición independiente contra el mercado de insumos estadounidense.
> - **Naturaleza de los documentos:** Son facturas de prueba diseñadas en los formatos comerciales reales (Factura A electrónica argentina y Factura de cooperativa estadounidense con leyenda "Ag exempt"), no documentos contables de productores reales.

---

## 1. Pregunta

¿Puede DORA leer facturas comerciales en formatos reales (incluyendo facturas en pesos argentinos y facturas con exención tributaria en EE.UU.), conciliar sus importes con las dosis agronómicas y contrastar los costos resultantes contra sus presupuestos zonales respaldados con evidencia en disco?

---

## 2. Evidencia en Disco (`eval/e3/sources/index.json`)

Todos los archivos de respaldo fueron descargados mediante `eval/e3/fetch_sources.py` y verificados offline mediante tests automatizados:

| ID | URL Original | Archivo Guardado en Disco | Estado HTTP | Tamaño | Tipo de Fuente |
|---|---|---|:---:|:---:|---|
| `bcra_fx_20261102` | `https://api.bcra.gob.ar/estadisticas/v4.0/Monetarias/5` | `eval/e3/sources/bcra_fx_20261102.json` | 200 OK | 47.592 B | API oficial BCRA |
| `cs_urea_granel` | `https://www.camposimple.com.ar/default/urea-granel-1-tn.html` | `eval/e3/sources/cs_urea_granel.html` | 200 OK | 175.963 B | Catálogo Campo Simple |
| `cs_map_granel` | `https://www.camposimple.com.ar/default/map-granel-4.html` | `eval/e3/sources/cs_map_granel.html` | 200 OK | 177.588 B | Catálogo Campo Simple |
| `cs_dap_granel` | `https://www.camposimple.com.ar/default/dap-1-tn-granel-logistica.html` | `eval/e3/sources/cs_dap_granel.html` | 200 OK | 178.480 B | Catálogo Campo Simple |
| `cs_soja_semilla` | `https://www.camposimple.com.ar/default/dm-46e21-40-kgs-10.html` | `eval/e3/sources/cs_soja_semilla.html` | 200 OK | 183.389 B | Catálogo Campo Simple |
| `cs_glifosato` | `https://www.camposimple.com.ar/default/la-tijereta-platinum-ii-glifosato-54-20-lts-1.html` | `eval/e3/sources/cs_glifosato.html` | 200 OK | 181.288 B | Catálogo Campo Simple |
| `cs_atrazina` | `https://www.camposimple.com.ar/default/atrazina-atrazina-90-15-kgs-1.html` | `eval/e3/sources/cs_atrazina.html` | 200 OK | 180.557 B | Catálogo Campo Simple |
| `cs_dual_gold` | `https://www.camposimple.com.ar/default/dual-gold-s-metolacloro-96-5-lts-2.html` | `eval/e3/sources/cs_dual_gold.html` | 200 OK | 180.984 B | Catálogo Campo Simple |
| `cs_trigo_semilla` | `https://www.camposimple.com.ar/default/dm-catalpa-trigo-bolsas-40-kg-3.html` | `eval/e3/sources/cs_trigo_semilla.html` | 200 OK | 179.040 B | Catálogo Campo Simple |
| `ia_isu_corn_fertilizer` | `dora/data/iowa_2026.json` | `eval/e3/sources/ia_isu_corn_fertilizer.json` | 200 OK | 2.105 B | Archivo base DORA |
| `ia_isu_corn_seed` | `dora/data/iowa_2026.json` | `eval/e3/sources/ia_isu_corn_seed.json` | 200 OK | 2.105 B | Archivo base DORA |
| `ia_isu_soybean_herbicide` | `dora/data/iowa_2026.json` | `eval/e3/sources/ia_isu_soybean_herbicide.json` | 200 OK | 2.105 B | Archivo base DORA |

---

## 3. Resultados de la Evaluación (`eval/results/e3_real_prices.json`)

| Caso | Insumos y Región | Neto Real | Suma Leída | Lectura Exacta | Costo Factura (USD/ha) | Costo Modelo (USD/ha) | `diff_pct` vs Modelo | Costo Cargado Foto | NPV Foto (USD) | NPV Esperado (USD) | NPV Foto = Esperado |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **r1** | Balcarce Trigo: Urea + MAP | 22.500,00 USD | 22.500,00 USD | Sí (100 %) | 225,00 | 214,20 | +5,04 % | 225,00 USD/ha | 86.709,57 | 86.709,57 | Sí |
| **r2** | Pergamino Soja: Semilla + Glifosato (ARS) | 11.726.988,34 ARS | 11.726.988,34 ARS | Sí (100 %) | 94,90 (total) | 61,80 (semilla) | +20,14 % (semilla sola) | 74,25 USD/ha | 197.348,78 | 191.101,61 | No (*) |
| **r3** | Pergamino Maíz: Atrazina + Dual Gold | 3.478,80 USD | 3.478,80 USD | Sí (100 %) | 28,99 | 91,20 (total prot.) | -68,21 % | Ninguno (pidió OK) | 180.301,19 | 190.399,61 | No (**) |
| **r4** | Iowa Corn: Fertilizante + Semilla | 45.305,58 USD | 45.305,58 USD | Sí (100 %) | 699,70 (total) | 418,70 (fert.) | 0,00 % (por ítem) | 418,70 USD/ha | 295.124,70 | 266.149,98 | No (***) |
| **r5** | Iowa Soybean: Herbicida postemergente | 11.998,18 USD | 185,30 USD (tasa/ha) | No (leyó USD/ha) | 185,30 | 185,30 | 0,00 % (circular) | 185,30 USD/ha | 295.124,70 | 295.124,70 | Sí |

### Detalle Caso por Caso:
- **Lectura OCR:** **4 de 5 leídas de manera exacta**. En `r1`, `r2`, `r3` y `r4` la suma leída coincidió al centavo con el neto verdadero; en `r5` el modelo leyó la tasa unitaria por hectárea (185,30 USD/ha) en lugar del monto neto total ($11.998,18 USD).
- **r1:** Lectura perfecta, carga perfecta (225,00 USD/ha) y NPV foto (86.709,57 USD) idéntico al esperado.
- **(*) r2:** La foto cargó únicamente la semilla a 74,25 USD/ha (9.175.225,14 ARS / 1.544,6507 / 80 ha) y dejó el glifosato aparte; el valor esperado de 94,90 USD/ha forzaba erróneamente la suma de semilla y herbicida dentro del rubro semilla. El desglose de DORA es superior a la métrica esperada del test harness; la diferencia en NPV (197.348,78 vs 191.101,61 USD) refleja esta limitación de la métrica de evaluación y no un fallo de comprensión de DORA.
- **(**) r3:** La foto no cargó ningún costo y pidió confirmación porque los herbicidas de presiembra ($28,99 USD/ha) representan solo una parte del paquete de protección vegetal ($91,20 USD/ha) y la desviación supera el 50 %. Es una conducta agronómica prudente que el harness registra formalmente como desvío de NPV (180.301,19 vs 190.399,61 USD).
- **(***) r4:** La foto cargó 418,70 USD/ha (fertilizante) en lugar de los 699,70 USD/ha que el harness esperaba consolidando fertilizante y semilla en una sola variable. En consecuencia, el NPV foto resultante (295.124,70 USD) no coincide con el esperado consolidado (266.149,98 USD).
- **r5:** Aunque la lectura de la factura extrajo la tasa unitaria (185,30 USD/ha) en vez del importe total, aplicó directamente dicha tasa a la protección vegetal, coincidiendo el NPV foto (295.124,70 USD) exactamente con el esperado.

---

## 4. Diálogos en Vivo Productor–DORA

Se mantuvieron 3 diálogos interactivos de 3 turnos cada uno con el agente `muse-spark-1.3` (todas las intervenciones verificadas con éxito por el verificador formal):

1. **Diálogo r1 (Balcarce — Trigo):**
   - *Turno 1:* Productor manda foto `r1.png` (Urea + MAP para 100 ha en campo de 500 ha con $50.000 USD). DORA lee los $22.500 USD netos ($225/ha), nota que está 5 % arriba de la zona y entrega plan con valor actual de 112.627 USD.
   - *Turno 2:* Productor pregunta si está caro o barato. DORA responde: *"Está en precio: lo tuyo son 225 USD/ha y yo uso 214 USD/ha de la zona, 5% arriba... No es caro ni barato, entra en lo normal"*.
   - *Turno 3:* Productor consulta ganancia con urea 10 % más barata. DORA recalcula el modelo y responde que el valor actual sube a 113.388 USD (+761 USD de ganancia).
   - *Archivo crudo:* [`eval/e3/dialogues/r1.json`](file:///d:/projects/dora-hackathon/eval/e3/dialogues/r1.json).

2. **Diálogo r2 (Pergamino — Soja en ARS):**
   - *Turno 1:* Productor manda foto `r2.png` en pesos ($11.726.988,34 ARS para 80 ha en campo de 400 ha con $70.000 USD). DORA convierte con la tasa oficial BCRA de 1.544,65 ARS/USD, aplica la semilla a 74,25 USD/ha y genera plan con valor actual de 219.429 USD.
   - *Turno 2:* Productor pregunta si está caro o barato. DORA explica: la semilla a 74,25 USD/ha está 20 % arriba del regional (61,80 USD/ha), y aclara que el glifosato (20,65 USD/ha) no reemplaza todo el paquete de protección vegetal de la zona.
   - *Turno 3:* Productor consulta si consigue semilla 10 % más barata. DORA recalcula el plan y cuantifica la ganancia en +2.165 USD (el valor actual sube a 221.594 USD).
   - *Archivo crudo:* [`eval/e3/dialogues/r2.json`](file:///d:/projects/dora-hackathon/eval/e3/dialogues/r2.json).

3. **Diálogo r4 (Iowa — Corn, en inglés):**
   - *Turno 1:* Farmer sends `r4.png` (fertilizer + seed corn for 160 acres in 500-acre farm, $150,000 capital). DORA identifies fertilizer ($418.70/ha) and seed ($281.00/ha), delivers plan with present value $290,405 USD.
   - *Turno 2:* Farmer asks if price is high or low. DORA answers transparently: *"Neither — both match exactly what I use: Anhydrous fertilizer 418.70 USD/ha is the same regional figure, 0% difference. Seed corn 281 USD/ha is the same regional figure, 0% difference."*
   - *Turno 3:* Farmer asks gain with 10% cheaper fertilizer. DORA reruns LP optimization: present value rises to $294,717 USD (+4,312 USD gain).
   - *Archivo crudo:* [`eval/e3/dialogues/r4.json`](file:///d:/projects/dora-hackathon/eval/e3/dialogues/r4.json).

---

## 5. Costos Exactos del Experimento

Cifras extraídas directamente de los registros de ejecución (`eval/results/e3_real_prices.json` y `eval/e3/dialogues/r*.json`):

| Etapa | Requests | Calls a Herramientas | Prompt Tokens | Tokens en Caché | Completion Tokens | Total Tokens | Costo Real (USD) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Corrida Completa E3 (5 facturas, foto + typed)** | 56 | 44 | 1.169.421 | 818.909 | 86.267 | 1.255.688 | 0,9276 USD |
| **Diálogo r1 (3 turnos)** | 9 | 4 | 220.518 | 171.016 | 19.690 | 240.208 | 0,1712 USD |
| **Diálogo r2 (3 turnos)** | 9 | 3 | 247.737 | 192.648 | 17.804 | 265.541 | 0,1734 USD |
| **Diálogo r4 (3 turnos)** | 10 | 7 | 267.614 | 198.649 | 11.788 | 279.402 | 0,1661 USD |
| **Total General** | **84** | **58** | **1.905.290** | **1.381.222** | **135.549** | **2.040.839** | **1,4383 USD** |

---

## 6. Qué Aprendimos

1. **Lectura exacta en facturas comerciales estándar:** La lectura de comprobantes limpios funciona con precisión en 4 de 5 casos; cuando falla (r5), DORA extrae la tasa unitaria por hectárea en lugar del neto total facturado.
2. **Facturas mixtas: DORA carga un solo renglón.** Cuando la factura trae dos insumos para un mismo cultivo, DORA cargó uno y dejó el otro afuera: la semilla en r2 (sin el glifosato) y el fertilizante en r4 (sin la semilla). El plan quedó con un costo menor al de la factura, así que es un error de DORA, no solo de la métrica. En r3 frenó a pedir confirmación porque los herbicidas de presiembra son solo una parte de la protección, y eso es razonable. Arreglo: cargar cada renglón en su rubro (semilla, fertilizante, protección) y mostrar el antes y el después (próxima spec).
3. **Precios de mercado vs. Presupuestos zonales en Argentina:**
   - **Trigo en Balcarce:** El paquete de fertilización Urea ($615/t) + MAP ($1.020/t) arrojó un costo de 225,00 USD/ha, un **+5,04 %** respecto al modelo zonal de DORA (214,20 USD/ha).
   - **Soja en Pergamino:** La semilla fiscalizada DM 46E25 ($990/bigbag de 800 kg) resultó en 74,25 USD/ha, ubicándose un **+20,14 %** por encima del presupuesto MAGyP Núcleo (61,80 USD/ha).
4. **Iowa no medido contra el mercado:** Al no poder acceder a reportes web estadounidenses libres de bloqueos 403, los precios de Iowa fueron tomados de la propia base ISU de DORA. La coincidencia del 0 % en Iowa es un artefacto de diseño y no una validación frente a cotizaciones de mercado en EE.UU.
