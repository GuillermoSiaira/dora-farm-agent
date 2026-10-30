# Handoff: SPEC-24 — Costo por respuesta correcta verificada

Rama: `spec-24-economics` (creada desde `main` en commit `adf49c3`, sin tocar `main` ni mergear).

---

## 1. Resumen del trabajo

Se implementó el sistema de medición económica y telemetría de evaluación de la SPEC-24:
- **Solo mide:** No se alteró el motor (`dora/engine.py`), ni los cálculos de las herramientas (`dora/tools.py`), ni los prompts del sistema, ni el comportamiento del agente.
- **Construcción sobre E1:** Se aprovechó la estructura preexistente en `eval/run_eval.py` (`_agent_record`, `_baseline_record`, `commit`, tokens por pregunta) sin rehacerla.
- **Precios auditados:** En `eval/pricing.json`, ningún precio fue inventado ni tomado de memoria. Los precios no disponibles en páginas públicas sin autenticación quedaron en `null` con su fuente y fecha de lectura.
- **Tests sin red:** Se crearon los 10 tests de aceptación en `tests/test_economics.py`. Toda la suite existente pasa sin modificaciones (258 passed, 1 skipped por requerir red).

---

## 2. Archivos modificados y creados

### 1. `dora/agent.py`
- Inicialización en `Agent.__init__` de `self.usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "requests": 0}`.
- En `_complete()`: incremento de `self.usage["requests"] += 1` por cada llamada a la API.
- Extracción de tokens cacheados de entrada desde `prompt_tokens_details.cached_tokens` (compatible con diccionarios y objetos OpenAI), registrándose en `self.usage["cached_prompt_tokens"]` solo si la API los reporta (> 0).

### 2. `eval/baseline.py`
- En `ask_baseline()`: se añade `"requests": 1` y, si la respuesta de la API reporta `cached_tokens`, se incluye `"cached_prompt_tokens"`.

### 3. `eval/run_eval.py`
- Medición del tiempo de pared con `time.perf_counter()` para cada pregunta tanto en `_agent_record` como en `_baseline_record`, registrando `latency_s` en segundos con 4 decimales.
- Cada registro por pregunta almacena: `requests`, `prompt_tokens`, `completion_tokens`, `latency_s` y opcionalmente `cached_prompt_tokens`.
- Nuevos argumentos de línea de comandos:
  - `--provider`: proveedor del modelo (`meta`, `modal`, `baseten`, etc.).
  - `--concurrency`: número de trabajadores concurrentes (por defecto 1; implementado con `concurrent.futures.ThreadPoolExecutor`).
- En el diccionario de resultados (`results_data`):
  - `provider`: nombre del proveedor.
  - `api_host`: host extraído limpiamente con `urllib.parse.urlparse` a partir de `DORA_API_BASE` o `client.base_url`. Sanitizado para no contener parámetros de autenticación ni tokens.
  - `commit`: commit actual (con sufijo `-dirty` si hay cambios locales).

### 4. `eval/pricing.json` (nuevo)
Catálogo formal de precios por modelo y proveedor:
- **`muse-spark-1.3@modal` / `default@modal`:**
  - Facturación: `serverless_gpu`
  - GPU: L40S (1 GPU)
  - Precio: `0.000542 USD/seg` (equivalente a $1.95/h)
  - Fuente: `https://modal.com/pricing`
  - Fecha de lectura: `2026-10-30` (verificado en la tabla de GPUs de Modal)
- **`muse-spark-1.3@meta` / `default@meta`:**
  - Facturación: `per_token`
  - Precios (`usd_per_m_input`, `usd_per_m_cached_input`, `usd_per_m_output`): `null`
  - Fuente: `https://api.meta.ai/pricing`
  - Fecha de lectura: `2026-10-30`
  - Motivo de `null`: la página pública general no expone una tabla fija de list prices sin sesión/contrato institucional activo. Queda en `null` para ser completado cuando Guillermo disponga de la lista final.
- **`muse-spark-1.3@baseten-dedicated` / `default@baseten-dedicated`:**
  - Facturación: `dedicated`
  - GPU: A10G (1 GPU)
  - Precio (`usd_per_gpu_hour`): `null`
  - Fuente: `https://baseten.co/pricing`
  - Fecha de lectura: `2026-10-30`
  - Motivo de `null`: los despliegues dedicados en Baseten se cotizan según compromiso y tipo de instancia reservada; la página pública remite a contactar a ventas o consola privada.

