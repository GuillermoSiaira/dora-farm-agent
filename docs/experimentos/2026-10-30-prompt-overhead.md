# Parte fija del prompt (30/10/2026)

**Pregunta:** ¿cuántos tokens manda DORA en cada pedido al modelo antes de la pregunta del productor? Es la parte que se paga en cada llamada (SPEC-24, sección 3).

## Montaje
- **Modelo:** Muse Spark 1.3, API de Meta.
- **Qué se manda:** el prompt del sistema más la guía de modelado (`FULL_SYSTEM_PROMPT`), los esquemas de las herramientas (`TOOL_SCHEMAS`) y la palabra "Hola", con `max_tokens=1`.
- **Función:** `eval.economics.measure_fixed_prompt_overhead`, con el código de la rama `spec-24-economics` (mergeada en `main` como `f2650f6`).

## Resultado
- **10.469 tokens de entrada** por pedido, medidos por el tokenizador de Muse Spark.
- La estimación previa del informe de la SPEC-24 (caracteres / 4) daba unos 9.243.
- Con Llama 3.1 8B en Modal, la pregunta `q08` usó 43.128 tokens de entrada en 3 pedidos ([ficha](2026-10-30-modal-llama-8b-q08.md)). Cada pedido reenvía la parte fija más la conversación que va creciendo.

## Qué significa
La evaluación del 28/10 midió unos 28.000 tokens de entrada por pregunta con Muse Spark, en 2 a 3 pedidos. La parte fija es entonces la mayor parte de lo que se paga por pregunta. Si hay que bajar costos, o ayudar a un modelo chico, lo primero es esa parte: acortarla o usar caché del prompt. No se cambió nada todavía.

## Costo
Un pedido con 1 token de respuesta. Muse Spark no publica su precio por token sin un acuerdo (`eval/pricing.json`), así que no se puede dar en dólares.
