# E9: tamaño del modelo, solo y dentro de DORA (6/11/2026)

**Pregunta.** ¿Hay un tamaño mínimo de modelo a partir del cual DORA da respuestas correctas y verificadas? Por encima de ese tamaño, ¿agrandar el modelo deja de mejorar la precisión y solo sube el costo?

**Hipótesis del diseño.** Con DORA el umbral es bajo y, por encima de él, la elasticidad del error es casi cero. Solo, el modelo mejora despacio y no llega.

Antecedentes: [diseño](2026-11-06-e9-diseno.md) y [piloto](2026-11-06-e9-piloto.md).

## Qué se corrió
- **Modelos:** la familia Qwen2.5-Instruct en 6 tamaños: 1,5B, 3B, 7B, 14B, 32B y 72B. Todos densos: los parámetros activos son los totales.
- **Dónde:** Modal, con vLLM 0.9.2 y [`infra/modal/serve_open.py`](../../infra/modal/serve_open.py). Hasta 14B, una L40S en bf16. El 32B, una H100 en FP8; el 72B, dos H100 en FP8 (en bf16 no entran con el contexto). Contexto de 32.768 tokens, el nativo de Qwen2.5.
- **Preguntas:** las 36 de `eval/questions.jsonl`; el modelo solo responde 33, porque las 3 de `compare_regions` quedan afuera, igual que en E1. **2 repeticiones** de 1,5B a 32B y **1 repetición** en el 72B, por costo. Techo de 4.096 tokens por respuesta.
- **Brazos:**
  - **solo**: `--baseline`;
  - **DORA**: nuestro agente, con verificador;
  - **MCP**: un agente genérico ([`eval/mcp_agent.py`](../../eval/mcp_agent.py)) con prompt neutro y las 9 herramientas del motor del MCP público;
  - **MCP + guía**: lo mismo, más la guía de modelado que el MCP publica como recurso.
- **Puntaje:** la regla estricta del E9 ([`strict_score`](../../eval/run_eval.py)). Con herramientas, el número correcto tiene que estar en la respuesta y haberlo devuelto el motor para el escenario del productor; además, el verificador no tiene que encontrar números sin respaldo. El modelo solo se mide contra los datos que recibió.
- **Comandos:** [`eval/run_e9.py`](../../eval/run_e9.py) por tamaño (ver el piloto), después `python eval/plot_e9.py`.
- **Salida cruda:** `eval/results/e9/full/`, con el análisis en `analysis.json`. Commit de partida: `b9628c3`.

![E9](../screenshots/e9-model-size.png)

## Resultado

Correctas y verificadas, sobre las respuestas puntuadas:

| Modelo | Solo | DORA | MCP | MCP + guía |
|---|---|---|---|---|
| 1,5B | 3/66 (5 %) | 0/72 (0 %) | 2/72 (3 %) | 2/72 (3 %) |
| 3B | 3/66 (5 %) | 7/72 (10 %) | 2/72 (3 %) | 2/72 (3 %) |
| 7B | 6/66 (9 %) | 5/72 (7 %) | 1/72 (1 %) | 6/72 (8 %) |
| 14B | 8/66 (12 %) | 15/72 (21 %) | 2/72 (3 %) | 12/72 (17 %) |
| 32B | 4/66 (6 %) | 27/72 (38 %) | 3/72 (4 %) | 17/72 (24 %) |
| 72B (×1) | 2/33 (6 %) | 18/36 (50 %) | 6/36 (17 %) | 9/36 (25 %) |

**El brazo DORA quedó limitado por el contexto.** El agente de DORA manda entre 29.000 y 53.000 tokens por pedido en las preguntas largas, sobre todo las de comparar regiones. Esas respuestas no entraron en los 32.768 tokens del servidor y cuentan como falladas:

| Modelo | 1,5B | 3B | 7B | 14B | 32B | 72B |
|---|---|---|---|---|---|---|
| Respuestas de DORA cortadas por contexto | 7/72 | 14/72 | 28/72 | 37/72 | 17/72 | 10/36 |
| DORA sobre las que entraron | 0 % | 12 % | 11 % | 43 % | 49 % | 69 % |

La segunda fila es solo una cota: las preguntas que no entraron son las más difíciles. En los brazos MCP casi no hubo cortes (1 en MCP y 2 en MCP + guía, sumando todos los tamaños), porque el agente genérico manda mucho menos texto.

**Llamadas a herramientas aceptadas** (de las que el modelo intentó), en el brazo DORA: 1,5B 0 %, 3B 43 %, 7B 30 %, 14B 57 %, 32B 90 % y 72B 89 %. El 1,5B casi nunca hace una llamada real: escribe el JSON como texto.

**Elasticidad del error** (pendiente de ln(error) contra ln(parámetros), con los 6 tamaños e intervalo del 95 %):

| Brazo | Elasticidad | Intervalo |
|---|---|---|
| Solo | −0,01 | −0,04 a 0,02: plana |
| DORA | −0,17 | −0,26 a −0,09 |
| MCP | −0,03 | −0,08 a 0,01: plana |
| MCP + guía | −0,08 | −0,11 a −0,05 |

**Umbral N\* (90 %):** ningún tamaño llega, en ningún brazo.

