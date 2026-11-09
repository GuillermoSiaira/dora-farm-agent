# Registro de experimentos

Cada corrida que se usa para afirmar algo deja acá su ficha y su salida cruda. Ningún número de la entrega se escribe a mano: sale de un archivo de esta carpeta o de `eval/results/`.

## Qué tiene cada ficha
- **Fecha y commit** del código con que se corrió.
- **Modelo y dónde corre** (proveedor, GPU, versión del servidor).
- **Qué se preguntó** y el comando exacto.
- **Resultado:** tiempos, herramientas llamadas, tokens, si quedó verificado, si acertó.
- **Costo,** con el precio de lista y su fuente.
- **Qué falló y cómo se arregló,** también cuando el error fue nuestro.
- **Qué significa,** y qué no se puede concluir de una sola corrida.
- **Salida cruda** en `raw/`, sin claves.
- **Qué aprendimos:** los conceptos que aparecieron, explicados en palabras simples, para repasar.

## Fichas

| Fecha | Experimento | Modelo · entorno | Resultado en una línea |
|---|---|---|---|
| 30/10/2026 | [Primera prueba de Llama en Modal](2026-10-30-modal-llama-8b-q08.md) | Llama 3.1 8B Instruct · Modal, L40S, vLLM 0.9.2 | Responde, pero no llama herramientas e inventa datos; el verificador lo frena |
| 30/10/2026 | [Parte fija del prompt](2026-10-30-prompt-overhead.md) | Muse Spark 1.3 · API de Meta | 10.469 tokens por pedido, antes de la pregunta |
| 30/10/2026 | [Dos arreglos del chasis para Llama](2026-10-30-modal-llama-8b-arreglos.md) | Llama 3.1 8B Instruct · Modal, plantilla de vLLM y herramienta obligatoria | Ninguno alcanza: el problema es el modelo, no cómo se sirve |
| 30/10/2026 | [E1 piloto: Muse Spark solo contra DORA](2026-10-30-e1-piloto-muse-spark.md) | Muse Spark 1.3 · API de Meta, condiciones A, B y C | Solo: 44 % correctas y números que cambian; DORA: 100 %, siempre el mismo número |
| 30/10/2026 | [E1 completo: Muse Spark solo contra DORA](2026-10-30-e1-completo-muse-spark.md) · [respuestas lado a lado](2026-10-30-e1-respuestas.html) | Muse Spark 1.3 · API de Meta, 39 preguntas × 5 × 3 condiciones | Solo: 38 % correctas, 9 planes imposibles; DORA completo: 97 %, ningún plan imposible |
| 31/10/2026 | [E3: voz, facturas y fotos aéreas](2026-10-31-e3-multimodal.md) · [respuestas lado a lado](2026-10-31-e3-respuestas.html) | Muse Spark 1.3 + Voice Transcribe + SAM 3.1 · API de Meta | Voz = escrito 6/6; facturas leídas 6/6 pero el texto carga mal el costo por ha en 3/6; SAM mide el agua a menos de 1 punto del valor real |
| 31/10/2026 | [E6: Muse Spark Open en Baseten](2026-10-31-e6-muse-spark-open.md) · [respuestas lado a lado](2026-10-31-e6-respuestas.html) | Muse Spark Open (`muse-spark-open-1026`) · Baseten Model APIs, 39 preguntas × 5 × 3 condiciones | Solo: 37 % correctas; DORA completo: 93 %, 100 % verificadas, ningún plan imposible; el verificador corrigió 127 de 195 |
| 31/10/2026 | [E1 con Contributor](2026-10-31-e1-contributor.md) · [respuestas lado a lado](2026-10-31-e1-contributor-respuestas.html) | Muse Spark 1.3 Contributor · API de Meta, 39 preguntas × 5 × 3 condiciones | Solo: 34 % correctas; DORA completo: 95 %, 100 % verificadas, ningún plan imposible; 1,23 USD en total, ~19 veces más barato que Standard |
| 31/10/2026 | [E2: panorama regional](2026-10-31-e2-panorama-regional.md) · [respuestas](2026-10-31-e2-e4-respuestas.html) | Muse Spark 1.3 · API de Meta, 5 respuestas | 5/5 verificadas y con el mismo ranking; nunca nombra Mato Grosso como provisorio; 4 errores de regiones (SPEC-28) |
| 31/10/2026 | [E4: precios en vivo](2026-10-31-e4-precios-en-vivo.md) · [respuestas](2026-10-31-e2-e4-respuestas.html) | Muse Spark 1.3 · API de Meta, fuentes con y sin red | Las fuentes andan y si se caen no se rompe nada, pero nunca dice "dato guardado"; 4 errores de precios (SPEC-28) |
| 31/10/2026 | [E5: robustez](2026-10-31-e5-robustez.md) · [respuestas](2026-10-31-e5-respuestas.html) | Muse Spark 1.3 · API de Meta, 11 preguntas trampa × 5 × B y C | Con verificador 55/55; sin verificador 54/55 y 11 respuestas con números sin respaldo |
| 01/11/2026 | [E1 final sobre el modelo v4](2026-11-01-e1-final.md) | Muse Spark 1.3 · API de Meta, 41 preguntas × 3, condición C | 121 de 123 correctas, 100 % verificadas, ningún plan imposible; las 2 fallas son escenarios de Iowa mal armados |
| 03/11/2026 | [E3 con precios reales](2026-11-03-e3-real-prices.md) | Muse Spark 1.3 · facturas de prueba con precios de mercado del 3/11 (Campo Simple, BCRA) | Contrasta los presupuestos de DORA con precios reales descargados en disco |
| 04/11/2026 | [E3: facturas por renglón](2026-11-04-e3-invoice-lines.md) | Muse Spark 1.3 · Factura A argentina y factura de cooperativa de EE. UU. | Desglose de cada factura por renglón, rubro y cultivo |

## Línea de investigación: eficiencia de los sistemas con LLM

Mapa de la investigación: https://claude.ai/artifact/215zdPbFWqgPr26AJtPMTf ([fuente](../investigacion/indice.html)). Agenda: [docs/investigacion/agenda.md](../investigacion/agenda.md). Desde el E9 se usa la regla estricta: el número correcto tiene que salir del motor y estar verificado.

| Fecha | Experimento | Modelo · entorno | Resultado en una línea |
|---|---|---|---|
| 04/11/2026 | [E8: cuatro generaciones de Muse Spark](2026-11-04-e8-generaciones.md) | Muse Spark 1.1 y 1.2 (más 1.3 y Open de E1 y E6) · API de Meta | Solas, todas 36-38 %; con DORA 93-100 %, escribiendo 4 veces menos |
| 06/11/2026 | [E9: diseño](2026-11-06-e9-diseno.md) · [piloto](2026-11-06-e9-piloto.md) | Qwen2.5 1,5B y 7B · Modal, L40S | El evaluador del E1 da falsos aciertos con modelos chicos; nace la regla estricta |
| 06-07/11/2026 | [E9: tamaño del modelo](2026-11-06-e9-tamano-de-modelo.md) · [todas las respuestas](2026-11-07-e9-respuestas.html) | Qwen2.5 de 1,5B a 72B · Modal (L40S, A100, H100), cuatro brazos | Solo 5-12 % en todos los tamaños; con DORA de 0 a 67 %; ningún tamaño llega al 90 %; 14,1 USD |
| 07/11/2026 | [E10: DeepSeek V4.1 Flash](2026-11-07-e10-deepseek.md) | DeepSeek V4.1 Flash · Baseten | Solo 9 %; con DORA 97 %, como Muse Spark, a un cuarto del precio por token; 2,11 USD |
