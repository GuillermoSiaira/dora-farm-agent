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