**Tokens por respuesta:**
- solo: unos 2.100 de entrada y entre 150 y 650 de salida;
- DORA: entre 27.000 y 62.000 de entrada y entre 250 y 640 de salida.

A diferencia de Muse Spark, Qwen solo escribe poco (Muse Spark escribía unos 19.000 tokens de razonamiento), así que acá DORA no ahorra tokens de salida: cuesta más lectura.

**Costo** (factura de Modal, `modal billing report`): 9,0 USD la corrida completa más 1,0 el piloto, **10,0 USD en total**. Por tamaño:

| 1,5B | 3B | 7B | 14B | 32B | 72B |
|---|---|---|---|---|---|
| 0,44 | 0,55 | 0,97 | 1,41 | 1,47 | 4,20 USD |

El costo por respuesta correcta y verificada de DORA baja de 0,07 USD (7B) a 0,012 USD (32B) y vuelve a 0,045 USD en el 72B. El costo de cada brazo es una parte del tiempo de GPU encendida, repartida por el tiempo que llevó cada brazo: es una estimación.

## Qué dice sobre la hipótesis
- **"Solo, el modelo sube despacio y no llega": se sostiene,** e incluso más fuerte de lo esperado. De 1,5B a 72B el modelo solo no mejora: la elasticidad es 0 y queda entre 5 y 12 %. Es el mismo patrón que E8 con cuatro versiones de Muse Spark, que solas se quedaban en 36-38 %.
- **"Con DORA hay un umbral bajo y arriba la curva es plana": no se sostiene con Qwen2.5.**
  - Ningún tamaño llega al 90 %.
  - Con DORA el error sigue bajando con el tamaño en todo el rango, y es el único brazo con una pendiente claramente distinta de cero.
  - DORA multiplica el efecto del tamaño en lugar de hacerlo innecesario: a 72B, 50 % contra 6 % solo.
- **Una diferencia con los antecedentes no se explica por el tamaño.** Muse Spark, de 42B activos en la versión Open, llega a 93-97 % con DORA (E1, E6). Qwen2.5 de 72B llega a 50 %. Entre familias, la generación y el entrenamiento para usar herramientas pesan más que los parámetros.
- **La comparación todavía está sesgada contra DORA por el contexto.** Con un contexto más largo, el brazo DORA de 14B a 72B debería subir: la cota es 43-69 %. No se puede afirmar cuánto sin correrlo.
- **Agente genérico contra el nuestro:** sin la guía, el agente genérico no sabe los nombres de los parámetros y casi no acierta. Con la guía queda a mitad de camino (25 % a 72B). El motor solo no alcanza: el valor está en motor más agente.

## Límites
- 1 familia, de 2024. Su modelo más grande es más chico y más viejo que Muse Spark.
- 2 repeticiones (1 en el 72B). Los intervalos del gráfico son amplios: entre 32B y 72B los intervalos se superponen en todos los brazos.
- El 32B y el 72B corren en FP8 y los demás en bf16. FP8 cambia poco la calidad, pero no es idéntico.
- El agente de DORA y su prompt se ajustaron con Muse Spark; con otra familia puede haber tropiezos de formato. Por ejemplo, el 7B copia el escenario expandido, `{value, unit, origin}`, en la llamada siguiente.
- Contexto de 32.768 tokens: ver arriba.

## Pendiente (pide OK de crédito)
Repetir solo el brazo DORA con 65.536 tokens de contexto, usando la extensión YaRN que Qwen documenta para Qwen2.5, en los 6 tamaños. Estimado: unos 5 USD de Modal. Diría cuánto del 50 % del 72B es límite del servidor y cuánto es del modelo.

## Qué aprendimos
- **La arquitectura no reemplaza al modelo; lo amplifica.** Solo, Qwen2.5 no mejora con el tamaño: de 1,5B a 72B queda entre 5 y 12 %. Dentro de DORA pasa de 0 a 50 %. El motor convierte la capacidad del modelo (formular el escenario, llamar bien las herramientas) en respuestas exactas, pero esa capacidad tiene que existir.
- **El umbral no es un número de parámetros.** Muse Spark, más nuevo y entrenado para usar herramientas, llega al 93-97 % con DORA; un Qwen2.5 de 72B, a 50 %. Para un agente verificable importa más qué tan bien el modelo llama herramientas que cuántos parámetros tiene. Por eso la medida que más explica el resultado es la tasa de llamadas aceptadas: 0 % en el 1,5B y cerca de 90 % en el 32B y el 72B.
- **El contexto es parte del costo de la arquitectura.** DORA lee 15 a 25 veces más tokens que el modelo solo. Con un servidor de 32.768 tokens, eso cortó hasta la mitad de las respuestas del 14B. Una arquitectura "más barata" tiene que medir también lo que pide leer, no solo lo que escribe.
- **Un evaluador hecho para modelos buenos da falsos aciertos con modelos malos.** La regla estricta (el número tiene que venir del motor) fue necesaria para no contar ecos de la pregunta como respuestas.
- **El costo de servir un modelo propio es el tiempo de la GPU encendida.** El 72B costó 4,20 USD, casi la mitad de todo: arranque en frío de 15 minutos más dos H100. Conviene agrupar las corridas por tamaño y apagar cada app al terminar con `modal app stop`.