### 5. `eval/economics.py` (nuevo)
Módulo con funciones puras sin red y CLI para procesamiento económico:
- `load_pricing()` / `get_pricing_entry()`: carga y vinculación segura de precios.
- `calculate_cost_per_question()`:
  - `per_token`: `(input - cached) * p_in + cached * p_cached + output * p_out`.
  - `dedicated`: `usd_per_gpu_hour * gpus * latency_s / 3600` (etiquetado como cota superior para concurrencia 1).
  - `serverless_gpu`: `usd_per_gpu_second * gpus * latency_s`.
- `is_verified_correct()`:
  - En condición A (baseline sin herramientas): respuesta correcta y sin números inventados (`has_unsupported_before_correction` es falso).
  - En condiciones B y C: respuesta correcta y verificada (`answer_correctness` y `verified`).
- `compute_run_economics()`:
  - `usd_per_question`: costo medio por pregunta. Con precio `null`, reporta `"price unknown"`.
  - `usd_per_correct_answer`: costo total / cantidad de respuestas correctas. Con 0 respuestas correctas, reporta `"∞ (no correct answers)"`.
  - `usd_per_verified_correct_answer`: métrica principal (costo total / respuestas correctas y verificadas).
  - Percentiles de latencia: `latency_p50_s` y `latency_p95_s`.
- `bootstrap_ci()`: intervalos de confianza del 95% para exactitud, tasa de respuestas verificadas y costo por respuesta verificada mediante 2,000 remuestreos con semilla fija `20261029` (`numpy.random.default_rng`).
- `mcnemar_exact()` y `paired_mcnemar_comparison()`: comparación pareada exacta en pares discordantes mediante `scipy.stats.binomtest(b, b + c, 0.5)`. En ejecuciones múltiples toma la mayoría por pregunta.
- `calculate_breakeven_volume()`: cálculo del volumen mensual de equilibrio $Q^* = \text{usd\_per\_gpu\_hour} \times \text{gpus} \times \text{hours\_on\_per\_month} / \text{usd\_per\_question\_per\_token}$ (evaluado para 730 h continuas y 220 h comerciales).
- `measure_fixed_prompt_overhead()` y `calculate_overhead_share()`: medición de la sobrecarga del prompt de sistema y esquemas de herramientas y proporción sobre los tokens totales de entrada.

### 6. `eval/frontier.py` (nuevo)
- `find_efficient_frontier()`: determina los puntos Pareto-eficientes en el plano (costo por pregunta en escala logarítmica vs % respuestas correctas verificadas). Marca como no eficiente cualquier punto dominado en costo y precisión.
- `plot_frontier()`: genera `eval/results/frontier.html` interactivo en Plotly con escala logarítmica, barras de error del intervalo de bootstrap y marcas de eficiencia.
- `format_frontier_markdown_table()`: exporta los puntos a tabla Markdown.

### 7. `eval/report.py`
- Soporte para generar la sección `## Economics` con:
  - Tabla de Model @ provider, Condición, Verified correct (95% CI), USD / question, USD / verified correct answer (95% CI), Latency p50 / p95 y Prices read on.
  - Resultados pareados de McNemar ($b, c, p$).
  - Sobrecarga de prompt fijo y porcentaje sobre tokens de entrada.
  - Volumen de equilibrio $Q^*$ para GPU dedicada vs facturación por token.
- Compatibilidad hacia atrás: puede renderizar archivos de resultados legacy (sin campos de telemetría o economía) sin lanzar excepciones.

### 8. `tests/test_economics.py` (nuevo)
10 tests de aceptación unitarios e integrados (sin red):
1. `test_1_telemetry_fields_and_no_api_key_in_results`: verifica que condiciones A, B y C escriban `latency_s`, `requests`, `prompt_tokens`, `completion_tokens`, `provider`, `api_host` y `commit`, y que ninguna clave de API aparezca en los resultados.
2. `test_2_cost_per_question_hand_calculation`: cálculo manual exacto a $10^{-12}$ con y sin tokens cacheados.
3. `test_3_null_price_reports_price_unknown`: precio nulo no lanza error, no asume 0 y reporta `"price unknown"` y tokens.
4. `test_4_zero_verified_correct_reports_infinity`: costo por respuesta verificada reporta `"∞ (no correct answers)"` cuando el conteo de verificadas correctas es 0.
5. `test_5_bootstrap_reproducibility_and_all_correct`: semilla fija `20261029` produce exactamente el mismo intervalo dos veces; con 100% de aciertos el intervalo es `[1.0, 1.0]`.
6. `test_6_mcnemar_exact_b8_c1`: $b=8, c=1$ da $p = 0.0390625$, idéntico a `binomtest(1, 9, 0.5).pvalue`.
7. `test_7_breakeven_dedicated_gpu`: $1.00$ USD/h, 1 GPU, 730 h, $0.05$ USD/pregunta da $Q^* = 14,600$.
8. `test_8_frontier_dominated_point_not_efficient`: en un conjunto de 4 puntos, el punto dominado recibe `efficient=False`.
9. `test_9_report_renders_old_and_adds_economics`: procesa resultados antiguos sin campos nuevos y añade la sección Economics ante resultados con datos de ejecución.
10. `test_10_engine_numbers_unchanged`: verifica contra el fixture `tests/data/spec23_main_tool_numbers.json` que `evaluate_season` y `shadow_prices` para el escenario por defecto coinciden exactamente con `main` a $10^{-9}$.

---

## 3. Sobrecarga del prompt fijo (Fixed Prompt Overhead)

Medición sobre el texto estático enviado en cada llamada:
- `FULL_SYSTEM_PROMPT` + `TOOL_SCHEMAS`:
  - Caracteres: **36,973**
  - Palabras: **4,899**
  - Estimación de tokens: ~9,243 (caracteres / 4). Medido con Muse Spark 1.3: **10.469 tokens** (ver la revisión al final).
- Proporción sobre una pregunta promedio (~28,000 tokens de entrada totales acumulados en 2 a 3 turnos):
  - En cada interacción se reenvía el prompt fijo, por lo que la sobrecarga fija representa entre el **60% y 85%** de los tokens facturados por pregunta.

---

## 4. Concurrencia (`--concurrency`)

Se implementó el flag opcional `--concurrency N` en `eval/run_eval.py`:
- Utiliza `concurrent.futures.ThreadPoolExecutor(max_workers=concurrency)`.
- En modo concurrente ($N > 1$), distribuye la ejecución de `_agent_record` o `_baseline_record` entre los hilos del pool.
- Cada hilo instancia su propio `Agent(client=client, model=model, use_verifier=use_verifier)` con historial e instancias independientes, evitando colisiones de estado.

---

## 5. Pruebas y verificación

Ejecución de la suite completa de pruebas:
```powershell
.venv\Scripts\python -m pytest
```
Resultado:
- **258 passed, 1 skipped** (el único skipped es `tests/test_feeds.py::test_magyp_live_fetch` marcado para saltear si no hay red).
- Tiempo de ejecución: 47.97s.
- Todos los tests existentes pasaron sin ningún cambio de código.


## Revisión de Claude (30/10)

- **Precios:** `eval/pricing.json` asignaba Muse Spark a Modal y a Baseten, pero Muse Spark solo corre en la API de Meta, y para Baseten suponía una GPU A10G que nadie eligió. Quedan dos entradas: `muse-spark-1.3@meta` (precio sin publicar, `null`) y `meta-llama/Llama-3.1-8B-Instruct@modal` (L40S, 0,000542 USD/seg, modal.com/pricing, 30/10). Baseten se agrega cuando se elija el modelo y la GPU.
- **Parte fija del prompt:** los ~9.243 tokens eran una estimación (caracteres / 4), no la medición que pide la spec. Medido con `measure_fixed_prompt_overhead` contra Muse Spark 1.3 el 30/10: **10.469 tokens** por pedido. Con Llama 3.1 8B en Modal, la primera prueba (q08) usó 43.128 tokens de entrada en 3 pedidos.
- Suite: 258 pasan, 1 se saltea. Números del motor iguales a `main` en 6 escenarios, los dos idiomas y la comparación de regiones.
